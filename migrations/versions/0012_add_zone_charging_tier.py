"""add charging_tier_id column to geofences (zones)

Revision ID: 0012
Revises: 0011
Create Date: 2026-06-13
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0012"
down_revision: str | None = "0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("geofences") as batch_op:
        batch_op.add_column(
            sa.Column("charging_tier_id", sa.String(length=32), nullable=True)
        )


def downgrade() -> None:
    with op.batch_alter_table("geofences") as batch_op:
        batch_op.drop_column("charging_tier_id")
