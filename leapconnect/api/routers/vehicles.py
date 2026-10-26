"""Vehicle telemetry routes: list, status, pictures, full data, live WebSocket."""

from __future__ import annotations

import asyncio
import base64
import io
import json
import logging
import zipfile
from contextlib import AsyncExitStack
from datetime import UTC, datetime
from typing import Annotated
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Request, WebSocket
from fastapi.responses import Response, StreamingResponse
from leapmotor_api.models import SoftwareVersion, VehicleStatus
from starlette.background import BackgroundTask
from starlette.websockets import WebSocketDisconnect

from leapconnect.api.deps import (
    SESSION_COOKIE_NAME,
    ClientDep,
    ContainerDep,
    RepoDep,
    VehicleDep,
)
from leapconnect.api.schemas import (
    FullVehicleDataResponse,
    LiveRefreshStatusResponse,
    ShareInvitationAnswerResponse,
    ShareInvitationListResponse,
    ShareInvitationSchema,
    SoftwareInfoResponse,
    VehicleListResponse,
    VehicleSchema,
    VehicleStatusResponse,
    VehicleStatusSchema,
)
from leapconnect.application.car_sharing import (
    InvitationNotFoundError,
    answer_share_invitation,
)
from leapconnect.application.settings_store import load_preferences, resolve_language
from leapconnect.application.software_updates import (
    archive_name,
    download_manifest,
    downloadable,
    find_package,
)
from leapconnect.application.status_sanitizer import fetch_vehicle_status
from leapconnect.asyncutils import spawn
from leapconnect.config import IMAGE_MEDIA_TYPES, VEHICLE_IMAGE_DIR
from leapconnect.container import AppContainer
from leapconnect.domain.telemetry.models import VehicleSnapshot
from leapconnect.infrastructure.ota_cdn import (
    CHUNK_SIZE,
    FORWARDED_HEADERS,
    OtaCdnError,
    open_package,
    zip_packages,
)

_LOGGER = logging.getLogger(__name__)

router = APIRouter(tags=["vehicles"])


# ---------------------------------------------------------------------------
# WebSocket — real-time vehicle status push
# ---------------------------------------------------------------------------


@router.websocket("/ws/vehicle/{vin}")
async def ws_vehicle_status(
    websocket: WebSocket, vin: str, container: ContainerDep
) -> None:
    """Push real-time status updates to the frontend for a vehicle."""
    # Validate session from query param or cookie
    # Cookie-only auth: a query-string token would leak into access logs
    token = websocket.cookies.get(SESSION_COOKIE_NAME)
    if not container.sessions.validate(token):
        await websocket.close(code=4401, reason="Unauthorized")
        return

    await websocket.accept()

    # Register this connection
    if vin not in container.ws_connections:
        container.ws_connections[vin] = set()
    container.ws_connections[vin].add(websocket)

    _LOGGER.info("WebSocket connected for VIN %s", vin)
    try:
        # Keep connection alive — read messages (pings / close)
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        container.ws_connections.get(vin, set()).discard(websocket)
        _LOGGER.info("WebSocket disconnected for VIN %s", vin)


# ---------------------------------------------------------------------------
# Vehicle data
# ---------------------------------------------------------------------------


@router.get("/api/vehicles")
async def get_vehicles(client: ClientDep, container: ContainerDep):
    container.vehicles = await client.get_vehicle_list()
    return VehicleListResponse(
        vehicles=[VehicleSchema.from_model(v) for v in container.vehicles]
    )


# ---------------------------------------------------------------------------
# Car sharing (recipient side)
# ---------------------------------------------------------------------------


@router.get("/api/share-invitations", response_model=ShareInvitationListResponse)
async def get_share_invitations(client: ClientDep) -> ShareInvitationListResponse:
    """Car-share invitations waiting for this account; a shared car stays out
    of the vehicle list until its invitation is accepted."""
    invitations = await client.get_share_invitations()
    return ShareInvitationListResponse(
        invitations=[ShareInvitationSchema.from_model(i) for i in invitations]
    )


async def _answer_invitation(
    vin: str, container: AppContainer, *, accept: bool
) -> ShareInvitationAnswerResponse:
    try:
        await answer_share_invitation(container.get_client(), vin, accept=accept)
    except InvitationNotFoundError as exc:
        raise HTTPException(
            status_code=404, detail=f"No pending invitation for {vin}"
        ) from exc
    vehicles = await container.refresh_vehicles()
    return ShareInvitationAnswerResponse(
        vin=vin,
        accepted=accept,
        vehicles=[VehicleSchema.from_model(v) for v in vehicles],
    )


