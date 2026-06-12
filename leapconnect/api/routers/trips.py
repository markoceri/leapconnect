"""Trip analytics routes — derived on the fly from local history snapshots."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, HTTPException

from leapconnect.api.deps import VehicleDep, parse_range_date, repo_required
from leapconnect.application.ports.repositories import AppRepository
from leapconnect.domain.trips.analysis import (
    build_local_trip_payload,
    calculate_local_regen_energy_kwh,
    detect_local_charge_sessions,
    flatten_trip_rows,
    trip_compare_metrics,
    trip_distance_km,
    trip_similarity_breakdown,
    trip_start_hour,
)

router = APIRouter()

# History repo with the endpoint-specific 503 message
HistoryRepo = Annotated[AppRepository, repo_required("History not available")]


async def _range_snapshots(
    repo: AppRepository,
    vin: str,
    begin_time: str | None,
    end_time: str | None,
    *,
    default_days: int = 30,
    max_points: int = 10_000,
):
    """Load history snapshots for a normalized date range."""
    today = date.today()
    bt = (
        parse_range_date(begin_time)
        or (today - timedelta(days=default_days)).isoformat()
    )
    et = parse_range_date(end_time) or today.isoformat()
    snapshots = await repo.get_history(
        vin,
        from_date=bt,
        to_date=et,
        max_points=max_points,
    )
    return snapshots, bt, et


@router.get("/api/vehicles/{vin}/trips")
async def get_trips(
    vin: str,
    repo: HistoryRepo,
    vehicle: VehicleDep,
    begin_time: str | None = None,
    end_time: str | None = None,
):
    """Get driving records from locally collected history snapshots."""
    snapshots, _, _ = await _range_snapshots(repo, vin, begin_time, end_time)
    return build_local_trip_payload(snapshots)


@router.get("/api/vehicles/{vin}/trips/totals")
async def get_trips_totals(
    vin: str,
    repo: HistoryRepo,
    vehicle: VehicleDep,
    begin_time: str | None = None,
    end_time: str | None = None,
):
    """Get total driving statistics computed from local history snapshots."""
    snapshots, _, _ = await _range_snapshots(repo, vin, begin_time, end_time)
    payload = build_local_trip_payload(snapshots)

    # Flatten trip rows for totals.
    trip_rows = [
        trip for day in payload.get("data", []) for trip in day.get("drivingRecord", [])
    ]
    max_speed = max((s.drive_speed or 0) for s in snapshots) if snapshots else 0
    total_hours = 0.0
    for trip in trip_rows:
        try:
            bt_dt = datetime.strptime(trip["beginTime"], "%Y-%m-%d %H:%M:%S")
            et_dt = datetime.strptime(trip["endTime"], "%Y-%m-%d %H:%M:%S")
            total_hours += max(0.0, (et_dt - bt_dt).total_seconds() / 3600)
        except (ValueError, KeyError):
            continue

    return {
        "source": "local_history",
        "maxspeed": int(max_speed),
        "totalenery": round(float(payload.get("total_enery", 0.0)), 3),
        "totalmileage": round(float(payload.get("total_milage", 0.0)), 2),
        "totalrecoveryenery": calculate_local_regen_energy_kwh(snapshots),
        "ustime": round(total_hours, 2),
    }


@router.get("/api/vehicles/{vin}/trips/gps/{gpskey}")
async def get_trip_gps(vin: str, gpskey: str, repo: HistoryRepo, vehicle: VehicleDep):
    """Get trip GPS trace from local history snapshots."""
    try:
        start_raw, end_raw = gpskey.split("_", 1)
        start_dt = datetime.utcfromtimestamp(int(start_raw))
        end_dt = datetime.utcfromtimestamp(int(end_raw))
    except ValueError as exc:
        raise HTTPException(
            status_code=422, detail=f"Invalid gpskey: {gpskey}"
        ) from exc

    snapshots = await repo.get_history(
        vin,
        from_date=start_dt.date().isoformat(),
        to_date=end_dt.date().isoformat(),
        max_points=10_000,
    )
    points = [
        {
            "timestamp": s.timestamp.isoformat(),
            "lat": s.vehicle_latitude,
            "lng": s.vehicle_longitude,
            "speed": s.drive_speed,
        }
        for s in snapshots
        if (
            s.vehicle_latitude is not None
            and s.vehicle_longitude is not None
            and start_dt <= s.timestamp <= end_dt
        )
    ]
    return points


@router.get("/api/vehicles/{vin}/trips/similar")
async def get_similar_trips(
    vin: str,
    gpskey: str,
    repo: HistoryRepo,
    vehicle: VehicleDep,
    limit: int = 3,
    begin_time: str | None = None,
    end_time: str | None = None,
):
    """Suggest trips similar to a reference trip.

    Similarity score is composed by route (40%), time-of-day (35%), and
    distance (25%).
    """
    snapshots, _, _ = await _range_snapshots(
        repo, vin, begin_time, end_time, default_days=90, max_points=50_000
    )
    payload = build_local_trip_payload(snapshots)
    trips = flatten_trip_rows(payload)

    # Try exact gpskey match first; if downsampling shifted boundaries,
    # fall back to fuzzy match using the timestamps embedded in gpskey.
    reference = next((t for t in trips if t.get("gpskey") == gpskey), None)
    if not reference:
        try:
            ref_start_ts, ref_end_ts = gpskey.split("_", 1)
            ref_start = int(ref_start_ts)
            ref_end = int(ref_end_ts)
            # Allow ±120 seconds tolerance for downsampling-induced shifts
            for t in trips:
                t_start = t.get("beginTime", "")
                t_end = t.get("endTime", "")
                if not t_start or not t_end:
                    continue
                try:
                    ts_s = int(
                        datetime.strptime(t_start, "%Y-%m-%d %H:%M:%S")
                        .replace(tzinfo=UTC)
                        .timestamp()
                    )
                    ts_e = int(
                        datetime.strptime(t_end, "%Y-%m-%d %H:%M:%S")
                        .replace(tzinfo=UTC)
                        .timestamp()
                    )
                except (ValueError, OSError):
                    continue
                if abs(ts_s - ref_start) <= 120 and abs(ts_e - ref_end) <= 120:
                    reference = t
                    break
        except (ValueError, IndexError):
            pass

    if not reference:
        raise HTTPException(
            status_code=404,
            detail=f"Trip not found for gpskey={gpskey}",
        )

    candidates: list[dict] = []
    ref_distance = trip_distance_km(reference)
    ref_hour = trip_start_hour(reference)
    for trip in trips:
        if trip.get("gpskey") == gpskey:
            continue

        cand_distance = trip_distance_km(trip)
        if ref_distance > 0:
            ratio = cand_distance / ref_distance if ref_distance else 0
            if ratio < 0.6 or ratio > 1.4:
                continue

        cand_hour = trip_start_hour(trip)
        if ref_hour is not None and cand_hour is not None:
            hour_diff = abs(ref_hour - cand_hour)
            hour_diff = min(hour_diff, 24 - hour_diff)
            if hour_diff > 6:
                continue

        similarity = trip_similarity_breakdown(reference, trip)
        metrics = trip_compare_metrics(reference, trip)
        candidates.append(
            {
                "trip": trip,
                "similarity_score": similarity["score"],
                "score_breakdown": similarity["breakdown"],
                "metrics": metrics,
            }
        )

    candidates.sort(
        key=lambda c: (
            c["similarity_score"],
            c["trip"].get("beginTime", ""),
        ),
        reverse=True,
    )
    max_limit = max(1, min(int(limit or 3), 10))

    return {
        "source": "local_history",
        "reference": reference,
        "count": len(candidates),
        "items": candidates[:max_limit],
    }


@router.get("/api/vehicles/{vin}/charge-stats/cloud")
async def get_charge_stats_cloud(
    vin: str,
    repo: HistoryRepo,
    vehicle: VehicleDep,
    begin_time: str | None = None,
    end_time: str | None = None,
):
    """Get daily charging statistics derived from local history."""
    snapshots, bt, et = await _range_snapshots(repo, vin, begin_time, end_time)
    sessions = detect_local_charge_sessions(snapshots)

    days: dict[str, dict] = {}
    for session in sessions:
        day = session["start_ts"].date().isoformat()
        bucket = days.setdefault(
            day,
            {
                "date": day,
                "sessions": 0,
                "energy_kwh": 0.0,
            },
        )
        bucket["sessions"] += 1
        bucket["energy_kwh"] += float(session["energy_kwh"] or 0.0)

    ordered = sorted(days.values(), key=lambda d: d["date"])
    total_energy = round(sum(d["energy_kwh"] for d in ordered), 3)
    return {
        "source": "local_history",
        "vin": vin,
        "beginTime": bt,
        "endTime": et,
        "days": [
            {
                "date": d["date"],
                "sessions": d["sessions"],
                "energy_kwh": round(d["energy_kwh"], 3),
            }
            for d in ordered
        ],
        "total_sessions": sum(d["sessions"] for d in ordered),
        "total_energy_kwh": total_energy,
    }


@router.get("/api/vehicles/{vin}/charge-stats/year")
async def get_charge_stats_year(
    vin: str, repo: HistoryRepo, vehicle: VehicleDep, year: str | None = None
):
    """Get annual charging statistics derived from local history."""
    y = year or str(date.today().year)
    if not y.isdigit() or len(y) != 4:
        raise HTTPException(status_code=422, detail="year must be YYYY")

    snapshots = await repo.get_history(
        vin,
        from_date=f"{y}-01-01",
        to_date=f"{y}-12-31",
        max_points=20_000,
    )
    sessions = detect_local_charge_sessions(snapshots)

    months: dict[str, dict] = {}
    for session in sessions:
        month = session["start_ts"].strftime("%Y-%m")
        bucket = months.setdefault(
            month,
            {
                "month": month,
                "sessions": 0,
                "energy_kwh": 0.0,
            },
        )
        bucket["sessions"] += 1
        bucket["energy_kwh"] += float(session["energy_kwh"] or 0.0)

    ordered = sorted(months.values(), key=lambda m: m["month"])
    return {
        "source": "local_history",
        "vin": vin,
        "year": y,
        "months": [
            {
                "month": m["month"],
                "sessions": m["sessions"],
                "energy_kwh": round(m["energy_kwh"], 3),
            }
            for m in ordered
        ],
        "total_sessions": sum(m["sessions"] for m in ordered),
        "total_energy_kwh": round(sum(m["energy_kwh"] for m in ordered), 3),
    }
