"""experiment_datasets link table (DB3, CLAUDE.md dataset-centric model):
a dataset can now be used by more than one experiment, and the SAME
experiment can use different datasets for different purposes (design/
analyze/validate) — datasets.experiment_id/kind (single link) stay as the
PRIMARY/first association for backward-compatible reads (design-dataset
lookup etc.), this table is the authoritative multi-use record going
forward, populated whenever a dataset is actually used by
design/analyze/validate (see abkit/jobs.py).

Revision ID: 0008
Revises: 0007
Create Date: 2026-07-12
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0008"
down_revision: Union[str, None] = "0007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "experiment_datasets",
        sa.Column(
            "id", postgresql.UUID(as_uuid=True), primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "experiment_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("experiments.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column(
            "dataset_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("datasets.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint(
            "kind IN ('pre_design','post_analysis','validation')", name="ck_experiment_datasets_kind"
        ),
        sa.UniqueConstraint(
            "experiment_id", "dataset_id", "kind", name="ux_experiment_datasets_experiment_dataset_kind"
        ),
    )
    op.create_index(
        "ix_experiment_datasets_experiment", "experiment_datasets", ["experiment_id"]
    )
    op.create_index("ix_experiment_datasets_dataset", "experiment_datasets", ["dataset_id"])

    # Backfill: existing single-link datasets (experiment_id/kind already
    # set) become their own first experiment_datasets row, so new code that
    # queries this table sees pre-migration data too.
    op.execute(
        """
        INSERT INTO experiment_datasets (experiment_id, dataset_id, kind)
        SELECT experiment_id, id, kind FROM datasets WHERE experiment_id IS NOT NULL
        ON CONFLICT DO NOTHING
        """
    )


def downgrade() -> None:
    op.drop_index("ix_experiment_datasets_dataset", table_name="experiment_datasets")
    op.drop_index("ix_experiment_datasets_experiment", table_name="experiment_datasets")
    op.drop_table("experiment_datasets")
