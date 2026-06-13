"""Trip analytics domain services (pure functions).

Builds cloud-compatible trip payloads from local telemetry snapshots:

1. Extract raw "moving" segments (contiguous speed>0 windows).
2. Merge segments whose inter-segment gap is small and not parked.
3. Drop segments below minimum distance.

Also provides trip similarity scoring and charge-session detection.
"""

from __future__ import annotations

import math
from datetime import datetime

from leapconnect.domain.telemetry.models import VehicleSnapshot

# Maximum gap (seconds) between two moving segments to still consider them
# the same trip (e.g. traffic light, stop sign).  If the pause is longer
# than this, the segments become separate trips.
MERGE_GAP_S = 300  # 5 minutes

# Trips shorter than this are considered noise and dropped.
MIN_TRIP_KM = 0.2


def is_snapshot_moving(snapshot: VehicleSnapshot) -> bool:
    speed = snapshot.drive_speed or 0
    return speed > 0 or snapshot.drive_is_parked is False


def _segment_end(seg: list[VehicleSnapshot]) -> VehicleSnapshot:
    return seg[-1]


def _segment_start(seg: list[VehicleSnapshot]) -> VehicleSnapshot:
    return seg[0]


def build_trip_row(segment: list[VehicleSnapshot]) -> dict | None:
    """Turn a *merged* segment into a trip row for the response payload."""
    if len(segment) < 2:
        return None

    start = _segment_start(segment)
    end = _segment_end(segment)
    duration_h = max(0.0, (end.timestamp - start.timestamp).total_seconds() / 3600.0)
    if duration_h <= 0:
        return None

    start_km = start.drive_total_mileage
    end_km = end.drive_total_mileage
    travel_km = 0.0
    if start_km is not None and end_km is not None:
        travel_km = max(0.0, float(end_km) - float(start_km))

    if travel_km < MIN_TRIP_KM:
        return None

    start_wh = start.battery_dump_energy
    end_wh = end.battery_dump_energy
    energy_wh = 0.0
    if start_wh is not None and end_wh is not None:
        energy_wh = abs(float(end_wh) - float(start_wh))

    return {
        "beginTime": start.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
        "endTime": end.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
        "travelMile": int(round(travel_km * 1000)),
        "energyConsumed": int(round(energy_wh)),
        "energyRecovered": int(round(segment_regen_energy_wh(segment))),
        "maxSpeed": max((s.drive_speed or 0) for s in segment),
        "avgSpeed": round(travel_km / duration_h, 1) if duration_h > 0 else 0,
        "startSoc": start.battery_soc,
        "endSoc": end.battery_soc,
        "outdoorTemp": start.climate_outdoor_temp,
        "startLat": start.vehicle_latitude,
        "startLng": start.vehicle_longitude,
        "endLat": end.vehicle_latitude,
        "endLng": end.vehicle_longitude,
        "gpskey": (
            f"{int(start.timestamp.timestamp())}_{int(end.timestamp.timestamp())}"
        ),
        "_travel_km": travel_km,
        "_energy_kwh": energy_wh / 1000.0,
        "_duration_h": duration_h,
    }


def _any_parked_in_gap(
    snapshots: list[VehicleSnapshot],
    seg_a: list[VehicleSnapshot],
    seg_b: list[VehicleSnapshot],
) -> bool:
    """Check whether the vehicle was explicitly *parked* in the gap
    between two segments."""
    # Look at snapshot rows whose timestamps fall between seg_a end and seg_b start.
    gap_start = _segment_end(seg_a).timestamp
    gap_end = _segment_start(seg_b).timestamp
    for s in snapshots:
        if gap_start < s.timestamp < gap_end and s.drive_is_parked is True:
            return True
    return False


def merge_segments(
    raw_segments: list[list[VehicleSnapshot]],
    snapshots: list[VehicleSnapshot],
) -> list[list[VehicleSnapshot]]:
    """Merge adjacent segments whose gap is small and there was no explicit park.

    Two raw segments are merged when:
    1. The time gap between them is <= ``MERGE_GAP_S``.
    2. No snapshot in the gap has ``drive_is_parked == True``.
    """
    if not raw_segments:
        return []

    merged: list[list[VehicleSnapshot]] = [raw_segments[0].copy()]

    for seg in raw_segments[1:]:
        last = merged[-1]
        gap_s = (
            _segment_start(seg).timestamp - _segment_end(last).timestamp
        ).total_seconds()
        parked_in_gap = _any_parked_in_gap(snapshots, last, seg)

        if gap_s <= MERGE_GAP_S and not parked_in_gap:
            # Extend the last merged segment instead of creating a new one.
            # Drop the first snapshot of 'seg' to avoid duplicating the boundary.
            if len(seg) > 1:
                merged[-1].extend(seg[1:])
            else:
                merged[-1].extend(seg)
        else:
            merged.append(seg.copy())

    return merged


