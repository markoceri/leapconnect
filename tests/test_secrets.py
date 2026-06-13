"""Tests for at-rest secret encryption."""

import pytest
from cryptography.fernet import Fernet

from leapconnect.domain.notifications.models import NotificationChannel
from leapconnect.infrastructure.secrets import SecretCipher, load_or_create_cipher


class TestSecretCipher:
    def setup_method(self):
        self.cipher = SecretCipher(Fernet.generate_key())

    def test_round_trip(self):
        token = self.cipher.encrypt("hunter2")
        assert token.startswith("enc:")
        assert "hunter2" not in token
        assert self.cipher.decrypt(token) == "hunter2"

    def test_empty_and_none_pass_through(self):
        assert self.cipher.encrypt("") == ""
        assert self.cipher.encrypt(None) is None
        assert self.cipher.decrypt("") == ""
        assert self.cipher.decrypt(None) is None

    def test_legacy_plaintext_read_unchanged(self):
        # Values written before encryption have no prefix → returned as-is.
        assert self.cipher.decrypt("plain-legacy-token") == "plain-legacy-token"

    def test_double_encrypt_is_idempotent(self):
        once = self.cipher.encrypt("secret")
        twice = self.cipher.encrypt(once)
        assert once == twice
        assert self.cipher.decrypt(twice) == "secret"

    def test_wrong_key_yields_empty(self):
        token = self.cipher.encrypt("secret")
        other = SecretCipher(Fernet.generate_key())
        assert other.decrypt(token) == ""

    def test_load_or_create_persists_key(self, tmp_path):
        key_file = tmp_path / "secret.key"
        c1 = load_or_create_cipher(key_file)
        assert key_file.exists()
        assert oct(key_file.stat().st_mode)[-3:] == "600"
        token = c1.encrypt("x")
        # A cipher reloaded from the same file decrypts what the first wrote.
        c2 = load_or_create_cipher(key_file)
        assert c2.decrypt(token) == "x"


@pytest.fixture
async def repo(tmp_path):
    from leapconnect.infrastructure.persistence.sqlite_adapter import (
        SqlAlchemyRepository,
    )

    repo = SqlAlchemyRepository(f"sqlite+aiosqlite:///{tmp_path}/secrets.db")
    await repo.init_db()
    yield repo
    await repo.close()


async def _raw_setting(repo, key):
    """Read a setting straight from the row, bypassing decryption."""
    from sqlalchemy import select

    from leapconnect.infrastructure.persistence.tables import AppSettingRow

    async with repo._session_factory() as session:
        result = await session.execute(
            select(AppSettingRow.value).where(AppSettingRow.key == key)
        )
        return result.scalar_one()


class TestSecretsAtRest:
    async def test_account_password_encrypted_on_disk(self, repo):
        await repo.save_account(
            username="user@example.com",
            password="cloud-pw",
            cert_path="/c",
            key_path="/k",
            p12_password="p12-pw",
        )
        # Round-trips in clear through the repo API
        account = await repo.get_account()
        assert account["password"] == "cloud-pw"
        assert account["p12_password"] == "p12-pw"

        # But the raw column is ciphertext
        from sqlalchemy import select

        from leapconnect.infrastructure.persistence.tables import AccountRow

        async with repo._session_factory() as session:
            row = (await session.execute(select(AccountRow))).scalar_one()
        assert row.password.startswith("enc:")
        assert "cloud-pw" not in row.password
        assert row.p12_password.startswith("enc:")

    async def test_secret_setting_encrypted_mqtt_password(self, repo):
        await repo.save_setting("mqtt_password", "broker-pw")
        assert await repo.get_setting("mqtt_password") == "broker-pw"
        assert (await _raw_setting(repo, "mqtt_password")).startswith("enc:")

    async def test_vehicle_pin_encrypted(self, repo):
        await repo.save_setting("mqtt_vehicle_pin", "1234")
        assert await repo.get_setting("mqtt_vehicle_pin") == "1234"
        assert (await _raw_setting(repo, "mqtt_vehicle_pin")).startswith("enc:")

    async def test_non_secret_setting_stored_plaintext(self, repo):
        await repo.save_setting("theme", "dark")
        assert await repo.get_setting("theme") == "dark"
        assert await _raw_setting(repo, "theme") == "dark"

    async def test_telegram_bot_token_encrypted(self, repo):
        saved = await repo.save_notification_channel(
            NotificationChannel(
                channel_type="telegram",
                config={"bot_token": "12345:abcdef", "chat_id": "999"},
                enabled=True,
            )
        )
        loaded = await repo.get_notification_channel(saved.id)
        assert loaded.config["bot_token"] == "12345:abcdef"
        assert loaded.config["chat_id"] == "999"

        from sqlalchemy import select

        from leapconnect.infrastructure.persistence.tables import (
            NotificationChannelRow,
        )

        async with repo._session_factory() as session:
            row = (await session.execute(select(NotificationChannelRow))).scalar_one()
        assert "12345:abcdef" not in row.config_json
        assert "enc:" in row.config_json
        assert "999" in row.config_json  # non-secret field stays readable
