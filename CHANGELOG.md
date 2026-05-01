# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Changed

- Migrated from pip/venv to uv (Astral) for dependency and environment management
- Replaced `requirements.txt` with `uv.lock` for deterministic builds
- Updated Dockerfile to use uv for dependency installation
- Updated `requires-python` from `>=3.11` to `>=3.12` (required by leapmotor-api)

### Added

- `bump-my-version` for automated versioning across `pyproject.toml` and `frontend/package.json`
- Pre-commit hooks: trailing whitespace, end-of-file fixer, YAML/TOML/JSON validation, ruff lint + format
- Pre-push hook: pytest suite must pass before pushing
- Test suite with pytest + pytest-asyncio
- `.python-version` file (3.13)

## [0.1.0] - 2026-05-01

### Added

- Live vehicle status: battery, range, speed, odometer, temperature, lock status
- Remote controls: lock/unlock, trunk, windows, sunshade, climate (A/C, quick cool/heat, defrost), battery preheat, find car
- Adjustable charge limit slider
- Vehicle details: doors, windows, tire pressure, climate, connectivity, ignition
- Location: OpenStreetMap embedded view with coordinates
- Mileage & energy delivery history
- Car picture view link
- Raw data viewer for debugging
- Multi-vehicle tab switching
- Docker Compose deployment with Traefik reverse proxy
- SQLite-based vehicle history persistence
- Certificate-based authentication setup flow
