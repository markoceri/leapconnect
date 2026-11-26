"""Charging sessions billed by a charging provider (pure domain service).

A provider (an e-mobility app such as EVDC) bills each public charge: when,
how many kWh, what it cost and which fees it added. Its sessions are matched
with the ones detected from the vehicle history, and their billed values are
applied to the cost records, without overriding what the user entered by hand.
"""

from __future__ import annotations

from collections.abc import Collection, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from leapconnect.domain.charging.models import (
    ChargingSessionCost,
    ChargingSessionExtra,
)
from leapconnect.domain.charging.sessions import ChargeSessionRow, naive_utc
from leapconnect.domain.zones.geometry import haversine_distance_m

# The provider's clock (the charger's) and the vehicle's snapshots don't agree
# to the minute, and the car reports charging a little after it starts.
MATCH_TOLERANCE = timedelta(minutes=15)

# An account can pay for other vehicles' charges too: a session overlapping a
# charge of this vehicle is only taken as its own when the place and the
# energy fit as well.
MAX_DISTANCE_M = 500.0
# kWh into the battery ÷ kWh billed: a bit less than 1 (charging losses),
# with room for the measurement steps of the battery energy
ENERGY_RATIO_RANGE = (0.7, 1.1)

MATCHED = "matched"  # overlapping, and place and energy fit
UNCERTAIN = "uncertain"  # overlapping, but the place or the energy doesn't fit
UNMATCHED = "unmatched"
IMPORTED = "imported"
DISMISSED = "dismissed"  # its session was unlinked by the user
ELSEWHERE = "elsewhere"  # linked to a session of another vehicle

# Provider sessions offered for a session picked by hand: this far around it
CANDIDATE_WINDOW = timedelta(hours=12)

PUBLIC_AC = "public_ac"
PUBLIC_DC = "public_dc"


@dataclass(frozen=True)
class ProviderFee:
    """A fee the provider billed on top of the energy (time, parking, ...)."""

    label: str
    amount: float


@dataclass(frozen=True)
class ProviderSession:
    """A charging session as billed by a provider. Times are naive UTC."""

    provider: str
    external_id: str
    started_at: datetime | None
    ended_at: datetime | None
    energy_kwh: float | None = None
    cost: float | None = None  # total billed, fees included
    currency: str | None = None
    price_kwh: float | None = None
    fees: tuple[ProviderFee, ...] = field(default=())
    evse_id: str | None = None
    operator: str | None = None
    location: str | None = None
    is_dc: bool | None = None  # the charger's power type; None = unknown
    latitude: float | None = None  # the charger's position
    longitude: float | None = None

    @property
    def energy_cost(self) -> float | None:
        """The billed total without the fees: what the energy cost."""
        if self.cost is None:
            return None
        return round(max(0.0, self.cost - sum(f.amount for f in self.fees)), 4)


@dataclass(frozen=True)
class ProviderMatch:
    """A provider session and the listed session it belongs to, if any."""

    session: ProviderSession
    row: ChargeSessionRow | None
    status: str  # MATCHED | UNCERTAIN | UNMATCHED | IMPORTED | DISMISSED | ELSEWHERE
    problems: tuple[str, ...] = ()  # why place or energy don't fit


def _window(row: ChargeSessionRow) -> tuple[datetime, datetime | None]:
    return naive_utc(row.start_ts), naive_utc(row.end_ts or row.detected_end_ts)


def _overlap(ps: ProviderSession, row: ChargeSessionRow) -> timedelta | None:
    """How long the two sessions overlap (with the tolerance); ``None`` when
    they don't."""
    if ps.started_at is None:
        return None
    start, end = _window(row)
    ps_end = ps.ended_at or ps.started_at
    end = end or start
    lo = max(ps.started_at, start - MATCH_TOLERANCE)
    hi = min(ps_end, end + MATCH_TOLERANCE)
    return hi - lo if hi >= lo else None


def _charger_distance_m(ps: ProviderSession, row: ChargeSessionRow) -> float | None:
    """Metres between the charger and where the vehicle charged; ``None``
    when either position is unknown. Some provider records have latitude and
    longitude swapped: the closer reading counts."""
    if ps.latitude is None or ps.longitude is None or row.location is None:
        return None
    lat, lon = row.location
    return min(
        haversine_distance_m(ps.latitude, ps.longitude, lat, lon),
        haversine_distance_m(ps.longitude, ps.latitude, lat, lon),
    )


def match_problems(ps: ProviderSession, row: ChargeSessionRow) -> tuple[str, ...]:
    """Why a provider session overlapping ``row`` may be another vehicle's:
    a charger far from where the vehicle charged, or an energy that doesn't
    fit the one the vehicle measured. Unknown data is no problem."""
    problems = []
    distance = _charger_distance_m(ps, row)
    if distance is not None and distance > MAX_DISTANCE_M:
        km = distance / 1000
        problems.append(f"charger {km:.1f} km from where the car charged")
    measured = [p.energy_kwh for p in row.parts if p.energy_kwh]
    if measured and ps.energy_kwh:
        battery = sum(measured)
        lo, hi = ENERGY_RATIO_RANGE
        if not lo <= battery / ps.energy_kwh <= hi:
            problems.append(
                f"billed {ps.energy_kwh:.1f} kWh, the car measured {battery:.1f} kWh"
            )
    return tuple(problems)


