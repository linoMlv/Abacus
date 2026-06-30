"""drop the legacy V2 tables (operation, balance, api_key)

The V2 association-login surface (operations, balances, API keys and the
legacy MCP server) has been removed from the application. This migration drops
the now-orphan tables so the V3 schema no longer carries them.

Forward-only by intent: the V3 deployment runs on a fresh database and the one
production association is migrated separately (plan §3/§11 Phase 7), reading the
old database — not these tables. The downgrade faithfully recreates the tables
(and the ``operationtype`` enum) for reversibility.

Revision ID: 0019_drop_legacy_v2_tables
Revises: 0018_ecriture_extourne
Create Date: 2026-06-30 00:00:00.000000

"""

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
import sqlmodel

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0019_drop_legacy_v2_tables"
down_revision: Union[str, Sequence[str], None] = "0018_ecriture_extourne"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# The native enum backing operation.type. Declared explicitly so the upgrade
# can drop it: Postgres does not remove an enum type when its table is dropped.
operationtype = sa.Enum("INCOME", "EXPENSE", name="operationtype")


def upgrade() -> None:
    """Drop the legacy V2 tables, children before parents."""
    op.drop_table("operation")  # FK -> balance
    op.drop_table("balance")  # FK -> association
    op.drop_table("api_key")  # FK -> association
    # Postgres keeps the enum type after its table is gone; checkfirst keeps
    # the no-op safe on SQLite, which has no separate enum type.
    operationtype.drop(op.get_bind(), checkfirst=True)


def downgrade() -> None:
    """Recreate the legacy V2 tables, parents before children."""
    op.create_table(
        "balance",
        sa.Column("id", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("name", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("initialAmount", sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column(
            "association_id", sqlmodel.sql.sqltypes.AutoString(), nullable=True
        ),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["association_id"], ["association.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "operation",
        sa.Column("id", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("name", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("description", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("group", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("amount", sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column("type", operationtype, nullable=False),
        sa.Column("date", sa.DateTime(), nullable=False),
        sa.Column("invoice", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("balance_id", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.ForeignKeyConstraint(["balance_id"], ["balance.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "api_key",
        sa.Column("id", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("name", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("key_hash", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column(
            "key_prefix", sqlmodel.sql.sqltypes.AutoString(length=8), nullable=False
        ),
        sa.Column(
            "association_id", sqlmodel.sql.sqltypes.AutoString(), nullable=False
        ),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("last_used_at", sa.DateTime(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(["association_id"], ["association.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
