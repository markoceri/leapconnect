"""add maintenance source tracking, repos and packs tables

Revision ID: 0010
Revises: 0009
Create Date: 2026-06-06
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0010"
down_revision: str | None = "0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Track where each plan item originated from.
    with op.batch_alter_table("maintenance_plan_items") as batch:
        batch.add_column(
            sa.Column(
                "source",
                sa.String(16),
                nullable=False,
                server_default="catalog",
            )
        )
        batch.add_column(sa.Column("source_ref", sa.String(128), nullable=True))

    # Community repositories the user has added.
    op.create_table(
        "maintenance_repos",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("type", sa.String(16), nullable=False, server_default="github"),
        sa.Column("url", sa.String(512), nullable=False),
        sa.Column("name", sa.String(128), nullable=True),
        sa.Column("author", sa.String(128), nullable=True),
        sa.Column("description", sa.String(512), nullable=True),
        sa.Column("branch", sa.String(64), nullable=True),
        sa.Column("added_at", sa.DateTime(), nullable=True),
        sa.Column("last_fetched_at", sa.DateTime(), nullable=True),
        sa.Column("etag", sa.String(128), nullable=True),
        sa.Column("status", sa.String(32), nullable=False, server_default="ok"),
        sa.Column("manifest_json", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("url", name="uq_repo_url"),
    )

    # Cached maintenance packs (downloaded from a repo, URL or uploaded file).
    op.create_table(
        "maintenance_packs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("repo_id", sa.Integer(), nullable=True),
        sa.Column("slug", sa.String(128), nullable=False),
        sa.Column("name", sa.String(128), nullable=True),
        sa.Column("version", sa.Integer(), nullable=True),
        sa.Column("author", sa.String(128), nullable=True),
        sa.Column("model_compat", sa.Text(), nullable=True),
        sa.Column("payload_json", sa.Text(), nullable=False),
        sa.Column("fetched_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_packs_repo_id", "maintenance_packs", ["repo_id"])


def downgrade() -> None:
    op.drop_table("maintenance_packs")
    op.drop_table("maintenance_repos")
    with op.batch_alter_table("maintenance_plan_items") as batch:
        batch.drop_column("source_ref")
        batch.drop_column("source")
