# LeapConnect — Architecture

LeapConnect is structured as a **hexagonal (ports & adapters) application** with
DDD-style bounded contexts. The Python backend lives in the `leapconnect/`
package; the Vue 3 SPA lives in `frontend/`.

```
                    ┌─────────────────────────────────────────┐
   driving side     │              leapconnect.api            │   (FastAPI)
   (who calls us)   │   routers/ · schemas/ (DTOs) · deps     │
                    └────────────────────┬────────────────────┘
                                         │
                    ┌────────────────────▼────────────────────┐
                    │         leapconnect.application         │
                    │  use cases · scheduler · dispatcher ·   │
                    │  vehicle cache · ports (interfaces)     │
                    └────────────────────┬────────────────────┘
                                         │
                    ┌────────────────────▼────────────────────┐
                    │            leapconnect.domain           │   pure Python
                    │  telemetry · trips · charging · maint.  │   (stdlib only)
                    │  notifications · identity · settings    │
                    └────────────────────▲────────────────────┘
                                         │ implements ports
                    ┌────────────────────┴────────────────────┐
   driven side      │        leapconnect.infrastructure       │
   (whom we call)   │  persistence (SQLite/SQLAlchemy) · mqtt │
                    │  telegram · abrp · community · logbuffer│
                    └─────────────────────────────────────────┘
```

## Layers

### `leapconnect.domain` — pure business model

One subpackage per **bounded context**:

| Context         | Contents |
|-----------------|----------|
| `telemetry`     | `VehicleSnapshot`, `VehicleEvent`, `TransitionDetector` (state-change rules) |
| `trips`         | trip segmentation/merging, similarity scoring, charge-session detection (`analysis.py`) — trips are derived on the fly, there is no persistent Trip aggregate |
| `charging`      | price tiers, time-of-use bands, session costs, TOU cost calculation (`costing.py`) |
| `maintenance`   | plan items/records/alerts, the due/overdue engine (`engine.py`), pack normalization (`packs.py`), model resolver (`resolver.py`) |
| `notifications` | channels/preferences/geofences/Telegram users, geofence geometry (`geofencing.py`), the event catalog + message templates (`event_catalog.py`) |
| `identity`      | local dashboard session policy (`sessions.py`, hash-keyed store persisted via the repository), login throttling (`throttle.py`) |
| `settings`      | typed user/scheduler/MQTT/ABRP settings models |

**Rule:** domain modules import only the stdlib and other domain modules.
Enforced by `tests/test_architecture.py`.

### `leapconnect.application` — use cases & orchestration

- `ports/` — interfaces implemented by infrastructure:
  `repositories.py` (segregated per context, combined as `AppRepository`)
  and `notifier.py` (`BaseNotifier`).
- `scheduler.py` — background polling loops (history, MQTT, transitions).
- `notifications/` — event → notification pipeline: `dispatcher.py`
  (orchestrator: channels, preferences, cooldowns, mute), `policies.py`
  (stateful custom-event detectors: movement alert, unlocked timeout, SOC
  thresholds, charge interrupted, range low, tire pressure, geofence watcher),
  `tracking.py` (periodic location tracking), `telegram_admin.py` (user
  approve/decline messages).
- `vehicle_cache.py` — rate-limited, single-flight status cache.
- `commands.py` — the remote-command registry (`CommandSpec`: client method,
  required vehicle right, Pydantic param model) shared by the REST endpoint
  `POST /api/vehicles/{vin}/commands/{command}`, the Telegram bot and the
  MQTT bridge; rights checks included (REST is pass-through for now).
- `settings_store.py` — typed settings ↔ key/value settings table.
- `maintenance.py` — plan auto-generation use case.

### `leapconnect.infrastructure` — driven adapters

