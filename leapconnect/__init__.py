"""LeapConnect — Leapmotor vehicle dashboard.

Package layout (hexagonal architecture):

- ``leapconnect.domain``         — pure domain model (no framework imports)
- ``leapconnect.application``    — use cases and ports
- ``leapconnect.infrastructure`` — driven adapters (DB, cloud API, MQTT, …)
- ``leapconnect.api``            — driving adapter (FastAPI)

See ``docs/ARCHITECTURE.md`` for the full picture.
"""
