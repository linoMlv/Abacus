"""treasury metadata on compte (type_tresorerie, iban, couleur, ordre)

Additive migration: enriches ``compte`` so a class-5 account can be a *named
treasury account* (§15.4) — bank / cash / online / savings / other — with an
optional IBAN, colour and display order. ``type_tresorerie`` is null on ordinary
chart-of-accounts lines. The current balance is never stored (computed from the
ledger). No existing column is modified.

Revision ID: 0011_compte_tresorerie
Revises: 0010_audit_log
Create Date: 2026-06-28 00:00:00.000000

"""

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
import sqlmodel

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0011_compte_tresorerie"
down_revision: Union[str, Sequence[str], None] = "0010_audit_log"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "compte",
        sa.Column("type_tresorerie", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
    )
    op.add_column(
        "compte", sa.Column("iban", sqlmodel.sql.sqltypes.AutoString(), nullable=True)
    )
    op.add_column(
        "compte",
        sa.Column("couleur", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
    )
    op.add_column(
        "compte",
        sa.Column("ordre", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_index(
        op.f("ix_compte_type_tresorerie"),
        "compte",
        ["type_tresorerie"],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f("ix_compte_type_tresorerie"), table_name="compte")
    op.drop_column("compte", "ordre")
    op.drop_column("compte", "couleur")
    op.drop_column("compte", "iban")
    op.drop_column("compte", "type_tresorerie")