- `persistence/` — SQLAlchemy/aiosqlite implementation of the repository port,
  split per bounded context: `tables.py` (ORM rows + Alembic `Base`),
  `migration.py` (startup Alembic upgrade + self-healing ALTER fallbacks),
  one repository class per context (`telemetry.py`, `settings.py`,
  `account.py`, `notifications.py`, `charging.py`, `maintenance.py`) sharing a
  session factory via `base.py`, and `sqlite_adapter.py` — the thin
  `SqlAlchemyRepository` facade composing them into `AppRepository` and owning
  the engine lifecycle. Secret fields (cloud/MQTT passwords, ABRP token,
  vehicle PIN, Telegram bot token) are encrypted at rest via `secrets.py`
  (`SecretCipher`); the repos that touch them encrypt on write / decrypt on
  read, tolerating legacy plaintext.
- `secrets.py` — Fernet `SecretCipher` + key file management
  (`0600`, beside the DB) for at-rest secret encryption.
- `mqtt/home_assistant.py` — Home Assistant MQTT discovery bridge.
- `telegram/` — bot polling (`bot.py`), notifier (`notifier.py`), config.
- `abrp/service.py` — A Better Route Planner telemetry.
- `community.py` — GitHub fetcher for community maintenance packs.
- `logbuffer.py` — in-memory ring buffer behind the log viewer.

### `leapconnect.api` — driving adapter (FastAPI)

- `app.py` — app factory: CORS, session middleware, error handler, SPA mount,
  router registration, lifespan (delegates to the container).
- `routers/` — one router per context, each with an OpenAPI tag: `identity`,
  `connection`, `vehicles`, `history`, `commands`, `trips`, `charging`,
  `maintenance`, `notifications`, `system`. On 2026-06-12 the inconsistent
  legacy paths were renamed **in place** (no `/api/v2` namespace): local auth
  and cloud connection are session-style (`POST/DELETE /api/auth/session`,
  `POST/PUT/DELETE /api/cloud/session`, `GET /api/cloud/status`,
  `GET/PUT /api/cloud/pin`), root-level kebab paths moved under their context
  (`/api/charging/tiers`, `/api/charging/time-bands`,
  `/api/vehicles/{vin}/charging/stats/daily|yearly`, `/api/telegram/*`).
  The Vue frontend is migrated in the same commit; path changes are breaking
  for installed PWA clients until they reload.
- `schemas/` — Pydantic DTOs grouped by context.
- `deps.py` — FastAPI dependency providers (`get_container`, `get_repo`,
  `get_client`, `get_vehicle` and their `Annotated` aliases), session cookie
  constants, date parsing. Routers receive collaborators via ``Depends``
  instead of importing the container singleton, so tests can override them
  with ``app.dependency_overrides[get_container]``.

### `leapconnect.container` — composition root

`AppContainer` (singleton `container`) replaces the old `main.py` module
globals. It owns the Leapmotor client/connection state, constructs and wires
all services at startup, manages live-refresh and WebSocket broadcast, and is
the only place where every layer may be imported together.

`leapconnect/config.py` centralises paths, env vars and the app version; the
environment is parsed by the pydantic-settings `AppSettings` class
(`DATA_DIR`, `DB_PATH`, `CORS_ORIGINS`, `HOST`, `PORT`).

## Entry points

- ASGI app: `leapconnect.api.app:app` (uvicorn target, used by the Dockerfile
  and the `serve` script).
- CLI: `python -m leapconnect` runs the server; `python -m leapconnect
  --reset-password <pw>` resets the local dashboard password.
- Alembic migrations live in `migrations/`; `migrations/env.py` imports the ORM
  `Base` from the infrastructure adapter.

The pre-refactoring top-level modules (`main.py`, `models.py`, `schemas.py`,
`services/*`, `persistence/*`) have been removed; all imports go through
`leapconnect.*`.

## Testing

- `tests/test_architecture.py` — layering rules (domain purity, application
  must not import the API layer).
- The rest of the suite exercises the API via `TestClient` with a temp DB
  (`tests/conftest.py` patches `AppContainer.auto_connect`).
