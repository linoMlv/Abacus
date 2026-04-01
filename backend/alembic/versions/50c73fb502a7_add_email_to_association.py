"""add_email_to_association

Revision ID: 50c73fb502a7
Revises: c4853e0ca426
Create Date: 2026-04-01 11:24:11.485952

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel

# revision identifiers, used by Alembic.
revision: str = '50c73fb502a7'
down_revision: Union[str, Sequence[str], None] = 'c4853e0ca426'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('association', sa.Column('email', sqlmodel.sql.sqltypes.AutoString(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('association', 'email')
