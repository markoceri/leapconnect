"""Vehicle appearance routes: accent-colour palettes, selection, auto-detect."""

from __future__ import annotations

import io
import logging
import zipfile

from fastapi import APIRouter

from leapconnect.api.deps import ClientDep, ContainerDep, RepoDep, VehicleDep
from leapconnect.api.schemas import (
    ColorDetectResponse,
    PaletteColorSchema,
    VehicleColorUpdate,
    VehiclePaletteResponse,
)
from leapconnect.application.settings_store import (
    load_vehicle_colors,
    save_vehicle_color,
)
from leapconnect.application.theme_detection import dominant_color
from leapconnect.domain.styling import (
    match_color_name,
    nearest_color,
    palette_for_car_type,
)

_LOGGER = logging.getLogger(__name__)

router = APIRouter(tags=["styling"])


def _color_by_key(palette, key):
    return next((c for c in palette if c.key == key), None)


@router.get("/api/vehicles/{vin}/palette", response_model=VehiclePaletteResponse)
async def get_vehicle_palette(
    vin: str, vehicle: VehicleDep, repo: RepoDep
) -> VehiclePaletteResponse:
    """Return the accent palette for a vehicle's model and its current choice."""
    from leapconnect.domain.styling.palettes import palette_key_for_car_type

    palette = palette_for_car_type(vehicle.car_type)
    selected_key = (await load_vehicle_colors(repo)).get(vin)
    selected = _color_by_key(palette, selected_key) if selected_key else None
    return VehiclePaletteResponse(
        vin=vin,
        model_key=palette_key_for_car_type(vehicle.car_type),
        colors=[PaletteColorSchema.from_model(c) for c in palette],
        selected=PaletteColorSchema.from_model(selected) if selected else None,
    )


@router.put("/api/vehicles/{vin}/color", response_model=VehiclePaletteResponse)
async def set_vehicle_color(
    vin: str, body: VehicleColorUpdate, vehicle: VehicleDep, repo: RepoDep
) -> VehiclePaletteResponse:
    """Set (or clear, when ``color_key`` is null) a vehicle's accent colour."""
    palette = palette_for_car_type(vehicle.car_type)
    # Only persist keys that exist in this model's palette; null clears it.
    key = (
        body.color_key
        if body.color_key and _color_by_key(palette, body.color_key)
        else None
    )
    await save_vehicle_color(repo, vin, key)
    return await get_vehicle_palette(vin, vehicle, repo)


async def _load_body_image_bytes(
    vin: str, vehicle: VehicleDep, client: ClientDep, container: ContainerDep
) -> bytes | None:
    """Return image bytes best representing the body colour, or ``None``."""
    cached = container.cached_vehicle_image(vin)
    if cached is not None:
        try:
            return cached.read_bytes()
        except OSError:
            pass

    picture_data = await client.get_car_picture(vehicle)
    key = (picture_data.get("data") or {}).get("key")
    if not key:
        return None
    zip_bytes = await client.download_car_picture_package(picture_key=key)
    try:
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
            names = [
                n
                for n in zf.namelist()
                if n.lower().endswith((".png", ".jpg", ".jpeg", ".webp"))
            ]
            if not names:
                return None
            # Prefer the plain body image (truest paint colour).
            body = [n for n in names if "body" in n.lower()]
            tripsum = [n for n in names if "tripsum" in n.lower()]
            chosen = (body or tripsum or names)[0]
            return zf.read(chosen)
    except zipfile.BadZipFile:
        return zip_bytes


@router.post("/api/vehicles/{vin}/color/detect", response_model=ColorDetectResponse)
async def detect_vehicle_color(
    vin: str,
    vehicle: VehicleDep,
    client: ClientDep,
    container: ContainerDep,
    repo: RepoDep,
) -> ColorDetectResponse:
    """Auto-detect the accent colour for a vehicle and persist the selection.

    Tries the cloud-reported ``out_color`` name first, then falls back to
    extracting the dominant body colour from the vehicle image.
    """
    palette = palette_for_car_type(vehicle.car_type)

    matched = match_color_name(vehicle.out_color, palette)
    source = "out_color"
    if matched is None:
        image_bytes = await _load_body_image_bytes(vin, vehicle, client, container)
        rgb = dominant_color(image_bytes) if image_bytes else None
        if rgb is not None:
            matched = nearest_color(rgb, palette)
            source = "image"
        else:
            source = "none"

    if matched is not None:
        await save_vehicle_color(repo, vin, matched.key)
        return ColorDetectResponse(
            detected=PaletteColorSchema.from_model(matched), source=source
        )
    return ColorDetectResponse(detected=None, source="none")
