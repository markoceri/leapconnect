"""add zone_name column to charging_session_costs

Revision ID: 0014
Revises: 0013
Create Date: 2026-06-15
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0014"
down_revision: str | None = "0013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("charging_session_costs") as batch_op:
        batch_op.add_column(
            sa.Column("zone_name", sa.String(length=128), nullable=True)
        )


def downgrade() -> None:
    with op.batch_alter_table("charging_session_costs") as batch_op:
        batch_op.drop_column("zone_name")
