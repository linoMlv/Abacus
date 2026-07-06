"""budget (prévu/réalisé by category, per exercice)

Additive migration for the fiscal-year budget (Phase 5, §15.5):

* ``budget`` — one budget per (association, exercice).
* ``ligne_budget`` — the prévu amount for one category within a budget
  (unique per category). The réalisé is never stored; it is recomputed from
  the ledger.

Revision ID: 0026_budget
Revises: 0025_recu_annule
Create Date: 2026-07-06 00:00:00.000000

"""

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
import sqlmodel

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0026_budget"
down_revision: Union[str, Sequence[str], None] = "0025_recu_annule"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_STR = sqlmodel.sql.sqltypes.AutoString


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "budget",
        sa.Column("id", _STR(), nullable=False),
        sa.Column("association_id", _STR(), nullable=False),
        sa.Column("exercice_id", _STR(), nullable=False),
        sa.ForeignKeyConstraint(["association_id"], ["association.id"]),
        sa.ForeignKeyConstraint(["exercice_id"], ["exercice.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "association_id", "exercice_id", name="uq_budget_assoc_exercice"
        ),
    )
    op.create_index(op.f("ix_budget_association_id"), "budget", ["association_id"])
    op.create_index(op.f("ix_budget_exercice_id"), "budget", ["exercice_id"])

    op.create_table(
        "ligne_budget",
        sa.Column("id", _STR(), nullable=False),
        sa.Column("budget_id", _STR(), nullable=False),
        sa.Column("categorie_id", _STR(), nullable=False),
        sa.Column("montant_prevu", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.ForeignKeyConstraint(["budget_id"], ["budget.id"]),
        sa.ForeignKeyConstraint(["categorie_id"], ["categorie_saisie.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("budget_id", "categorie_id", name="uq_ligne_budget_cat"),
    )
    op.create_index(op.f("ix_ligne_budget_budget_id"), "ligne_budget", ["budget_id"])
    op.create_index(
        op.f("ix_ligne_budget_categorie_id"), "ligne_budget", ["categorie_id"]
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f("ix_ligne_budget_categorie_id"), "ligne_budget")
    op.drop_index(op.f("ix_ligne_budget_budget_id"), "ligne_budget")
    op.drop_table("ligne_budget")
    op.drop_index(op.f("ix_budget_exercice_id"), "budget")
    op.drop_index(op.f("ix_budget_association_id"), "budget")
    op.drop_table("budget")
