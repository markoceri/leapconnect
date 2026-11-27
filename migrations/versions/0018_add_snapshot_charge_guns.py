"""add the charging-gun signals to the vehicle snapshots

Revision ID: 0018
Revises: 0017
Create Date: 2026-11-27
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0018"
down_revision: str | None = "0017"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("vehicle_snapshots") as batch_op:
        batch_op.add_column(
            sa.Column("dc_input_fast_charge", sa.Integer(), nullable=True)
        )
        batch_op.add_column(
            sa.Column("ac_input_slow_charge", sa.Integer(), nullable=True)
        )


def downgrade() -> None:
    with op.batch_alter_table("vehicle_snapshots") as batch_op:
        batch_op.drop_column("ac_input_slow_charge")
        batch_op.drop_column("dc_input_fast_charge")
