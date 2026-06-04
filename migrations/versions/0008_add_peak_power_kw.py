"""add peak_power_kw column to charging_session_costs

Revision ID: 0008
Revises: 0007
Create Date: 2026-06-04
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0008"
down_revision: str | None = "0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("charging_session_costs") as batch_op:
        batch_op.add_column(sa.Column("peak_power_kw", sa.Float(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("charging_session_costs") as batch_op:
        batch_op.drop_column("peak_power_kw")
