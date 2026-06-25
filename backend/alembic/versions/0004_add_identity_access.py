"""add identity & access (user, membership, invitation)

Additive migration: introduces the V3 multi-association identity model.

* ``user``        — physical-person account (global identity).
* ``membership``  — grants a user a role within an association (RBAC).
* ``invitation``  — pending invite of an email to an association with a role.

No existing table is modified; the legacy Association-as-login path keeps
working until the auth flow is migrated in a later change.

Revision ID: 0004_add_identity_access
Revises: 0003_index_log_entry_timestamp
Create Date: 2026-06-25 00:00:00.000000

"""

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
import sqlmodel

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0004_add_identity_access"
down_revision: Union[str, Sequence[str], None] = "0003_index_log_entry_timestamp"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "user",
        sa.Column("id", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("email", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("password", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("name", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_user_email"), "user", ["email"], unique=True)

    op.create_table(
        "membership",
        sa.Column("id", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("user_id", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column(
            "association_id", sqlmodel.sql.sqltypes.AutoString(), nullable=False
        ),
        sa.Column("role", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("status", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("invited_by", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["association_id"], ["association.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["invited_by"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "user_id", "association_id", name="uq_membership_user_assoc"
        ),
    )
    op.create_index(
        op.f("ix_membership_user_id"), "membership", ["user_id"], unique=False
    )
    op.create_index(
        op.f("ix_membership_association_id"),
        "membership",
        ["association_id"],
        unique=False,
    )

    op.create_table(
        "invitation",
        sa.Column("id", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column(
            "association_id", sqlmodel.sql.sqltypes.AutoString(), nullable=False
        ),
        sa.Column("email", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("role", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("token_hash", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("invited_by", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("accepted_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["association_id"], ["association.id"]),
        sa.ForeignKeyConstraint(["invited_by"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_invitation_association_id"),
        "invitation",
        ["association_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_invitation_email"), "invitation", ["email"], unique=False
    )
    op.create_index(
        op.f("ix_invitation_token_hash"),
        "invitation",
        ["token_hash"],
        unique=True,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f("ix_invitation_token_hash"), table_name="invitation")
    op.drop_index(op.f("ix_invitation_email"), table_name="invitation")
    op.drop_index(op.f("ix_invitation_association_id"), table_name="invitation")
    op.drop_table("invitation")

    op.drop_index(op.f("ix_membership_association_id"), table_name="membership")
    op.drop_index(op.f("ix_membership_user_id"), table_name="membership")
    op.drop_table("membership")

    op.drop_index(op.f("ix_user_email"), table_name="user")
    op.drop_table("user")
