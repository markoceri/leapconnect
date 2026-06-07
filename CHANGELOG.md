# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- **New dedicated Charging tab** — full-page view with:
  - Session detection from vehicle snapshots (battery_is_charging transitions)
  - KPI cards: total energy, cost, home grid/solar/public breakdown
  - Energy per session bar chart (chronological)
  - Daily cost line chart
  - Energy by tier pie chart
  - Time-of-use bands energy distribution visualization
  - Monthly summary table
  - Editable session list with tier assignment (create/update cost records)
- **Multi-tier charging cost system** — configurable price tiers for home grid, home solar, public AC, and public DC charging:
  - New Settings card "Energy & Charging Costs" in General section
  - Solar panels toggle (enables/disables home solar tier)
  - Home pricing mode: flat rate or time-of-use bands (e.g. Italian ARERA bands F1/F2/F3)
  - Configurable time-of-use bands with day/time schedule and per-band pricing
- **Automatic tier detection on charge events** — the scheduler detects AC/DC charging and assigns the appropriate cost tier when a session starts/stops
- **Dashboard active tier indicator** — shows the current charging tier badge in the charging widget during active sessions
- **Dashboard charge-start toast** — notification when charging begins with tier info
- **Database migration 0007**: added `charging_price_tiers`, `charging_time_bands`, `charging_session_costs` tables with default Italian ARERA time-of-use schedule
- **New API endpoints**:
  - `GET /api/charging-tiers` — full tier and band configuration
  - `PUT /api/charging-tiers/{tier_id}` — update a tier's price/label/enabled state
  - `GET/POST/PUT/DELETE /api/charging-tiers/time-bands[/{band_id}]` — CRUD for time-of-use bands
  - `GET/POST/PUT/DELETE /api/vehicles/{vin}/charging-costs[/{cost_id}]` — CRUD for session cost records
- **Trip management** — new dedicated Trips tab with driving records and statistics:
  - Chronological trip list grouped by day with distance, energy use, regen energy, and consumption summary
  - Trip detail modal with GPS trace map, speed chart, and per-trip stats such as duration, max speed, SOC, and outside temperature
  - Monthly totals and navigation for reviewing trips by period
- **Trip comparison** — compare driving records side-by-side to analyze efficiency, performance, and conditions:
  - **Manual compare**: select any two trips from the trip list (even across different months) and compare them in a split-panel view with metric-by-metric deltas and insight cards
  - **Similar trips suggestions**: from any trip detail, find trips with similar route (start/end proximity), time-of-day, and distance; grouped by month with a composite similarity score and breakdown (route 40%, time 35%, distance 25%)
  - **Scoped search**: suggestions first search within the trip's own month, then offer to extend across all available data on demand
  - **Comparison insights**: efficiency analysis (kWh/100km, regen), performance metrics (distance, duration, avg speed), conditions (outside temperature), and a combined ranking with score explanation
  - **Backend similarity engine**: haversine-based route matching, circular 24h time-of-day scoring, distance tolerance gating (±40%), and fuzzy gpskey fallback for downsampled trip boundaries
  - **New API endpoint**: `GET /api/vehicles/{vin}/trips/similar` with configurable date range and result limit