def match_provider_sessions(
    sessions: Sequence[ProviderSession],
    rows: Sequence[ChargeSessionRow],
    linked_elsewhere: Collection[str] = (),
) -> list[ProviderMatch]:
    """Match provider sessions with listed sessions, oldest first.

    A session already imported (a record holding its ``external_id``) stays
    with that record, and one linked to another vehicle's record
    (``linked_elsewhere``) is left alone. The others go to the row they
    overlap the most, one provider session per row (a merged session spans
    all its runs); a match where the place or the energy doesn't fit is
    ``UNCERTAIN`` (the account may have paid for another vehicle), one with a
    record the user unlinked ``DISMISSED``: neither is imported unless chosen.
    """
    by_external = {
        (r.record.external_source, r.record.external_id): r
        for r in rows
        if r.record is not None and r.record.external_id
    }
    taken: set[int] = set()
    results: dict[int, ProviderMatch] = {}
    candidates = []
    for i, ps in enumerate(sessions):
        row = by_external.get((ps.provider, ps.external_id))
        if row is not None:
            results[i] = ProviderMatch(ps, row, IMPORTED)
            taken.add(id(row))
            continue
        if ps.external_id in linked_elsewhere:
            results[i] = ProviderMatch(ps, None, ELSEWHERE)
            continue
        for row in rows:
            if row.record is not None and row.record.external_id:
                continue  # holds another provider session
            overlap = _overlap(ps, row)
            if overlap is not None:
                candidates.append((match_problems(ps, row), overlap, i, row))
    # Plausible matches first, then the largest overlaps: each row goes to the
    # session it fits best
    candidates.sort(key=lambda c: (bool(c[0]), -c[1]))
    for problems, _overlap_len, i, row in candidates:
        if i in results or id(row) in taken:
            continue
        if row.record is not None and row.record.auto_link_disabled:
            status = DISMISSED
        else:
            status = UNCERTAIN if problems else MATCHED
        results[i] = ProviderMatch(sessions[i], row, status, problems)
        taken.add(id(row))
    for i, ps in enumerate(sessions):
        results.setdefault(i, ProviderMatch(ps, None, UNMATCHED))
    return sorted(
        results.values(),
        key=lambda m: m.session.started_at or datetime.min,
    )


def public_tier(
    ps: ProviderSession, vehicle_dc: bool | None = None, current: str | None = None
) -> str:
    """Public AC or DC: as the vehicle saw the charge, else as the charger
    reports its power type. When neither knows, a public ``current`` tier is
    kept, else AC."""
    dc = vehicle_dc if vehicle_dc is not None else ps.is_dc
    if dc is None:
        return current if current in (PUBLIC_AC, PUBLIC_DC) else PUBLIC_AC
    return PUBLIC_DC if dc else PUBLIC_AC


def apply_provider_session(
    sc: ChargingSessionCost, ps: ProviderSession, *, vehicle_dc: bool | None = None
) -> None:
    """Apply a provider's billed values to a cost record, in place.

    Energy and cost entered by hand are kept; the provider's fees replace the
    extras it added before, the user's extras stay. A session billed on a
    public charger gets the public tier of its charge type (``vehicle_dc``:
    whether the vehicle saw a DC charge, ``None`` when it has no data).
    """
    if not sc.energy_manual and ps.energy_kwh is not None:
        sc.energy_kwh = ps.energy_kwh
    if not sc.cost_manual and sc.manual_price_kwh is None and ps.cost is not None:
        sc.cost = ps.energy_cost
    sc.extras = [e for e in sc.extras if e.source != ps.provider] + [
        ChargingSessionExtra(
            kind="fixed",
            label=f.label,
            amount=f.amount,
            cost=f.amount,
            source=ps.provider,
        )
        for f in ps.fees
    ]
    sc.tier_id = public_tier(ps, vehicle_dc, sc.tier_id)
    sc.external_source = ps.provider
    sc.external_id = ps.external_id
    sc.auto_link_disabled = False


def new_record_for(vin: str, ps: ProviderSession) -> ChargingSessionCost:
    """A cost record for a provider session the vehicle history doesn't show."""
    sc = ChargingSessionCost(
        vin=vin,
        start_ts=ps.started_at,
        end_ts=ps.ended_at,
        tier_id=public_tier(ps),
        note=" · ".join(p for p in (ps.operator, ps.location) if p) or None,
    )
    apply_provider_session(sc, ps)
    return sc


@dataclass(frozen=True)
class ProviderCandidate:
    """A provider session offered for a session picked by hand."""

    session: ProviderSession
    overlap: timedelta | None  # None: no overlap, only close in time
    distance: timedelta  # between the two starts
    problems: tuple[str, ...] = ()  # why place or energy don't fit


def rank_candidates(
    sessions: Sequence[ProviderSession], row: ChargeSessionRow
) -> list[ProviderCandidate]:
    """Provider sessions around a listed session, best first.

    Plausible overlapping ones come first (the largest overlap first), then
    the overlapping ones whose place or energy doesn't fit, then the ones
    within ``CANDIDATE_WINDOW`` that don't overlap, the closest first.
    """
    start = naive_utc(row.start_ts)
    ranked = []
    for ps in sessions:
        if ps.started_at is None:
            continue
        distance = abs(ps.started_at - start)
        overlap = _overlap(ps, row)
        if overlap is None and distance > CANDIDATE_WINDOW:
            continue
        ranked.append(ProviderCandidate(ps, overlap, distance, match_problems(ps, row)))
    return sorted(
        ranked,
        key=lambda c: (
            c.overlap is None,
            bool(c.problems),
            -(c.overlap or timedelta()),
            c.distance,
        ),
    )


def unlink_provider_session(
    sc: ChargingSessionCost, *, disable_auto_link: bool = True
) -> None:
    """Detach a record from its provider session, in place: the provider's
    extras go and, when unlinked by the user (``disable_auto_link``), the
    automatic import won't link it again."""
    source = sc.external_source
    sc.extras = [e for e in sc.extras if not e.source or e.source != source]
    sc.external_source = sc.external_id = None
    sc.auto_link_disabled = disable_auto_link
