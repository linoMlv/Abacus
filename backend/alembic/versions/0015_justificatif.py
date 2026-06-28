"""supporting documents (justificatif)

Additive migration: a per-association ``justificatif`` table holding the
metadata of a file attached to an entry (the bytes live behind a FileStorage,
addressed by ``storage_key``). No existing table is modified.

Revision ID: 0015_justificatif
Revises: 0014_tiers
Create Date: 2026-06-28 00:00:04.000000

"""

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
import sqlmodel

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0015_justificatif"
down_revision: Union[str, Sequence[str], None] = "0014_tiers"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "justificatif",
        sa.Column("id", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column(
            "association_id", sqlmodel.sql.sqltypes.AutoString(), nullable=False
        ),
        sa.Column(
            "ecriture_id", sqlmodel.sql.sqltypes.AutoString(), nullable=True
        ),
        sa.Column("filename", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column(
            "content_type", sqlmodel.sql.sqltypes.AutoString(), nullable=False
        ),
        sa.Column("size", sa.Integer(), nullable=False),
        sa.Column(
            "storage_key", sqlmodel.sql.sqltypes.AutoString(), nullable=False
        ),
        sa.Column(
            "uploaded_by", sqlmodel.sql.sqltypes.AutoString(), nullable=True
        ),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["association_id"],
            ["association.id"],
            name=op.f("fk_justificatif_association_id_association"),
        ),
        sa.ForeignKeyConstraint(
            ["ecriture_id"],
            ["ecriture.id"],
            name=op.f("fk_justificatif_ecriture_id_ecriture"),
        ),
        sa.ForeignKeyConstraint(
            ["uploaded_by"],
            ["user.id"],
            name=op.f("fk_justificatif_uploaded_by_user"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_justificatif")),
    )
    op.create_index(
        op.f("ix_justificatif_association_id"),
        "justificatif",
        ["association_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_justificatif_ecriture_id"),
        "justificatif",
        ["ecriture_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_justificatif_storage_key"),
        "justificatif",
        ["storage_key"],
        unique=True,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f("ix_justificatif_storage_key"), table_name="justificatif")
    op.drop_index(op.f("ix_justificatif_ecriture_id"), table_name="justificatif")
    op.drop_index(op.f("ix_justificatif_association_id"), table_name="justificatif")
    op.drop_table("justificatif")
