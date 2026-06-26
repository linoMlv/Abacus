"""double-entry bookkeeping (ecriture, ligne_ecriture)

Additive migration: per-association accounting vouchers (ecriture) and their
balanced lines (ligne_ecriture) for the V3 double-entry engine (ANC 2018-06).
No existing table is modified.

Revision ID: 0008_double_entry
Revises: 0007_accounting_referential
Create Date: 2026-06-27 00:00:00.000000

"""

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
import sqlmodel

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0008_double_entry"
down_revision: Union[str, Sequence[str], None] = "0007_accounting_referential"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "ecriture",
        sa.Column("id", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column(
            "association_id", sqlmodel.sql.sqltypes.AutoString(), nullable=False
        ),
        sa.Column("exercice_id", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("journal_id", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("numero_piece", sa.Integer(), nullable=False),
        sa.Column("libelle", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("statut", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("origine", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("created_by", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("validated_by", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("validated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["association_id"], ["association.id"]),
        sa.ForeignKeyConstraint(["exercice_id"], ["exercice.id"]),
        sa.ForeignKeyConstraint(["journal_id"], ["journal.id"]),
        sa.ForeignKeyConstraint(["created_by"], ["user.id"]),
        sa.ForeignKeyConstraint(["validated_by"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "association_id", "numero_piece", name="uq_ecriture_assoc_piece"
        ),
    )
    op.create_index(
        op.f("ix_ecriture_association_id"),
        "ecriture",
        ["association_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_ecriture_exercice_id"), "ecriture", ["exercice_id"], unique=False
    )
    op.create_index(
        op.f("ix_ecriture_journal_id"), "ecriture", ["journal_id"], unique=False
    )

    op.create_table(
        "ligne_ecriture",
        sa.Column("id", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("ecriture_id", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("compte_id", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("libelle", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("debit", sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column("credit", sa.Numeric(precision=10, scale=2), nullable=False),
        sa.ForeignKeyConstraint(["ecriture_id"], ["ecriture.id"]),
        sa.ForeignKeyConstraint(["compte_id"], ["compte.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_ligne_ecriture_ecriture_id"),
        "ligne_ecriture",
        ["ecriture_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_ligne_ecriture_compte_id"),
        "ligne_ecriture",
        ["compte_id"],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(
        op.f("ix_ligne_ecriture_compte_id"), table_name="ligne_ecriture"
    )
    op.drop_index(
        op.f("ix_ligne_ecriture_ecriture_id"), table_name="ligne_ecriture"
    )
    op.drop_table("ligne_ecriture")

    op.drop_index(op.f("ix_ecriture_journal_id"), table_name="ecriture")
    op.drop_index(op.f("ix_ecriture_exercice_id"), table_name="ecriture")
    op.drop_index(op.f("ix_ecriture_association_id"), table_name="ecriture")
    op.drop_table("ecriture")
