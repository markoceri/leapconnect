"""Zone routes: CRUD for geographic zones (consumed by notifications + charging).

Mutations trigger a dispatcher reload so the cached zone list used for
enter/exit detection refreshes immediately.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Request

from leapconnect.api.deps import ContainerDep, RepoDep
from leapconnect.api.schemas import (
    StatusResponse,
    ZoneCreate,
    ZoneResponse,
    ZoneUpdate,
)
from leapconnect.container import AppContainer
from leapconnect.domain.zones import Zone, polygon_centroid

_LOGGER = logging.getLogger(__name__)

router = APIRouter(tags=["zones"])


async def _reload_zones(container: AppContainer) -> None:
    """Refresh the dispatcher's cached zones after a mutation."""
    if container.notification_dispatcher:
        await container.notification_dispatcher.reload_config()


def _zone_to_response(zone: Zone) -> ZoneResponse:
    return ZoneResponse(
        id=zone.id,
        vin=zone.vin,
        name=zone.name,
        shape_type=zone.shape_type,
        latitude=zone.latitude,
        longitude=zone.longitude,
        radius_m=zone.radius_m,
        points=zone.points,
        notify_on_enter=zone.notify_on_enter,
        notify_on_exit=zone.notify_on_exit,
        enabled=zone.enabled,
        charging_tier_id=zone.charging_tier_id,
        dwell_alert_minutes=zone.dwell_alert_minutes,
        absence_alert_minutes=zone.absence_alert_minutes,
    )


@router.get("/api/zones")
async def get_zones(
    request: Request, repo: RepoDep, vin: str | None = None
) -> list[ZoneResponse]:
    """List zones, optionally filtered by VIN."""
    zones = await repo.get_zones(vin=vin)
    return [_zone_to_response(z) for z in zones]


@router.get("/api/zones/presence")
async def get_zone_presence(container: ContainerDep) -> dict[str, list[str]]:
    """Map each tracked VIN to the zone names it is currently inside."""
    if not container.notification_dispatcher:
        return {}
    return container.notification_dispatcher.zone_presence()


@router.post("/api/zones")
async def create_zone(
    request: Request, body: ZoneCreate, repo: RepoDep, container: ContainerDep
) -> ZoneResponse:
    """Create a new zone."""
    latitude, longitude = body.latitude, body.longitude
    points = body.points
    if body.shape_type == "polygon":
        if not points or len(points) < 3:
            raise HTTPException(
                status_code=400, detail="A polygon zone needs at least 3 points"
            )
        latitude, longitude = polygon_centroid(points)
    else:
        points = None
    zone = Zone(
        vin=body.vin,
        name=body.name,
        shape_type=body.shape_type,
        latitude=latitude,
        longitude=longitude,
        radius_m=body.radius_m,
        points=points,
        notify_on_enter=body.notify_on_enter,
        notify_on_exit=body.notify_on_exit,
        enabled=body.enabled,
        charging_tier_id=body.charging_tier_id or None,
        dwell_alert_minutes=body.dwell_alert_minutes,
        absence_alert_minutes=body.absence_alert_minutes,
    )
    saved = await repo.save_zone(zone)
    await _reload_zones(container)
    return _zone_to_response(saved)


@router.put("/api/zones/{zone_id}")
async def update_zone(
    request: Request,
    zone_id: int,
    body: ZoneUpdate,
    repo: RepoDep,
    container: ContainerDep,
) -> ZoneResponse:
    """Update a zone."""
    zones = await repo.get_zones()
    existing = next((z for z in zones if z.id == zone_id), None)
    if not existing:
        raise HTTPException(status_code=404, detail="Zone not found")
    if body.name is not None:
        existing.name = body.name
    if body.shape_type is not None:
        existing.shape_type = body.shape_type
    if body.radius_m is not None:
        existing.radius_m = body.radius_m
    if body.notify_on_enter is not None:
        existing.notify_on_enter = body.notify_on_enter
    if body.notify_on_exit is not None:
        existing.notify_on_exit = body.notify_on_exit
    if body.enabled is not None:
        existing.enabled = body.enabled
    if body.points is not None:
        existing.points = body.points
    if body.charging_tier_id is not None:
        # Empty string clears the assignment.
        existing.charging_tier_id = body.charging_tier_id or None
    if body.dwell_alert_minutes is not None:
        existing.dwell_alert_minutes = body.dwell_alert_minutes
    if body.absence_alert_minutes is not None:
        existing.absence_alert_minutes = body.absence_alert_minutes
    # Recompute geometry: polygons derive center from points, circles use lat/lon.
    if existing.shape_type == "polygon":
        if not existing.points or len(existing.points) < 3:
            raise HTTPException(
                status_code=400, detail="A polygon zone needs at least 3 points"
            )
        existing.latitude, existing.longitude = polygon_centroid(existing.points)
    else:
        existing.points = None
        if body.latitude is not None:
            existing.latitude = body.latitude
        if body.longitude is not None:
            existing.longitude = body.longitude
    saved = await repo.save_zone(existing)
    await _reload_zones(container)
    return _zone_to_response(saved)


@router.delete("/api/zones/{zone_id}")
async def delete_zone_endpoint(
    request: Request, zone_id: int, repo: RepoDep, container: ContainerDep
) -> StatusResponse:
    """Delete a zone."""
    deleted = await repo.delete_zone(zone_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Zone not found")
    await _reload_zones(container)
    return StatusResponse(status="ok")