@router.post(
    "/api/share-invitations/{vin}/accept",
    response_model=ShareInvitationAnswerResponse,
)
async def accept_share_invitation(
    vin: str, container: ContainerDep
) -> ShareInvitationAnswerResponse:
    """Accept the invitation: the shared car joins the vehicle list."""
    return await _answer_invitation(vin, container, accept=True)


@router.post(
    "/api/share-invitations/{vin}/reject",
    response_model=ShareInvitationAnswerResponse,
)
async def reject_share_invitation(
    vin: str, container: ContainerDep
) -> ShareInvitationAnswerResponse:
    """Reject the invitation."""
    return await _answer_invitation(vin, container, accept=False)


# ---------------------------------------------------------------------------
# Software (OTA)
# ---------------------------------------------------------------------------


@router.get("/api/vehicles/{vin}/software", response_model=SoftwareInfoResponse)
async def get_software_info(
    vin: str,
    client: ClientDep,
    vehicle: VehicleDep,
    container: ContainerDep,
    repo: RepoDep,
    refresh: bool = False,
) -> SoftwareInfoResponse:
    """Installed software version and pending OTA update, with the release
    notes in the ``language`` preference. Cached for hours; ``refresh=true``
    asks the cloud again. Only the account that owns the car gets the data:
    for a shared account ``status`` is ``owner_only``."""
    lookup = await container.software_updates.get(client, vehicle, refresh=refresh)
    language = resolve_language((await load_preferences(repo)).language)
    return SoftwareInfoResponse.from_lookup(lookup, language)


def _attachment(name: str) -> str:
    """``Content-Disposition`` for a download, safe for any file name."""
    ascii_name = name.encode("ascii", "replace").decode().replace('"', "_")
    return f"attachment; filename=\"{ascii_name}\"; filename*=UTF-8''{quote(name)}"


async def _pending_update(
    client: ClientDep, vehicle: VehicleDep, container: ContainerDep
) -> SoftwareVersion:
    """The update waiting to be installed, with fresh download links."""
    lookup = await container.software_updates.for_download(client, vehicle)
    if lookup.owner_only:
        raise HTTPException(
            status_code=403,
            detail="Only the account that owns the car can download its software.",
        )
    if lookup.pending is None:
        raise HTTPException(status_code=404, detail="No software update is pending.")
    return lookup.pending


PendingUpdateDep = Annotated[SoftwareVersion, Depends(_pending_update)]


def _cdn_failure(exc: OtaCdnError) -> HTTPException:
    if exc.status_code == 416:
        return HTTPException(status_code=416, detail="Requested range not satisfiable.")
    _LOGGER.warning("OTA package download failed: %s", exc)
    return HTTPException(
        status_code=502,
        detail=f"Leapmotor's download server refused the package: {exc}.",
    )


@router.get("/api/vehicles/{vin}/software/packages/{seq}/download")
async def download_software_package(
    seq: int, request: Request, update: PendingUpdateDep
) -> StreamingResponse:
    """One package of the pending update, streamed from Leapmotor's CDN.

    ``Range`` is forwarded, so browsers can resume. The file is served
    encrypted (``.encrypt``), as Leapmotor stores it."""
    package = find_package(update, seq)
    if package is None:
        raise HTTPException(status_code=404, detail="Package not found.")
    stack = AsyncExitStack()
    try:
        cdn = await stack.enter_async_context(
            open_package(
                package.download_url,
                range_header=request.headers.get("range"),
                if_range=request.headers.get("if-range"),
            )
        )
    except OtaCdnError as exc:
        await stack.aclose()
        raise _cdn_failure(exc) from None

    async def body():
        try:
            async for chunk in cdn.aiter_raw(CHUNK_SIZE):
                yield chunk
        finally:
            await stack.aclose()

    headers = {k: cdn.headers[k] for k in FORWARDED_HEADERS if k in cdn.headers}
    headers["Content-Disposition"] = _attachment(package.served_file_name)
    return StreamingResponse(
        body(),
        status_code=cdn.status_code,
        media_type="application/octet-stream",
        headers=headers,
        background=BackgroundTask(stack.aclose),
    )


