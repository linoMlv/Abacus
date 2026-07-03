"""recurring entries (recurrence) + ecriture.recurrence_id link

Additive migration (§5 Récurrences): a per-association ``recurrence`` table
holding a recurring simple-entry template and its schedule, plus a nullable
``recurrence_id`` on ``ecriture`` linking a generated entry back to its source.

Revision ID: 0021_recurrence
Revises: 0020_banque
Create Date: 2026-07-03 00:00:01.000000

"""

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
import sqlmodel

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0021_recurrence"
down_revision: Union[str, Sequence[str], None] = "0020_banque"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "recurrence",
        sa.Column("id", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column(
            "association_id", sqlmodel.sql.sqltypes.AutoString(), nullable=False
        ),
        sa.Column("libelle", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column(
            "categorie_id", sqlmodel.sql.sqltypes.AutoString(), nullable=False
        ),
        sa.Column(
            "compte_tresorerie_id",
            sqlmodel.sql.sqltypes.AutoString(),
            nullable=False,
        ),
        sa.Column("montant", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("tiers_id", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column(
            "evenement_id", sqlmodel.sql.sqltypes.AutoString(), nullable=True
        ),
        sa.Column(
            "reference_externe", sqlmodel.sql.sqltypes.AutoString(), nullable=True
        ),
        sa.Column(
            "mode_reglement", sqlmodel.sql.sqltypes.AutoString(), nullable=True
        ),
        sa.Column("periodicite", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("prochaine_echeance", sa.Date(), nullable=False),
        sa.Column("date_fin", sa.Date(), nullable=True),
        sa.Column("mode", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("actif", sa.Boolean(), nullable=False),
        sa.Column("created_by", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("derniere_generation", sa.Date(), nullable=True),
        sa.ForeignKeyConstraint(
            ["association_id"],
            ["association.id"],
            name=op.f("fk_recurrence_association_id_association"),
        ),
        sa.ForeignKeyConstraint(
            ["categorie_id"],
            ["categorie_saisie.id"],
            name=op.f("fk_recurrence_categorie_id_categorie_saisie"),
        ),
        sa.ForeignKeyConstraint(
            ["compte_tresorerie_id"],
            ["compte.id"],
            name=op.f("fk_recurrence_compte_tresorerie_id_compte"),
        ),
        sa.ForeignKeyConstraint(
            ["tiers_id"],
            ["tiers.id"],
            name=op.f("fk_recurrence_tiers_id_tiers"),
        ),
        sa.ForeignKeyConstraint(
            ["evenement_id"],
            ["evenement.id"],
            name=op.f("fk_recurrence_evenement_id_evenement"),
        ),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["user.id"],
            name=op.f("fk_recurrence_created_by_user"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_recurrence")),
    )
    op.create_index(
        op.f("ix_recurrence_association_id"),
        "recurrence",
        ["association_id"],
        unique=False,
    )

    op.add_column(
        "ecriture",
        sa.Column(
            "recurrence_id", sqlmodel.sql.sqltypes.AutoString(), nullable=True
        ),
    )
    op.create_index(
        op.f("ix_ecriture_recurrence_id"),
        "ecriture",
        ["recurrence_id"],
        unique=False,
    )
    op.create_foreign_key(
        op.f("fk_ecriture_recurrence_id_recurrence"),
        "ecriture",
        "recurrence",
        ["recurrence_id"],
        ["id"],
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint(
        op.f("fk_ecriture_recurrence_id_recurrence"), "ecriture", type_="foreignkey"
    )
    op.drop_index(op.f("ix_ecriture_recurrence_id"), table_name="ecriture")
    op.drop_column("ecriture", "recurrence_id")
    op.drop_index(op.f("ix_recurrence_association_id"), table_name="recurrence")
    op.drop_table("recurrence")
