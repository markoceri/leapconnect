"""Custom-event detection policies (run on every poll cycle).

Each policy owns its per-VIN state and detects one kind of notification-worthy
condition from the latest ``VehicleStatus``. The dispatcher composes them via
``CustomEventPipeline`` and hands them a ``ChannelView`` to resolve per-channel
event configuration.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING

from leapconnect.domain.zones import haversine_distance_m

if TYPE_CHECKING:
    from collections.abc import Callable

    from leapmotor_api.models import VehicleStatus

_LOGGER = logging.getLogger(__name__)

# An emitted event: (event_type, extra template context)
DetectedEvent = tuple[str, dict]


@dataclass
class ChannelView:
    """What a policy may ask about the configured channels."""

    channel_ids: list[int]
    get_config: Callable[[int, str], dict | None]
    is_enabled: Callable[[int, str], bool]


@dataclass
class StatusReading:
    """Normalized view of the fields the policies need from VehicleStatus."""

    lat: float | None = None
    lon: float | None = None
    soc: int | None = None
    range_km: int | None = None
    is_parked: bool | None = None
    is_locked: bool | None = None
    is_charging: bool | None = None
    is_regening: bool | None = None
    is_plugged: bool | None = None
    ignition_on: bool | None = None
    gun_inserted: bool | None = None  # None = sensor data unavailable
    tires: object | None = None

    @classmethod
    def from_status(cls, status: VehicleStatus) -> StatusReading:
        lat = getattr(status, "latitude", None) or (
            status.vehicle.latitude
            if hasattr(status, "vehicle") and status.vehicle
            else None
        )
        lon = getattr(status, "longitude", None) or (
            status.vehicle.longitude
            if hasattr(status, "vehicle") and status.vehicle
            else None
        )
        # Fallback: check location sub-object
        if not lat and hasattr(status, "location") and status.location:
            lat = status.location.latitude
            lon = status.location.longitude

        battery = getattr(status, "battery", None)
        gun_inserted: bool | None = None
        if battery:
            fast_gun = getattr(battery, "is_charge_fast_gun_insert", None)
            slow_gun = getattr(battery, "is_charge_slow_gun_insert", None)
            if fast_gun is not None or slow_gun is not None:
                gun_inserted = (fast_gun is True) or (slow_gun is True)

        return cls(
            lat=lat,
            lon=lon,
            soc=battery.soc if battery else None,
            range_km=battery.expected_mileage if battery else None,
            is_parked=getattr(status, "is_parked", None),
            is_locked=getattr(status, "is_locked", None),
            is_charging=getattr(status, "is_charging", None),
            is_regening=getattr(status, "is_regening", None),
            is_plugged=getattr(status, "is_plugged", None),
            ignition_on=(
                status.ignition.bcm_key_position_on3
                if hasattr(status, "ignition") and status.ignition
                else None
            ),
            gun_inserted=gun_inserted,
            tires=getattr(status, "tires", None),
        )


def charge_transition_suppression(
    reading: StatusReading, event_type: str
) -> str | None:
    """Why a charge_start/charge_stop transition should be suppressed, if at all.

    Do NOT rely solely on ``VehicleStatus.is_plugged`` because its fallback
    path (when ac_input_slow_charge is None) incorrectly returns True for
    regenerative braking while the vehicle is momentarily stopped (speed=0).
    Instead check the actual gun-insert sensors and the explicit is_regening
    flag to distinguish real plug-in charging from regenerative braking.
    """
    if event_type not in ("charge_start", "charge_stop"):
        return None
    if reading.is_regening:
        return "is_regening=True (regen braking)"
    if reading.gun_inserted is not None and not reading.gun_inserted:
        return "no gun inserted (regen or driving)"
    # When gun sensor data is unavailable, fall back to the is_plugged
    # property as a best-effort heuristic
    if reading.gun_inserted is None and not reading.is_plugged:
        return "is_plugged=False (gun data unavailable)"
    return None


class SocGlitchFilter:
    """Ignore one-off/brief 0% SOC readings; accept only persistent zeros."""

    def __init__(
        self, persist_seconds: float = 120.0, persist_samples: int = 6
    ) -> None:
        self._persist_seconds = persist_seconds
        self._persist_samples = persist_samples
        # vin -> tracking state for temporary SOC=0 glitches
        self._observations: dict[str, dict[str, float | int]] = {}

    def filter(self, vin: str, soc: int | None) -> int | None:
        """Return the SOC usable for alerts (None while a zero looks glitchy)."""
        if soc != 0:
            self._observations.pop(vin, None)
            return soc

        obs = self._observations.get(vin)
        now_mono = time.monotonic()
        if obs is None:
            obs = {"first_seen": now_mono, "count": 1}
            self._observations[vin] = obs
        else:
            obs["count"] = int(obs.get("count", 0)) + 1

        elapsed = now_mono - float(obs["first_seen"])
        count = int(obs["count"])
        is_persistent_zero = (
            elapsed >= self._persist_seconds or count >= self._persist_samples
        )
        return soc if is_persistent_zero else None


class MovementAlertPolicy:
    """Anti-theft: parked vehicle moved beyond a distance threshold."""

    def __init__(self) -> None:
        # vin -> (lat, lon) last known parked position
        self._parked_positions: dict[str, tuple[float, float]] = {}

    def detect(self, vin: str, r: StatusReading) -> list[DetectedEvent]:
        results: list[DetectedEvent] = []
        if r.is_parked and not r.ignition_on and r.lat and r.lon:
            parked_pos = self._parked_positions.get(vin)
            if parked_pos:
                distance = haversine_distance_m(
                    parked_pos[0], parked_pos[1], r.lat, r.lon
                )
                if distance > 50:  # default 50m threshold
                    results.append(
                        (
                            "movement_alert",
                            {"distance": f"{distance:.0f}", "lat": r.lat, "lon": r.lon},
                        )
                    )
                    # Update position to avoid repeated alerts
                    self._parked_positions[vin] = (r.lat, r.lon)
            else:
                self._parked_positions[vin] = (r.lat, r.lon)
        elif not r.is_parked:
            # Vehicle is moving — clear parked position
            self._parked_positions.pop(vin, None)
        return results


class UnlockedTimeoutPolicy:
    """Vehicle left parked and unlocked for too long."""

    def __init__(self) -> None:
        # vin -> timestamp when unlocked was detected (while parked)
        self._unlock_times: dict[str, float] = {}

    def detect(self, vin: str, r: StatusReading) -> list[DetectedEvent]:
        results: list[DetectedEvent] = []
        if r.is_parked and not r.is_locked:
            if vin not in self._unlock_times:
                self._unlock_times[vin] = time.monotonic()
            else:
                elapsed_min = (time.monotonic() - self._unlock_times[vin]) / 60
                if elapsed_min >= 30:  # default 30 min
                    results.append(
                        ("unlocked_timeout", {"minutes": f"{elapsed_min:.0f}"})
                    )
                    # Reset to avoid repeated alerts every cycle
                    self._unlock_times[vin] = time.monotonic()
        else:
            self._unlock_times.pop(vin, None)
        return results


class SocThresholdPolicy:
    """SOC crossed a configured high/low threshold."""

    def __init__(self) -> None:
        # vin -> last SOC value (for threshold crossings)
        self._last_soc: dict[str, int] = {}

    def detect(
        self, vin: str, soc: int | None, channels: ChannelView
    ) -> list[DetectedEvent]:
        results: list[DetectedEvent] = []
        if soc is None:
            return results
        prev_soc = self._last_soc.get(vin)
        if prev_soc is not None:
            # High threshold (crossing upward)
            for channel_id in channels.channel_ids:
                cfg = channels.get_config(channel_id, "soc_threshold_high")
                threshold = (cfg or {}).get("threshold", 80)
                if prev_soc < threshold <= soc:
                    results.append(
                        ("soc_threshold_high", {"threshold": str(threshold)})
                    )
                    break
            # Low threshold (crossing downward)
            for channel_id in channels.channel_ids:
                cfg = channels.get_config(channel_id, "soc_threshold_low")
                threshold = (cfg or {}).get("threshold", 20)
                if prev_soc >= threshold > soc:
                    results.append(("soc_threshold_low", {"threshold": str(threshold)}))
                    break
        self._last_soc[vin] = soc
        return results


class ChargeInterruptedPolicy:
    """A real charging session ended below the configured SOC target.

    Only fires on an actual charging → not-charging transition, with the same
    gun-sensor + regen guards as charge_start/charge_stop.
    """

    def __init__(self) -> None:
        # vin -> previous charging state (for transition detection)
        self._was_charging: dict[str, bool] = {}

    def detect(
        self, vin: str, r: StatusReading, soc: int | None, channels: ChannelView
    ) -> list[DetectedEvent]:
        results: list[DetectedEvent] = []
        prev_charging = self._was_charging.get(vin, False)
        charge_stopped = (
            r.is_charging is False and prev_charging is True and soc is not None
        )
        if charge_stopped:
            if r.is_regening:
                _LOGGER.debug("Suppressing charge_interrupted — is_regening=True")
            elif r.gun_inserted is False:
                _LOGGER.debug("Suppressing charge_interrupted — no gun inserted")
            elif r.gun_inserted is None and not r.is_plugged:
                # Gun data unavailable — fall back to is_plugged
                _LOGGER.debug("Suppressing charge_interrupted — is_plugged=False")
            else:
                # Gun inserted, or gun data unavailable but is_plugged=True
                for channel_id in channels.channel_ids:
                    cfg = channels.get_config(channel_id, "charge_interrupted")
                    soc_target = (cfg or {}).get("soc_target", 80)
                    enabled = channels.is_enabled(channel_id, "charge_interrupted")
                    if soc < soc_target and enabled:
                        results.append(
                            ("charge_interrupted", {"soc_target": str(soc_target)})
                        )
                        break
        # Track current charging state for next cycle
        self._was_charging[vin] = bool(r.is_charging)
        return results


class RangeLowPolicy:
    """Remaining range below the configured threshold (stateless)."""

    def detect(self, r: StatusReading, channels: ChannelView) -> list[DetectedEvent]:
        results: list[DetectedEvent] = []
        if r.range_km is not None:
            for channel_id in channels.channel_ids:
                cfg = channels.get_config(channel_id, "range_low")
                threshold_km = (cfg or {}).get("threshold_km", 50)
                if r.range_km < threshold_km:
                    results.append(("range_low", {"threshold_km": str(threshold_km)}))
                    break
        return results


class TirePressurePolicy:
    """Any tire outside the configured pressure window (stateless)."""

    def detect(self, r: StatusReading, channels: ChannelView) -> list[DetectedEvent]:
        results: list[DetectedEvent] = []
        if not r.tires:
            return results
        pressures = {
            "FL": getattr(r.tires, "front_left_pressure", None),
            "FR": getattr(r.tires, "front_right_pressure", None),
            "RL": getattr(r.tires, "rear_left_pressure", None),
            "RR": getattr(r.tires, "rear_right_pressure", None),
        }
        for channel_id in channels.channel_ids:
            cfg = channels.get_config(channel_id, "tire_pressure_alert")
            min_bar = (cfg or {}).get("min_bar", 2.2)
            max_bar = (cfg or {}).get("max_bar", 3.0)
            alerts = []
            for pos, val in pressures.items():
                if val is not None and (val < min_bar or val > max_bar):
                    alerts.append(f"{pos}: {val:.1f} bar")
            if alerts:
                results.append(("tire_pressure_alert", {"details": ", ".join(alerts)}))
                break
        return results


class CustomEventPipeline:
    """Runs every policy in order and aggregates the detected events."""

    def __init__(self) -> None:
        self._soc_filter = SocGlitchFilter()
        self._movement = MovementAlertPolicy()
        self._unlocked = UnlockedTimeoutPolicy()
        self._soc_thresholds = SocThresholdPolicy()
        self._charge_interrupted = ChargeInterruptedPolicy()
        self._range_low = RangeLowPolicy()
        self._tire_pressure = TirePressurePolicy()

    def detect(
        self, vin: str, status: VehicleStatus, channels: ChannelView
    ) -> list[DetectedEvent]:
        """Detect events that require stateful logic beyond simple transitions."""
        r = StatusReading.from_status(status)
        soc_for_alerts = self._soc_filter.filter(vin, r.soc)

        results: list[DetectedEvent] = []
        results += self._movement.detect(vin, r)
        results += self._unlocked.detect(vin, r)
        results += self._soc_thresholds.detect(vin, soc_for_alerts, channels)
        results += self._charge_interrupted.detect(vin, r, soc_for_alerts, channels)
        results += self._range_low.detect(r, channels)
        results += self._tire_pressure.detect(r, channels)
        return results


__all__ = [
    "ChannelView",
    "CustomEventPipeline",
    "DetectedEvent",
    "StatusReading",
    "charge_transition_suppression",
]