@router.get("/api/vehicles/{vin}/software/download")
async def download_software_update(
    vehicle: VehicleDep, update: PendingUpdateDep, repo: RepoDep
) -> StreamingResponse:
    """Every package of the pending update in one ZIP, with a ``manifest.json``
    describing them. Streamed: a CDN failure mid-way truncates the archive."""
    packages = [p for p in update.packages if downloadable(p)]
    if not packages:
        raise HTTPException(status_code=404, detail="The update has no packages.")
    language = resolve_language((await load_preferences(repo)).language)
    manifest = download_manifest(vehicle, update, language)
    archive = zip_packages(
        [(p.served_file_name, p.download_url) for p in packages],
        {"manifest.json": json.dumps(manifest, indent=2, ensure_ascii=False).encode()},
    )
    return StreamingResponse(
        archive,
        media_type="application/zip",
        headers={"Content-Disposition": _attachment(archive_name(vehicle, update))},
    )


def snapshot_from_status(vin: str, status: VehicleStatus) -> VehicleSnapshot:
    """Map a cloud VehicleStatus to a persistence snapshot."""
    return VehicleSnapshot(
        vin=vin,
        timestamp=status.collect_time or datetime.now(UTC).replace(tzinfo=None),
        battery_soc=status.battery.soc,
        battery_current=status.battery.battery_current,
        battery_voltage=status.battery.battery_voltage,
        battery_is_charging=status.is_charging,
        battery_dump_energy=status.battery.dump_energy,
        battery_expected_mileage=status.battery.expected_mileage,
        battery_charge_state=status.battery.charge_state.value
        if status.battery.charge_state
        else None,
        drive_is_parked=status.driving.is_parked,
        drive_speed=status.driving.speed,
        drive_total_mileage=status.driving.total_mileage,
        ignition_is_on1=status.ignition.bcm_key_position_on1
        if status.ignition
        else None,
        ignition_is_on2=status.ignition.bcm_key_position_on3
        if status.ignition
        else None,
        vehicle_is_charging=status.is_charging,
        vehicle_is_plugged=status.is_plugged,
        vehicle_is_regening=status.is_regening,
        vehicle_is_parked=status.is_parked,
        vehicle_is_locked=status.is_locked,
        vehicle_latitude=status.location.latitude,
        vehicle_longitude=status.location.longitude,
        climate_outdoor_temp=status.climate.outdoor_temp,
        tire_front_left_pressure=status.tires.front_left_kpa if status.tires else None,
        tire_front_right_pressure=status.tires.front_right_kpa
        if status.tires
        else None,
        tire_rear_left_pressure=status.tires.rear_left_kpa if status.tires else None,
        tire_rear_right_pressure=status.tires.rear_right_kpa if status.tires else None,
    )


async def _save_snapshot_safe(
    container: AppContainer, snapshot: VehicleSnapshot
) -> None:
    """Fire-and-forget snapshot save; errors are logged, never raised."""
    try:
        await container.repo.save_snapshot(snapshot)
    except Exception:
        _LOGGER.exception("Failed to save vehicle snapshot")


@router.get("/api/vehicles/{vin}/status", response_model=VehicleStatusResponse)
async def get_vehicle_status(
    vin: str, client: ClientDep, vehicle: VehicleDep, container: ContainerDep
) -> VehicleStatusResponse:
    """Get the current real-time status of a vehicle."""

    # Use shared cache if available (respects rate limit + single-flight)
    if container.vehicle_cache:
        status = await container.vehicle_cache.get(vehicle)
    else:
        status = await fetch_vehicle_status(client, vehicle)

    # Persist snapshot for historical tracking
    if container.repo and isinstance(status, VehicleStatus):
        snapshot = snapshot_from_status(vin, status)
        spawn(_save_snapshot_safe(container, snapshot))

    # Publish to MQTT / Home Assistant
    if (
        container.mqtt_service
        and container.mqtt_service.is_connected
        and isinstance(status, VehicleStatus)
    ):
        spawn(container.mqtt_publish_status(vin, status))

    return VehicleStatusResponse(status=VehicleStatusSchema.from_model(status))


@router.get("/api/vehicles/{vin}/raw-status")
async def get_vehicle_raw_status(
    vin: str, client: ClientDep, vehicle: VehicleDep
) -> dict:
    """Get the raw unprocessed status data from the API."""
    raw = await client.get_vehicle_raw_status(vehicle)
    return raw


@router.get("/api/vehicles/{vin}/mileage")
async def get_mileage(vin: str, client: ClientDep, vehicle: VehicleDep) -> dict:
    """Get mileage and energy consumption details."""
    data = await client.get_mileage_energy_detail(vehicle)
    return data


# ---------------------------------------------------------------------------
# Pictures
# ---------------------------------------------------------------------------


