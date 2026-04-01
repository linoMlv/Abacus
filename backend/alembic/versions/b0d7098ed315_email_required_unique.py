"""email_required_unique

Revision ID: b0d7098ed315
Revises: 50c73fb502a7
Create Date: 2026-04-01 12:21:08.728584

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision: str = 'b0d7098ed315'
down_revision: Union[str, Sequence[str], None] = '50c73fb502a7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Fill NULL emails with a placeholder based on association name
    op.execute(
        "UPDATE association SET email = CONCAT(name, '@placeholder.local') WHERE email IS NULL"
    )
    op.alter_column('association', 'email',
               existing_type=mysql.VARCHAR(collation='utf8mb4_general_ci', length=255),
               nullable=False)
    op.create_unique_constraint('uq_association_email', 'association', ['email'])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint('uq_association_email', 'association', type_='unique')
    op.alter_column('association', 'email',
               existing_type=mysql.VARCHAR(collation='utf8mb4_general_ci', length=255),
               nullable=True)
