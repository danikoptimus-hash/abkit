"""experiment_flow_images (Stage 4, CLAUDE.md — variant flow screenshots) —
additive: one new table, nothing existing changes. Unlike datasets
(ON DELETE SET NULL — independent entities), these images are part of the
test itself: ON DELETE CASCADE, and their on-disk files live under the
experiment's own data directory so run_delete_experiment's existing
shutil.rmtree() already removes them alongside the DB rows.

Revision ID: 0014
Revises: 0013
Create Date: 2026-07-12
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0014"
down_revision: Union[str, None] = "0013"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "experiment_flow_images",
        sa.Column(
            "id", postgresql.UUID(as_uuid=True), primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "experiment_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("experiments.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column("group_name", sa.Text(), nullable=False),
        sa.Column("flow_title", sa.Text(), nullable=False, server_default=""),
        sa.Column("file_path", sa.Text(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "uploaded_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True,
        ),
        sa.Column("uploaded_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index(
        "ix_experiment_flow_images_experiment_group",
        "experiment_flow_images",
        ["experiment_id", "group_name", "position"],
    )


def downgrade() -> None:
    op.drop_index("ix_experiment_flow_images_experiment_group", table_name="experiment_flow_images")
    op.drop_table("experiment_flow_images")
