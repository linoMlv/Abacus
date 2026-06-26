"""business audit trail (audit_log)

Additive migration: a per-association audit trail of sensitive business actions
(entry created/validated/deleted, …) for accounting integrity. No existing table
is modified.

Revision ID: 0010_audit_log
Revises: 0009_categorie_saisie
Create Date: 2026-06-27 00:00:02.000000

"""

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
import sqlmodel

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0010_audit_log"
down_revision: Union[str, Sequence[str], None] = "0009_categorie_saisie"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "audit_log",
        sa.Column("id", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("timestamp", sa.DateTime(), nullable=False),
        sa.Column("association_id", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("actor_user_id", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("action", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("target_type", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("target_id", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("detail", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.ForeignKeyConstraint(["association_id"], ["association.id"]),
        sa.ForeignKeyConstraint(["actor_user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_audit_log_timestamp"), "audit_log", ["timestamp"], unique=False
    )
    op.create_index(
        op.f("ix_audit_log_association_id"),
        "audit_log",
        ["association_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_audit_log_action"), "audit_log", ["action"], unique=False
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f("ix_audit_log_action"), table_name="audit_log")
    op.drop_index(op.f("ix_audit_log_association_id"), table_name="audit_log")
    op.drop_index(op.f("ix_audit_log_timestamp"), table_name="audit_log")
    op.drop_table("audit_log")
