"""add_log_entry

Revision ID: c4853e0ca426
Revises: 
Create Date: 2026-03-28 17:39:30.474377

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel

# revision identifiers, used by Alembic.
revision: str = 'c4853e0ca426'
down_revision: Union[str, Sequence[str], None] = '0001_initial_schema'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('log_entry',
    sa.Column('id', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('timestamp', sa.DateTime(), nullable=False),
    sa.Column('method', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('path', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('status_code', sa.Integer(), nullable=False),
    sa.Column('ip_address', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
    sa.Column('user_agent', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
    sa.Column('user', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
    sa.Column('duration_ms', sa.Float(), nullable=True),
    sa.Column('event_type', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
    sa.Column('detail', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('log_entry')
