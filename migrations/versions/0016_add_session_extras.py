"""add charging_session_extras and manual_price_kwh

Revision ID: 0016
Revises: 0015
Create Date: 2026-10-26
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0016"
down_revision: str | None = "0015"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("charging_session_costs") as batch_op:
        batch_op.add_column(sa.Column("manual_price_kwh", sa.Float(), nullable=True))
    # create_all at startup may have created the table already
    if sa.inspect(op.get_bind()).has_table("charging_session_extras"):
        return
    op.create_table(
        "charging_session_extras",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("session_cost_id", sa.Integer(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(length=16), nullable=False),
        sa.Column("label", sa.String(length=64), nullable=False),
        sa.Column("included", sa.Boolean(), nullable=False),
        sa.Column("amount", sa.Float(), nullable=True),
        sa.Column("rate", sa.Float(), nullable=True),
        sa.Column("time_unit", sa.String(length=8), nullable=False),
        sa.Column("billing", sa.String(length=8), nullable=False),
        sa.Column("start_ref", sa.String(length=16), nullable=False),
        sa.Column("start_offset_min", sa.Integer(), nullable=False),
        sa.Column("end_ref", sa.String(length=16), nullable=False),
        sa.Column("duration_min", sa.Integer(), nullable=True),
        sa.Column("cap", sa.Float(), nullable=True),
        sa.Column("minutes", sa.Integer(), nullable=True),
        sa.Column("cost", sa.Float(), nullable=True),
    )
    op.create_index(
        "ix_charging_session_extras_session_cost_id",
        "charging_session_extras",
        ["session_cost_id"],
    )


def downgrade() -> None:
    op.drop_table("charging_session_extras")
    with op.batch_alter_table("charging_session_costs") as batch_op:
        batch_op.drop_column("manual_price_kwh")
