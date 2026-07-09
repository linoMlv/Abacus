"""per-account login lockout (user.failed_login_count, user.locked_until)

Additive migration: two columns on ``user`` backing the brute-force lockout —
a counter of consecutive failed logins and the instant until which login is
refused once the threshold is crossed. Existing rows default to 0 / NULL (never
locked).

Revision ID: 0029_login_lockout
Revises: 0028_annexe_rubrique
Create Date: 2026-07-09 00:00:01.000000

"""

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0029_login_lockout"
down_revision: Union[str, Sequence[str], None] = "0028_annexe_rubrique"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "user",
        sa.Column(
            "failed_login_count",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
    )
    op.add_column("user", sa.Column("locked_until", sa.DateTime(), nullable=True))
    # Drop the server_default now that existing rows are backfilled: the ORM
    # always supplies the value on insert.
    op.alter_column("user", "failed_login_count", server_default=None)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("user", "locked_until")
    op.drop_column("user", "failed_login_count")
