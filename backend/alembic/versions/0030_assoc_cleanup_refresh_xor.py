"""legacy cleanup: association email non-unique + password nullable, refresh owner XOR

Assainit deux vestiges de l'auth V2 supprimée et durcit ``refresh_session`` :

* ``association.email`` — contact info only, no longer a login identity, so the
  global unique constraint is dropped (two associations may share a contact).
* ``association.password`` — V3 associations have no login, so the column becomes
  nullable (creation now stores NULL instead of an unusable fake hash).
* ``refresh_session`` — a CHECK enforces the owner-XOR invariant: exactly one of
  ``user_id`` / ``association_id`` is set.

Revision ID: 0030_assoc_cleanup_refresh_xor
Revises: 0029_login_lockout
Create Date: 2026-07-09 00:00:02.000000

"""

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0030_assoc_cleanup_refresh_xor"
down_revision: Union[str, Sequence[str], None] = "0029_login_lockout"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_CK_ONE_OWNER = "ck_refresh_session_one_owner"


def upgrade() -> None:
    """Upgrade schema."""
    op.drop_constraint("uq_association_email", "association", type_="unique")
    op.create_index(op.f("ix_association_email"), "association", ["email"])
    op.alter_column("association", "password", existing_type=sa.String(), nullable=True)
    op.create_check_constraint(
        _CK_ONE_OWNER,
        "refresh_session",
        "(user_id IS NULL) <> (association_id IS NULL)",
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint(_CK_ONE_OWNER, "refresh_session", type_="check")
    op.alter_column(
        "association", "password", existing_type=sa.String(), nullable=False
    )
    op.drop_index(op.f("ix_association_email"), "association")
    op.create_unique_constraint("uq_association_email", "association", ["email"])
