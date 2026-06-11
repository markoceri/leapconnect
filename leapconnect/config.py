"""Application configuration: paths, environment, version.

Single place where environment variables and filesystem layout are resolved.
"""

from __future__ import annotations

import logging
import os
import tomllib
from pathlib import Path

_LOGGER = logging.getLogger(__name__)

# Repository root (the directory containing pyproject.toml / main.py).
ROOT_DIR = Path(__file__).resolve().parent.parent

try:
    APP_VERSION: str = tomllib.loads((ROOT_DIR / "pyproject.toml").read_text())[
        "project"
    ]["version"]
except Exception:  # pragma: no cover - dev fallback
    APP_VERSION = "dev"

# Data directory — mounted from host for persistence across container restarts.
DATA_DIR = Path(os.environ.get("DATA_DIR", str(ROOT_DIR / "data")))
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
    """Resolve the SQLite database path (env override for tests/deploys)."""
    return os.environ.get("HISTORY_DB_PATH", str(ROOT_DIR / "leapconnect.db"))


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
