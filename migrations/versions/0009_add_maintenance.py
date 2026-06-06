"""add maintenance plan items and records tables

Revision ID: 0009
Revises: 0008
Create Date: 2026-06-06
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0009"
down_revision: str | None = "0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "maintenance_plan_items",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("vin", sa.String(20), nullable=False),
        sa.Column("service_type", sa.String(64), nullable=False),
        sa.Column("label", sa.String(128), nullable=False),
        sa.Column("category", sa.String(32), nullable=False, server_default="other"),
        sa.Column("interval_km", sa.Integer(), nullable=True),
        sa.Column("interval_months", sa.Integer(), nullable=True),
        sa.Column("trigger_mode", sa.String(8), nullable=False, server_default="or"),
        sa.Column("priority", sa.String(16), nullable=False, server_default="routine"),
        sa.Column("last_done_km", sa.Integer(), nullable=True),
        sa.Column("last_done_date", sa.DateTime(), nullable=True),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column("notes", sa.String(256), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("vin", "service_type", name="uq_vin_service_type"),
    )
    op.create_index("ix_plan_items_vin", "maintenance_plan_items", ["vin"])

    op.create_table(
        "maintenance_records",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("vin", sa.String(20), nullable=False),
        sa.Column("service_type", sa.String(64), nullable=False),
        sa.Column("label", sa.String(128), nullable=False),
        sa.Column("timestamp", sa.DateTime(), nullable=False),
        sa.Column("mileage_km", sa.Integer(), nullable=True),
        sa.Column("cost", sa.Float(), nullable=True),
        sa.Column("provider", sa.String(128), nullable=True),
        sa.Column("notes", sa.String(256), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_records_vin", "maintenance_records", ["vin"])
    op.create_index("ix_records_vin_ts", "maintenance_records", ["vin", "timestamp"])


def downgrade() -> None:
    op.drop_table("maintenance_records")
    op.drop_table("maintenance_plan_items")
