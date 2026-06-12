"""Unit tests for the custom-event detection policies."""

from types import SimpleNamespace

from leapconnect.application.notifications.policies import (
    ChannelView,
    ChargeInterruptedPolicy,
    GeofenceWatcher,
    MovementAlertPolicy,
    SocGlitchFilter,
    SocThresholdPolicy,
    StatusReading,
    charge_transition_suppression,
)
from leapconnect.domain.notifications.models import Geofence


def _channels(configs: dict[str, dict] | None = None, enabled: bool = True):
    """A single-channel view with per-event configs."""
    cfg = configs or {}
    return ChannelView(
        channel_ids=[1],
        get_config=lambda _cid, event_type: cfg.get(event_type),
        is_enabled=lambda _cid, _event_type: enabled,
    )


def _status(**kw):
    """Minimal VehicleStatus stand-in for StatusReading.from_status."""
    defaults = dict(
        latitude=None,
        longitude=None,
        battery=None,
        is_parked=None,
        is_locked=None,
        is_charging=None,
        is_regening=None,
        is_plugged=None,
        tires=None,
    )
    defaults.update(kw)
    return SimpleNamespace(**defaults)


class TestChargeTransitionSuppression:
    def test_regen_braking_suppressed(self):
        r = StatusReading(is_regening=True)
        assert charge_transition_suppression(r, "charge_start") is not None

    def test_no_gun_inserted_suppressed(self):
        r = StatusReading(gun_inserted=False)
        assert charge_transition_suppression(r, "charge_stop") is not None

    def test_gun_inserted_allowed(self):
        r = StatusReading(gun_inserted=True)
        assert charge_transition_suppression(r, "charge_start") is None

    def test_no_gun_data_falls_back_to_is_plugged(self):
        assert (
            charge_transition_suppression(
                StatusReading(gun_inserted=None, is_plugged=False), "charge_start"
            )
            is not None
        )
        assert (
            charge_transition_suppression(
                StatusReading(gun_inserted=None, is_plugged=True), "charge_start"
            )
            is None
        )

    def test_other_events_never_suppressed(self):
        r = StatusReading(is_regening=True, gun_inserted=False)
        assert charge_transition_suppression(r, "lock") is None


class TestSocGlitchFilter:
    def test_nonzero_passes_through(self):
        f = SocGlitchFilter()
        assert f.filter("V1", 55) == 55

    def test_first_zero_is_filtered(self):
        f = SocGlitchFilter()
        assert f.filter("V1", 0) is None

    def test_persistent_zero_by_sample_count(self):
        f = SocGlitchFilter(persist_seconds=9999, persist_samples=3)
        assert f.filter("V1", 0) is None
        assert f.filter("V1", 0) is None
        assert f.filter("V1", 0) == 0  # third sample crosses the threshold

    def test_recovery_resets_observations(self):
        f = SocGlitchFilter(persist_seconds=9999, persist_samples=2)
        assert f.filter("V1", 0) is None
        assert f.filter("V1", 42) == 42
        assert f.filter("V1", 0) is None  # counts restart after recovery


class TestMovementAlertPolicy:
    def test_first_parked_position_is_stored_silently(self):
        p = MovementAlertPolicy()
        r = StatusReading(is_parked=True, ignition_on=False, lat=45.0, lon=9.0)
        assert p.detect("V1", r) == []

    def test_moving_beyond_50m_fires(self):
        p = MovementAlertPolicy()
        p.detect("V1", StatusReading(is_parked=True, lat=45.0, lon=9.0))
        # ~111m north
        events = p.detect("V1", StatusReading(is_parked=True, lat=45.001, lon=9.0))
        assert events and events[0][0] == "movement_alert"

    def test_small_drift_does_not_fire(self):
        p = MovementAlertPolicy()
        p.detect("V1", StatusReading(is_parked=True, lat=45.0, lon=9.0))
        events = p.detect("V1", StatusReading(is_parked=True, lat=45.0001, lon=9.0))
        assert events == []

    def test_driving_clears_parked_position(self):
        p = MovementAlertPolicy()
        p.detect("V1", StatusReading(is_parked=True, lat=45.0, lon=9.0))
        p.detect("V1", StatusReading(is_parked=False, lat=45.5, lon=9.5))
        # Re-park far away: stored as new baseline, no alert
        events = p.detect("V1", StatusReading(is_parked=True, lat=46.0, lon=10.0))
        assert events == []


class TestSocThresholdPolicy:
    def test_high_threshold_crossing_up(self):
        p = SocThresholdPolicy()
        ch = _channels({"soc_threshold_high": {"threshold": 80}})
        assert p.detect("V1", 75, ch) == []
        events = p.detect("V1", 82, ch)
        assert ("soc_threshold_high", {"threshold": "80"}) in events

    def test_low_threshold_crossing_down(self):
        p = SocThresholdPolicy()
        ch = _channels({"soc_threshold_low": {"threshold": 20}})
        assert p.detect("V1", 25, ch) == []
        events = p.detect("V1", 18, ch)
        assert ("soc_threshold_low", {"threshold": "20"}) in events

    def test_no_event_without_previous_reading(self):
        p = SocThresholdPolicy()
        ch = _channels({"soc_threshold_high": {"threshold": 80}})
        assert p.detect("V1", 95, ch) == []

    def test_none_soc_keeps_previous_state(self):
        p = SocThresholdPolicy()
        ch = _channels({"soc_threshold_high": {"threshold": 80}})
        p.detect("V1", 75, ch)
        assert p.detect("V1", None, ch) == []
        # 75 (not the None) is still the reference value
        events = p.detect("V1", 85, ch)
        assert events and events[0][0] == "soc_threshold_high"


