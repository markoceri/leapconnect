"""add shape_type and points columns to geofences

Revision ID: 0011
Revises: 0010
Create Date: 2026-06-11
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0011"
down_revision: str | None = "0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("geofences") as batch_op:
        batch_op.add_column(
            sa.Column(
                "shape_type",
                sa.String(length=16),
                nullable=False,
                server_default="circle",
            )
        )
        batch_op.add_column(sa.Column("points_json", sa.Text(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("geofences") as batch_op:
        batch_op.drop_column("points_json")
        batch_op.drop_column("shape_type")