- **Vehicle Maintenance & Health** — full-service tracker with model-aware schedules, community intervention library, service logging, and proactive reminders:
  - **Maintenance tab** in the main navigation (Wrench icon) with a segmented control: **Overview** | **Interventions**
  - **Overview**: static base vehicle image, hero status, KPI dashboard (overdue/upcoming counters, next action card, model badge), "Coming up" shortlist of overdue + due-soon interventions (≤ 2,000 km or ≤ 60 days), recent service records, and quick service logging
  - **Interventions library**: full plan table (edit / log / remove, with source badges), plus:
    - **Local** custom interventions — add your own, export as a shareable pack JSON, import from a file or raw URL
    - **Remote** community repositories: add a GitHub repo, browse its maintenance packs, and explicitly import items into your plan with collision handling (update / keep both / skip)
    - Official community repository ([leapconnect-maintenance-packs](https://github.com/markoceri/leapconnect-maintenance-packs)) pre-configured by default with factory schedules as versioned JSON packs, auto-registered on first use and hidden from the user repo list
  - **Model-aware maintenance rules** — schedules automatically loaded per vehicle model:
    - T03: 21 factory-specified service items extracted from the user manual (brakes, tires, drivetrain, climate, battery, body, electrical)
    - B10: 13 items (medium-confidence, inferred from manual text)
    - C10 BEV: 13 items
    - C10 REEV (hybrid): 17 items including engine-specific services (oil, air filter, spark plugs, fuel filter)
    - **C10 variant auto-detection**: heuristic based on allocation_code, fuel-heating ability, car_type string; manual fallback with persisted per-VIN override
  - **Service logging** — record completed interventions with date, mileage, cost, provider, and notes:
    - Auto-updates the plan item's `last_done` fields on log
    - Deleting a record recalculates `last_done` from the latest remaining record (or clears it)
  - **Overdue/upcoming computation** — per-item status based on km thresholds and time elapsed; configurable trigger mode (km-only, time-only, either, or both); server-computed alerts honouring each item's `trigger_mode`
  - Plan items track their `source` (`catalog` / `repo` / `local`)
  - Inline editing: interval, trigger mode, priority, last-done km, enabled/disabled toggle; Log Service modal with date picker, mileage field, cost, provider, notes; "Use current" button to fetch live odometer; delete confirmation modal
  - **Notification events** extended:
    - `maintenance_upcoming` — service due soon (configurable warning days)
    - `maintenance_overdue` — service past due date/mileage
    - `maintenance_critical` — urgent overdue items
    - Message templates with service label, remaining/overdue days, vehicle name
  - **Database migrations**:
    - **0009**: added `maintenance_plan_items` and `maintenance_records` tables with indexes and unique constraint
    - **0010**: added `maintenance_repos` and `maintenance_packs` tables; added `source` / `source_ref` columns to `maintenance_plan_items`
  - **API endpoints**:
    - `GET /api/vehicles/{vin}/maintenance/model` — resolve vehicle model and variant
    - `POST /api/vehicles/{vin}/maintenance/model` — override C10 variant (bev/reev)
    - `GET /api/vehicles/{vin}/maintenance/rules` — get maintenance rules for resolved model
    - `GET /api/vehicles/{vin}/maintenance/plan` — get (auto-generated on first access) service plan
    - `PUT /api/vehicles/{vin}/maintenance/plan/{service_type}` — edit a plan item
    - `POST /api/vehicles/{vin}/maintenance/plan` — create a custom local intervention
    - `DELETE /api/vehicles/{vin}/maintenance/plan/{service_type}` — remove an item from the plan
    - `POST /api/vehicles/{vin}/maintenance/plan/import` — explicit import with conflict strategy
    - `GET /api/vehicles/{vin}/maintenance/export` — download local items as a shareable pack
    - `GET /api/vehicles/{vin}/maintenance/library` — aggregated catalog + local + community packs with `in_plan` flags
    - `GET /api/vehicles/{vin}/maintenance/records` — list service records
    - `POST /api/vehicles/{vin}/maintenance/records` — log a completed service
    - `DELETE /api/vehicles/{vin}/maintenance/records/{record_id}` — delete a record (with plan recalculation)
    - `GET /api/vehicles/{vin}/maintenance/overview` — full dashboard with counts, plan, records, next action, current km, and `due_soon` shortlist
    - `GET /api/vehicles/{vin}/maintenance/current-mileage` — fetch live odometer from vehicle API
    - `GET/POST/DELETE /api/maintenance/repos`, `POST /api/maintenance/repos/{id}/refresh`, `GET /api/maintenance/repos/{id}/packs`
    - `POST /api/maintenance/packs/import` (repo+slug / raw URL / inline) and `POST /api/maintenance/upload` (file)

### Changed
- **Navigation menu refactor**:
  - **Desktop**: the icon-only sidebar can now be expanded/collapsed via an always-visible toggle. Collapsed by default (icons only), expands to show page titles; the state is remembered across sessions
  - **Mobile**: the bottom bar no longer crams in every tab — it now shows the 4 primary sections (Dashboard, Charging, Trips, Maintenance) plus a **"More"** button that opens a bottom sheet with the remaining sections (Details, History, Messages, Settings). New sections added in the future fall under "More" automatically. Unread badge now surfaces on "More" and on the Messages row inside the sheet
  - Tabs reordered by usage hierarchy (Dashboard, Charging, Trips, Maintenance first)
- **Settings layout**: energy/charging preferences moved from "Preferences" card to dedicated "Energy & Charging Costs" card
- **Preferences API**: extended with `has_solar_panels` and `home_pricing_mode` fields
- **History tab**: removed tier-specific KPIs (moved to dedicated Charging tab)
- **Dynamic car image in notifications — selective defaults**: the dynamic vehicle image is now disabled by default for most notification events. It remains enabled by default only for the four key charging plug events: `charge_start`, `charge_stop`, `plugged_in`, `unplugged`. A per-event "Dynamic image" toggle in Settings → Notifications lets the user override each event individually.
- **Telegram bot `/status` command now sends dynamic car image**: the `/status` command attaches the current vehicle state image as a photo with the text status as caption. Falls back gracefully to text-only if image composition fails.
- **Telegram bot `/status` command now shows doors, trunk, and windows**: the status overview always reports door state ("All closed" or which are open), trunk state ("Open"/"Closed"), and window state ("All closed" or open percentages like "Driver 50%").

### Fixed
- **False "SOC below threshold" notification on transient 0% glitches**: the notification dispatcher now ignores brief SOC=0 spikes (e.g. when unlocking after a long park). A 0% value must persist for at least 120 seconds or 6 consecutive samples before it is treated as a genuine low-battery condition and allowed to trigger `soc_threshold_low` alerts.
- **Regen energy always showing 0 in trips/details** — `battery_charging_power_kw`, `battery_discharge_power_kw`, and `vehicle_is_regening` were missing from the scheduler's history and transition poll snapshots, leaving `charging_power_kw` column always NULL in the database. The retrieval fallback in `sqlite_adapter` only computed charging power when `is_charging` was True (vehicle-level, always False during regen). Fixed by storing the battery power fields from `BatteryStatus.charging_power_kw` / `discharging_power_kw` in both poll methods, adding `vehicle_is_regening` to the history poll snapshot, and extending the retrieval fallback to also compute charging power when `is_regening` is True
- **False "Charging interrupted" notifications during regenerative braking**: `charge_interrupted` was being detected on every poll cycle when `is_charging=False` and SOC was below target, causing spam during driving. Fixed by (a) applying the same gun-sensor + `is_regening` guard already used for `charge_start`/`charge_stop`, and (b) only triggering on an actual charging→not-charging transition (stateful tracking), not on every cycle where the vehicle simply isn't charging.

## [0.8.2] - 2026-06-02

### Added
- **Login: show/hide password toggle** — the login page now includes an eye icon to reveal the password, helping users verify input of complex passwords with special characters
- **CLI: password reset command** — locked-out users can reset their LeapConnect password from CLI command (see [README.md](README.md#password-reset) for details)
- **Telegram Bot: multi-user access management** — the bot now supports multiple users with an approval workflow:
  - **Dashboard Web Approval**: users send `/start` to the bot and appear as "pending" in the Settings > Services > Telegram section; the admin approves or rejects from the web UI
  - **Deep Linking via Token**: the web UI generates a one-time `t.me/Bot?start=TOKEN` link (valid 10 minutes); the user clicks it and is auto-approved without manual intervention
  - **Admin inline notifications**: when a new user sends `/start`, all approved users receive an inline keyboard notification with ✅ Approve / ❌ Reject buttons directly in Telegram
  - **Status change notifications**: approved/rejected users receive a Telegram message; all admins are also notified of the outcome (with user name and username)
- **Telegram Users management UI** — new "Linked Users" section in the Telegram Bot card:
  - User list with status badges (pending/approved/rejected), username, and action buttons
  - Generate deep-link token with copy-to-clipboard functionality
  - Approve / Reject / Remove buttons per user
  - Auto-polling every 5 seconds for real-time updates
- **Database migration 0006**: added `telegram_users` and `telegram_link_tokens` tables for multi-user state persistence
- **New API endpoints**:
  - `GET /api/notifications/channels/telegram/users` — list Telegram users (optional `?status=` filter)
  - `PUT /api/notifications/channels/telegram/users/{chat_id}/approve` — approve a pending user
  - `PUT /api/notifications/channels/telegram/users/{chat_id}/reject` — reject a pending user
  - `DELETE /api/notifications/channels/telegram/users/{chat_id}` — remove a user
  - `POST /api/notifications/channels/telegram/link-token` — generate a deep-link token

### Changed
- **Telegram notifier: multi-user dispatch** — notifications are now sent to all approved users instead of a single configured `chat_id`
- **Bot silence for unapproved users** — the bot no longer responds to messages from users who haven't been approved, preventing information leakage
- **User profile auto-update** — approved users' username, first name, and last name are kept in sync from their Telegram messages

### Removed
- **Auto-seed of configured chat_id** — the first user is no longer auto-approved; all users must go through the approval flow (deep link or web approval)

## [0.8.1] - 2026-06-01

### Added
- **Telegram Bot: mute/unmute commands** — `/mute` (permanent), `/mute N` (for N minutes), `/unmute` to control notification delivery directly from the chat
- **Telegram Bot: notification settings menu** — `/notifications` command opens an interactive inline keyboard with:
  - Mute/unmute quick actions (permanent, 30 min, 1h, 8h)
  - Category submenus (Charging, Driving, Security, Maintenance)
  - Per-event toggle buttons (✅/❌) that persist to the database in real-time
- **History Events: notification event types** — the Events view in Data History now shows geofence enter/exit, security alerts (movement alert, unlocked timeout), maintenance alerts (tire pressure, low range), and tracking start/stop events
- **Backend: persist notification events** — custom-detected events from the notification dispatcher (geofence, movement, tire pressure, range low, unlocked timeout) and tracking start/stop are now saved to the `vehicle_events` table for historical analysis
- **New event dot colors** in History timeline: orange for geofence, cyan for tracking, red for maintenance

### Fixed
- **Charging notifications during regenerative braking** — `charge_start`/`charge_stop` notifications are now suppressed when the vehicle is not plugged in, preventing false alerts during regen braking
- **Geofence enter/exit notifications not firing** — added missing `status.location` fallback for GPS coordinate extraction in `_detect_custom_events`; vehicles that expose GPS via the `location` sub-object now correctly trigger geofence events

## [0.8.0] - 2026-05-30

### Added
- **Telegram Bot service** (`services/telegram_bot.py`): full interactive bot for controlling and querying the vehicle via Telegram commands. Features:
  - **20+ bot commands**: `/status`, `/location`, `/lock`, `/unlock`, `/trunk_open`, `/trunk_close`, `/find`, `/ac_on`, `/ac_off`, `/defrost`, `/windows_open`, `/windows_close`, `/charging_start`, `/charging_stop`, `/unlock_charger`, `/sunroof_open`, `/sunroof_close`, `/track`, `/track_stop`, `/commands`
  - **Permission enforcement**: commands respect the same rights + abilities model used by the frontend and MQTT HA — vehicles without specific hardware capabilities won't allow those commands
  - **Per-command PIN authentication**: every vehicle action command prompts for the operation PIN via Telegram; the PIN message is immediately deleted for security and the PIN is used only for that single command (never persisted from Telegram)
  - **Dynamic command menu**: `/commands` shows only the commands available for the current vehicle based on its permissions
  - **Location tracking**: `/track [N]` sends periodic GPS locations with a stop button; `/track_stop` cancels
  - **Rich status messages**: `/status` shows battery SOC, range, charging state, lock, climate, parking, odometer, tire pressures
- **Shared Telegram configuration** (`services/telegram_config.py`): `TelegramConfig` dataclass shared between the notifier and the bot service, holding `bot_token`, `chat_id`, and `bot_enabled`
- **Bot enable/disable toggle**: the Telegram bot commands can be independently enabled or disabled from the UI without affecting notifications; takes effect immediately (no restart required)
- **Frontend: Telegram Bot card in Services section**: dedicated configuration card with connection settings (Bot Token, Chat ID, Save, Test) and a Bot Commands subsection with enable/disable toggle and status indicator
- **Frontend: simplified Notifications channel view**: the Telegram channel in Notifications now shows only status, enable/disable toggle, and test button — configuration is managed from the Services section
- **Vehicle command permission checks** (`main.py`): centralized `_COMMAND_RIGHTS` mapping and `_vehicle_has_right()` function enforce rights + abilities before executing any vehicle command (used by both Telegram bot and future command sources). Commands without the required permission raise `PermissionError`.
- **Notification system with Telegram**: event-driven notifications dispatched via configurable channels. First implementation: Telegram Bot API with rich HTML messages and dynamic vehicle images.
  - **Abstract notifier architecture**: `BaseNotifier` interface (`services/notifiers/`) allows future extension to email, webhooks, push notifications, etc.
  - **Telegram notifier**: sends formatted messages via `sendMessage` (text) and `sendPhoto` (with composed vehicle image) using the existing `CarImagePackage` pipeline
  - **19 notification event types** across 4 categories:
    - *Charging*: charge start/stop, charge interrupted (SOC < target), SOC above/below threshold, plug/unplug
    - *Driving*: driving start, parked, ignition on/off
    - *Security*: locked/unlocked, movement alert (anti-theft with haversine distance), geofence enter/exit, unlocked timeout
    - *Maintenance*: tire pressure out of range, range below threshold
  - **Notification dispatcher** (`services/notification_dispatcher.py`): orchestrates the full pipeline — receives events from transition detection, checks user preferences, applies custom stateful logic (geofencing, SOC thresholds, unlock timeout, movement detection), composes messages from templates, and dispatches to notifiers with per-event cooldowns (5 min)
  - **Geofencing**: configurable geographic zones with haversine distance calculation; fires notifications on enter/exit based on user preference per zone
  - **Movement alert (anti-theft)**: detects vehicle displacement (>50m default) while parked with ignition off
  - **Configurable thresholds**: SOC high/low, tire pressure min/max, range threshold, unlock timeout — all per-event parameters adjustable from the UI
  - **Rich message templates**: each event type has an emoji-prefixed title + contextual body (SOC%, range, zone name, distance, etc.)
  - **Dynamic vehicle image in notifications**: photo-bearing events automatically compose and attach the current vehicle state image
- **Database migration 0005**: added `notification_channels`, `notification_preferences`, and `geofences` tables
- **Notification API endpoints**:
  - `GET/POST/PUT/DELETE /api/notifications/channels` — CRUD for notification channels
  - `POST /api/notifications/channels/{id}/test` — send test message
  - `GET/PUT /api/notifications/events` — list available events with status, bulk update preferences
  - `GET/POST/PUT/DELETE /api/notifications/geofences` — CRUD for geofences
- **Frontend: Notifications settings section** in Settings tab — new navigation pill with:
  - Telegram configuration card (bot token + chat ID, enable/disable, test button)
  - Events card with per-category toggle list and inline threshold configuration for configurable events
  - Geofences card with list of zones (enter/exit toggles) and form to add new zones (name, lat/lng, radius)
- **Scheduler integration**: notification dispatcher is called after each transition detection cycle, processing events in real-time alongside the existing event persistence
- **Transition detection & event tracking**: new fast-polling loop (default 10s, configurable 5–300s) that detects state transitions in real-time and persists them to a lightweight `vehicle_events` table. Captures:
  - Boolean transitions: regenerative braking start/stop, charging start/stop, plug/unplug, park/drive, lock/unlock, ignition on/off
  - Threshold transitions: speed crosses zero (moving start/stop), battery SOC changes ≥5%, charge state changes
  - On each transition: saves both a compact event row (for analytics/duration tracking) and a full vehicle snapshot (for complete telemetry at the moment of change)
  - Deduplication window (default 10s, configurable) prevents DB flooding during rapid oscillations
  - Runs independently of the WebSocket live refresh — captures events even when no UI is open
- **Database migration 0004**: added `vehicle_events` table (`id`, `vin`, `timestamp`, `event_type`, `field_name`, `old_value`, `new_value`) with indexes on vin, timestamp, and event_type
- **Events API endpoint**: `GET /api/vehicles/{vin}/events?days=30&event_type=regen_start` for querying recorded events
- **Scheduler settings extended**: new configuration fields `transition_detection_enabled`, `transition_poll_interval_seconds`, `transition_min_event_interval_seconds` — exposed via `PUT /api/scheduler` and persisted to DB
- **Frontend: Transition Detection settings card** in Services section — toggle, poll interval, and dedup interval controls
- **Frontend: Events timeline view** in History tab — new "Events" source toggle with filterable timeline showing color-coded events (regen=green, charge=blue, drive=orange, security=purple, SOC=pink), timestamps, and old→new value transitions
- **MQTT: expanded Home Assistant controls** — the MQTT integration now exposes nearly all vehicle commands available in the web UI, up from the previous 4 buttons (lock, unlock, trunk open, find). New entities include:
  - **20 button entities**: lock, unlock, trunk open/close, find, windows open/close, charging start/stop, battery preheat on/off, unlock charger, sunroof open/close, ON3 on/off, BLE key restart, hotspot, autopark, windshield defrost
  - **6 switch entities** (with state feedback): Air Conditioning, Sentry Mode, Steering Wheel Heat, Fuel Heating, Rearview Mirror Heat, Healthy Charging
  - **AC Temperature number entity**: slider control (16–32°C)
  - **Permission gating**: all MQTT entities are only registered if the vehicle has the corresponding right + hardware ability, matching the same permission logic used by the web UI. Vehicles with limited capabilities won't show unsupported controls in HA.
- **MQTT: cloud statistics sensors** — Leapmotor cloud consumption data is now published to Home Assistant via MQTT Discovery. New sensor entities: Consumption Rank (%), Consumption kWh/100km, Weekly Energy Total, Weekly Energy Driving, Weekly Energy A/C, Weekly Energy Other
- **New KPI: "Total charged"** — shows the combined energy from grid charging + regenerative braking
- **New KPI: "Charged (grid)"** — shows only the energy drawn from the electrical grid (used for cost calculation)
- **New KPI: "Regen energy"** — dedicated card showing energy recovered from regenerative braking (kWh), computed from valid positive energy deltas during non-charging segments (with zero-energy gap filtering)
- **History API: `from_date`/`to_date` parameters** — the `/api/vehicles/{vin}/history` endpoint now accepts optional `from_date` and `to_date` (YYYY-MM-DD) query params for fetching only a specific date range of snapshots, enabling much faster on-demand loading
- **History API: server-side downsampling (`max_points`)** — when a date range contains more snapshots than `max_points`, the server returns a downsampled subset that preserves state-transition boundaries (charge start/stop) for accurate KPIs while reducing payload size by 10–20×
- **Downsampling settings** — new configurable setting in Data Collection (Services tab): enable/disable downsampling and choose the max points limit (500–10,000). Saved in local DB and used automatically by the History tab

### Fixed
- **History page extremely slow to load**: the frontend was downloading **all** 35k+ snapshots on every page open (with `days=3650`). Now only today's snapshots + lightweight daily summaries are fetched on initial load; detailed snapshots for other date ranges are fetched on-demand when the user selects a period. This reduces the initial payload from ~15 MB to ~200 KB.
- **No feedback when selecting a date range**: pressing "Select" in the date picker modal gave no visual indication while data was loading. Added a loading spinner and "Loading..." text on the Select button, with the modal staying open until data is ready.
- **Charge limit error reporting**: setting the charge limit from the web UI or Home Assistant returned a plain-text "Internal Server Error" (not JSON), causing the frontend to show a confusing JSON parse error. The `/api/vehicles/{vin}/charge-limit` endpoint now catches `LeapmotorApiError` and returns a proper JSON 502 response with the actual error message. Also hardened the frontend `useApi` helper to gracefully handle non-JSON error responses.
- **Charge limit fails on vehicles without charge plan in status**: on some models (e.g. T03), `status.battery.charge_plan` is empty even when a schedule exists on the cloud. The library's `set_charge_limit()` relied on that field, failing with "Current charging plan is incomplete". Fixed in `leapmotor-api` v0.3.1: the method now retrieves the plan via the dedicated `get_charge_schedule()` API call and falls back to sensible defaults if no schedule exists.
- **Energy KPI calculation completely reworked**: the previous delta-by-delta algorithm was amplifying measurement noise from rapid transition polling (10s intervals), inflating "Energy used" by 5–10× (e.g. showing 47.6 kWh instead of the real 9.3 kWh). Replaced with a segment-based approach that splits snapshots into contiguous charging/non-charging periods and uses net energy change per segment, eliminating oscillation noise.
- **Cost calculation no longer includes regen energy**: charging cost now uses only grid-charged energy, not the total energy entering the battery (which previously included regenerative braking).

### Changed
- **Updated leapmotor-api to v0.3.1**: fixes `set_charge_limit()` for vehicles where the charge plan is not included in the vehicle status response
- The former single `Energy charged` KPI card in history tab is now split into `Total charged` and `Charged (grid)` for better clarity and accurate cost calculation
- `Regen efficiency` now uses the segment-based regen value for accuracy
- **Vehicle usage pie chart now shows percentages**: the "Parked vs In use" doughnut chart previously displayed raw snapshot counts; it now shows percentage values with labels like "Parked (85%)" and "In use (15%)"

## [0.7.3] - 2026-05-26

### Fixed
- Update proxy target from localhost to 127.0.0.1 to fix Docker Compose connectivity issues on some platforms (e.g. Windows 8.1) (fixes #4)
- **Geolocation no longer requested automatically**: the browser geolocation prompt was triggered immediately when opening the Details page or Destination Modal, causing an error on non-HTTPS connections. Now geolocation is only requested when the user clicks the "Locate" button (fixes #5)
- **Destination Modal: added Locate button**: new button on the map (top-left) to manually request the user's position, with loading animation and error toasts
- **MQTT state publishing fixed**: state payloads were never published to Home Assistant because some vehicle status fields (gear, climate mode, charge state, etc.) are returned as plain `int` by the API instead of enum objects. Accessing `.value` on them caused an `AttributeError` that was silently swallowed, preventing all sensor updates. Now uses a safe `_enum_val` helper. Also improved error isolation so discovery, state JSON, and individual sensors are published independently — a failure in one no longer blocks the others. Scheduler MQTT errors now log at WARNING level for visibility. (fixes #7)
- **MQTT dynamic car image auto-load**: the vehicle image package is now automatically downloaded on the first MQTT poll if not already cached, so the HA image entity works without requiring the frontend to be opened first.
- **History data recording fixed for some models (e.g. B10)**: the scheduler snapshot builder crashed on vehicles where `charge_state` is returned as a plain `int` instead of an enum (same `.value` bug as MQTT). Also added null-safety for `battery`, `driving`, `location`, and `climate` sub-objects which may be `None` on some models — previously any missing sub-object would crash the entire snapshot and no history was ever recorded. (fixes #8)

## [0.7.2] - 2026-05-19

### Fixed

- **Missing production dependency**: moved `httpx` from dev dependencies to main dependencies — required at runtime by the ABRP service

## [0.7.1] - 2026-05-16

### Fixed

- **Transient "Information verification failed" error handling**: after a token refresh or re-login, the Leapmotor API can return error code 39 for a few seconds. The vehicle cache now catches this transient error, performs a full re-login (clear auth + login, aligned with leapmotor-ha strategy), and retries once — instead of surfacing the error to the user.
- **Scheduler error logging reduced**: `LeapmotorApiError` in the history scheduler now logs at WARNING (one line) instead of ERROR with full traceback. Unexpected non-API exceptions still log at ERROR with traceback.

## [0.7.0] - 2026-05-16

### Added

- **ABRP integration**: new service to send live vehicle telemetry to [A Better Route Planner](https://abetterrouteplanner.com) for real-time route planning and car model calibration. Sends 20+ data fields (SOC, speed, location, power, temperatures, tire pressures, etc.) with adaptive frequency — every 10s while driving, 30s while charging, 5min while parked
- **ABRP settings UI**: new "ABRP" card in Settings → Services with enable/disable toggle, user token input (with show/hide), and send/error counters
- **ABRP in Services Setup wizard**: ABRP can now be configured during the initial setup flow alongside Data Recording and Home Assistant
- **ABRP status in user menu**: the top-right user menu now shows ABRP service status (Running/Stopped/Disabled) alongside Live Refresh and Home Assistant
- **33 new remote command endpoints**: battery preheat off, sentry mode on/off, start/stop charging, steering wheel heat on/off, fuel heating on/off, rearview mirror heat on/off, healthy charging on/off, ON3 on/off, BLE key restart, sunroof open/close, unlock charger, hotspot, autopark, seat heat, seat ventilation, speed limit, music control, video control, FOTA download/install/schedule, rear seats, prepare car, seat adjust, piloted parking
- **3 new data endpoints**: `GET /api/vehicles/{vin}/charging-history` (paginated charging session history), `GET /api/vehicles/{vin}/consumption/weekly-rank`, `GET /api/vehicles/{vin}/consumption/last-week`
- **Seat Control Modal**: new modal in Dashboard for controlling seat heating and ventilation — supports driver, passenger, rear-left, and rear-right positions with 4 levels (Off/Low/Med/High). Extended with Adjust tab (seat position forward/backward/up/down/recline) and Rear tab (fold/unfold/heat on/off for C16 rear seats)
- **Speed Limit Modal**: new modal to set vehicle speed limit (30–200 km/h slider)
- **Media Control Modal**: new modal for music and video playback (play/pause/next/previous) with music/video tab toggle
- **FOTA Modal**: new modal for firmware-over-the-air operations — download, install, and schedule with task ID input and datetime picker. Includes a safety warning banner
- **Close Trunk command**: added trunk/close button alongside existing trunk/open in Remote Controls
- **Autopark, Piloted Parking, Prepare Car commands**: added as simple action buttons in Vehicle Controls section
- **Full command coverage**: Dashboard now exposes all 51 vehicle command endpoints from the backend API
- **Charge Schedule Modal**: new modal in the Charging section to program the full battery charging schedule — enable/disable, SOC limit slider, start/end time pickers, day-of-week selector (Mon–Sun), repeat weekly toggle, and auto-recharge toggle. Pre-fills from the current charge plan on open. New backend endpoint `POST /api/vehicles/{vin}/charge-schedule` using `leapmotor-api`'s `set_charge_schedule()` method
- **Permission gating for new commands**: all new commands have proper `right` codes assigned — Speed Limit (510), Autopark (150), Piloted Parking (350), Prepare Car (360), Media (270), Firmware (390), Charge Schedule (340) — and are hidden/greyed out when the user lacks the corresponding right or the vehicle lacks the hardware ability
- **Battery preheat moved to Charging section**: battery-preheat and preheat-off buttons relocated from Remote/Vehicle Controls to the Charging section for better organization
- **Grouped Dashboard controls**: remote controls are now organized into 5 sections — Main, Charging, Comfort, Security, and Vehicle — instead of a single flat grid
- **Permission-based control visibility**: Dashboard controls are now filtered by vehicle abilities (hardware support) and user rights (account permissions). Each section shows only the commands the vehicle supports and the user is authorized to use; a per-section toggle button reveals hidden commands (displayed greyed out) with a count badge. The Charge Limit card is also hidden when the user lacks the corresponding right/ability.
- **Details: Charge Plan section**: displays charge limit, scheduled charge status, start/end times, cycles, and recharge flag
- **Details: Seat Comfort section**: shows driver/passenger seat heating and ventilation levels, steering wheel heat status and remaining minutes
- **Details: Security section**: shows security active status, sentry mode, left/right mirror heating, and roof opening
- **Details: expanded Climate info**: interior temperature, right-side temperature, recirculation mode, windshield defrost, rear window heating, climate mode, and AC operate mode
- **Details: expanded Battery info**: precise SoC, minimum battery temperature, healthy charge status, and charge completed flag
- **Details: expanded Driving info**: speed limit with active indicator, parking brake state, live remaining range
- **Details: Ignition ON2** added to Connectivity section
- **New MQTT fields**: seat comfort (6 fields), security (5 fields), additional battery/driving/climate/ignition fields published to Home Assistant
- **Database migration 0003**: added `is_regening` column to `vehicle_snapshots` table for tracking regenerative braking state in history
- **Vehicle Bar toggle**: the vehicle tabs bar below the navbar is now hidden by default when there is only one vehicle and shown when there are multiple vehicles. A toggle in the user menu (top-right) allows manually showing/hiding it. The preference is persisted in localStorage.

### Changed

- **Updated leapmotor-api to v0.3.0**: major library update with 30+ new remote commands, typed enums for permissions/gear/HVAC, new sub-objects (ChargePlan, SeatComfortStatus, SecurityStatus), and expanded vehicle status fields
- **schemas.py rewritten**: all enum fields (`rights`, `abilities`, `module_rights`, `gear_status`, `ac_cooling_and_heating`) now properly serialize enum values; charge plan fields relocated to `battery.charge_plan` sub-object; added `ChargePlanSchema`, `SeatComfortSchema`, and `SecuritySchema`
- **MQTT/HA integration updated**: fixed enum serialization for gear status and HVAC direction; charge plan fields read from new sub-object path; `is_charging` now uses the library's native property instead of a power-based workaround
- **Slow charging detection fixed**: `isSlowCharging` on the Dashboard now checks `charge_state_label === 'CHARGING' && !battery.dc_input_fast_charge` instead of the removed `AC_CONNECTED` label
- **ClimateRequest.windlevel** type changed from `str` to `int` to match the updated library

### Fixed

- **PIN "Remember for this session" now works**: checking the remember checkbox in the PIN dialog persists the PIN flag in `sessionStorage`, so it survives page refreshes. The flag is cleared on logout or new login.
- **PIN dialog hidden behind command modals**: the PIN dialog now renders above command modals (Windows, Sunshade, Climate, Seats) by using a higher z-index.

## [0.6.1] - 2026-05-07

### Changed

- **Updated leapmotor-api to v0.1.7**: adds support for retrieving vehicle status on the B10 model using the same method as the C10

## [0.6.0] - 2026-05-06

### Added

- **Log level control**: you can now change the logging verbosity for the app and the leapmotor-api library separately from Settings → Advanced, without restarting the application
- **Live log viewer**: a new real-time console output panel in Settings → Advanced lets you see application logs directly in the browser for easier troubleshooting. Disabled by default — enable it with a toggle when needed. Includes level filtering, text search, auto-scroll, and a live connection indicator

### Changed

- **Updated leapmotor-api to v0.1.6**

## [0.5.2] - 2026-05-05

### Added

- **Live Refresh**: new background task that automatically refreshes vehicle data at a configurable interval and pushes updates to all connected WebSocket clients — no manual refresh needed. Configurable in Settings → Services with start/stop toggle and interval selector (10–3600 seconds)
- Live Refresh is **active by default** at 30-second intervals for new installations
- Live Refresh status shown in the user menu dropdown (green dot + interval when running, grey dot + "Disabled" when off)
- `GET /api/live-refresh` and `PUT /api/live-refresh` endpoints to query and configure live refresh
- Live Refresh respects the API rate limit — uses the shared vehicle cache to avoid redundant requests

### Fixed

- **Docker build failure**: replaced `COPY --from=ghcr.io/astral-sh/uv:latest` (which required authentication) with a curl-based uv installation that works without registry access

## [0.5.1] - 2026-05-04

### Fixed

- **Messages and car image no longer crash the app**: previously, if your Leapmotor session expired or you skipped the certificate setup, opening the app would show repeated server errors (500). Now the app handles these situations gracefully and shows a clear error instead of breaking

## [0.5.0] - 2026-05-04

### Changed

- **History time filter redesigned**: replaced the period buttons (Today/7d/30d/90d) with a compact toolbar inspired by calendar apps — includes a calendar icon to open a date range picker, a label showing the selected date(s), a "Today" quick-jump pill, left/right arrows to navigate day-by-day, and a three-dot menu with CSV export
- **Date range picker**: the calendar popup now includes a "Last 12 months" preset alongside the existing quick filters (Today, Yesterday, This week/month/quarter/year, Last 7/30/90 days)
- **Removed table view toggle**: the History page now always shows charts (the chart/table switch has been removed)
- **Mobile layout**: title and description are left-aligned on mobile while the date toolbar stays centered
- **Navbar refactored**: the connection badge now shows a cloud icon with "CLOUD" / "OFFLINE" label always visible (including mobile). The refresh button and data freshness indicator are merged into a single color-coded pill. Notifications bell icon is standalone in the navbar. User avatar menu contains cloud disconnect/reconnect, Home Assistant status, and logout
- **User menu redesigned**: cleaner dropdown with improved spacing, backdrop blur, and visual hierarchy. Shows Home Assistant connection status (dot + Online/Offline/Disabled). Cloud disconnect/reconnect button explicitly labeled "Leapmotor Cloud" with confirmation dialog. Removed redundant cloud status (already in topbar badge)

### Added

- **Alembic database migrations**: added a proper migration system using Alembic. Migrations run automatically at startup (async-safe) and can also be managed via CLI (`alembic upgrade head`, `alembic history`). Existing databases are stamped at baseline and upgraded seamlessly
- **Faster History page**: the History tab now shows placeholder shapes while loading, displays summary cards first, and remembers previous data so revisiting the page feels instant
- **Smart API rate limiting**: all data requests to Leapmotor servers now go through a shared cache — no matter how many features need vehicle data (Home Assistant, history recording, dashboard), only one request is made within the configured time window. Configurable in Settings → Account with a dedicated "API Rate Limit" card (default: 10 seconds)
- **Data freshness indicator**: the top navigation bar now shows how old the displayed data is (e.g. "32s ago", "5m ago"), with color coding — green for fresh (< 2 min), yellow for stale (< 10 min), red for old data. Updates every 10 seconds
- **Real-time updates via WebSocket**: when the backend fetches fresh data from Leapmotor (via scheduler, MQTT polling, or any API call), it pushes the new vehicle status to the frontend instantly over a WebSocket connection — no manual refresh needed. The data age badge resets automatically on each push. Auto-reconnects if the connection drops
- **Cloud disconnect/reconnect**: new `POST /api/disconnect` endpoint allows disconnecting from Leapmotor Cloud without logging out — accessible from the user avatar menu with a confirmation prompt
- **Light theme**: full light mode with mint-green tinted palette inspired by the official Leapmotor app. Toggle in user menu and Settings → Preferences. Preference saved to database (default: dark)

### Fixed

- **Dynamic car image broken under HA Ingress**: the static image URL in `DynamicCarImage.vue` used an absolute path (`/api/vehicles/...`) which resolved against the Home Assistant host instead of going through the ingress proxy. Changed to a relative path (`./api/vehicles/...`) consistent with the charge frame fetch URLs
- **Power chart not displaying**: the Charging/Discharging power chart on the History page was always empty because power values were never persisted to the database. Added `charging_power_kw` and `discharge_power_kw` columns (via Alembic migration) so power data from the Leapmotor API is now saved. For historical data collected before this fix, power is derived from stored current × voltage values
- **Vampire drain chart**: added an explanatory message when no drain events are detected, instead of showing an empty chart. Explains that the battery SOC remained stable during parked sessions and describes the conditions needed to trigger the chart
- **Trip map replaced with Leaflet**: the lat/lon scatter chart is now a real interactive map (OpenStreetMap via Leaflet). Shows the route as a polyline color-coded by speed (green ≤40, orange 40–80, red >80 km/h), with Start/End markers and speed tooltips on each point. Supports dark/light tile layers based on theme, and a maximize button to expand the map to full width at 70vh height

## [0.4.1] - 2026-05-04

### Fixed

- **Reverse proxy / subpath support**: the app now works correctly behind Home Assistant Ingress or any reverse proxy that adds a path prefix — all asset and API paths are relative instead of absolute
- History page: period selector and chart/table toggle are now centered on mobile screens

## [0.4.0] - 2026-05-03

### Added

- **HTTPS support**: Docker Compose now serves the app over HTTPS (port 443) with automatic HTTP→HTTPS redirect
- Auto-generated self-signed TLS certificates: a one-shot init container creates certificates on first startup with all local IPs in the SAN, so the app is accessible via `https://<server-ip>` from any device on the network
- `generate-traefik-certs.sh` standalone script for manual certificate regeneration with support for extra IPs/hostnames as arguments
- Traefik dynamic TLS configuration (`traefik/dynamic.yml`)
- **Services setup wizard step**: after entering Leapmotor credentials, the initial setup now offers an optional step to configure Home Assistant (MQTT) and local data recording (history) before entering the app
- Users can enable/disable data recording and set the collection interval directly during first-time setup
- Users can enable Home Assistant, configure MQTT broker settings, and test the connection during first-time setup
- Both services can be skipped and configured later from Settings → Services
- **Home Assistant integration**: your vehicle data (battery, doors, climate, tires, location, and more) is now automatically shared with Home Assistant via MQTT, so you can see everything in your smart home dashboard
- In Settings → Services, you can enable Home Assistant, enter your MQTT broker details, and test the connection before saving
- All vehicle sensors appear in Home Assistant as ready-to-use entities: battery level, mileage, temperatures, tire pressures, door/window status, GPS position, live car image, and remote control buttons
- Vehicle data is sent to Home Assistant automatically every time the app collects new data
- **Separate polling timers**: history collection and Home Assistant updates now run on independent schedules — you can collect history every 15 minutes while pushing updates to HA every 30 seconds, for example
- The Home Assistant polling interval supports sub-minute values (10 sec, 30 sec, etc.) for near-real-time updates in your smart home dashboard
- **HA polling interval exposed as a Home Assistant entity**: you can adjust the polling interval directly from your HA dashboard using a slider (10 s – 3600 s), without opening the webapp
- **Charge limit controllable from Home Assistant**: a new slider entity (50%–100%) lets you set the charge limit directly from HA — the command is sent to the vehicle via the Leapmotor API
- Both ignition states are now exposed in Home Assistant: "Ignition" (key on) and "Ignition Ready" (vehicle ready to drive)
- **About page**: new dedicated "About" section in Settings with app version, GitHub links (source code, star, report issue), and a disclaimer clarifying this is an unofficial project with no affiliation to Leapmotor

### Changed

- **Settings page redesigned**: instead of a long list of cards, settings are now organized in four tabs — Account, General, Services, and Advanced — making it much easier to find what you need
- Credentials, Certificates, MQTT configuration, and Debug data now open in clean popup dialogs instead of expanding inline
- On wider screens, the Credentials and Certificates cards sit side by side in a compact grid
- Settings now use the full available width instead of being limited to a narrow column
- The app version shown in Settings is now read automatically from the project configuration, so it always stays up to date
- The Home Assistant section in Services now includes a polling interval control with +/− stepper (10 sec steps below 1 min, 1 min steps above)

### Fixed

- "Battery Charging" entity in Home Assistant no longer shows true when the car is idle — the check now uses actual charging power instead of a flag that was incorrectly set by the API library

## [0.3.0] - 2026-05-03

### Added

- User preferences system with dedicated `UserPreferences` model and `PreferencesResponse` Pydantic schema
- `GET /api/preferences` and `PUT /api/preferences` endpoints for reading/updating user preferences
- Configurable electricity price (€/kWh) in Settings → Preferences section, stored in DB (default: 0.25)
- History tab "Cost (€)" KPI now uses the user-configured electricity price instead of a hardcoded value
- The app now shows whether the vehicle is plugged in for charging, visible on the dashboard, details page, and vehicle selector
- The battery card on the dashboard now indicates the charging type: "Slow charging (AC)" or "Fast charging (DC)" based on the connection type, with a matching icon
- During setup, if certificate files are already present on the server (e.g. from a previous installation), the app detects them and offers a one-click option to reuse them instead of uploading again
- History tab: new "Today" filter shows individual snapshots (per-collection) instead of daily aggregates
- History tab: "All" filter to display the entire available history
- History tab: table view alongside charts, with toggle
- History tab: hover tooltip on charts now snaps to the nearest point with a visible indicator
- History tab: period buttons (7/30/90 days) are disabled when fewer than 2 days of data are available
- VehicleSnapshot model expanded with full telemetry: battery current/voltage, tire pressures, ignition state, locked/parked status

### Changed

- The data collection scheduler in Settings now has explicit Start/Stop buttons instead of a toggle switch
- Changing the collection interval no longer applies immediately; you pick the desired time first, then confirm with a "Set" button
- The scheduler status now shows the current interval alongside the running state (e.g. "Running · every 15 min")
- `/api/login` endpoint now reads certificate paths from the database instead of environment variables, consistent with the setup flow and auto-connect logic
- History tab defaults to "Today" period on load
- History tab labels translated to English
- SnapshotSchema API response now uses namespaced field names (e.g. `battery_expected_mileage`, `climate_outdoor_temp`) matching the internal model

### Removed

- Removed `.env` / `.env.example` and all `python-dotenv` usage; certificates are now managed entirely via the web UI (`/api/setup/certificates`); `DATA_DIR` and `HISTORY_DB_PATH` can still be set as standard environment variables (e.g. in `docker-compose.yml`)

## [0.2.0] - 2026-05-02

### Added

- **Session-based authentication**: the app now requires login with the LeapConnect password before accessing any data; other devices can no longer auto-enter without authenticating
- `POST /api/auth/login` endpoint: authenticates with LeapConnect user password and sets an HttpOnly session cookie (7-day expiry)
- `POST /api/auth/logout` endpoint: invalidates the session and clears the cookie
- HTTP middleware that blocks all `/api/` routes (except `/api/setup/status`, `/api/setup/user`, `/api/auth/login`) without a valid session cookie
- `LoginView.vue`: password-only login screen shown to returning users who don't have a valid session
- `authenticated` field in `SetupStatusResponse` schema
- `AuthLoginResponse` schema for the login endpoint
- Auto-login on first-time user creation (session cookie set by `POST /api/setup/user`)
- 401 response handler in the frontend API composable — expired sessions redirect to login automatically
- `auth_client` test fixture and session-aware tests (`test_status_requires_session`, `test_vehicles_requires_session`, `test_auth_login_wrong_password`)
- Tests now use a temporary DB (`tmp_path`) to avoid stale state between runs
- Separate LeapConnect user account from Leapmotor API credentials: first-time setup flow is now User → Certificates → Leapmotor credentials
- `UserSetupView.vue`: new first-time setup screen to create a LeapConnect account (display name + password)
- `leapconnect_users` DB table with hashed passwords (PBKDF2-SHA256 + salt) for local account management
- Backend endpoints: `POST /api/setup/user` (create), `GET /api/setup/user` (info), `PUT /api/setup/user` (update with password verification)
- Settings now has 3 separate editable sections: LeapConnect Account, Leapmotor Credentials, Certificates
- Certificate status indicators (installed/missing) in Settings
- `ClimateControlModal` component: consolidated A/C Toggle, Quick Cool, Quick Heat, and Defrost into a single "Climate" modal with quick-action buttons and full parameter controls (temperature 16–32°C, fan level 1–7, mode cool/heat/fan, operate auto/manual, air circulation recirculate/fresh, windshield normal/defrost)
- Backend `ClimateRequest` model with optional climate parameters (`circle`, `mode`, `operate`, `position`, `temperature`, `windlevel`, `wshld`)
- Message notification dropdown in the top navbar with unread badge, inline message preview, infinite scroll, and periodic polling (60s)
- Unread indicator dot on the Messages tab icon in both the sidebar and bottom tab bar
- `unreadMessages` reactive state and `loadUnreadCount()` action in the app store
- `WindowControlModal` component: merged open/close windows into a single control with quick-action buttons and a horizontal slider (0–100%) for precise window positioning; displays per-window state indicators (4 colored dots) with legend
- `SunshadeControlModal` component: merged open/close sunshade into a single control with quick-action buttons and a horizontal slider (0–10) for precise sunshade positioning; shows current sunshade state indicator on the track
- Backend `POST /api/vehicles/{vin}/windows` endpoint accepting a `value` parameter (0–100) for arbitrary window position
- Backend `POST /api/vehicles/{vin}/sunshade` endpoint accepting a `value` parameter (0–10) for arbitrary sunshade position
- `execControl()` in the store now supports an optional request body for parameterized commands
- Active state dot indicator on remote control buttons (pulsing colored dot) for trunk open, lock/unlock, and A/C status
- Raw data viewer in Settings tab with tabbed UI (Vehicle / Status) showing the unprocessed API responses for both `Vehicle.raw` and `VehicleStatus.raw`
- `vehicle_raw` and `status_raw` fields in `FullVehicleDataResponse` API schema
- `raw` field in `VehicleSchema` and `VehicleStatusSchema`

### Changed

- Logout now clears the LeapConnect session only, without disconnecting the Leapmotor API (the background scheduler continues collecting data); user is redirected to the login screen
- All frontend API requests now include `credentials: 'include'` for cookie-based session handling
- Setup flow now requires creating a LeapConnect user first, then uploading certificates, then adding Leapmotor credentials (previously certificates → credentials only)
- Settings "Account" section split into three: LeapConnect Account (display name, password), Leapmotor Credentials (email, password), Certificates (cert/key upload)
- `SetupStatusResponse` and `ConnectionStatusResponse` now include `has_user` and `display_name` fields
- Climate remote controls consolidated from four separate buttons (A/C Toggle, Quick Cool, Quick Heat, Defrost) into a single "Climate" button that opens a dedicated modal; quick actions remain available inside the modal
- Backend climate endpoints (`ac`, `quick-cool`, `quick-heat`, `defrost`) now accept an optional `ClimateRequest` body to forward parameters to the leapmotor-api client
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
