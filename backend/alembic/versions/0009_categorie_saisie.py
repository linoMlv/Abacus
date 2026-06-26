"""assisted-entry categories (categorie_saisie)

Additive migration: per-association plain-language entry categories bridging the
simple "recette / dépense" screen to the chart of accounts. Seeded at
association creation; no existing table is modified.

Revision ID: 0009_categorie_saisie
Revises: 0008_double_entry
Create Date: 2026-06-27 00:00:01.000000

"""

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
import sqlmodel

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0009_categorie_saisie"
down_revision: Union[str, Sequence[str], None] = "0008_double_entry"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "categorie_saisie",
        sa.Column("id", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column(
            "association_id", sqlmodel.sql.sqltypes.AutoString(), nullable=False
        ),
        sa.Column("sens", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("libelle", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("compte_id", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("journal_id", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("ordre", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["association_id"], ["association.id"]),
        sa.ForeignKeyConstraint(["compte_id"], ["compte.id"]),
        sa.ForeignKeyConstraint(["journal_id"], ["journal.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "association_id", "libelle", name="uq_categorie_assoc_libelle"
        ),
    )
    op.create_index(
        op.f("ix_categorie_saisie_association_id"),
        "categorie_saisie",
        ["association_id"],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(
        op.f("ix_categorie_saisie_association_id"), table_name="categorie_saisie"
    )
    op.drop_table("categorie_saisie")
