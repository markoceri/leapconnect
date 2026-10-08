"""Telemetry persistence: snapshots, events, history queries (SQLAlchemy/SQLite)."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta, tzinfo
from typing import Any

from sqlalchemy import case, func, select

from leapconnect.application.ports.repositories import (
    TelemetryRepository,
)
from leapconnect.domain.telemetry.battery_health import FullChargeSample
from leapconnect.domain.telemetry.models import VehicleEvent, VehicleSnapshot
from leapconnect.infrastructure.persistence.base import SqlRepositoryBase
from leapconnect.infrastructure.persistence.tables import (
    VehicleEventRow,
    VehicleSnapshotRow,
)


class SqlTelemetryRepository(SqlRepositoryBase, TelemetryRepository):
    """Telemetry persistence: snapshots, events, history queries."""

    async def save_snapshot(self, snapshot: VehicleSnapshot) -> None:
        row = VehicleSnapshotRow(
            vin=snapshot.vin,
            timestamp=snapshot.timestamp,
            battery_soc=snapshot.battery_soc,
            battery_current=snapshot.battery_current,
            battery_voltage=snapshot.battery_voltage,
            charging_power_kw=snapshot.battery_charging_power_kw,
            discharge_power_kw=snapshot.battery_discharge_power_kw,
            expected_mileage=snapshot.battery_expected_mileage,
            total_mileage=snapshot.drive_total_mileage,
            energy_kwh=snapshot.battery_dump_energy,
            outdoor_temp=snapshot.climate_outdoor_temp,
            is_charging=snapshot.battery_is_charging,
            is_plugged=snapshot.vehicle_is_plugged,
            latitude=snapshot.vehicle_latitude,
            longitude=snapshot.vehicle_longitude,
            charge_state=snapshot.battery_charge_state,
            speed=snapshot.drive_speed,
            is_parked=snapshot.drive_is_parked,
            is_locked=snapshot.vehicle_is_locked,
            tire_fl_pressure=snapshot.tire_front_left_pressure,
            tire_fr_pressure=snapshot.tire_front_right_pressure,
            tire_rl_pressure=snapshot.tire_rear_left_pressure,
            tire_rr_pressure=snapshot.tire_rear_right_pressure,
            is_regening=snapshot.vehicle_is_regening,
        )
        async with self._session_factory() as session:
            session.add(row)
            await session.commit()

    async def save_event(self, event: VehicleEvent) -> None:
        """Persist a single state-transition event."""
        row = VehicleEventRow(
            vin=event.vin,
            timestamp=event.timestamp,
            event_type=event.event_type,
            field_name=event.field_name,
            old_value=event.old_value,
            new_value=event.new_value,
        )
        async with self._session_factory() as session:
            session.add(row)
            await session.commit()

    async def get_events(
        self,
        vin: str,
        *,
        days: int = 30,
        event_type: str | None = None,
    ) -> list[VehicleEvent]:
        """Return events for *vin* over the last *days* days."""
        since = datetime.now(UTC) - timedelta(days=days)
        conditions = [
            VehicleEventRow.vin == vin,
            VehicleEventRow.timestamp >= since,
        ]
        if event_type:
            conditions.append(VehicleEventRow.event_type == event_type)
        stmt = (
            select(VehicleEventRow)
            .where(*conditions)
            .order_by(VehicleEventRow.timestamp.asc())
        )
        async with self._session_factory() as session:
            result = await session.execute(stmt)
            rows = result.scalars().all()

        return [
            VehicleEvent(
                vin=r.vin,
                timestamp=r.timestamp,
                event_type=r.event_type,
                field_name=r.field_name,
                old_value=r.old_value,
                new_value=r.new_value,
            )
            for r in rows
        ]

    # -- read ----------------------------------------------------------------

    async def get_history(
        self,
        vin: str,
        *,
        days: int = 30,
        from_date: str | None = None,
        to_date: str | None = None,
        max_points: int | None = None,
        tz: tzinfo = UTC,
    ) -> list[VehicleSnapshot]:
        if from_date and to_date:
            # Explicit range of days (YYYY-MM-DD, inclusive) in ``tz``
            since = datetime.fromisoformat(from_date).replace(tzinfo=tz).astimezone(UTC)
            until = (
                (datetime.fromisoformat(to_date) + timedelta(days=1))
                .replace(tzinfo=tz)
                .astimezone(UTC)
            )
            stmt = (
                select(VehicleSnapshotRow)
                .where(
                    VehicleSnapshotRow.vin == vin,
                    VehicleSnapshotRow.timestamp >= since,
                    VehicleSnapshotRow.timestamp < until,
                )
                .order_by(VehicleSnapshotRow.timestamp.asc())
            )
        elif days == 1:
            # "Today": from midnight of the current day in ``tz``
            now = datetime.now(tz)
            since = now.replace(hour=0, minute=0, second=0, microsecond=0).astimezone(
                UTC
            )
            stmt = (
                select(VehicleSnapshotRow)
                .where(
                    VehicleSnapshotRow.vin == vin, VehicleSnapshotRow.timestamp >= since
                )
                .order_by(VehicleSnapshotRow.timestamp.asc())
            )
        else:
            since = datetime.now(UTC) - timedelta(days=days)
            stmt = (
                select(VehicleSnapshotRow)
                .where(
                    VehicleSnapshotRow.vin == vin, VehicleSnapshotRow.timestamp >= since
                )
                .order_by(VehicleSnapshotRow.timestamp.asc())
            )
        async with self._session_factory() as session:
            result = await session.execute(stmt)
            rows = result.scalars().all()

        # Downsample if max_points is specified and we have more rows
        if max_points and len(rows) > max_points:
            rows = self._downsample_rows(rows, max_points)

        return [
            VehicleSnapshot(
                vin=r.vin,
                timestamp=r.timestamp,
                battery_soc=r.battery_soc,
                battery_current=r.battery_current,
                battery_voltage=r.battery_voltage,
                battery_charging_power_kw=r.charging_power_kw
                if r.charging_power_kw
                else (
                    round(abs(r.battery_current) * r.battery_voltage / 1000, 2)
                    if r.battery_current
                    and r.battery_voltage
                    and (r.is_charging or r.is_regening)
                    else None
                ),
                battery_discharge_power_kw=r.discharge_power_kw
                if r.discharge_power_kw
                else (
                    round(r.battery_current * r.battery_voltage / 1000, 2)
                    if r.battery_current
                    and r.battery_voltage
                    and r.battery_current > 0
                    and not r.is_charging
                    and not r.is_regening
                    else None
                ),
                battery_expected_mileage=r.expected_mileage,
                drive_total_mileage=r.total_mileage,
                battery_dump_energy=r.energy_kwh,
                climate_outdoor_temp=r.outdoor_temp,
                battery_is_charging=r.is_charging,
                vehicle_is_plugged=r.is_plugged,
                vehicle_latitude=r.latitude,
                vehicle_longitude=r.longitude,
                battery_charge_state=r.charge_state,
                drive_speed=r.speed,
                drive_is_parked=r.is_parked,
                vehicle_is_locked=r.is_locked,
                tire_front_left_pressure=r.tire_fl_pressure,
                tire_front_right_pressure=r.tire_fr_pressure,
                tire_rear_left_pressure=r.tire_rl_pressure,
                tire_rear_right_pressure=r.tire_rr_pressure,
                vehicle_is_regening=r.is_regening,
            )
            for r in rows
        ]

    @staticmethod
    def _downsample_rows(rows: list, max_points: int) -> list:
        """Downsample rows to max_points while preserving state transitions.

        Always keeps: first row, last row, and any row where charging/plugged
        state changes compared to the previous row (critical for KPI accuracy).
        Remaining budget is filled with evenly-spaced samples.
        """
        n = len(rows)
        # Mark transition boundary indices (always keep these)
        keep = {0, n - 1}
        for i in range(1, n):
            if rows[i].is_charging != rows[i - 1].is_charging:
                keep.add(i)
                keep.add(i - 1)
            if rows[i].is_plugged != rows[i - 1].is_plugged:
                keep.add(i)
                keep.add(i - 1)

        # Fill remaining budget with evenly-spaced samples
        remaining_budget = max_points - len(keep)
        if remaining_budget > 0:
            step = max(1, n / (remaining_budget + 1))
            pos = step
            while pos < n and len(keep) < max_points:
                keep.add(int(pos))
                pos += step

        return [rows[i] for i in sorted(keep)]

    async def get_full_charge_samples(self, vin: str) -> list[FullChargeSample]:
        """Highest energy reported at SOC 100% per (UTC) day, oldest first."""
        day = func.date(VehicleSnapshotRow.timestamp).label("day")
        stmt = (
            select(day, func.max(VehicleSnapshotRow.energy_kwh).label("wh"))
            .where(
                VehicleSnapshotRow.vin == vin,
                VehicleSnapshotRow.battery_soc == 100,
                VehicleSnapshotRow.energy_kwh > 0,
            )
            .group_by(day)
            .order_by(day.asc())
        )
        async with self._session_factory() as session:
            rows = (await session.execute(stmt)).all()
        # The column holds Wh despite its name (the cloud reports Wh).
        return [
            FullChargeSample(day=date.fromisoformat(r.day), energy_kwh=r.wh / 1000)
            for r in rows
        ]

    async def get_daily_summary(
        self,
        vin: str,
        *,
        days: int = 30,
        tz: tzinfo = UTC,
    ) -> list[dict[str, Any]]:
        """Per-day aggregates, days being calendar days in ``tz``.

        SQLite can't apply an IANA zone, so rows are aggregated per UTC hour in
        SQL and the hours are folded into local days here (exact for whole-hour
        offsets, which covers every DST rule).
        """
        since = datetime.now(UTC) - timedelta(days=days)
        hour_label = func.strftime(
            "%Y-%m-%d %H:00:00", VehicleSnapshotRow.timestamp
        ).label("hour")

        # Partial status payloads report the odometer as 0: ignore them so a
        # glitch doesn't turn the whole odometer into "km driven".
        valid_mileage = case(
            (VehicleSnapshotRow.total_mileage > 0, VehicleSnapshotRow.total_mileage)
        )

        stmt = (
            select(
                hour_label,
                func.min(VehicleSnapshotRow.battery_soc).label("min_soc"),
                func.max(VehicleSnapshotRow.battery_soc).label("max_soc"),
                func.sum(VehicleSnapshotRow.battery_soc).label("sum_soc"),
                func.count(VehicleSnapshotRow.battery_soc).label("n_soc"),
                func.min(VehicleSnapshotRow.expected_mileage).label("min_range"),
                func.max(VehicleSnapshotRow.expected_mileage).label("max_range"),
                func.min(valid_mileage).label("min_mileage"),
                func.max(valid_mileage).label("max_mileage"),
                func.sum(VehicleSnapshotRow.outdoor_temp).label("sum_temp"),
                func.count(VehicleSnapshotRow.outdoor_temp).label("n_temp"),
                func.sum(
                    func.iif(VehicleSnapshotRow.is_charging == True, 1, 0)  # noqa: E712
                ).label("charge_sessions"),
                func.count().label("sample_count"),
            )
            .where(VehicleSnapshotRow.vin == vin, VehicleSnapshotRow.timestamp >= since)
            .group_by(hour_label)
            .order_by(hour_label.asc())
        )

        async with self._session_factory() as session:
            result = await session.execute(stmt)
            rows = result.all()

        def _merge(a, b, fn):
            if a is None:
                return b
            return a if b is None else fn(a, b)

        by_day: dict[str, dict[str, Any]] = {}
        for r in rows:
            local_day = (
                datetime.fromisoformat(r.hour)
                .replace(tzinfo=UTC)
                .astimezone(tz)
                .date()
                .isoformat()
            )
            d = by_day.setdefault(
                local_day,
                dict.fromkeys(
                    (
                        "min_soc",
                        "max_soc",
                        "min_range",
                        "max_range",
                        "min_mileage",
                        "max_mileage",
                    )
                )
                | {"sum_soc": 0, "n_soc": 0, "sum_temp": 0.0, "n_temp": 0}
                | {"charge_sessions": 0, "sample_count": 0},
            )
            for key in ("min_soc", "min_range", "min_mileage"):
                d[key] = _merge(d[key], getattr(r, key), min)
            for key in ("max_soc", "max_range", "max_mileage"):
                d[key] = _merge(d[key], getattr(r, key), max)
            d["sum_soc"] += r.sum_soc or 0
            d["n_soc"] += r.n_soc or 0
            d["sum_temp"] += r.sum_temp or 0
            d["n_temp"] += r.n_temp or 0
            d["charge_sessions"] += r.charge_sessions or 0
            d["sample_count"] += r.sample_count or 0

        summaries: list[dict[str, Any]] = []
        for day, d in sorted(by_day.items()):
            km_driven = 0
            if d["max_mileage"] is not None and d["min_mileage"] is not None:
                km_driven = max(0, d["max_mileage"] - d["min_mileage"])

            # Rough energy estimate: ~0.15 kWh/km
            energy_delta = round(km_driven * 0.15, 1) if km_driven else 0

            summaries.append(
                {
                    "date": day,
                    "min_soc": d["min_soc"],
                    "max_soc": d["max_soc"],
                    "avg_soc": round(d["sum_soc"] / d["n_soc"]) if d["n_soc"] else None,
                    "min_range": d["min_range"],
                    "max_range": d["max_range"],
                    "km_driven": km_driven,
                    "energy_delta": energy_delta,
                    "avg_temp": round(d["sum_temp"] / d["n_temp"])
                    if d["n_temp"]
                    else None,
                    "charge_sessions": d["charge_sessions"],
                    "sample_count": d["sample_count"],
                }
            )

        return summaries
