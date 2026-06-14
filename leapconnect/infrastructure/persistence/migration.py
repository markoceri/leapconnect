"""Startup schema management: Alembic upgrade + self-healing fallbacks."""

from __future__ import annotations

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
