"""notification bell: one pending thing, one person, one association

The bell (C28) persists what awaits a member so a read one stays read across
sessions. Derived notifications carry a subject key (``cle``) — unique per
recipient and association — which is what keeps the sync idempotent: the same
pending draft never rings twice.

Revision ID: 0031_notification
Revises: 0030_assoc_cleanup_refresh_xor
Create Date: 2026-07-13 23:00:00.000000

"""

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
import sqlmodel

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0031_notification"
down_revision: Union[str, Sequence[str], None] = "0030_assoc_cleanup_refresh_xor"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "notification",
        sa.Column("id", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("association_id", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("user_id", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("type", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("titre", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("message", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("lien", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("cle", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("lu_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["association_id"], ["association.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "user_id", "association_id", "cle", name="uq_notification_cle"
        ),
    )
    op.create_index(
        op.f("ix_notification_association_id"), "notification", ["association_id"]
    )
    op.create_index(op.f("ix_notification_user_id"), "notification", ["user_id"])
    op.create_index(op.f("ix_notification_cle"), "notification", ["cle"])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f("ix_notification_cle"), table_name="notification")
    op.drop_index(op.f("ix_notification_user_id"), table_name="notification")
    op.drop_index(op.f("ix_notification_association_id"), table_name="notification")
    op.drop_table("notification")
