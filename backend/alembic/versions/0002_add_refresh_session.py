"""add refresh_session

Additive migration: introduces the refresh_session table backing revocable
refresh tokens. No existing table is modified.

Revision ID: 0002_add_refresh_session
Revises: 2419cf9e8202
Create Date: 2026-06-18 00:00:01.000000

"""

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
import sqlmodel

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0002_add_refresh_session"
down_revision: Union[str, Sequence[str], None] = "2419cf9e8202"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "refresh_session",
        sa.Column("id", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column(
            "association_id", sqlmodel.sql.sqltypes.AutoString(), nullable=False
        ),
        sa.Column("token_hash", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("revoked_at", sa.DateTime(), nullable=True),
        sa.Column("user_agent", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("ip_address", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.ForeignKeyConstraint(["association_id"], ["association.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_refresh_session_token_hash"),
        "refresh_session",
        ["token_hash"],
        unique=True,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(
        op.f("ix_refresh_session_token_hash"), table_name="refresh_session"
    )
    op.drop_table("refresh_session")
