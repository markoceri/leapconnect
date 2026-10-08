"""Transition detector: unknown readings must not fake state changes."""

from types import SimpleNamespace

from leapconnect.domain.telemetry.transitions import TransitionDetector


def _status(is_charging, charge_state=None):
    return SimpleNamespace(
        is_charging=is_charging,
        battery=SimpleNamespace(soc=None, charge_state=charge_state),
    )


def _events(detector, status):
    return [e.event_type for e in detector.detect("V1", status)]


def test_unknown_reading_mid_charge_does_not_restart_session():
    detector = TransitionDetector(min_event_interval_seconds=1)
    detector._can_emit = lambda times, field: True  # no dedup in the test
    _events(detector, _status(False))
    assert _events(detector, _status(True)) == ["charge_start"]
    assert _events(detector, _status(None)) == []
    assert _events(detector, _status(True)) == []
    assert _events(detector, _status(False)) == ["charge_stop"]


def test_change_across_unknown_reading_is_still_reported():
    detector = TransitionDetector(min_event_interval_seconds=1)
    detector._can_emit = lambda times, field: True
    _events(detector, _status(True))
    assert _events(detector, _status(None)) == []
    assert _events(detector, _status(False)) == ["charge_stop"]


def test_threshold_field_keeps_last_known_value():
    detector = TransitionDetector(min_event_interval_seconds=1)
    detector._can_emit = lambda times, field: True
    _events(detector, _status(True, charge_state=1))
    assert _events(detector, _status(True, charge_state=None)) == []
    assert _events(detector, _status(True, charge_state=2)) == ["charge_state_change"]
