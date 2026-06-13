"""Unit and endpoint tests for the failed-login throttle."""

from leapconnect.domain.identity.throttle import LoginThrottle


class FakeClock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


class TestLoginThrottle:
    def test_not_blocked_below_max_attempts(self):
        t = LoginThrottle(max_attempts=3)
        for _ in range(2):
            t.record_failure("ip")
        assert t.retry_after("ip") is None

    def test_blocked_at_max_attempts(self):
        clock = FakeClock()
        t = LoginThrottle(max_attempts=3, base_lockout_seconds=30, clock=clock)
        for _ in range(3):
            t.record_failure("ip")
        assert t.retry_after("ip") == 30.0

    def test_lockout_doubles_and_caps(self):
        clock = FakeClock()
        t = LoginThrottle(
            max_attempts=1,
            base_lockout_seconds=30,
            max_lockout_seconds=100,
            clock=clock,
        )
        t.record_failure("ip")
        assert t.retry_after("ip") == 30.0
        t.record_failure("ip")
        assert t.retry_after("ip") == 60.0
        t.record_failure("ip")
        assert t.retry_after("ip") == 100.0  # capped

    def test_lockout_expires(self):
        clock = FakeClock()
        t = LoginThrottle(max_attempts=1, base_lockout_seconds=30, clock=clock)
        t.record_failure("ip")
        clock.now += 31
        assert t.retry_after("ip") is None

    def test_success_clears_failures(self):
        t = LoginThrottle(max_attempts=2)
        t.record_failure("ip")
        t.record_success("ip")
        t.record_failure("ip")
        assert t.retry_after("ip") is None

    def test_keys_are_independent(self):
        t = LoginThrottle(max_attempts=1)
        t.record_failure("a")
        assert t.retry_after("a") is not None
        assert t.retry_after("b") is None


def test_login_throttled_after_repeated_failures(auth_client):
    """The 6th wrong password gets a 429 with Retry-After, not another 401."""
    for _ in range(5):
        resp = auth_client.post("/api/auth/session", json={"password": "wrong"})
        assert resp.status_code == 401

    resp = auth_client.post("/api/auth/session", json={"password": "wrong"})
    assert resp.status_code == 429
    assert "Retry-After" in resp.headers

    # Even the correct password is rejected while locked out
    resp = auth_client.post("/api/auth/session", json={"password": "testpass"})
    assert resp.status_code == 429
