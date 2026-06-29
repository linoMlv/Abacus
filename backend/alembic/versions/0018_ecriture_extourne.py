"""contre-passation link on ecriture (extourne_de_id)

Additive migration for entry correction (plan §10): an optional, indexed
self-referential ``ecriture.extourne_de_id`` pointing to the entry a reversal
(origine EXTOURNE) contre-passes. Nullable — set only on extourne entries; no
existing column is dropped or made stricter.

Revision ID: 0018_ecriture_extourne
Revises: 0017_permission_preset
Create Date: 2026-06-29 00:00:00.000000

"""

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
import sqlmodel

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0018_ecriture_extourne"
down_revision: Union[str, Sequence[str], None] = "0017_permission_preset"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "ecriture",
        sa.Column(
            "extourne_de_id", sqlmodel.sql.sqltypes.AutoString(), nullable=True
        ),
    )
    op.create_index(
        op.f("ix_ecriture_extourne_de_id"),
        "ecriture",
        ["extourne_de_id"],
        unique=False,
    )
    op.create_foreign_key(
        op.f("fk_ecriture_extourne_de_id_ecriture"),
        "ecriture",
        "ecriture",
        ["extourne_de_id"],
        ["id"],
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint(
        op.f("fk_ecriture_extourne_de_id_ecriture"),
        "ecriture",
        type_="foreignkey",
    )
    op.drop_index(op.f("ix_ecriture_extourne_de_id"), table_name="ecriture")
    op.drop_column("ecriture", "extourne_de_id")
