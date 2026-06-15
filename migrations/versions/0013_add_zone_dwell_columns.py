"""add dwell/absence alert columns to geofences (zones)

Revision ID: 0013
Revises: 0012
Create Date: 2026-06-15
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0013"
down_revision: str | None = "0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("geofences") as batch_op:
        batch_op.add_column(
            sa.Column(
                "dwell_alert_minutes",
                sa.Integer(),
                nullable=False,
                server_default="0",
            )
        )
        batch_op.add_column(
            sa.Column(
                "absence_alert_minutes",
                sa.Integer(),
                nullable=False,
                server_default="0",
            )
        )


def downgrade() -> None:
    with op.batch_alter_table("geofences") as batch_op:
        batch_op.drop_column("absence_alert_minutes")
        batch_op.drop_column("dwell_alert_minutes")
