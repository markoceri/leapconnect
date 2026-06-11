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
| `identity`      | local dashboard session policy (`sessions.py`) |
| `settings`      | typed user/scheduler/MQTT/ABRP settings models |

**Rule:** domain modules import only the stdlib and other domain modules.
Enforced by `tests/test_architecture.py`.

### `leapconnect.application` — use cases & orchestration

- `ports/` — interfaces implemented by infrastructure:
  `repositories.py` (segregated per context, combined as
  `AppRepository`; `VehicleHistoryRepository` kept as deprecated alias) and
  `notifier.py` (`BaseNotifier`).
- `scheduler.py` — background polling loops (history, MQTT, transitions).
- `notification_dispatcher.py` — event → notification pipeline.
- `vehicle_cache.py` — rate-limited, single-flight status cache.
- `commands.py` — remote-command rights checks and execution maps.
- `settings_store.py` — typed settings ↔ key/value settings table.
- `maintenance.py` — plan auto-generation use case.

### `leapconnect.infrastructure` — driven adapters

- `persistence/sqlite_adapter.py` — SQLAlchemy/aiosqlite implementation of the
  repository port; runs Alembic migrations at startup.
- `mqtt/home_assistant.py` — Home Assistant MQTT discovery bridge.
- `telegram/` — bot polling (`bot.py`), notifier (`notifier.py`), config.
- `abrp/service.py` — A Better Route Planner telemetry.
- `community.py` — GitHub fetcher for community maintenance packs.
- `logbuffer.py` — in-memory ring buffer behind the log viewer.

### `leapconnect.api` — driving adapter (FastAPI)

- `app.py` — app factory: CORS, session middleware, error handler, SPA mount,
  router registration, lifespan (delegates to the container).
- `routers/` — one router per context: `identity`, `connection`, `vehicles`,
  `history`, `commands`, `trips`, `charging`, `maintenance`, `notifications`,
  `system`. **URL paths are unchanged** from the pre-refactoring monolith so
  the frontend and PWA clients keep working.
- `schemas/` — Pydantic DTOs grouped by context.
- `deps.py` — repository access helpers, session cookie constants, date parsing.

### `leapconnect.container` — composition root

`AppContainer` (singleton `container`) replaces the old `main.py` module
globals. It owns the Leapmotor client/connection state, constructs and wires
all services at startup, manages live-refresh and WebSocket broadcast, and is
the only place where every layer may be imported together.

`leapconnect/config.py` centralises paths, env vars and the app version.

## Entry points

- `main.py` — thin shim: re-exports `app` (uvicorn target `main:app`) and the
  `--reset-password` CLI.
- Alembic migrations live in `migrations/`; `migrations/env.py` imports the ORM
  `Base` from the infrastructure adapter.

## Legacy compatibility shims

The historical module paths still work and simply re-export from the new
locations (kept until the next major release; enforced by tests):

`models.py`, `schemas.py`, `persistence/repository.py`,
`persistence/sqlite_adapter.py`, `services/*` (scheduler, vehicle_cache,
notification_dispatcher, telegram_bot, telegram_config, notifiers,
maintenance_service, maintenance_resolver, maintenance_community, mqtt_ha,
abrp, transition_detector).

New code must import from `leapconnect.*` directly.

## Testing

- `tests/test_architecture.py` — layering rules (domain purity, application
  must not import the API layer) and shim re-exports.
- The rest of the suite exercises the API via `TestClient` with a temp DB
  (`tests/conftest.py` patches `AppContainer.auto_connect`).
