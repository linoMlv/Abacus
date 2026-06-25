"""accounting referential (compte, journal, exercice)

Additive migration: per-association chart of accounts, journals and fiscal
years for the V3 double-entry accounting (ANC 2018-06). Seeded at association
creation; no existing table is modified.

Revision ID: 0007_accounting_referential
Revises: 0006_log_entry_association
Create Date: 2026-06-26 00:00:02.000000

"""

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
import sqlmodel

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0007_accounting_referential"
down_revision: Union[str, Sequence[str], None] = "0006_log_entry_association"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "compte",
        sa.Column("id", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column(
            "association_id", sqlmodel.sql.sqltypes.AutoString(), nullable=False
        ),
        sa.Column("numero", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("libelle", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("classe", sa.Integer(), nullable=False),
        sa.Column("type", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(["association_id"], ["association.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "association_id", "numero", name="uq_compte_assoc_numero"
        ),
    )
    op.create_index(
        op.f("ix_compte_association_id"), "compte", ["association_id"], unique=False
    )
    op.create_index(op.f("ix_compte_numero"), "compte", ["numero"], unique=False)

    op.create_table(
        "journal",
        sa.Column("id", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column(
            "association_id", sqlmodel.sql.sqltypes.AutoString(), nullable=False
        ),
        sa.Column("code", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("libelle", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.ForeignKeyConstraint(["association_id"], ["association.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "association_id", "code", name="uq_journal_assoc_code"
        ),
    )
    op.create_index(
        op.f("ix_journal_association_id"),
        "journal",
        ["association_id"],
        unique=False,
    )

    op.create_table(
        "exercice",
        sa.Column("id", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column(
            "association_id", sqlmodel.sql.sqltypes.AutoString(), nullable=False
        ),
        sa.Column("libelle", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("date_debut", sa.Date(), nullable=False),
        sa.Column("date_fin", sa.Date(), nullable=False),
        sa.Column("statut", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("report_a_nouveau_genere", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(["association_id"], ["association.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_exercice_association_id"),
        "exercice",
        ["association_id"],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f("ix_exercice_association_id"), table_name="exercice")
    op.drop_table("exercice")

    op.drop_index(op.f("ix_journal_association_id"), table_name="journal")
    op.drop_table("journal")

    op.drop_index(op.f("ix_compte_numero"), table_name="compte")
    op.drop_index(op.f("ix_compte_association_id"), table_name="compte")
    op.drop_table("compte")