def build_local_trip_payload(snapshots: list[VehicleSnapshot]) -> dict:
    """Build a cloud-like trip payload from local history snapshots."""
    if len(snapshots) < 2:
        return {
            "source": "local_history",
            "total_energy": 0,
            "total_mileage": 0,
            "total_hours": 0,
            "data": [],
        }

    # --- Step 1: collect raw moving segments ---
    raw_segments: list[list[VehicleSnapshot]] = []
    cur: list[VehicleSnapshot] = []

    for idx, snap in enumerate(snapshots):
        moving = is_snapshot_moving(snap)
        if moving:
            if not cur:
                prev = snapshots[idx - 1] if idx > 0 else snap
                cur = [prev]
            cur.append(snap)
        elif cur:
            cur.append(snap)
            raw_segments.append(cur)
            cur = []

    if cur:
        raw_segments.append(cur)

    # --- Step 2: merge close segments ---
    segments = merge_segments(raw_segments, snapshots)

    # --- Step 3: build trip rows ---
    trip_rows = [r for seg in segments if (r := build_trip_row(seg))]

    # --- Step 4: group by day ---
    by_day: dict[str, dict] = {}
    total_energy_kwh = 0.0
    total_distance_km = 0.0
    total_hours = 0.0

    for trip in trip_rows:
        day = trip["beginTime"][:10]
        bucket = by_day.setdefault(
            day,
            {
                "day": day,
                "accumulated_energy_consumed": 0,
                "accumulated_mileage": 0.0,
                "current_mileage": 0.0,
                "drivingRecord": [],
            },
        )
        bucket["drivingRecord"].append(
            {
                "beginTime": trip["beginTime"],
                "endTime": trip["endTime"],
                "travelMile": trip["travelMile"],
                "energyConsumed": trip["energyConsumed"],
                "energyRecovered": trip["energyRecovered"],
                "maxSpeed": trip["maxSpeed"],
                "avgSpeed": trip["avgSpeed"],
                "startSoc": trip["startSoc"],
                "endSoc": trip["endSoc"],
                "outdoorTemp": trip["outdoorTemp"],
                "startLat": trip["startLat"],
                "startLng": trip["startLng"],
                "endLat": trip["endLat"],
                "endLng": trip["endLng"],
                "gpskey": trip["gpskey"],
            }
        )
        bucket["accumulated_energy_consumed"] += trip["energyConsumed"]
        bucket["accumulated_mileage"] += trip["_travel_km"]
        bucket["current_mileage"] = round(bucket["accumulated_mileage"], 2)

        total_energy_kwh += trip["_energy_kwh"]
        total_distance_km += trip["_travel_km"]
        total_hours += trip["_duration_h"]

    for b in by_day.values():
        b["accumulated_mileage"] = round(b["accumulated_mileage"], 2)

    ordered_days = sorted(by_day.values(), key=lambda d: d["day"], reverse=True)
    return {
        "source": "local_history",
        "total_energy": round(total_energy_kwh, 3),
        "total_mileage": round(total_distance_km, 2),
        "total_hours": round(total_hours, 2),
        "data": ordered_days,
    }


def calculate_local_regen_energy_kwh(snapshots: list[VehicleSnapshot]) -> float:
    total = 0.0
    for i in range(1, len(snapshots)):
        prev = snapshots[i - 1]
        curr = snapshots[i]
        if not curr.vehicle_is_regening:
            continue
        power_kw = curr.battery_charging_power_kw
        if power_kw is None or power_kw <= 0:
            continue
        dt_h = (curr.timestamp - prev.timestamp).total_seconds() / 3600
        if dt_h <= 0 or dt_h > 0.5:
            continue
        total += power_kw * dt_h
    return round(total, 3)


