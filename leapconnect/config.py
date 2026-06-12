"""Application configuration: paths, environment, version.

Single place where environment variables and filesystem layout are resolved.
Environment is parsed by :class:`AppSettings` (pydantic-settings); the
module-level ``settings`` instance is the import-time snapshot used by the
rest of the app.
"""

from __future__ import annotations

import logging
import os
import tomllib
from pathlib import Path
from typing import Annotated

from pydantic import field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

_LOGGER = logging.getLogger(__name__)

# Repository root (the directory containing pyproject.toml).
ROOT_DIR = Path(__file__).resolve().parent.parent

try:
    APP_VERSION: str = tomllib.loads((ROOT_DIR / "pyproject.toml").read_text())[
        "project"
    ]["version"]
except Exception:  # pragma: no cover - dev fallback
    APP_VERSION = "dev"


class AppSettings(BaseSettings):
    """Environment-driven configuration.

    Field names map to environment variables case-insensitively
    (``data_dir`` ← ``DATA_DIR``, ``history_db_path`` ← ``HISTORY_DB_PATH``…).
    """

    model_config = SettingsConfigDict(extra="ignore")

    # Data directory — mounted from host for persistence across restarts.
    data_dir: Path = ROOT_DIR / "data"

    # SQLite database file (overridden per-test and in Docker).
    history_db_path: Path = ROOT_DIR / "leapconnect.db"

    # Origins allowed by CORS (the Vue dev server by default). Accepts a
    # comma-separated string or a JSON list.
    cors_origins: Annotated[list[str], NoDecode] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]

    # Bind address for ``python -m leapconnect``.
    host: str = "0.0.0.0"
    port: int = 8099

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _parse_origins(cls, value: object) -> object:
        if isinstance(value, str):
            raw = value.strip()
            if raw.startswith("["):
                import json

                return json.loads(raw)
            return [part.strip() for part in raw.split(",") if part.strip()]
        return value


# Import-time snapshot. Path-like values derived from it are constants below.
settings = AppSettings()

DATA_DIR = settings.data_dir
CERTS_DIR = DATA_DIR / "certs"

# On-disk cache for static vehicle images (fetched from the cloud once per VIN).
VEHICLE_IMAGE_DIR = DATA_DIR / "vehicle_images"

# Built Vue SPA served in production.
FRONTEND_DIST = ROOT_DIR / "frontend" / "dist"

IMAGE_MEDIA_TYPES = {
    "png": "image/png",
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "webp": "image/webp",
}


def database_path() -> str:
    """Resolve the SQLite database path.

    Re-reads the environment on every call: the test suite points
    ``HISTORY_DB_PATH`` at a fresh temporary file for each test.
    """
    return str(AppSettings().history_db_path)


def database_url() -> str:
    return f"sqlite+aiosqlite:///{database_path()}"


def migrate_legacy_db(target_path: str) -> None:
    """Auto-rename legacy history.db → leapconnect.db if needed."""
    if os.path.isfile(target_path):
        return  # Target already exists, nothing to do

    parent = os.path.dirname(target_path)
    legacy_path = os.path.join(parent, "history.db")
    if os.path.isfile(legacy_path):
        _LOGGER.info("Migrating legacy DB: %s → %s", legacy_path, target_path)
        os.rename(legacy_path, target_path)
        _LOGGER.info("Legacy DB migrated successfully")
