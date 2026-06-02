"""add charging price tiers, time bands, and session costs

Revision ID: 0007
Revises: 0006
Create Date: 2026-06-03
"""

from __future__ import annotations

import json
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0007"
down_revision: str | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

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
    {"days": [5], "start_hour": 7, "start_min": 0, "end_hour": 23, "end_min": 0},
]
F3_SCHEDULE = [
    {
        "days": [0, 1, 2, 3, 4, 5],
        "start_hour": 23,
        "start_min": 0,
        "end_hour": 7,
        "end_min": 0,
    },
    {"days": [6], "start_hour": 0, "start_min": 0, "end_hour": 24, "end_min": 0},
]


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    # -- charging_price_tiers --
    if "charging_price_tiers" not in inspector.get_table_names():
        op.create_table(
            "charging_price_tiers",
            sa.Column("id", sa.String(32), primary_key=True),
            sa.Column("label", sa.String(128), nullable=False),
            sa.Column("price_kwh", sa.Float(), nullable=False, server_default="0.0"),
            sa.Column("enabled", sa.Boolean(), nullable=False, server_default="1"),
        )

    # -- charging_time_bands --
    if "charging_time_bands" not in inspector.get_table_names():
        op.create_table(
            "charging_time_bands",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column(
                "tier_id", sa.String(32), nullable=False, server_default="home_grid"
            ),
            sa.Column("name", sa.String(128), nullable=False),
            sa.Column("price_kwh", sa.Float(), nullable=False, server_default="0.0"),
            sa.Column("schedule", sa.Text(), nullable=False, server_default="[]"),
            sa.Column("color", sa.String(32), nullable=True),
            sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
        )

    # -- charging_session_costs --
    if "charging_session_costs" not in inspector.get_table_names():
        op.create_table(
            "charging_session_costs",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("vin", sa.String(20), nullable=False, index=True),
            sa.Column("start_ts", sa.DateTime(), nullable=False, index=True),
            sa.Column("end_ts", sa.DateTime(), nullable=True),
            sa.Column("tier_id", sa.String(32), nullable=False),
            sa.Column("time_band_id", sa.Integer(), nullable=True),
            sa.Column("energy_kwh", sa.Float(), nullable=True),
            sa.Column("cost", sa.Float(), nullable=True),
            sa.Column("note", sa.String(256), nullable=True),
        )

    # -- Seed default tiers --
    # Migrate existing electricity_price_kwh setting if available
    result = bind.execute(
        sa.text("SELECT value FROM app_settings WHERE key = 'electricity_price_kwh'")
    )
    row = result.fetchone()
    home_grid_price = float(row[0]) if row else 0.25

    # Check if tiers already seeded
    result = bind.execute(sa.text("SELECT COUNT(*) FROM charging_price_tiers"))
    if result.scalar() == 0:
        bind.execute(
            sa.text(
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

    # -- Seed default time bands --
    result = bind.execute(sa.text("SELECT COUNT(*) FROM charging_time_bands"))
    if result.scalar() == 0:
        bind.execute(
            sa.text(
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


def downgrade() -> None:
    op.drop_table("charging_session_costs")
    op.drop_table("charging_time_bands")
    op.drop_table("charging_price_tiers")
