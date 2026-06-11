"""Setup, certificates, account and local-user DTOs."""

from __future__ import annotations

from pydantic import BaseModel

from leapconnect.api.schemas.vehicle import VehicleSchema


class SetupStatusResponse(BaseModel):
    has_user: bool
    has_account: bool
    has_certificates: bool
    certificates_valid: bool
    certs_found_on_disk: bool = False
    authenticated: bool = False
    connected: bool
    vehicles: list[VehicleSchema]
    display_name: str | None = None


class CertificateUploadResponse(BaseModel):
    status: str = "ok"
    cert_path: str
    key_path: str


class CertificateStatusResponse(BaseModel):
    cert_exists: bool
    key_exists: bool


class CertificateFetchResponse(BaseModel):
    status: str = "ok"
    cert_path: str | None = None
    key_path: str | None = None
    source: str | None = None


class AccountSetupResponse(BaseModel):
    status: str = "ok"
    connected: bool
    vehicles: list[VehicleSchema] = []
    connection_error: str | None = None


class AccountTestResponse(BaseModel):
    status: str = "ok"
    connected: bool
    vehicles: list[VehicleSchema] = []
    connection_error: str | None = None


class UserCreateResponse(BaseModel):
    status: str = "ok"
    display_name: str


class AuthLoginResponse(BaseModel):
    status: str = "ok"
    display_name: str


class UserUpdateResponse(BaseModel):
    status: str = "ok"
    display_name: str


class UserInfoResponse(BaseModel):
    has_user: bool
    display_name: str | None = None
