"""DTOs of the charging providers (EVDC) and the import of their sessions."""

from __future__ import annotations

from pydantic import BaseModel, Field

from leapconnect.api.schemas.charging import ChargingSessionCostResponse


class ProviderStatusResponse(BaseModel):
    provider: str
    label: str
    connected: bool
    email: str | None = None
    # "email" | "totp" while a login waits for a verification code
    two_factor_pending: str | None = None
    auto_sync: bool = True
    last_sync: str | None = None
    last_error: str | None = None


class ProviderLoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=256)
    password: str = Field(min_length=1, max_length=256)


class ProviderVerifyRequest(BaseModel):
    code: str = Field(min_length=4, max_length=16)


class ProviderSettingsUpdate(BaseModel):
    auto_sync: bool


class ProviderFeeSchema(BaseModel):
    label: str
    amount: float


class ProviderSessionSchema(BaseModel):
    external_id: str
    started_at: str | None = None
    ended_at: str | None = None
    energy_kwh: float | None = None
    cost: float | None = None  # billed total, fees included
    energy_cost: float | None = None
    currency: str | None = None
    price_kwh: float | None = None
    fees: list[ProviderFeeSchema] = []
    evse_id: str | None = None
    operator: str | None = None
    location: str | None = None


class ProviderImportPeriod(BaseModel):
    year: int = Field(ge=2000, le=2100)
    month: int = Field(ge=1, le=12)


class ProviderImportItem(BaseModel):
    # matched | uncertain | unmatched | imported | dismissed | elsewhere
    status: str
    session: ProviderSessionSchema
    # The listed session it matches: its record (None when not stored yet)
    row_start_ts: str | None = None
    row_end_ts: str | None = None
    current: ChargingSessionCostResponse | None = None
    proposed: ChargingSessionCostResponse | None = None
    energy_kept: bool = False  # entered by hand: not replaced
    cost_kept: bool = False
    # Why it may be another vehicle's charge (place or energy don't fit)
    problems: list[str] = []


class ProviderImportPreviewResponse(BaseModel):
    provider: str
    items: list[ProviderImportItem]  # oldest first


class ProviderImportApplyRequest(ProviderImportPeriod):
    # Matched sessions to import (all when omitted)
    external_ids: list[str] | None = None
    # Unmatched sessions to create
    create_ids: list[str] = []


class ProviderImportApplyResponse(BaseModel):
    applied: int
    created: int
    skipped: int


class ProviderLinkCandidate(BaseModel):
    session: ProviderSessionSchema
    overlap_minutes: int | None = None  # None: close in time, no overlap
    problems: list[str] = []  # why it may be another vehicle's charge
    best: bool = False  # the one to propose
    # Linked now to another record: linking it here moves it
    linked_vin: str | None = None
    linked_cost_id: int | None = None
    proposed: ChargingSessionCostResponse


class ProviderLinkCandidatesResponse(BaseModel):
    provider: str
    candidates: list[ProviderLinkCandidate]  # best first


class ProviderLinkRequest(BaseModel):
    external_id: str = Field(min_length=1, max_length=64)
    # The session: its record, or its start when seen only in the history
    cost_id: int | None = None
    start_ts: str | None = None
