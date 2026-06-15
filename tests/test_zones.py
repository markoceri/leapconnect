"""Unit tests for the zones domain geometry + application tracker."""

from leapconnect.application.zones import ZoneTracker
from leapconnect.domain.zones import (
    Zone,
    detect_transitions,
    point_in_polygon,
    polygon_centroid,
    zone_contains,
)


def _zone(**kw):
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
    return Zone(**defaults)


class TestGeometry:
    def test_circle_contains(self):
        z = _zone()
        assert zone_contains(z, 45.0, 9.0) is True
        assert zone_contains(z, 46.0, 9.0) is False

    def test_polygon_contains(self):
        z = _zone(
            shape_type="polygon",
            points=[[45.0, 9.0], [45.0, 9.1], [45.1, 9.1], [45.1, 9.0]],
        )
        assert zone_contains(z, 45.05, 9.05) is True
        assert zone_contains(z, 45.05, 9.5) is False

    def test_point_in_polygon_needs_three_points(self):
        assert point_in_polygon(45.0, 9.0, [[45.0, 9.0], [45.1, 9.1]]) is False

    def test_polygon_centroid(self):
        lat, lon = polygon_centroid([[0.0, 0.0], [0.0, 2.0], [2.0, 2.0], [2.0, 0.0]])
        assert (lat, lon) == (1.0, 1.0)


class TestDetectTransitions:
    def test_enter_then_exit(self):
        zones = [_zone()]
        # Outside
        entered, exited, inside = detect_transitions(zones, "V1", 46.0, 9.0, set())
        assert entered == [] and exited == [] and inside == set()
        # Enter
        entered, exited, inside = detect_transitions(zones, "V1", 45.0, 9.0, inside)
        assert [z.name for z in entered] == ["Home"] and inside == {1}
        # Stay
        entered, exited, inside = detect_transitions(zones, "V1", 45.0, 9.0, inside)
        assert entered == [] and exited == []
        # Exit
        entered, exited, inside = detect_transitions(zones, "V1", 46.0, 9.0, inside)
        assert [z.name for z in exited] == ["Home"] and inside == set()

    def test_disabled_zone_ignored(self):
        zones = [_zone(enabled=False)]
        entered, _, inside = detect_transitions(zones, "V1", 45.0, 9.0, set())
        assert entered == [] and inside == set()

    def test_other_vehicle_zone_ignored(self):
        zones = [_zone(vin="OTHER")]
        entered, _, inside = detect_transitions(zones, "V1", 45.0, 9.0, set())
        assert entered == [] and inside == set()


class TestZoneTracker:
    def test_enter_and_exit(self):
        t = ZoneTracker()
        zones = [_zone()]
        assert t.update("V1", 46.0, 9.0, zones) == ([], [])
        entered, exited = t.update("V1", 45.0, 9.0, zones)
        assert [z.name for z in entered] == ["Home"] and exited == []
        assert t.update("V1", 45.0, 9.0, zones) == ([], [])
        entered, exited = t.update("V1", 46.0, 9.0, zones)
        assert entered == [] and [z.name for z in exited] == ["Home"]

    def test_per_vin_isolation(self):
        t = ZoneTracker()
        zones = [_zone()]
        t.update("V1", 45.0, 9.0, zones)  # V1 inside
        entered, exited = t.update("V2", 45.0, 9.0, zones)  # V2 first fix inside
        assert [z.name for z in entered] == ["Home"] and exited == []

    def test_current_zone_ids(self):
        t = ZoneTracker()
        zones = [_zone()]
        t.update("V1", 45.0, 9.0, zones)
        assert t.current_zone_ids("V1") == {1}
        t.update("V1", 46.0, 9.0, zones)
        assert t.current_zone_ids("V1") == set()


class TestDueAlerts:
    def test_dwell_fires_once_after_threshold(self):
        t = ZoneTracker()
        zones = [_zone(dwell_alert_minutes=10)]
        t.update("V1", 45.0, 9.0, zones)  # enter at t≈now
        # Before the threshold: nothing
        assert t.due_alerts("V1", zones, now=0) == []
        # After 10 min: fires once
        fired = t.due_alerts("V1", zones, now=10**9)
        assert [(z.name, kind) for z, kind in fired] == [("Home", "dwell")]
        # Does not fire again while still inside
        assert t.due_alerts("V1", zones, now=10**9) == []

    def test_dwell_resets_on_exit(self):
        t = ZoneTracker()
        zones = [_zone(dwell_alert_minutes=10)]
        t.update("V1", 45.0, 9.0, zones)
        assert t.due_alerts("V1", zones, now=10**9)  # fired
        t.update("V1", 46.0, 9.0, zones)  # exit clears the guard
        t.update("V1", 45.0, 9.0, zones)  # re-enter
        assert [k for _, k in t.due_alerts("V1", zones, now=2 * 10**9)] == ["dwell"]

    def test_absence_fires_once_after_exit(self):
        t = ZoneTracker()
        zones = [_zone(absence_alert_minutes=60)]
        t.update("V1", 45.0, 9.0, zones)  # inside — no absence baseline yet
        assert t.due_alerts("V1", zones, now=10**9) == []
        t.update("V1", 46.0, 9.0, zones)  # exit records the baseline
        assert t.due_alerts("V1", zones, now=0) == []  # not long enough
        fired = t.due_alerts("V1", zones, now=10**9)
        assert [(z.name, kind) for z, kind in fired] == [("Home", "absence")]
        assert t.due_alerts("V1", zones, now=10**9) == []  # once only

    def test_no_alerts_when_thresholds_off(self):
        t = ZoneTracker()
        zones = [_zone()]  # both thresholds default 0
        t.update("V1", 45.0, 9.0, zones)
        assert t.due_alerts("V1", zones, now=10**9) == []
