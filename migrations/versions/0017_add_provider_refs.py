"""add charging provider references to session costs and extras

Revision ID: 0017
Revises: 0016
Create Date: 2026-11-26
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0017"
down_revision: str | None = "0016"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("charging_session_costs") as batch_op:
        batch_op.add_column(
            sa.Column("external_source", sa.String(length=16), nullable=True)
        )
        batch_op.add_column(
            sa.Column("external_id", sa.String(length=64), nullable=True)
        )
        batch_op.add_column(
            sa.Column(
                "auto_link_disabled",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            )
        )
        batch_op.create_index("ix_charging_session_costs_external_id", ["external_id"])
    with op.batch_alter_table("charging_session_extras") as batch_op:
        batch_op.add_column(sa.Column("source", sa.String(length=16), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("charging_session_extras") as batch_op:
        batch_op.drop_column("source")
    with op.batch_alter_table("charging_session_costs") as batch_op:
        batch_op.drop_index("ix_charging_session_costs_external_id")
        batch_op.drop_column("auto_link_disabled")
        batch_op.drop_column("external_id")
        batch_op.drop_column("external_source")
