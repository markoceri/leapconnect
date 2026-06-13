"""Tests for persisted dashboard sessions and cookie-only WebSocket auth."""

import time

import pytest
from starlette.websockets import WebSocketDisconnect

from leapconnect.domain.identity.sessions import SessionStore, hash_token


class TestSessionStore:
    def test_create_validate_invalidate(self):
        store = SessionStore()
        token = store.create()
        assert store.validate(token) is True
        store.invalidate(token)
        assert store.validate(token) is False

    def test_expired_token_rejected(self):
        store = SessionStore(max_age_seconds=-1)
        token = store.create()
        assert store.validate(token) is False

    def test_restore_skips_expired_entries(self):
        store = SessionStore()
        token = store.create()
        fresh = SessionStore()
        fresh.restore(
            {
                hash_token(token): store.expiry_of(token),
                "expired-hash": time.time() - 10,
            }
        )
        assert fresh.validate(token) is True
        assert fresh.expiry_of(token) == store.expiry_of(token)


class TestSessionPersistence:
    @pytest.fixture
    async def repo(self, tmp_path):
        from leapconnect.infrastructure.persistence.sqlite_adapter import (
            SqlAlchemyRepository,
        )

        repo = SqlAlchemyRepository(f"sqlite+aiosqlite:///{tmp_path}/sessions.db")
        await repo.init_db()
        yield repo
        await repo.close()

    async def test_session_survives_restart(self, repo):
        """A persisted session restores into a fresh store after a 'restart'."""
        store = SessionStore()
        token = store.create()
        await repo.save_session(hash_token(token), store.expiry_of(token))

        restarted = SessionStore()
        restarted.restore(await repo.load_sessions())
        assert restarted.validate(token) is True

    async def test_logout_revokes_persisted_session(self, repo):
        store = SessionStore()
        token = store.create()
        await repo.save_session(hash_token(token), store.expiry_of(token))
        await repo.delete_session(hash_token(token))

        restarted = SessionStore()
        restarted.restore(await repo.load_sessions())
        assert restarted.validate(token) is False

    async def test_expired_rows_are_purged_on_load(self, repo):
        await repo.save_session("expired-hash", time.time() - 10)
        assert "expired-hash" not in await repo.load_sessions()


class TestWebSocketAuth:
    def test_query_string_token_is_rejected(self, auth_client):
        """The pre-existing query-token fallback is gone (it leaked into logs)."""
        cookies = dict(auth_client.cookies)
        token = cookies.get("leapconnect_session")
        assert token
        auth_client.cookies.clear()  # simulate a client sending only ?token=
        try:
            with (
                pytest.raises(WebSocketDisconnect) as exc,
                auth_client.websocket_connect(f"/ws/logs?token={token}") as ws,
            ):
                ws.receive_text()
            assert exc.value.code == 4401
        finally:
            auth_client.cookies.update(cookies)

    def test_cookie_auth_accepted(self, auth_client):
        with auth_client.websocket_connect("/ws/logs") as ws:
            # Connection is accepted; just close it again.
            ws.close()
