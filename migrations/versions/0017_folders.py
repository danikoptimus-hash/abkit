"""folders + experiments.folder_id (item 5, folders package) — additive:
one new table, one new nullable FK column on experiments. One level deep by
design (no subfolders in v1, CLAUDE.md) — folders.name is plain Text unique
(not CITEXT like tags.name, see abkit/db/models.py::Folder for why exact-
case uniqueness is what's wanted here). folder_id is ON DELETE SET NULL —
deleting a folder never deletes or touches the experiments in it, they just
move back to "Uncategorized" (folder_id IS NULL), same non-destructive
pattern as datasets.experiment_id (migration 0012).

Revision ID: 0017
Revises: 0016
Create Date: 2026-07-16
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0017"
down_revision: Union[str, None] = "0016"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "folders",
        sa.Column(
            "id", postgresql.UUID(as_uuid=True), primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("name", sa.Text(), nullable=False, unique=True),
        sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "created_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.add_column(
        "experiments",
        sa.Column(
            "folder_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("folders.id", ondelete="SET NULL"), nullable=True,
        ),
    )
    op.create_index("ix_experiments_folder", "experiments", ["folder_id"])


def downgrade() -> None:
    op.drop_index("ix_experiments_folder", table_name="experiments")
    op.drop_column("experiments", "folder_id")
    op.drop_table("folders")
