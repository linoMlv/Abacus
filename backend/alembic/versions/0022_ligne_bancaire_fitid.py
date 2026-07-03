"""bank line dedup key (ligne_bancaire.fitid)

Additive migration: a nullable ``fitid`` on ``ligne_bancaire`` holding the OFX
transaction id (null for CSV imports), used to skip a movement already imported
for the same treasury account.

Revision ID: 0022_ligne_bancaire_fitid
Revises: 0021_recurrence
Create Date: 2026-07-04 00:00:00.000000

"""

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
import sqlmodel

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0022_ligne_bancaire_fitid"
down_revision: Union[str, Sequence[str], None] = "0021_recurrence"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "ligne_bancaire",
        sa.Column("fitid", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
    )
    op.create_index(
        op.f("ix_ligne_bancaire_fitid"),
        "ligne_bancaire",
        ["fitid"],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f("ix_ligne_bancaire_fitid"), table_name="ligne_bancaire")
    op.drop_column("ligne_bancaire", "fitid")
