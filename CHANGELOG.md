# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- All FastAPI endpoints now declare `response_model` with typed Pydantic schemas where applicable, enabling automatic validation and OpenAPI documentation
- Added concise docstrings to every API endpoint
- Added return type annotations to all endpoint functions
- New response wrapper schemas: `FullVehicleDataResponse`, `VehicleHistoryResponse`, `DailySummaryResponse`, `SchedulerStatusResponse`, `MessageListResponse`, `UnreadCountResponse`, and others
- Certificate setup page now supports drag & drop for certificate and key file uploads
- New `schemas.py` file with Pydantic models for all API responses (vehicle, status, messages), each with a `from_model` method for easy conversion
- Migrated from pip/venv to uv (Astral) for dependency and environment management
- Replaced `requirements.txt` with `uv.lock` for deterministic builds
- Updated Dockerfile to use uv for dependency installation
- Updated `requires-python` from `>=3.11` to `>=3.12` (required by leapmotor-api)
- Updated leapmotor-api dependency to v0.1.2
- `bump-my-version` for automated versioning across `pyproject.toml` and `frontend/package.json`
- Pre-commit hooks: trailing whitespace, end-of-file fixer, YAML/TOML/JSON validation, ruff lint + format
- Pre-push hook: pytest suite must pass before pushing
- Test suite with pytest + pytest-asyncio
- `.python-version` file (3.13)
- Added menu to read messages from leapmotor account

### Fixed

- Charging status in the frontend now uses the vehicle-level `is_charging` property instead of the battery-level one, which was incorrectly showing charging during regenerative braking

### Changed

- Endpoints now return Pydantic model instances directly instead of manually calling `.model_dump()`; FastAPI handles serialization via `response_model`
- Vehicle data now uses structured response schemas, making the API output consistent and complete with the underlying vehicle model
- All vehicle properties (doors, windows, tires, connectivity, ignition, etc.) now use their original field names instead of shortened aliases
- The vehicle nickname field is now returned as `vehicle_nickname` to match the data source
- Tire pressure data now includes both raw kPa values and converted bar values, plus a status indicator for each wheel
- Battery information now exposes all available fields, including raw energy in Wh and converted kWh
- Climate, door, window, and connectivity sections now include all available data points instead of a subset
- Updated the entire frontend to work with the new field names
- Moved data models (snapshot, scheduler settings) to a dedicated file for better organization
- Moved the background data collection scheduler to a separate `services` folder, keeping storage-related code separate from application logic

### Removed

- Removed manual data conversion helpers in favor of Pydantic response schemas

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