def segment_regen_energy_wh(segment: list[VehicleSnapshot]) -> float:
    """Calculate regenerative braking energy (in Wh) for a single trip segment."""
    total = 0.0
    for i in range(1, len(segment)):
        prev = segment[i - 1]
        curr = segment[i]
        if not curr.vehicle_is_regening:
            continue
        power_kw = curr.battery_charging_power_kw
        if power_kw is None or power_kw <= 0:
            continue
        dt_h = (curr.timestamp - prev.timestamp).total_seconds() / 3600
        if dt_h <= 0 or dt_h > 0.5:
            continue
        total += power_kw * dt_h * 1000  # kWh → Wh
    return round(total, 1)


def flatten_trip_rows(payload: dict) -> list[dict]:
    return [
        trip
        for day in payload.get("data", [])
        for trip in day.get("drivingRecord", [])
        if isinstance(trip, dict)
    ]


def trip_distance_km(trip: dict) -> float:
    return max(0.0, (float(trip.get("travelMile") or 0.0)) / 1000.0)


def trip_duration_h(trip: dict) -> float:
    try:
        start_dt = datetime.strptime(trip["beginTime"], "%Y-%m-%d %H:%M:%S")
        end_dt = datetime.strptime(trip["endTime"], "%Y-%m-%d %H:%M:%S")
        return max(0.0, (end_dt - start_dt).total_seconds() / 3600.0)
    except (KeyError, TypeError, ValueError):
        return 0.0


def trip_start_hour(trip: dict) -> int | None:
    try:
        start_dt = datetime.strptime(trip["beginTime"], "%Y-%m-%d %H:%M:%S")
        return start_dt.hour
    except (KeyError, TypeError, ValueError):
        return None


def trip_consumption_kwh_100km(trip: dict) -> float | None:
    km = trip_distance_km(trip)
    kwh = (float(trip.get("energyConsumed") or 0.0)) / 1000.0
    if km <= 0:
        return None
    return (kwh / km) * 100.0


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius_km = 6371.0
    p1 = math.radians(lat1)
    p2 = math.radians(lat2)
    d_lat = math.radians(lat2 - lat1)
    d_lon = math.radians(lon2 - lon1)
    a = (
        math.sin(d_lat / 2) ** 2
        + math.cos(p1) * math.cos(p2) * math.sin(d_lon / 2) ** 2
    )
    return radius_km * (2 * math.atan2(math.sqrt(a), math.sqrt(1 - a)))


def trip_similarity_breakdown(reference: dict, candidate: dict) -> dict:
    """Score how similar two trips are (route 40%, time-of-day 35%, distance 25%)."""
    ref_distance = trip_distance_km(reference)
    cand_distance = trip_distance_km(candidate)

    # Distance score: 1 when equal, 0 when difference >= 100% of reference.
    if ref_distance <= 0:
        distance_score = 0.0
    else:
        distance_score = 1.0 - min(
            1.0, abs(cand_distance - ref_distance) / ref_distance
        )

    # Time score on circular 24h clock.
    ref_hour = trip_start_hour(reference)
    cand_hour = trip_start_hour(candidate)
    if ref_hour is None or cand_hour is None:
        time_score = 0.0
    else:
        hour_diff = abs(ref_hour - cand_hour)
        hour_diff = min(hour_diff, 24 - hour_diff)
        time_score = 1.0 - min(1.0, hour_diff / 12.0)

    # Route score based on start/end distance; fallback if GPS anchors are missing.
    route_score = 0.5
    try:
        ref_start = (float(reference["startLat"]), float(reference["startLng"]))
        ref_end = (float(reference["endLat"]), float(reference["endLng"]))
        cand_start = (float(candidate["startLat"]), float(candidate["startLng"]))
        cand_end = (float(candidate["endLat"]), float(candidate["endLng"]))
        start_d = haversine_km(
            ref_start[0],
            ref_start[1],
            cand_start[0],
            cand_start[1],
        )
        end_d = haversine_km(ref_end[0], ref_end[1], cand_end[0], cand_end[1])
        avg_d = (start_d + end_d) / 2.0
        route_score = 1.0 - min(1.0, avg_d / 30.0)
    except (KeyError, TypeError, ValueError):
        route_score = 0.5

    score = 0.40 * route_score + 0.35 * time_score + 0.25 * distance_score

    return {
        "score": round(score, 4),
        "breakdown": {
            "route": round(route_score, 4),
            "time": round(time_score, 4),
            "distance": round(distance_score, 4),
        },
    }


