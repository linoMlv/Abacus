"""api keys for MCP machine access (Phase 6, §7)

Additive migration: a single ``api_key`` table. Each key is bound to a
``membership`` (the identity/role it acts as) and denormalises ``association_id``
for tenant-scoped listing. Only the SHA-256 hash of the secret is stored. The
legacy V2 ``api_key`` table was dropped in 0019; this is an unrelated V3 shape.

Revision ID: 0027_api_key
Revises: 0026_budget
Create Date: 2026-07-07 00:00:00.000000

"""

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
import sqlmodel

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0027_api_key"
down_revision: Union[str, Sequence[str], None] = "0026_budget"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_STR = sqlmodel.sql.sqltypes.AutoString


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "api_key",
        sa.Column("id", _STR(), nullable=False),
        sa.Column("association_id", _STR(), nullable=False),
        sa.Column("membership_id", _STR(), nullable=False),
        sa.Column("name", _STR(), nullable=False),
        sa.Column("prefix", _STR(), nullable=False),
        sa.Column("key_hash", _STR(), nullable=False),
        sa.Column("created_by", _STR(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("last_used_at", sa.DateTime(), nullable=True),
        sa.Column("revoked_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["association_id"], ["association.id"]),
        sa.ForeignKeyConstraint(["membership_id"], ["membership.id"]),
        sa.ForeignKeyConstraint(["created_by"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_api_key_association_id"), "api_key", ["association_id"])
    op.create_index(op.f("ix_api_key_membership_id"), "api_key", ["membership_id"])
    op.create_index(op.f("ix_api_key_key_hash"), "api_key", ["key_hash"], unique=True)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f("ix_api_key_key_hash"), "api_key")
    op.drop_index(op.f("ix_api_key_membership_id"), "api_key")
    op.drop_index(op.f("ix_api_key_association_id"), "api_key")
    op.drop_table("api_key")
