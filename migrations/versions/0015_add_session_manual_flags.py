"""add cost_manual/energy_manual columns to charging_session_costs

Revision ID: 0015
Revises: 0014
Create Date: 2026-10-26
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0015"
down_revision: str | None = "0014"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("charging_session_costs") as batch_op:
        batch_op.add_column(
            sa.Column(
                "cost_manual", sa.Boolean(), nullable=False, server_default=sa.false()
            )
        )
        batch_op.add_column(
            sa.Column(
                "energy_manual", sa.Boolean(), nullable=False, server_default=sa.false()
            )
        )


def downgrade() -> None:
    with op.batch_alter_table("charging_session_costs") as batch_op:
        batch_op.drop_column("energy_manual")
        batch_op.drop_column("cost_manual")
