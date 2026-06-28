"""events (evenement) + ecriture.evenement_id

Additive migration: a per-association ``evenement`` table (analytic axis, §15.6)
and an optional, indexed ``evenement_id`` on ``ecriture`` so an entry can be
tagged to an action/project. The event table is created before the referencing
column. No existing table is modified.

Revision ID: 0016_evenement
Revises: 0015_justificatif
Create Date: 2026-06-28 00:00:05.000000

"""

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
import sqlmodel

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0016_evenement"
down_revision: Union[str, Sequence[str], None] = "0015_justificatif"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "evenement",
        sa.Column("id", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column(
            "association_id", sqlmodel.sql.sqltypes.AutoString(), nullable=False
        ),
        sa.Column("nom", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column(
            "description", sqlmodel.sql.sqltypes.AutoString(), nullable=True
        ),
        sa.Column("date_debut", sa.Date(), nullable=True),
        sa.Column("date_fin", sa.Date(), nullable=True),
        sa.Column("budget_recettes", sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column("budget_depenses", sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column("statut", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("couleur", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["association_id"],
            ["association.id"],
            name=op.f("fk_evenement_association_id_association"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_evenement")),
        sa.UniqueConstraint("association_id", "nom", name="uq_evenement_assoc_nom"),
    )
    op.create_index(
        op.f("ix_evenement_association_id"),
        "evenement",
        ["association_id"],
        unique=False,
    )

    op.add_column(
        "ecriture",
        sa.Column("evenement_id", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
    )
    op.create_index(
        op.f("ix_ecriture_evenement_id"), "ecriture", ["evenement_id"], unique=False
    )
    op.create_foreign_key(
        op.f("fk_ecriture_evenement_id_evenement"),
        "ecriture",
        "evenement",
        ["evenement_id"],
        ["id"],
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint(
        op.f("fk_ecriture_evenement_id_evenement"), "ecriture", type_="foreignkey"
    )
    op.drop_index(op.f("ix_ecriture_evenement_id"), table_name="ecriture")
    op.drop_column("ecriture", "evenement_id")
    op.drop_index(op.f("ix_evenement_association_id"), table_name="evenement")
    op.drop_table("evenement")
