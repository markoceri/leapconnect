"""Zone DTOs."""

from __future__ import annotations

from pydantic import BaseModel


class ZoneCreate(BaseModel):
    vin: str | None = None
    name: str
    shape_type: str = "circle"
    latitude: float
    longitude: float
    radius_m: float = 200.0
    points: list[list[float]] | None = None
    notify_on_enter: bool = True
    notify_on_exit: bool = True
    enabled: bool = True
    charging_tier_id: str | None = None
    dwell_alert_minutes: int = 0
    absence_alert_minutes: int = 0


class ZoneUpdate(BaseModel):
    name: str | None = None
    shape_type: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    radius_m: float | None = None
    points: list[list[float]] | None = None
    notify_on_enter: bool | None = None
    notify_on_exit: bool | None = None
    enabled: bool | None = None
    charging_tier_id: str | None = None
    dwell_alert_minutes: int | None = None
    absence_alert_minutes: int | None = None


class ZoneResponse(BaseModel):
    id: int
    vin: str | None = None
    name: str
    shape_type: str
    latitude: float
    longitude: float
    radius_m: float
    points: list[list[float]] | None = None
    notify_on_enter: bool
    notify_on_exit: bool
    enabled: bool
    charging_tier_id: str | None = None
    dwell_alert_minutes: int = 0
    absence_alert_minutes: int = 0
