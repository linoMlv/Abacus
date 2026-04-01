"""add_api_key

Revision ID: 2419cf9e8202
Revises: b0d7098ed315
Create Date: 2026-04-01 12:23:09.637834

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel

# revision identifiers, used by Alembic.
revision: str = '2419cf9e8202'
down_revision: Union[str, Sequence[str], None] = 'b0d7098ed315'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('api_key',
    sa.Column('id', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('name', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('key_hash', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('key_prefix', sqlmodel.sql.sqltypes.AutoString(length=8), nullable=False),
    sa.Column('association_id', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('last_used_at', sa.DateTime(), nullable=True),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.ForeignKeyConstraint(['association_id'], ['association.id'], ),
    sa.PrimaryKeyConstraint('id')
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('api_key')
