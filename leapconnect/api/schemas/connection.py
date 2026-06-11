"""Leapmotor cloud connection DTOs."""

from __future__ import annotations

from pydantic import BaseModel

from leapconnect.api.schemas.vehicle import VehicleSchema


class ReconnectResponse(BaseModel):
    status: str = "ok"
    connected: bool
    vehicles: list[VehicleSchema]


class LoginResponse(BaseModel):
    status: str = "ok"
    user_id: str | None = None
    vehicles: list[VehicleSchema]
    display_name: str | None = None


class SetPinResponse(BaseModel):
    status: str = "ok"
    has_pin: bool


class ConnectionStatusResponse(BaseModel):
    connected: bool
    has_account: bool
    has_user: bool
    user_id: str | None = None
    leapmotor_email: str | None = None
    display_name: str | None = None
    vehicles: list[VehicleSchema]
    has_pin: bool
    app_version: str | None = None
