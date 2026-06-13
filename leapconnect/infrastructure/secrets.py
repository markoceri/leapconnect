"""At-rest encryption for stored secrets (Leapmotor/MQTT passwords, tokens…).

A Fernet key lives on disk next to the database (``secret.key``, ``0600``),
generated on first use. Encrypted values are tagged with an ``enc:`` prefix so
the adapter can tell ciphertext from legacy plaintext: existing rows are read
as-is and transparently re-encrypted the next time they are written (lazy
migration — no separate migration step, no downtime).
"""

from __future__ import annotations

import logging
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken

_LOGGER = logging.getLogger(__name__)

_PREFIX = "enc:"


class SecretCipher:
    """Encrypt/decrypt short secret strings, tolerant of legacy plaintext."""

    def __init__(self, key: bytes) -> None:
        self._fernet = Fernet(key)

    def encrypt(self, plaintext: str | None) -> str | None:
        """Encrypt a value. Empty/None and already-encrypted values pass through."""
        if not plaintext:
            return plaintext
        if plaintext.startswith(_PREFIX):
            return plaintext  # already ciphertext
        token = self._fernet.encrypt(plaintext.encode()).decode()
        return _PREFIX + token

    def decrypt(self, stored: str | None) -> str | None:
        """Decrypt a value, returning legacy plaintext (unprefixed) unchanged."""
        if not stored or not stored.startswith(_PREFIX):
            return stored  # legacy plaintext or empty
        try:
            return self._fernet.decrypt(stored[len(_PREFIX) :].encode()).decode()
        except InvalidToken:
            _LOGGER.warning(
                "Failed to decrypt a stored secret (wrong or rotated key); "
                "treating it as unset"
            )
            return ""


def load_or_create_cipher(key_path: Path) -> SecretCipher:
    """Return a :class:`SecretCipher`, generating the key file on first use."""
    if key_path.exists():
        key = key_path.read_bytes().strip()
    else:
        key = Fernet.generate_key()
        key_path.parent.mkdir(parents=True, exist_ok=True)
        key_path.write_bytes(key)
        key_path.chmod(0o600)
        _LOGGER.info("Generated new secret encryption key at %s", key_path)
    return SecretCipher(key)
