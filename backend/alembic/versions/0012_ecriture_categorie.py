"""record the assisted-entry category on ecriture (categorie_id)

Additive migration: an entry created from the assisted screen remembers the
plain-language category it came from (null on manual entries), enabling
"by category" views. The accounting truth stays on the lines. No existing column
is modified.

Revision ID: 0012_ecriture_categorie
Revises: 0011_compte_tresorerie
Create Date: 2026-06-28 00:00:01.000000

"""

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
import sqlmodel

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0012_ecriture_categorie"
down_revision: Union[str, Sequence[str], None] = "0011_compte_tresorerie"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "ecriture",
        sa.Column("categorie_id", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
    )
    op.create_index(
        op.f("ix_ecriture_categorie_id"), "ecriture", ["categorie_id"], unique=False
    )
    op.create_foreign_key(
        op.f("fk_ecriture_categorie_id_categorie_saisie"),
        "ecriture",
        "categorie_saisie",
        ["categorie_id"],
        ["id"],
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint(
        op.f("fk_ecriture_categorie_id_categorie_saisie"),
        "ecriture",
        type_="foreignkey",
    )
    op.drop_index(op.f("ix_ecriture_categorie_id"), table_name="ecriture")
    op.drop_column("ecriture", "categorie_id")