@router.get("/api/vehicles/{vin}/picture")
async def get_picture(vin: str, client: ClientDep, vehicle: VehicleDep) -> dict:
    """Get the car picture metadata and download key."""
    data = await client.get_car_picture(vehicle)
    return data


@router.get("/api/vehicles/{vin}/picture/download")
async def download_picture(vin: str, key: str, client: ClientDep) -> Response:
    """Download the raw car picture ZIP package."""
    data = await client.download_car_picture_package(picture_key=key)
    return Response(content=data, media_type="application/zip")


@router.get("/api/vehicles/{vin}/picture/image")
async def get_picture_image(
    vin: str,
    client: ClientDep,
    vehicle: VehicleDep,
    container: ContainerDep,
    refresh: bool = False,
) -> Response:
    """Serve the main car image, caching it on the server's local disk.

    The image is downloaded from the Leapmotor cloud only on the first request
    per vehicle (or when ``refresh=1``); afterwards it is served from local
    storage without contacting the cloud.
    """

    # Serve from local disk if already cached.
    if not refresh:
        cached = container.cached_vehicle_image(vin)
        if cached is not None:
            media_type = IMAGE_MEDIA_TYPES.get(
                cached.suffix.lstrip(".").lower(), "image/png"
            )
            return Response(
                content=cached.read_bytes(),
                media_type=media_type,
                headers={"Cache-Control": "public, max-age=86400"},
            )

    # Cache miss — fetch from the cloud once.
    picture_data = await client.get_car_picture(vehicle)
    key = (picture_data.get("data") or {}).get("key")
    if not key:
        raise HTTPException(status_code=404, detail="No picture key available")

    zip_bytes = await client.download_car_picture_package(picture_key=key)

    # Extract the tripsum (complete car) image, fallback to first image
    try:
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
            image_names = [
                n
                for n in zf.namelist()
                if n.lower().endswith((".png", ".jpg", ".jpeg", ".webp"))
            ]
            if not image_names:
                raise HTTPException(
                    status_code=404,
                    detail=f"No image found in package. Contents: {zf.namelist()}",
                )
            # Prefer carpic_for_tripsum (complete car) over body-only
            tripsum = [n for n in image_names if "tripsum" in n.lower()]
            img_name = tripsum[0] if tripsum else image_names[0]
            img_data = zf.read(img_name)
    except zipfile.BadZipFile:
        # Not a ZIP — maybe the response is already a raw image
        img_data = zip_bytes
        img_name = "image.png"

    ext = img_name.rsplit(".", 1)[-1].lower()
    if ext not in IMAGE_MEDIA_TYPES:
        ext = "png"
    media_type = IMAGE_MEDIA_TYPES[ext]

    # Persist to local disk for subsequent requests (best-effort).
    try:
        VEHICLE_IMAGE_DIR.mkdir(parents=True, exist_ok=True)
        for stale in VEHICLE_IMAGE_DIR.glob(f"{vin}.*"):
            stale.unlink()
        (VEHICLE_IMAGE_DIR / f"{vin}.{ext}").write_bytes(img_data)
    except OSError as exc:
        _LOGGER.warning("Could not cache vehicle image for %s: %s", vin, exc)

    return Response(
        content=img_data,
        media_type=media_type,
        headers={"Cache-Control": "public, max-age=86400"},
    )


@router.get("/api/vehicles/{vin}/picture/package")
async def get_picture_package(
    vin: str, client: ClientDep, vehicle: VehicleDep, container: ContainerDep
) -> dict[str, str]:
    """Extract all images from the picture ZIP and return as data URIs."""
    if vin in container.picture_cache:
        return container.picture_cache[vin]

    picture_data = await client.get_car_picture(vehicle)
    key = (picture_data.get("data") or {}).get("key")
    if not key:
        raise HTTPException(status_code=404, detail="No picture key available")

    zip_bytes = await client.download_car_picture_package(picture_key=key)

    images: dict[str, str] = {}
    try:
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
            for entry in zf.namelist():
                lower = entry.lower()
                if not lower.endswith((".png", ".jpg", ".jpeg", ".webp")):
                    continue
                # Use the bare filename without directory prefix
                basename = entry.rsplit("/", 1)[-1]
                raw = zf.read(entry)
                ext = basename.rsplit(".", 1)[-1].lower()
                mime = IMAGE_MEDIA_TYPES.get(ext, "image/png")
                images[basename] = (
                    f"data:{mime};base64,{base64.b64encode(raw).decode()}"
                )
    except zipfile.BadZipFile as exc:
        raise HTTPException(status_code=500, detail="Invalid picture package") from exc

    container.picture_cache[vin] = images
    return images


