"""fiscal receipt cancellation flag (recu_fiscal.annule)

Additive migration: a receipt is cancelled, never hard-deleted, so its order
number is never reused. ``annule`` marks a cancelled receipt (its dons are freed
but the numbered row stays).

Revision ID: 0025_recu_annule
Revises: 0024_recu_fiscal
Create Date: 2026-07-05 00:00:00.000000

"""

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0025_recu_annule"
down_revision: Union[str, Sequence[str], None] = "0024_recu_fiscal"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "recu_fiscal",
        sa.Column("annule", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("recu_fiscal", "annule")
