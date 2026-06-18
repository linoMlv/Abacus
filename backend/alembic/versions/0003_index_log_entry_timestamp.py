"""index log_entry.timestamp

Additive migration: index the log timestamp, which is used by the retention
purge (WHERE timestamp < cutoff) and by the logs page (ORDER BY timestamp DESC).

Revision ID: 0003_index_log_entry_timestamp
Revises: 0002_add_refresh_session
Create Date: 2026-06-18 00:00:02.000000

"""

from collections.abc import Sequence
from typing import Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0003_index_log_entry_timestamp"
down_revision: Union[str, Sequence[str], None] = "0002_add_refresh_session"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_index(
        op.f("ix_log_entry_timestamp"), "log_entry", ["timestamp"], unique=False
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f("ix_log_entry_timestamp"), table_name="log_entry")