class TestChargeInterruptedPolicy:
    def test_fires_on_real_interruption_below_target(self):
        p = ChargeInterruptedPolicy()
        ch = _channels({"charge_interrupted": {"soc_target": 80}})
        p.detect("V1", StatusReading(is_charging=True, gun_inserted=True), 50, ch)
        events = p.detect(
            "V1", StatusReading(is_charging=False, gun_inserted=True), 55, ch
        )
        assert ("charge_interrupted", {"soc_target": "80"}) in events

    def test_silent_when_target_reached(self):
        p = ChargeInterruptedPolicy()
        ch = _channels({"charge_interrupted": {"soc_target": 80}})
        p.detect("V1", StatusReading(is_charging=True, gun_inserted=True), 70, ch)
        events = p.detect(
            "V1", StatusReading(is_charging=False, gun_inserted=True), 85, ch
        )
        assert events == []

    def test_suppressed_without_gun(self):
        p = ChargeInterruptedPolicy()
        ch = _channels({"charge_interrupted": {"soc_target": 80}})
        p.detect("V1", StatusReading(is_charging=True, gun_inserted=True), 50, ch)
        events = p.detect(
            "V1", StatusReading(is_charging=False, gun_inserted=False), 55, ch
        )
        assert events == []

    def test_requires_charging_transition(self):
        p = ChargeInterruptedPolicy()
        ch = _channels({"charge_interrupted": {"soc_target": 80}})
        # Never seen charging=True before: no event
        events = p.detect(
            "V1", StatusReading(is_charging=False, gun_inserted=True), 55, ch
        )
        assert events == []

    def test_respects_disabled_channel(self):
        p = ChargeInterruptedPolicy()
        ch = _channels({"charge_interrupted": {"soc_target": 80}}, enabled=False)
        p.detect("V1", StatusReading(is_charging=True, gun_inserted=True), 50, ch)
        events = p.detect(
            "V1", StatusReading(is_charging=False, gun_inserted=True), 55, ch
        )
        assert events == []


class TestGeofenceWatcher:
    def _zone(self, **kw):
        defaults = dict(
            id=1,
            name="Home",
            shape_type="circle",
            latitude=45.0,
            longitude=9.0,
            radius_m=200.0,
            notify_on_enter=True,
            notify_on_exit=True,
            enabled=True,
        )
        defaults.update(kw)
        return Geofence(**defaults)

    def _channels_with_zone(self, zone):
        ch = _channels()
        ch.geofences = [zone]
        return ch

    def test_enter_and_exit(self):
        w = GeofenceWatcher()
        ch = self._channels_with_zone(self._zone())
        # Start outside: no events
        assert w.detect("V1", StatusReading(lat=46.0, lon=9.0), ch) == []
        # Enter
        events = w.detect("V1", StatusReading(lat=45.0, lon=9.0), ch)
        assert ("geofence_enter", {"zone_name": "Home"}) in events
        # Stay inside: no repeat
        assert w.detect("V1", StatusReading(lat=45.0, lon=9.0), ch) == []
        # Exit
        events = w.detect("V1", StatusReading(lat=46.0, lon=9.0), ch)
        assert ("geofence_exit", {"zone_name": "Home"}) in events

    def test_disabled_zone_ignored(self):
        w = GeofenceWatcher()
        ch = self._channels_with_zone(self._zone(enabled=False))
        assert w.detect("V1", StatusReading(lat=45.0, lon=9.0), ch) == []

    def test_other_vehicle_zone_ignored(self):
        w = GeofenceWatcher()
        ch = self._channels_with_zone(self._zone(vin="OTHER"))
        assert w.detect("V1", StatusReading(lat=45.0, lon=9.0), ch) == []


class TestStatusReading:
    def test_reads_top_level_coordinates(self):
        r = StatusReading.from_status(_status(latitude=45.0, longitude=9.0))
        assert (r.lat, r.lon) == (45.0, 9.0)

    def test_gun_inserted_from_battery_sensors(self):
        battery = SimpleNamespace(
            soc=50,
            expected_mileage=200,
            is_charge_fast_gun_insert=None,
            is_charge_slow_gun_insert=True,
        )
        r = StatusReading.from_status(_status(battery=battery))
        assert r.gun_inserted is True
        assert r.soc == 50
        assert r.range_km == 200

    def test_gun_data_unavailable(self):
        battery = SimpleNamespace(
            soc=50,
            expected_mileage=200,
            is_charge_fast_gun_insert=None,
            is_charge_slow_gun_insert=None,
        )
        r = StatusReading.from_status(_status(battery=battery))
        assert r.gun_inserted is None
