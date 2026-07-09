"""narrative annexe rubrics (annexe_rubrique)

Additive migration: a single per-association ``annexe_rubrique`` table holding
the free-text sections of an exercice's annexe (comptes annuels ANC). Each row
belongs to one exercice and carries a title, body and display order. The default
ANC rubric set is seeded lazily on first read, so no data migration is needed.

Revision ID: 0028_annexe_rubrique
Revises: 0027_api_key
Create Date: 2026-07-09 00:00:00.000000

"""

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
import sqlmodel

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0028_annexe_rubrique"
down_revision: Union[str, Sequence[str], None] = "0027_api_key"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_STR = sqlmodel.sql.sqltypes.AutoString


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "annexe_rubrique",
        sa.Column("id", _STR(), nullable=False),
        sa.Column("association_id", _STR(), nullable=False),
        sa.Column("exercice_id", _STR(), nullable=False),
        sa.Column("titre", _STR(), nullable=False),
        sa.Column("contenu", _STR(), nullable=False),
        sa.Column("ordre", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["association_id"], ["association.id"]),
        sa.ForeignKeyConstraint(["exercice_id"], ["exercice.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_annexe_rubrique_association_id"),
        "annexe_rubrique",
        ["association_id"],
    )
    op.create_index(
        op.f("ix_annexe_rubrique_exercice_id"),
        "annexe_rubrique",
        ["exercice_id"],
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f("ix_annexe_rubrique_exercice_id"), "annexe_rubrique")
    op.drop_index(op.f("ix_annexe_rubrique_association_id"), "annexe_rubrique")
    op.drop_table("annexe_rubrique")
