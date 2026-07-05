"""fiscal receipts (dons) + fiscal identity

Additive migration for donation tax receipts (§8):

* ``association`` gains its fiscal identity (address, RNA, SIRET, objet).
* ``tiers`` gains an optional postal address (for a donor's receipt).
* ``recu_fiscal`` (the receipt) and ``recu_fiscal_ligne`` (its links to the
  donation entries, unique per entry) tables.

Revision ID: 0024_recu_fiscal
Revises: 0023_tva
Create Date: 2026-07-05 00:00:00.000000

"""

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
import sqlmodel

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0024_recu_fiscal"
down_revision: Union[str, Sequence[str], None] = "0023_tva"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_STR = sqlmodel.sql.sqltypes.AutoString


def upgrade() -> None:
    """Upgrade schema."""
    for col in ("adresse", "code_postal", "ville", "rna", "siret", "objet"):
        op.add_column("association", sa.Column(col, _STR(), nullable=True))
    for col in ("adresse", "code_postal", "ville"):
        op.add_column("tiers", sa.Column(col, _STR(), nullable=True))

    op.create_table(
        "recu_fiscal",
        sa.Column("id", _STR(), nullable=False),
        sa.Column("association_id", _STR(), nullable=False),
        sa.Column("numero", sa.Integer(), nullable=False),
        sa.Column("tiers_id", _STR(), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("annee", sa.Integer(), nullable=False),
        sa.Column("montant", sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column("forme", _STR(), nullable=False),
        sa.Column("mode_reglement", _STR(), nullable=True),
        sa.Column("created_by", _STR(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["association_id"], ["association.id"]),
        sa.ForeignKeyConstraint(["tiers_id"], ["tiers.id"]),
        sa.ForeignKeyConstraint(["created_by"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("association_id", "numero", name="uq_recu_assoc_numero"),
    )
    op.create_index(
        op.f("ix_recu_fiscal_association_id"), "recu_fiscal", ["association_id"]
    )
    op.create_index(op.f("ix_recu_fiscal_tiers_id"), "recu_fiscal", ["tiers_id"])

    op.create_table(
        "recu_fiscal_ligne",
        sa.Column("id", _STR(), nullable=False),
        sa.Column("recu_fiscal_id", _STR(), nullable=False),
        sa.Column("ecriture_id", _STR(), nullable=False),
        sa.ForeignKeyConstraint(["recu_fiscal_id"], ["recu_fiscal.id"]),
        sa.ForeignKeyConstraint(["ecriture_id"], ["ecriture.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("ecriture_id", name="uq_recu_ligne_ecriture"),
    )
    op.create_index(
        op.f("ix_recu_fiscal_ligne_recu_fiscal_id"),
        "recu_fiscal_ligne",
        ["recu_fiscal_id"],
    )
    op.create_index(
        op.f("ix_recu_fiscal_ligne_ecriture_id"),
        "recu_fiscal_ligne",
        ["ecriture_id"],
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f("ix_recu_fiscal_ligne_ecriture_id"), "recu_fiscal_ligne")
    op.drop_index(op.f("ix_recu_fiscal_ligne_recu_fiscal_id"), "recu_fiscal_ligne")
    op.drop_table("recu_fiscal_ligne")
    op.drop_index(op.f("ix_recu_fiscal_tiers_id"), "recu_fiscal")
    op.drop_index(op.f("ix_recu_fiscal_association_id"), "recu_fiscal")
    op.drop_table("recu_fiscal")
    for col in ("adresse", "code_postal", "ville"):
        op.drop_column("tiers", col)
    for col in ("objet", "siret", "rna", "ville", "code_postal", "adresse"):
        op.drop_column("association", col)
