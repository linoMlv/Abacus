"""bank statement import & reconciliation (import_releve, ligne_bancaire)

Additive migration (§5 Banque): two per-association tables. ``import_releve`` is
one import batch bound to a treasury account; ``ligne_bancaire`` is a statement
movement, optionally lettré to an accounting entry. No existing table is modified.

Revision ID: 0020_banque
Revises: 0019_drop_legacy_v2_tables
Create Date: 2026-07-03 00:00:00.000000

"""

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
import sqlmodel

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0020_banque"
down_revision: Union[str, Sequence[str], None] = "0019_drop_legacy_v2_tables"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "import_releve",
        sa.Column("id", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column(
            "association_id", sqlmodel.sql.sqltypes.AutoString(), nullable=False
        ),
        sa.Column("compte_id", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("filename", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("nb_lignes", sa.Integer(), nullable=False),
        sa.Column(
            "imported_by", sqlmodel.sql.sqltypes.AutoString(), nullable=True
        ),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["association_id"],
            ["association.id"],
            name=op.f("fk_import_releve_association_id_association"),
        ),
        sa.ForeignKeyConstraint(
            ["compte_id"],
            ["compte.id"],
            name=op.f("fk_import_releve_compte_id_compte"),
        ),
        sa.ForeignKeyConstraint(
            ["imported_by"],
            ["user.id"],
            name=op.f("fk_import_releve_imported_by_user"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_import_releve")),
    )
    op.create_index(
        op.f("ix_import_releve_association_id"),
        "import_releve",
        ["association_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_import_releve_compte_id"),
        "import_releve",
        ["compte_id"],
        unique=False,
    )

    op.create_table(
        "ligne_bancaire",
        sa.Column("id", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column(
            "association_id", sqlmodel.sql.sqltypes.AutoString(), nullable=False
        ),
        sa.Column("import_id", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("compte_id", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("date_operation", sa.Date(), nullable=False),
        sa.Column("libelle", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column(
            "montant", sa.Numeric(precision=12, scale=2), nullable=False
        ),
        sa.Column("statut", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column(
            "ecriture_id", sqlmodel.sql.sqltypes.AutoString(), nullable=True
        ),
        sa.Column(
            "rapproche_by", sqlmodel.sql.sqltypes.AutoString(), nullable=True
        ),
        sa.Column("rapproche_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(
            ["association_id"],
            ["association.id"],
            name=op.f("fk_ligne_bancaire_association_id_association"),
        ),
        sa.ForeignKeyConstraint(
            ["import_id"],
            ["import_releve.id"],
            name=op.f("fk_ligne_bancaire_import_id_import_releve"),
        ),
        sa.ForeignKeyConstraint(
            ["compte_id"],
            ["compte.id"],
            name=op.f("fk_ligne_bancaire_compte_id_compte"),
        ),
        sa.ForeignKeyConstraint(
            ["ecriture_id"],
            ["ecriture.id"],
            name=op.f("fk_ligne_bancaire_ecriture_id_ecriture"),
        ),
        sa.ForeignKeyConstraint(
            ["rapproche_by"],
            ["user.id"],
            name=op.f("fk_ligne_bancaire_rapproche_by_user"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_ligne_bancaire")),
    )
    op.create_index(
        op.f("ix_ligne_bancaire_association_id"),
        "ligne_bancaire",
        ["association_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_ligne_bancaire_import_id"),
        "ligne_bancaire",
        ["import_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_ligne_bancaire_compte_id"),
        "ligne_bancaire",
        ["compte_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_ligne_bancaire_ecriture_id"),
        "ligne_bancaire",
        ["ecriture_id"],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f("ix_ligne_bancaire_ecriture_id"), table_name="ligne_bancaire")
    op.drop_index(op.f("ix_ligne_bancaire_compte_id"), table_name="ligne_bancaire")
    op.drop_index(op.f("ix_ligne_bancaire_import_id"), table_name="ligne_bancaire")
    op.drop_index(
        op.f("ix_ligne_bancaire_association_id"), table_name="ligne_bancaire"
    )
    op.drop_table("ligne_bancaire")
    op.drop_index(op.f("ix_import_releve_compte_id"), table_name="import_releve")
    op.drop_index(op.f("ix_import_releve_association_id"), table_name="import_releve")
    op.drop_table("import_releve")
