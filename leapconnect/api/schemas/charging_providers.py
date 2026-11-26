"""DTOs of the charging providers (eMSP accounts such as EVDC), the import of
their billed sessions, their charging points and the charge sites."""

from __future__ import annotations

from pydantic import BaseModel, Field

from leapconnect.api.schemas.charging import ChargingSessionCostResponse

# -- accounts -------------------------------------------------------------------


class ProviderTypeSchema(BaseModel):
    id: str  # e.g. "evdc"
    label: str
    url: str
    username_label: str
    note: str | None = None
    has_stations: bool = False


class ProviderAccountResponse(BaseModel):
    id: int
    provider: str
    label: str  # the provider type's
    username: str
    connected: bool
    auto_sync: bool = True
    last_sync: str | None = None
    last_error: str | None = None


class ProvidersResponse(BaseModel):
    types: list[ProviderTypeSchema]
    accounts: list[ProviderAccountResponse]


class ProviderLoginRequest(BaseModel):
    provider: str = Field(min_length=1, max_length=16)
    username: str = Field(min_length=3, max_length=256)
    password: str = Field(min_length=1, max_length=256)


class ProviderLoginResponse(BaseModel):
    # Connected, or waiting for the two-factor code sent to /pending/{id}/verify
    account: ProviderAccountResponse | None = None
    pending_id: str | None = None
    two_factor_method: str | None = None  # "email" | "totp"


class ProviderVerifyRequest(BaseModel):
    code: str = Field(min_length=4, max_length=16)


class ProviderAccountUpdate(BaseModel):
    auto_sync: bool


# -- charging points --------------------------------------------------------------


class ChargingStationSchema(BaseModel):
    provider: str
    provider_label: str
    evse_id: str
    name: str | None = None
    operator: str | None = None
    address: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    max_power_kw: float | None = None
    is_dc: bool | None = None
    plugs: list[str] = []
    is_open_24h: bool | None = None
    # Live (from the provider)
    status: str | None = None
    price: float | None = None
    price_unit: str | None = None
    currency: str | None = None
    distance_m: float | None = None


class ChargingStationsResponse(BaseModel):
    stations: list[ChargingStationSchema]  # nearest first, per provider
    errors: dict[str, str] = {}  # provider -> why its search failed


class ChargeSiteSchema(BaseModel):
    latitude: float
    longitude: float
    sessions: int
    first_ts: str | None = None
    last_ts: str | None = None
    energy_kwh: float
    cost: float
    zone_name: str | None = None
    tier_id: str | None = None
    stations: list[ChargingStationSchema] = []


class ChargeSitesResponse(BaseModel):
    sites: list[ChargeSiteSchema]  # latest first


# -- billed sessions --------------------------------------------------------------


class ProviderFeeSchema(BaseModel):
    label: str
    amount: float


class ProviderSessionSchema(BaseModel):
    provider: str
    provider_label: str
    account_id: int | None = None
    account_username: str | None = None
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
    station: ChargingStationSchema | None = None


class ProviderImportPeriod(BaseModel):
    year: int = Field(ge=2000, le=2100)
    month: int = Field(ge=1, le=12)
    # The account to import from; every connected one when omitted
    account_id: int | None = None


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
    candidates: list[ProviderLinkCandidate]  # best first


class ProviderLinkRequest(BaseModel):
    account_id: int
    external_id: str = Field(min_length=1, max_length=64)
    # The session: its record, or its start when seen only in the history
    cost_id: int | None = None
    start_ts: str | None = None
