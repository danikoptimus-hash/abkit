"""users.strata_balance_expanded: per-user "strata balance table expanded" flag

Segment-combinations package §3: the analysis strata-balance table is collapsed
by default when it has many strata (> 12) — showing only a summary line
("N strata · balance chi-square p=X.XX · passed/failed") — but the user's choice
to expand it should persist, exactly like folders_panel_collapsed (migration
0018). This is per-user preference №2, and per the rule documented in 0018 the
answer to "one more flag" is another additive typed BOOLEAN column, not a switch
to JSONB (reconsider only if several land at once).

server_default=false — collapsed/not-expanded by default (the product decision
"collapsed when many strata"). Existing users get the same as new ones. The flag
only matters when the table is long enough to be collapsed in the first place
(<= 12 strata always renders expanded regardless).

Revision ID: 0019
Revises: 0018
Create Date: 2026-07-20
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0019"
down_revision: Union[str, None] = "0018"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "strata_balance_expanded",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )


def downgrade() -> None:
    op.drop_column("users", "strata_balance_expanded")
