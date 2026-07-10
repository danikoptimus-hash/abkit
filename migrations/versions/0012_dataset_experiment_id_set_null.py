"""datasets.experiment_id: CASCADE -> SET NULL (6-part package pt.6, CLAUDE.md
"датасеты — самостоятельные сущности, живут независимо от экспериментов").
Deleting an experiment must not delete the datasets it used — only the
assignments/results/blocks that belong to it, plus the experiment_datasets
link rows (those keep their own CASCADE, unaffected here — the link records
a use, not the dataset's existence). abkit/jobs.py::run_delete_experiment's
matching file-unlink loop is removed in the same package — the dataset row
now survives, so its file on disk must too.

Revision ID: 0012
Revises: 0011
Create Date: 2026-07-14
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "0012"
down_revision: Union[str, None] = "0011"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_FK_NAME = "datasets_experiment_id_fkey"


def upgrade() -> None:
    op.drop_constraint(_FK_NAME, "datasets", type_="foreignkey")
    op.create_foreign_key(
        _FK_NAME, "datasets", "experiments", ["experiment_id"], ["id"], ondelete="SET NULL"
    )


def downgrade() -> None:
    op.drop_constraint(_FK_NAME, "datasets", type_="foreignkey")
    op.create_foreign_key(
        _FK_NAME, "datasets", "experiments", ["experiment_id"], ["id"], ondelete="CASCADE"
    )