def trip_compare_metrics(reference: dict, candidate: dict) -> dict:
    ref_distance = trip_distance_km(reference)
    cand_distance = trip_distance_km(candidate)
    ref_duration = trip_duration_h(reference)
    cand_duration = trip_duration_h(candidate)

    ref_cons = trip_consumption_kwh_100km(reference)
    cand_cons = trip_consumption_kwh_100km(candidate)
    ref_regen = (float(reference.get("energyRecovered") or 0.0)) / 1000.0
    cand_regen = (float(candidate.get("energyRecovered") or 0.0)) / 1000.0

    ref_avg_speed = float(reference.get("avgSpeed") or 0.0)
    cand_avg_speed = float(candidate.get("avgSpeed") or 0.0)
    ref_temp = reference.get("outdoorTemp")
    cand_temp = candidate.get("outdoorTemp")

    return {
        "efficiency": {
            "consumption_kwh_100km": {
                "reference": round(ref_cons, 2) if ref_cons is not None else None,
                "candidate": round(cand_cons, 2) if cand_cons is not None else None,
                "delta": round((cand_cons - ref_cons), 2)
                if ref_cons is not None and cand_cons is not None
                else None,
            },
            "regen_kwh": {
                "reference": round(ref_regen, 3),
                "candidate": round(cand_regen, 3),
                "delta": round(cand_regen - ref_regen, 3),
            },
        },
        "performance": {
            "distance_km": {
                "reference": round(ref_distance, 2),
                "candidate": round(cand_distance, 2),
                "delta": round(cand_distance - ref_distance, 2),
            },
            "duration_h": {
                "reference": round(ref_duration, 2),
                "candidate": round(cand_duration, 2),
                "delta": round(cand_duration - ref_duration, 2),
            },
            "avg_speed_kmh": {
                "reference": round(ref_avg_speed, 1),
                "candidate": round(cand_avg_speed, 1),
                "delta": round(cand_avg_speed - ref_avg_speed, 1),
            },
        },
        "conditions": {
            "outside_temp_c": {
                "reference": ref_temp,
                "candidate": cand_temp,
                "delta": (cand_temp - ref_temp)
                if ref_temp is not None and cand_temp is not None
                else None,
            },
        },
    }


def detect_local_charge_sessions(snapshots: list[VehicleSnapshot]) -> list[dict]:
    """Detect charge sessions (start/end/energy) from snapshot history."""

    def _session(start_snap, end_snap, *, open_ended: bool) -> dict:
        start_energy = (
            start_snap.battery_dump_energy / 1000
            if start_snap.battery_dump_energy is not None
            else None
        )
        end_energy = (
            end_snap.battery_dump_energy / 1000
            if end_snap.battery_dump_energy is not None
            else None
        )
        energy = (
            abs(end_energy - start_energy)
            if start_energy is not None and end_energy is not None
            else None
        )
        return {
            "start_ts": start_snap.timestamp,
            "end_ts": None if open_ended else end_snap.timestamp,
            "energy_kwh": round(energy, 3) if energy is not None else None,
        }

    sessions: list[dict] = []
    in_session = False
    start_idx = -1

    for i, snap in enumerate(snapshots):
        is_charging = bool(snap.battery_is_charging)
        if is_charging and not in_session:
            in_session = True
            start_idx = i
        elif not is_charging and in_session:
            in_session = False
            end_snap = snapshots[i - 1] if i > 0 else snap
            sessions.append(_session(snapshots[start_idx], end_snap, open_ended=False))

    if in_session and start_idx >= 0:
        sessions.append(_session(snapshots[start_idx], snapshots[-1], open_ended=True))

    return sessions


__all__ = [
    "MERGE_GAP_S",
    "MIN_TRIP_KM",
    "build_local_trip_payload",
    "build_trip_row",
    "calculate_local_regen_energy_kwh",
    "detect_local_charge_sessions",
    "flatten_trip_rows",
    "haversine_km",
    "is_snapshot_moving",
    "merge_segments",
    "segment_regen_energy_wh",
    "trip_compare_metrics",
    "trip_consumption_kwh_100km",
    "trip_distance_km",
    "trip_duration_h",
    "trip_similarity_breakdown",
    "trip_start_hour",
]
