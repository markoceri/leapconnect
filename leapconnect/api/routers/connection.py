"""Leapmotor cloud connection routes: session lifecycle, PIN, status."""

from __future__ import annotations

import logging
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request

from leapconnect.api.deps import ContainerDep, RepoDep
from leapconnect.api.schemas import (
    ConnectionStatusResponse,
    LoginResponse,
    ReconnectResponse,
    StatusResponse,
    VehicleSchema,
)
from leapconnect.config import APP_VERSION
from leapconnect.container import AppContainer

_LOGGER = logging.getLogger(__name__)

router = APIRouter(tags=["cloud-connection"])


async def _save_vehicle_pin(container: AppContainer, pin: str) -> None:
    """Persist the vehicle operation PIN for MQTT commands."""
    if container.repo:
        await container.repo.save_setting("mqtt_vehicle_pin", pin)


@router.put("/api/cloud/session", response_model=ReconnectResponse)
async def reconnect(repo: RepoDep, container: ContainerDep) -> ReconnectResponse:
    """Reconnect using previously saved credentials."""

    account = await repo.get_account()
    if not account:
        raise HTTPException(status_code=400, detail="No account configured")

    try:
        vehicles = await container.connect(
            username=account["username"],
            password=account["password"],
            cert_path=account["cert_path"],
            key_path=account["key_path"],
            p12_password=account.get("p12_password"),
        )
        return ReconnectResponse(
            status="ok",
            connected=True,
            vehicles=[VehicleSchema.from_model(v) for v in vehicles],
        )
    except Exception as exc:
        raise HTTPException(
            status_code=502, detail=f"Connection failed: {exc}"
        ) from exc


@router.delete("/api/cloud/session", response_model=StatusResponse)
async def disconnect(container: ContainerDep) -> StatusResponse:
    """Disconnect from the Leapmotor cloud without clearing session."""
    container.disconnect()
    return StatusResponse(status="ok")


@router.post("/api/cloud/session", response_model=LoginResponse)
async def login(
    request: Request, repo: RepoDep, container: ContainerDep
) -> LoginResponse:
    """Authenticate with Leapmotor using email and password."""
    body = await request.json()
    username = body.get("username", "").strip()
    password = body.get("password", "").strip()

    if not all([username, password]):
        raise HTTPException(status_code=422, detail="Missing email or password")

    # Certificate paths from DB (uploaded via /api/setup/certificates)
    account = await repo.get_account()
    if account:
        app_cert_path = account.get("cert_path", "")
        app_key_path = account.get("key_path", "")
        account_p12_password = account.get("p12_password")
    else:
        app_cert_path = await repo.get_setting("cert_path") or ""
        app_key_path = await repo.get_setting("key_path") or ""
        account_p12_password = None

    if not app_cert_path or not app_key_path:
        raise HTTPException(
            status_code=500,
            detail="Certificates not configured. Upload them via setup first.",
        )
    if not Path(app_cert_path).is_file():
        raise HTTPException(
            status_code=500, detail=f"App cert not found: {app_cert_path}"
        )
    if not Path(app_key_path).is_file():
        raise HTTPException(
            status_code=500, detail=f"App key not found: {app_key_path}"
        )

    try:
        vehicles = await container.connect(
            username=username,
            password=password,
            cert_path=app_cert_path,
            key_path=app_key_path,
            p12_password=account_p12_password,
        )
        user = await repo.get_user() or {}
        return LoginResponse(
            status="ok",
            user_id=container.sync_client.user_id,
            vehicles=[VehicleSchema.from_model(v) for v in vehicles],
            display_name=user.get("display_name"),
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc


@router.get("/api/cloud/pin")
async def get_vehicle_pin(container: ContainerDep) -> dict:
    """Get the saved vehicle PIN status (the PIN itself is write-only)."""
    saved_pin = None
    if container.repo:
        saved_pin = await container.repo.get_setting("mqtt_vehicle_pin")
    runtime_pin = (
        container.sync_client.operation_password if container.sync_client else None
    )
    pin = saved_pin or runtime_pin
    return {"has_pin": bool(pin)}


@router.put("/api/cloud/pin")
async def update_vehicle_pin(request: Request, container: ContainerDep) -> dict:
    """Save or clear the vehicle operation PIN (never echoed back)."""
    body = await request.json()
    pin = str(body.get("pin", "")).strip()
    await _save_vehicle_pin(container, pin)
    if container.sync_client and pin:
        container.sync_client.operation_password = pin
    return {"has_pin": bool(pin)}


@router.get("/api/cloud/status", response_model=ConnectionStatusResponse)
async def connection_status(container: ContainerDep) -> ConnectionStatusResponse:
    """Get current connection status, account info, and vehicle list."""
    has_account = False
    has_user = False
    display_name = None
    leapmotor_email = None
    if container.repo:
        account = await container.repo.get_account()
        has_account = account is not None
        leapmotor_email = account["username"] if account else None
        user = await container.repo.get_user()
        has_user = user is not None
        display_name = user["display_name"] if user else None
    return ConnectionStatusResponse(
        connected=container.connected,
        has_account=has_account,
        has_user=has_user,
        user_id=container.sync_client.user_id if container.sync_client else None,
        leapmotor_email=leapmotor_email,
        display_name=display_name,
        vehicles=[VehicleSchema.from_model(v) for v in container.vehicles],
        has_pin=bool(
            container.sync_client and container.sync_client.operation_password
        ),
        app_version=APP_VERSION,
    )
