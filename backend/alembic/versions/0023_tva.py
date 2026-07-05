"""optional VAT (régime TVA)

Additive migration for the optional VAT support (§4):

* ``association.regime_tva`` — whether the association is subject to VAT
  (default false: VAT is off and entirely hidden until switched on).
* ``categorie_saisie.tva_taux`` — the category's default VAT rate.
* ``ligne_ecriture.tva_taux`` / ``tva_montant`` — the rate and extracted VAT
  amount carried by the taxable-base line.

Revision ID: 0023_tva
Revises: 0022_ligne_bancaire_fitid
Create Date: 2026-07-05 00:00:00.000000

"""

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0023_tva"
down_revision: Union[str, Sequence[str], None] = "0022_ligne_bancaire_fitid"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "association",
        sa.Column(
            "regime_tva",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    op.add_column(
        "categorie_saisie",
        sa.Column("tva_taux", sa.Numeric(precision=5, scale=2), nullable=True),
    )
    op.add_column(
        "ligne_ecriture",
        sa.Column("tva_taux", sa.Numeric(precision=5, scale=2), nullable=True),
    )
    op.add_column(
        "ligne_ecriture",
        sa.Column("tva_montant", sa.Numeric(precision=10, scale=2), nullable=True),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("ligne_ecriture", "tva_montant")
    op.drop_column("ligne_ecriture", "tva_taux")
    op.drop_column("categorie_saisie", "tva_taux")
    op.drop_column("association", "regime_tva")
