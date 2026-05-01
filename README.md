# LeapConnect

Web dashboard for monitoring and controlling Leapmotor vehicles via the [leapmotor-api](https://github.com/markoceri/leapmotor-api) Python client.

## Features

- **Live vehicle status**: Battery, range, speed, odometer, temperature, lock status
- **Remote controls**: Lock/unlock, trunk, windows, sunshade, climate (A/C, quick cool/heat, defrost), battery preheat, find car
- **Charge limit**: Adjustable charge limit slider
- **Vehicle details**: Doors, windows, tire pressure, climate, connectivity, ignition
- **Location**: OpenStreetMap embedded view with coordinates
- **Mileage & energy**: Delivery history, total mileage
- **Car picture**: View link when available
- **Raw data viewer**: Full JSON inspection for debugging
- **Multi-vehicle**: Tab switching for accounts with multiple vehicles

## Tested Vehicles

| Model | Status |
|-------|--------|
| T03 | ✅ Tested |
| C10 | 🟡 Should work (same cloud API) |
| B10 | 🟡 Should work (same cloud API) |
| C16 | 🟡 Should work (same cloud API) |
| B05 | 🟡 Should work (same cloud API) |

## Requirements

- Docker & Docker Compose (for production)
- [uv](https://docs.astral.sh/uv/) (for local development)
- Leapmotor app certificate files (`.pem`)
- A valid Leapmotor account

## Quick Start (Docker)

```bash
# 1. Clone the repository
git clone https://github.com/markoceri/leapmotor-webapp
cd leapmotor-webapp

# 2. Configure environment
cp .env.example .env
# Edit .env and set APP_CERT_PATH and APP_KEY_PATH

# 3. Build and start
docker compose build
docker compose up -d
```

The app is available at **http://localhost**.

Traefik handles reverse proxying on port 80. The app container runs internally on port 8099.

Vehicle history data is persisted in a Docker volume (`app-data`).

## Development

### Install uv

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

See [uv installation docs](https://docs.astral.sh/uv/getting-started/installation/) for other methods (Homebrew, Windows, pipx).

### Backend

```bash
uv sync
uv run pre-commit install && uv run pre-commit install --hook-type pre-push
uv run uvicorn main:app --host 0.0.0.0 --port 8099 --reload
```

The API runs at **http://localhost:8099**.

### Tests

```bash
uv run pytest
```

### Code Quality

Pre-commit hooks run automatically:

- **On commit**: trailing whitespace, end-of-file fix, YAML/TOML/JSON validation, ruff lint + format
- **On push**: full pytest suite

To run all checks manually:

```bash
uv run pre-commit run --all-files
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

The Vue dev server runs at **http://localhost:5173** and proxies `/api` calls to the backend.

### Production build (manual)

```bash
cd frontend
npm run build
```

This outputs to `frontend/dist/`. The FastAPI backend will automatically serve the built SPA.

### Versioning

The project uses [bump-my-version](https://github.com/callowayproject/bump-my-version) to manage versions across `pyproject.toml` and `frontend/package.json`.

```bash
uv run bump-my-version bump patch   # 0.1.0 → 0.1.1 (bugfix)
uv run bump-my-version bump minor   # 0.1.0 → 0.2.0 (new feature)
uv run bump-my-version bump major   # 0.1.0 → 1.0.0 (breaking change)
```

Each command updates the version in both files, creates a commit, and tags it `vX.Y.Z`.

**Release workflow:**

1. Commit all changes
2. Update `CHANGELOG.md` (move entries from `[Unreleased]` to a new version section)
3. `uv run bump-my-version bump patch|minor|major`
4. `git push --follow-tags`

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `APP_CERT_PATH` | Yes | Path to the app certificate PEM file |
| `APP_KEY_PATH` | Yes | Path to the app key PEM file |
| `ACCOUNT_P12_PASSWORD` | No | P12 password (usually auto-derived from login) |
| `HISTORY_DB_PATH` | No | SQLite database path (default: `/app/data/history.db`) |

## Login

You will need:
- **Email & Password**: Your Leapmotor account credentials
- **Vehicle PIN** (optional): Required for remote control actions (lock, unlock, climate, etc.)
