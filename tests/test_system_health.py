"""Low disk space alerts: thresholds, reminder policy, probe, monitor, API."""

from datetime import UTC, datetime, timedelta

from leapconnect.application.system_health import DISK_EVENT, DiskSpaceMonitor
from leapconnect.domain.system import (
    DiskAlertSettings,
    DiskUsage,
    is_low_disk,
    low_disk_alert_due,
)
from leapconnect.domain.system.disk import GB
from leapconnect.infrastructure.system import read_disk_usage

T0 = datetime(2026, 10, 7, 12, tzinfo=UTC)


def _usage(free_gb, total_gb=100.0, path="/data"):
    return DiskUsage(
        path=path, total_bytes=int(total_gb * GB), free_bytes=int(free_gb * GB)
    )


def _limits(gb=1.0, pct=10.0):
    return DiskAlertSettings(min_free_gb=gb, min_free_percent=pct)


# -- domain -----------------------------------------------------------------


def test_low_when_under_either_threshold():
    assert is_low_disk(_usage(0.5), _limits(1, 0))
    assert is_low_disk(_usage(5), _limits(1, 10))  # 5% < 10%
    assert not is_low_disk(_usage(20), _limits(1, 10))


def test_zero_disables_threshold():
    assert not is_low_disk(_usage(0.5), _limits(0, 0))
    assert not is_low_disk(_usage(5), _limits(1, 0))
    assert not _limits(0, 0).enabled


def test_describe_thresholds():
    assert _limits(1, 10).describe() == "below 1 GB or 10%"
    assert _limits(2.5, 0).describe() == "below 2.5 GB"
    assert _limits(0, 0).describe() == "off"


def test_alert_first_time_then_daily_reminder():
    assert low_disk_alert_due(True, None, T0)
    assert not low_disk_alert_due(True, T0, T0 + timedelta(hours=23))
    assert low_disk_alert_due(True, T0, T0 + timedelta(hours=24))
    assert not low_disk_alert_due(False, None, T0)


# -- infrastructure ---------------------------------------------------------


def test_read_disk_usage_dedupes_filesystems(tmp_path):
    db = tmp_path / "leapconnect.db"
    db.write_text("")
    usages = read_disk_usage([db, tmp_path / "data" / "not-created-yet"])
    assert len(usages) == 1
    assert usages[0].path == str(tmp_path.resolve())
    assert 0 < usages[0].free_bytes <= usages[0].total_bytes


# -- monitor ----------------------------------------------------------------


class _Dispatcher:
    def __init__(self):
        self.sent = []

    async def dispatch_system(self, event_type, sender_name, context):
        assert event_type == DISK_EVENT
        self.sent.append(context)
        return 1


def _monitor(usages, limits=None):
    state = {"usages": usages, "limits": limits or _limits()}

    async def load_limits():
        return state["limits"]

    dispatcher = _Dispatcher()
    monitor = DiskSpaceMonitor(dispatcher, lambda: list(state["usages"]), load_limits)
    return monitor, dispatcher, state


async def test_monitor_raises_event_reminds_and_rearms():
    monitor, dispatcher, state = _monitor([_usage(5)])

    assert await monitor.check(T0)
    assert dispatcher.sent[0] == {
        "free_gb": "5.0",
        "free_percent": "5.0",
        "total_gb": "100.0",
        "disk_path": "/data",
        "disk_limits": "below 1 GB or 10%",
    }

    assert not await monitor.check(T0 + timedelta(hours=1))  # within 24 h
    assert await monitor.check(T0 + timedelta(hours=24))  # daily reminder

    state["usages"] = [_usage(50)]  # recovered → re-armed
    assert not await monitor.check(T0 + timedelta(hours=25))
    state["usages"] = [_usage(5)]
    assert await monitor.check(T0 + timedelta(hours=26))
    assert len(dispatcher.sent) == 3


async def test_monitor_reports_tightest_low_filesystem():
    monitor, dispatcher, _ = _monitor(
        [_usage(50, path="/"), _usage(2, path="/data"), _usage(8, path="/srv")]
    )
    await monitor.check(T0)
    assert dispatcher.sent[0]["disk_path"] == "/data"


async def test_monitor_disabled_thresholds_skip_disk_read():
    def boom():
        raise AssertionError("disk must not be read")

    async def off():
        return _limits(0, 0)

    monitor = DiskSpaceMonitor(_Dispatcher(), boom, off)
    assert not await monitor.check(T0)


# -- dispatcher -------------------------------------------------------------


def _dispatcher_with_channels(enabled_for):
    from leapconnect.application.notifications import NotificationDispatcher
    from leapconnect.domain.notifications.models import NotificationPreference

    class _Notifier:
        def __init__(self):
            self.sent = []

        async def send(self, notification):
            self.sent.append(notification)
            return True

    dispatcher = NotificationDispatcher(repo=None)
    dispatcher._notifiers = {1: _Notifier(), 2: _Notifier()}
    dispatcher._preferences = {
        cid: {
            DISK_EVENT: NotificationPreference(
                channel_id=cid, event_type=DISK_EVENT, enabled=True
            )
        }
        for cid in enabled_for
    }
    return dispatcher


async def test_dispatch_system_targets_enabled_channels_and_respects_mute():
    import asyncio

    dispatcher = _dispatcher_with_channels(enabled_for=[1])
    ctx = {
        "free_gb": "0.8",
        "free_percent": "4.2",
        "total_gb": "29.1",
        "disk_path": "/data",
        "disk_limits": "below 1 GB or 10%",
    }
    assert await dispatcher.dispatch_system(DISK_EVENT, "LeapConnect", ctx) == 1
    await asyncio.sleep(0)  # let the spawned send run
    [notification] = dispatcher._notifiers[1].sent
    assert notification.title == "💾 Low disk space — LeapConnect"
    assert "0.8 GB free (4.2%) of 29.1 GB on /data" in notification.body
    assert not dispatcher._notifiers[2].sent

    dispatcher.mute()
    assert await dispatcher.dispatch_system(DISK_EVENT, "LeapConnect", ctx) == 0


async def test_template_values_are_html_escaped():
    """Values are data: '<' or '&' must not break Telegram's HTML parsing."""
    dispatcher = _dispatcher_with_channels(enabled_for=[])
    notification = await dispatcher._build_notification(
        "zone_dwell", "V1", "Car <B&B>", {"zone_name": "A<B & C", "minutes": 5}
    )
    assert notification.title.endswith("— Car &lt;B&amp;B&gt;")
    assert "A&lt;B &amp; C" in notification.body


# -- API --------------------------------------------------------------------


def test_disk_space_api_roundtrip(auth_client):
    data = auth_client.get("/api/system/disk-space").json()
    assert (data["min_free_gb"], data["min_free_percent"]) == (1.0, 10.0)
    assert data["filesystems"] and data["filesystems"][0]["total_gb"] > 0

    resp = auth_client.put(
        "/api/system/disk-space", json={"min_free_gb": 2.5, "min_free_percent": 0}
    )
    assert resp.status_code == 200
    assert (resp.json()["min_free_gb"], resp.json()["min_free_percent"]) == (2.5, 0)
    again = auth_client.get("/api/system/disk-space").json()
    assert again["min_free_gb"] == 2.5

    bad = auth_client.put(
        "/api/system/disk-space", json={"min_free_gb": -1, "min_free_percent": 10}
    )
    assert bad.status_code == 422
