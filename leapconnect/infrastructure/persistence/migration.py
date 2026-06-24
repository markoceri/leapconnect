"""Startup schema management: Alembic upgrade + self-healing fallbacks."""

from __future__ import annotations

import json

from sqlalchemy import text


def run_alembic_upgrade(sync_conn) -> None:
    """Run pending Alembic migrations on a sync connection."""
    from pathlib import Path

    import sqlalchemy
    from alembic.config import Config
    from alembic.migration import MigrationContext
    from alembic.operations import Operations
    from alembic.script import ScriptDirectory

    from leapconnect.config import ROOT_DIR

    base_dir = Path(ROOT_DIR)
    alembic_cfg = Config(str(base_dir / "alembic.ini"))
    alembic_cfg.set_main_option("script_location", str(base_dir / "migrations"))
    script = ScriptDirectory.from_config(alembic_cfg)

    # If alembic_version doesn't exist, determine if this is a fresh DB
    # (created by create_all with full schema) or a pre-alembic DB.
    inspector = sqlalchemy.inspect(sync_conn)
    if not inspector.has_table("alembic_version"):
        sync_conn.execute(
            text("CREATE TABLE alembic_version (  version_num VARCHAR(32) NOT NULL)")
        )
        # If the table already has columns from later migrations,
        # it was created by create_all — stamp at head.
        columns = {c["name"] for c in inspector.get_columns("vehicle_snapshots")}
        if inspector.has_table("vehicle_events"):
            stamp_rev = script.get_current_head()
        elif "is_regening" in columns:
            stamp_rev = "0003"
        elif "charging_power_kw" in columns:
            stamp_rev = "0002"
        else:
            stamp_rev = "0001"
        sync_conn.execute(
            text("INSERT INTO alembic_version (version_num) VALUES (:rev)"),
            {"rev": stamp_rev},
        )

    # Run pending migrations
    context = MigrationContext.configure(sync_conn, opts={"render_as_batch": True})
    current_rev = context.get_current_revision()
    head_rev = script.get_current_head()

    if current_rev != head_rev:
        # Detect tables that may have been pre-created by Base.metadata.create_all
        # but whose migrations haven't been stamped yet.
        _known_create_all_tables = {
            "maintenance_plan_items",
            "maintenance_records",
            "maintenance_repos",
            "maintenance_packs",
        }
        existing_tables = set(inspector.get_table_names())
        pre_created = _known_create_all_tables & existing_tables

        if pre_created:
            # Tables already exist from create_all — stamp to head to
            # avoid "table already exists" errors from Alembic.
            _LOGGER = __import__("logging").getLogger(__name__)
            _LOGGER.info(
                "Tables %s already present — stamping Alembic to head (%s)",
                pre_created,
                head_rev,
            )
            sync_conn.execute(
                text("DELETE FROM alembic_version"),
            )
            sync_conn.execute(
                text("INSERT INTO alembic_version (version_num) VALUES (:rev)"),
                {"rev": head_rev},
            )

        # Re-check after possible stamp
        current_rev = context.get_current_revision()
        if current_rev != head_rev:

            def do_upgrade(revision, context):
                return script._upgrade_revs(head_rev, revision)

            with Operations.context(context):
                context._migrations_fn = do_upgrade
                context.run_migrations()

    # Self-healing: ensure additive columns exist even when a prior boot
    # stamped Alembic past a migration that ALTERs a pre-existing table.
    # The create_all + "stamp to head" path skips ALTER TABLE migrations
    # (e.g. 0010 adding maintenance_plan_items.source), leaving the DB
    # marked up-to-date but missing columns. Reconcile them idempotently.
    reconcile = sqlalchemy.inspect(sync_conn)
    if reconcile.has_table("maintenance_plan_items"):
        cols = {c["name"] for c in reconcile.get_columns("maintenance_plan_items")}
        if "source" not in cols:
            sync_conn.execute(
                text(
                    "ALTER TABLE maintenance_plan_items "
                    "ADD COLUMN source VARCHAR(16) NOT NULL DEFAULT 'catalog'"
                )
            )
        if "source_ref" not in cols:
            sync_conn.execute(
                text(
                    "ALTER TABLE maintenance_plan_items "
                    "ADD COLUMN source_ref VARCHAR(128)"
                )
            )

        # The (vin, service_type) unique constraint is also skipped when the
        # table was pre-created by create_all (which lacked it) and 0009 got
        # stamped. De-duplicate any rows that slipped in, then enforce it.
        indexes = {ix["name"] for ix in reconcile.get_indexes("maintenance_plan_items")}
        if "uq_vin_service_type" not in indexes:
            sync_conn.execute(
                text(
                    "DELETE FROM maintenance_plan_items WHERE id NOT IN ("
                    "  SELECT MIN(id) FROM maintenance_plan_items "
                    "  GROUP BY vin, service_type)"
                )
            )
            sync_conn.execute(
                text(
                    "CREATE UNIQUE INDEX IF NOT EXISTS uq_vin_service_type "
                    "ON maintenance_plan_items (vin, service_type)"
                )
            )

    # Self-healing for geofences: migration 0011 (ALTER TABLE adding
    # shape_type/points_json) is skipped when the create_all + "stamp to
    # head" path runs, leaving the DB marked up-to-date but missing the
    # columns. Add them idempotently.
    geo_inspect = sqlalchemy.inspect(sync_conn)
    if geo_inspect.has_table("geofences"):
        geo_cols = {c["name"] for c in geo_inspect.get_columns("geofences")}
        if "shape_type" not in geo_cols:
            sync_conn.execute(
                text(
                    "ALTER TABLE geofences "
                    "ADD COLUMN shape_type VARCHAR(16) NOT NULL DEFAULT 'circle'"
                )
            )
        if "points_json" not in geo_cols:
            sync_conn.execute(text("ALTER TABLE geofences ADD COLUMN points_json TEXT"))
        # 0012: charging_tier_id (zone tier auto-selection). Skipped on the
        # create_all + "stamp to head" path; add it idempotently.
        if "charging_tier_id" not in geo_cols:
            sync_conn.execute(
                text("ALTER TABLE geofences ADD COLUMN charging_tier_id VARCHAR(32)")
            )
        # 0013: dwell/absence alert thresholds (per-zone minutes).
        if "dwell_alert_minutes" not in geo_cols:
            sync_conn.execute(
                text(
                    "ALTER TABLE geofences "
                    "ADD COLUMN dwell_alert_minutes INTEGER NOT NULL DEFAULT 0"
                )
            )
        if "absence_alert_minutes" not in geo_cols:
            sync_conn.execute(
                text(
                    "ALTER TABLE geofences "
                    "ADD COLUMN absence_alert_minutes INTEGER NOT NULL DEFAULT 0"
                )
            )

    # Self-healing for charging_session_costs: 0014 adds zone_name. Add it
    # idempotently when the create_all + "stamp to head" path skipped the ALTER.
    sc_inspect = sqlalchemy.inspect(sync_conn)
    if sc_inspect.has_table("charging_session_costs"):
        sc_cols = {c["name"] for c in sc_inspect.get_columns("charging_session_costs")}
        if "zone_name" not in sc_cols:
            sync_conn.execute(
                text(
                    "ALTER TABLE charging_session_costs "
                    "ADD COLUMN zone_name VARCHAR(128)"
                )
            )

    # Self-healing: seed default charging price tiers and time-of-use bands.
    # Migration 0007's upgrade() seeds these, but when Base.metadata.create_all
    # pre-creates the tables and Alembic gets stamped to head (because
    # vehicle_events already exists), the upgrade function never runs, leaving
    # the tables empty. Seed idempotently here so every installation has the
    # default tiers regardless of the boot path.
    ct_inspect = sqlalchemy.inspect(sync_conn)
    if ct_inspect.has_table("charging_price_tiers"):
        result = sync_conn.execute(text("SELECT COUNT(*) FROM charging_price_tiers"))
        if result.scalar() == 0:
            # Read the user's electricity price if already set, else default
            price_result = sync_conn.execute(
                text(
                    "SELECT value FROM app_settings WHERE key = 'electricity_price_kwh'"
                )
            )
            price_row = price_result.fetchone()
            home_grid_price = float(price_row[0]) if price_row else 0.25

            sync_conn.execute(
                text(
                    "INSERT INTO charging_price_tiers"
                    " (id, label, price_kwh, enabled)"
                    " VALUES (:id, :label, :price, :enabled)"
                ),
                [
                    {
                        "id": "home_grid",
                        "label": "Home (grid)",
                        "price": home_grid_price,
                        "enabled": True,
                    },
                    {
                        "id": "home_solar",
                        "label": "Home (solar)",
                        "price": 0.0,
                        "enabled": False,
                    },
                    {
                        "id": "public_ac",
                        "label": "Public AC",
                        "price": 0.40,
                        "enabled": True,
                    },
                    {
                        "id": "public_dc",
                        "label": "Public DC (fast)",
                        "price": 0.55,
                        "enabled": True,
                    },
                ],
            )

    # Self-healing: seed default time-of-use bands for home_grid (Italian ARERA).
    if ct_inspect.has_table("charging_time_bands"):
        result = sync_conn.execute(text("SELECT COUNT(*) FROM charging_time_bands"))
        if result.scalar() == 0:
            # Default Italian ARERA time-of-use schedules
            F1_SCHEDULE = [
                {
                    "days": [0, 1, 2, 3, 4],
                    "start_hour": 8,
                    "start_min": 0,
                    "end_hour": 19,
                    "end_min": 0,
                }
            ]
            F2_SCHEDULE = [
                {
                    "days": [0, 1, 2, 3, 4],
                    "start_hour": 7,
                    "start_min": 0,
                    "end_hour": 8,
                    "end_min": 0,
                },
                {
                    "days": [0, 1, 2, 3, 4],
                    "start_hour": 19,
                    "start_min": 0,
                    "end_hour": 23,
                    "end_min": 0,
                },
                {
                    "days": [5],
                    "start_hour": 7,
                    "start_min": 0,
                    "end_hour": 23,
                    "end_min": 0,
                },
            ]
            F3_SCHEDULE = [
                {
                    "days": [0, 1, 2, 3, 4, 5],
                    "start_hour": 23,
                    "start_min": 0,
                    "end_hour": 7,
                    "end_min": 0,
                },
                {
                    "days": [6],
                    "start_hour": 0,
                    "start_min": 0,
                    "end_hour": 24,
                    "end_min": 0,
                },
            ]
            sync_conn.execute(
                text(
                    "INSERT INTO charging_time_bands"
                    " (tier_id, name, price_kwh, schedule, color, position)"
                    " VALUES (:tier_id, :name, :price, :schedule, :color, :pos)"
                ),
                [
                    {
                        "tier_id": "home_grid",
                        "name": "F1 Peak",
                        "price": 0.30,
                        "schedule": json.dumps(F1_SCHEDULE),
                        "color": "#ef4444",
                        "pos": 1,
                    },
                    {
                        "tier_id": "home_grid",
                        "name": "F2 Mid-Peak",
                        "price": 0.27,
                        "schedule": json.dumps(F2_SCHEDULE),
                        "color": "#f59e0b",
                        "pos": 2,
                    },
                    {
                        "tier_id": "home_grid",
                        "name": "F3 Off-Peak",
                        "price": 0.22,
                        "schedule": json.dumps(F3_SCHEDULE),
                        "color": "#22c55e",
                        "pos": 3,
                    },
                ],
            )
