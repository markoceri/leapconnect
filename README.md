# Leapmotor Vehicle Command Center

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

## Requirements

- Docker & Docker Compose
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

### Backend

```bash
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8099 --reload
```

The API runs at **http://localhost:8099**.

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
