"""third parties (tiers) + ecriture.tiers_id

Additive migration: a lightweight per-association ``tiers`` table (supplier,
member/client, donor, funder…) and an optional, indexed ``tiers_id`` on
``ecriture`` so an assisted entry can remember the third party it is with
(§3 / §15.3). The tiers table is created before the referencing column.

Revision ID: 0014_tiers
Revises: 0013_ecriture_payment_metadata
Create Date: 2026-06-28 00:00:03.000000

"""

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
import sqlmodel

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0014_tiers"
down_revision: Union[str, Sequence[str], None] = "0013_ecriture_payment_metadata"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "tiers",
        sa.Column("id", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column(
            "association_id", sqlmodel.sql.sqltypes.AutoString(), nullable=False
        ),
        sa.Column("type", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("nom", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["association_id"],
            ["association.id"],
            name=op.f("fk_tiers_association_id_association"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_tiers")),
        sa.UniqueConstraint("association_id", "nom", name="uq_tiers_assoc_nom"),
    )
    op.create_index(
        op.f("ix_tiers_association_id"), "tiers", ["association_id"], unique=False
    )

    op.add_column(
        "ecriture",
        sa.Column("tiers_id", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
    )
    op.create_index(
        op.f("ix_ecriture_tiers_id"), "ecriture", ["tiers_id"], unique=False
    )
    op.create_foreign_key(
        op.f("fk_ecriture_tiers_id_tiers"),
        "ecriture",
        "tiers",
        ["tiers_id"],
        ["id"],
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint(
        op.f("fk_ecriture_tiers_id_tiers"), "ecriture", type_="foreignkey"
    )
    op.drop_index(op.f("ix_ecriture_tiers_id"), table_name="ecriture")
    op.drop_column("ecriture", "tiers_id")
    op.drop_index(op.f("ix_tiers_association_id"), table_name="tiers")
    op.drop_table("tiers")
