"""initial schema

Creates the base tables (association, balance, operation) that were
previously bootstrapped with SQLModel.metadata.create_all and never had a
migration. Adding it as the root of the revision chain lets `alembic upgrade
head` build the whole schema from an empty database (required for the
container-based deployment).

The columns reflect the schema as it stood before the email column was
introduced (see 50c73fb502a7); later revisions add email, log_entry and
api_key on top.

Revision ID: 0001_initial_schema
Revises:
Create Date: 2026-06-18 00:00:00.000000

"""

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
import sqlmodel

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0001_initial_schema"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Native enum type shared by the operation.type column. Declared explicitly
# so downgrade can drop it: Postgres does not remove an enum type when its
# table is dropped, which would otherwise break a re-upgrade.
operationtype = sa.Enum("INCOME", "EXPENSE", name="operationtype")


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "association",
        sa.Column("id", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("name", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("password", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )

    op.create_table(
        "balance",
        sa.Column("id", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("name", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("initialAmount", sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column("association_id", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
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


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("operation")
    op.drop_table("balance")
    op.drop_table("association")
    operationtype.drop(op.get_bind(), checkfirst=True)
