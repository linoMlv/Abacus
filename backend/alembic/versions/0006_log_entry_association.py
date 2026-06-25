"""log_entry: add association_id for per-tenant logs

Additive migration: tags each log entry with the association targeted by the
request (parsed from /api/asso/{id}/...), so an admin can read the logs scoped
to their own association. Plain indexed column, no foreign key (logging must
never fail on an arbitrary path id).

Revision ID: 0006_log_entry_association
Revises: 0005_refresh_session_user
Create Date: 2026-06-26 00:00:01.000000

"""

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
import sqlmodel

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0006_log_entry_association"
down_revision: Union[str, Sequence[str], None] = "0005_refresh_session_user"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "log_entry",
        sa.Column(
            "association_id", sqlmodel.sql.sqltypes.AutoString(), nullable=True
        ),
    )
    op.create_index(
        op.f("ix_log_entry_association_id"),
        "log_entry",
        ["association_id"],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f("ix_log_entry_association_id"), table_name="log_entry")
    op.drop_column("log_entry", "association_id")
