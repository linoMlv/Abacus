"""refresh_session: support user-owned sessions

Additive migration for V3 user authentication:

* add nullable ``user_id`` (FK -> user) so a refresh session can belong to a
  user instead of an association;
* relax ``association_id`` to nullable (a user session has no association).

Legacy association sessions keep working (association_id set, user_id null).

Revision ID: 0005_refresh_session_user
Revises: 0004_add_identity_access
Create Date: 2026-06-26 00:00:00.000000

"""

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
import sqlmodel

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0005_refresh_session_user"
down_revision: Union[str, Sequence[str], None] = "0004_add_identity_access"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "refresh_session",
        sa.Column(
            "user_id", sqlmodel.sql.sqltypes.AutoString(), nullable=True
        ),
    )
    op.create_index(
        op.f("ix_refresh_session_user_id"),
        "refresh_session",
        ["user_id"],
        unique=False,
    )
    op.create_foreign_key(
        "fk_refresh_session_user_id",
        "refresh_session",
        "user",
        ["user_id"],
        ["id"],
    )
    op.alter_column(
        "refresh_session",
        "association_id",
        existing_type=sqlmodel.sql.sqltypes.AutoString(),
        nullable=True,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.alter_column(
        "refresh_session",
        "association_id",
        existing_type=sqlmodel.sql.sqltypes.AutoString(),
        nullable=False,
    )
    op.drop_constraint(
        "fk_refresh_session_user_id", "refresh_session", type_="foreignkey"
    )
    op.drop_index(
        op.f("ix_refresh_session_user_id"), table_name="refresh_session"
    )
    op.drop_column("refresh_session", "user_id")
