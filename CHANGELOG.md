# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Message notification dropdown in the top navbar with unread badge, inline message preview, infinite scroll, and periodic polling (60s)
- Unread indicator dot on the Messages tab icon in both the sidebar and bottom tab bar
- `unreadMessages` reactive state and `loadUnreadCount()` action in the app store
- `WindowControlModal` component: merged open/close windows into a single control with quick-action buttons and a horizontal slider (0–100%) for precise window positioning; displays per-window state indicators (4 colored dots) with legend
- `SunshadeControlModal` component: merged open/close sunshade into a single control with quick-action buttons and a horizontal slider (0–10) for precise sunshade positioning; shows current sunshade state indicator on the track
- Backend `POST /api/vehicles/{vin}/windows` endpoint accepting a `value` parameter (0–100) for arbitrary window position
- Backend `POST /api/vehicles/{vin}/sunshade` endpoint accepting a `value` parameter (0–10) for arbitrary sunshade position
- `execControl()` in the store now supports an optional request body for parameterized commands
- Active state dot indicator on remote control buttons (pulsing colored dot) for trunk open, lock/unlock, and A/C status

### Changed

- Window and sunshade remote controls consolidated from two separate buttons each into a single button that opens a dedicated modal
- Removed "Close Trunk" button (not supported); trunk control is now a single "Open Trunk" button with `PackageOpen` icon
- Existing `windows/open`, `windows/close`, `sunshade/open`, `sunshade/close` endpoints now accept an optional `value` body parameter to override defaults
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
- Swap icons for window controls to match action labels

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
