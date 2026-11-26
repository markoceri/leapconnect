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
| `telemetry`     | `VehicleSnapshot`, `VehicleEvent`, `TransitionDetector` (state-change rules), battery SOH estimate from full-charge readings (`battery_health.py`) |
| `trips`         | trip segmentation/merging, similarity scoring, charge-session detection (`analysis.py`) — trips are derived on the fly, there is no persistent Trip aggregate |
| `charging`      | price tiers, time-of-use bands, session costs, TOU cost calculation (`costing.py`), charging provider sessions and their matching (`providers.py`), charging points and the charge sites grouping (`stations.py`) |
| `maintenance`   | plan items/records/alerts, the due/overdue engine (`engine.py`), pack normalization (`packs.py`), model resolver (`resolver.py`) |
| `notifications` | channels/preferences/Telegram users, the event catalog + message templates (`event_catalog.py`) |
| `zones`         | `Zone` model, zone geometry (`geometry.py`), pure enter/exit transition detection (`detection.py`) — a reusable location concept consumed by notifications (alerts) and charging (tier-by-zone) |
| `identity`      | local dashboard session policy (`sessions.py`, hash-keyed store persisted via the repository), login throttling (`throttle.py`) |
| `settings`      | typed user/scheduler/MQTT/ABRP settings models |
| `styling`       | vehicle accent-colour palettes (`palettes.py`), map tile provider selection and validation (`map_tiles.py`; the URL catalog lives in `frontend/src/utils/mapTiles.js`) |
| `system`        | health of the host running LeapConnect: `DiskUsage`, low-disk threshold and daily-reminder rules (`disk.py`) |

**Rule:** domain modules import only the stdlib and other domain modules.
Enforced by `tests/test_architecture.py`.

### `leapconnect.application` — use cases & orchestration

- `ports/` — interfaces implemented by infrastructure:
  `repositories.py` (segregated per context, combined as `AppRepository`),
  `notifier.py` (`BaseNotifier`) and `charging_provider.py`
  (`ChargingProvider`: read-only access to one connected account of a
  charging provider — an eMSP such as EVDC — its billed sessions, receipts and
  charging points; `ChargingProviderError` for its failures).
- `scheduler.py` — background polling loops (history, MQTT, transitions).
- `notifications/` — event → notification pipeline: `dispatcher.py`
  (orchestrator: channels, preferences, cooldowns, mute; also owns the
  `ZoneTracker` and maps zone enter/exit crossings to `geofence_enter`/
  `geofence_exit` events), `policies.py` (stateful custom-event detectors:
  movement alert, unlocked timeout, SOC thresholds, charge interrupted, range
  low, tire pressure), `tracking.py` (periodic location tracking),
  `telegram_admin.py` (user approve/decline messages).
- `zones/` — `ZoneTracker` holds the per-VIN inside-zone state and delegates
  the set math to `domain.zones.detect_transitions`.
- `vehicle_cache.py` — rate-limited, single-flight status cache.
- `commands.py` — the remote-command registry (`CommandSpec`: client method,
  required vehicle right, Pydantic param model) shared by the REST endpoint
  `POST /api/vehicles/{vin}/commands/{command}`, the Telegram bot and the
  MQTT bridge; rights checks included (REST is pass-through for now).
- `settings_store.py` — typed settings ↔ key/value settings table.
- `system_health.py` — `DiskSpaceMonitor`, a background task raising the
  `disk_space_low` event from the global thresholds (Settings → General →
  System), delivered via `NotificationDispatcher.dispatch_system` to the
  channels that enabled it; the disk probe is `infrastructure/system.py`.
- `maintenance.py` — plan auto-generation use case.
- `battery_health.py` — estimated battery SOH for a vehicle (full-charge
  samples from the repository + the per-vehicle reference capacity stored
  in the settings table).
- `charging_providers.py` — use cases over the connected charging provider
  accounts (a list: one, or all of them): import of their billed sessions
  (preview, apply — matched records updated, unmatched ones created on
  request — and the per-account automatic import the scheduler runs), manual
  link/unlink, receipts, the charging points search (one account per provider
  type) and the charge sites; matching and the precedence rules (values
  entered by hand are kept) are `domain.charging.providers`.

### `leapconnect.infrastructure` — driven adapters

- `persistence/` — SQLAlchemy/aiosqlite implementation of the repository port,
  split per bounded context: `tables.py` (ORM rows + Alembic `Base`),
  `migration.py` (startup Alembic upgrade + self-healing ALTER fallbacks),
  one repository class per context (`telemetry.py`, `settings.py`,
  `account.py`, `notifications.py`, `zones.py`, `charging.py`,
  `charging_providers.py`, `maintenance.py`) sharing a
  session factory via `base.py`, and `sqlite_adapter.py` — the thin
  `SqlAlchemyRepository` facade composing them into `AppRepository` and owning
  the engine lifecycle. Secret fields (cloud/MQTT passwords, ABRP token,
  vehicle PIN, Telegram bot token, charging provider credentials) are encrypted at rest via `secrets.py`
  (`SecretCipher`); the repos that touch them encrypt on write / decrypt on
  read, tolerating legacy plaintext.
- `secrets.py` — Fernet `SecretCipher` + key file management
  (`0600`, beside the DB) for at-rest secret encryption.
- `mqtt/home_assistant.py` — Home Assistant MQTT discovery bridge.
- `telegram/` — bot polling (`bot.py`), notifier (`notifier.py`), config.
- `abrp/service.py` — A Better Route Planner telemetry.
- `charging_providers.py` — `ChargingProviderRegistry`: the connected
  accounts of every supported provider type (`PROVIDER_TYPES`), built from the
  `charging_provider_accounts` table, and the logins waiting for a two-factor
  code.
- `evdc/service.py` — one EVDC account (`ChargingProvider`) over
  `evdc-network-api`: read-only (login, charging history, receipts, charging
  points with a short search cache); the account is connected once and a
  device key is enrolled, so the password is never stored (device key and
  tokens are the account's encrypted credentials). `evdc/live.py`
  (`EvdcLiveFeed`): live progress of the sessions in progress over
  socket.io, opened on demand and closed when idle.
- `community.py` — GitHub fetcher for community maintenance packs.
- `logbuffer.py` — in-memory ring buffer behind the log viewer.

### `leapconnect.api` — driving adapter (FastAPI)

- `app.py` — app factory: CORS, session middleware, error handler, SPA mount,
  router registration, lifespan (delegates to the container).
- `routers/` — one router per context, each with an OpenAPI tag: `identity`,
  `connection`, `vehicles`, `history`, `commands`, `trips`, `charging`,
  `maintenance`, `notifications`, `zones`, `system`. On 2026-06-12 the inconsistent
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
