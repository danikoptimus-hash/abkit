"""datasets.source/connection_id/sql_text/fetched_at (DB2, CLAUDE.md dataset-
from-SQL feature): a dataset can now be materialized from a SQL query
against a database_connections row instead of an uploaded file. Existing
rows backfilled to source='upload' (or 'demo' for the demo-generator's
telltale filenames) so the NOT NULL constraint holds for pre-existing data.

Revision ID: 0007
Revises: 0006
Create Date: 2026-07-11
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0007"
down_revision: Union[str, None] = "0006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "datasets", sa.Column("source", sa.Text(), nullable=False, server_default="upload")
    )
    op.add_column(
        "datasets",
        sa.Column(
            "connection_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("database_connections.id", ondelete="SET NULL"), nullable=True,
        ),
    )
    op.add_column("datasets", sa.Column("sql_text", sa.Text(), nullable=True))
    op.add_column("datasets", sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=True))
    op.create_check_constraint(
        "ck_datasets_source", "datasets", "source IN ('upload','sql','demo')"
    )
    op.execute("UPDATE datasets SET source = 'demo' WHERE filename LIKE 'demo\\_%' ESCAPE '\\'")


def downgrade() -> None:
    op.drop_constraint("ck_datasets_source", "datasets", type_="check")
    op.drop_column("datasets", "fetched_at")
    op.drop_column("datasets", "sql_text")
    op.drop_column("datasets", "connection_id")
    op.drop_column("datasets", "source")
