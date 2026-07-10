"""analysis_results.dataset_id: RESTRICT (implicit, no ondelete was ever
specified) -> SET NULL (UX package, Datasets §2.2: deleting a dataset must
not be blocked by — nor break — the results of experiments that already
analyzed it). Since SET NULL means dataset_id itself goes null the moment
the dataset is deleted, a separate dataset_filename column freezes the name
at analyze time so "what was analyzed" survives regardless — results.json
is meant to be self-sufficient, this makes the Results tab's display of it
actually live up to that instead of degrading to "unknown dataset".

Revision ID: 0009
Revises: 0008
Create Date: 2026-07-11
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0009"
down_revision: Union[str, None] = "0008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_FK_NAME = "analysis_results_dataset_id_fkey"


def upgrade() -> None:
    op.drop_constraint(_FK_NAME, "analysis_results", type_="foreignkey")
    op.create_foreign_key(
        _FK_NAME, "analysis_results", "datasets", ["dataset_id"], ["id"], ondelete="SET NULL"
    )
    op.add_column("analysis_results", sa.Column("dataset_filename", sa.Text(), nullable=True))
    # Backfill from the still-live join for existing rows — best-effort,
    # NULL stays NULL for rows whose dataset is already gone.
    op.execute(
        """
        UPDATE analysis_results ar
        SET dataset_filename = d.filename
        FROM datasets d
        WHERE ar.dataset_id = d.id
        """
    )


def downgrade() -> None:
    op.drop_column("analysis_results", "dataset_filename")
    op.drop_constraint(_FK_NAME, "analysis_results", type_="foreignkey")
    op.create_foreign_key(_FK_NAME, "analysis_results", "datasets", ["dataset_id"], ["id"])
