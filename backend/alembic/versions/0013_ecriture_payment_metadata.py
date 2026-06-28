"""payment metadata on ecriture (reference_externe, mode_reglement)

Additive migration: optional, purely informative "Avancé" metadata on an entry
(§15.3) — an external reference (supplier invoice n°…) and a payment method.
Neither affects the accounting. Both nullable; no existing column is modified.

Revision ID: 0013_ecriture_payment_metadata
Revises: 0012_ecriture_categorie
Create Date: 2026-06-28 00:00:02.000000

"""

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
import sqlmodel

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0013_ecriture_payment_metadata"
down_revision: Union[str, Sequence[str], None] = "0012_ecriture_categorie"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "ecriture",
        sa.Column(
            "reference_externe", sqlmodel.sql.sqltypes.AutoString(), nullable=True
        ),
    )
    op.add_column(
        "ecriture",
        sa.Column(
            "mode_reglement", sqlmodel.sql.sqltypes.AutoString(), nullable=True
        ),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("ecriture", "mode_reglement")
    op.drop_column("ecriture", "reference_externe")