@router.get("/api/vehicles/{vin}/picture/dynamic")
async def get_dynamic_picture(
    vin: str,
    client: ClientDep,
    vehicle: VehicleDep,
    container: ContainerDep,
    charge_frame: int = 0,
) -> Response:
    """Compose a dynamic car image reflecting current vehicle status."""

    if container.vehicle_cache:
        pkg, status_raw = await asyncio.gather(
            container.get_image_package(vin),
            container.vehicle_cache.get(vehicle),
        )
    else:
        pkg, status_raw = await asyncio.gather(
            container.get_image_package(vin),
            fetch_vehicle_status(client, vehicle),
        )

    status = status_raw if isinstance(status_raw, VehicleStatus) else None
    img_bytes = await asyncio.to_thread(
        pkg.compose, status, charge_frame=charge_frame, format="PNG"
    )

    return Response(
        content=img_bytes,
        media_type="image/png",
        headers={"Cache-Control": "no-cache"},
    )


@router.get("/api/vehicles/{vin}/full", response_model=FullVehicleDataResponse)
async def get_full_vehicle_data(
    vin: str, client: ClientDep, vehicle: VehicleDep, container: ContainerDep
) -> FullVehicleDataResponse:
    """Fetch status, mileage, and picture data for a vehicle in one call."""

    status_task = (
        container.vehicle_cache.get(vehicle)
        if container.vehicle_cache
        else fetch_vehicle_status(client, vehicle)
    )
    mileage_task = client.get_mileage_energy_detail(vehicle)
    picture_task = client.get_car_picture(vehicle)

    results = await asyncio.gather(
        status_task,
        mileage_task,
        picture_task,
        return_exceptions=True,
    )

    status = results[0] if not isinstance(results[0], Exception) else None
    mileage = results[1] if not isinstance(results[1], Exception) else None
    picture = results[2] if not isinstance(results[2], Exception) else None

    return FullVehicleDataResponse(
        vehicle=VehicleSchema.from_model(vehicle),
        status=VehicleStatusSchema.from_model(status) if status else None,
        mileage=mileage if isinstance(mileage, dict) else None,
        picture=picture if isinstance(picture, dict) else None,
        errors={
            "status": str(results[0]) if isinstance(results[0], Exception) else None,
            "mileage": str(results[1]) if isinstance(results[1], Exception) else None,
            "picture": str(results[2]) if isinstance(results[2], Exception) else None,
        },
        vehicle_raw=vehicle.raw,
        status_raw=status.raw if status else None,
        cache_age_seconds=(
            container.vehicle_cache.cache_age(vin) if container.vehicle_cache else None
        ),
    )


# ---------------------------------------------------------------------------
# Live refresh
# ---------------------------------------------------------------------------


@router.get("/api/live-refresh", response_model=LiveRefreshStatusResponse)
async def get_live_refresh(container: ContainerDep) -> LiveRefreshStatusResponse:
    """Get live refresh status and current interval."""
    return LiveRefreshStatusResponse(
        interval_seconds=container.live_refresh_interval,
        is_running=container.live_refresh_running,
    )


@router.put("/api/live-refresh", response_model=LiveRefreshStatusResponse)
async def update_live_refresh(
    request: Request, container: ContainerDep
) -> LiveRefreshStatusResponse:
    """Enable/disable live refresh or change its interval.

    Set interval_seconds to 0 to disable. Valid range: 10–600 seconds.
    """
    body = await request.json()
    interval = body.get("interval_seconds")
    if interval is None:
        raise HTTPException(status_code=422, detail="'interval_seconds' is required")
    try:
        interval = int(interval)
    except (TypeError, ValueError) as exc:
        raise HTTPException(
            status_code=422, detail="'interval_seconds' must be an integer"
        ) from exc
    if interval < 0:
        raise HTTPException(status_code=422, detail="'interval_seconds' must be >= 0")
    # Cap at reasonable max (10 min) and min (10 sec when enabled)
    if interval > 0:
        interval = max(10, min(600, interval))

    container.live_refresh_interval = interval
    # Persist
    if container.repo:
        await container.repo.save_setting("live_refresh_interval", str(interval))

    # (Re)start or stop the loop
    if interval > 0 and container.connected:
        container.start_live_refresh()
    else:
        container.stop_live_refresh()

    return LiveRefreshStatusResponse(
        interval_seconds=container.live_refresh_interval,
        is_running=container.live_refresh_running,
    )
