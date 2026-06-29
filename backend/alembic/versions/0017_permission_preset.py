"""permission presets + per-member permission overrides (T8)

Additive migration for fine-grained access (plan §2/§15.10):

* a per-association ``permission_preset`` table (a reusable named permission set,
  i.e. a custom role);
* an optional, indexed ``membership.preset_id`` referencing it (preset as an
  alternative permission base);
* a ``membership.permission_overrides`` JSON map (``{permission_value: bool}``,
  grant=True / revoke=False) defaulting to an empty object.

The preset table is created before the referencing column. No existing column is
dropped or made stricter; existing memberships get an empty override map.

Revision ID: 0017_permission_preset
Revises: 0016_evenement
Create Date: 2026-06-29 00:00:00.000000

"""

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
import sqlmodel

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0017_permission_preset"
down_revision: Union[str, Sequence[str], None] = "0016_evenement"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "permission_preset",
        sa.Column("id", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column(
            "association_id", sqlmodel.sql.sqltypes.AutoString(), nullable=False
        ),
        sa.Column("nom", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("permissions", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["association_id"],
            ["association.id"],
            name=op.f("fk_permission_preset_association_id_association"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_permission_preset")),
        sa.UniqueConstraint("association_id", "nom", name="uq_preset_assoc_nom"),
    )
    op.create_index(
        op.f("ix_permission_preset_association_id"),
        "permission_preset",
        ["association_id"],
        unique=False,
    )

    op.add_column(
        "membership",
        sa.Column("preset_id", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
    )
    op.create_index(
        op.f("ix_membership_preset_id"), "membership", ["preset_id"], unique=False
    )
    op.create_foreign_key(
        op.f("fk_membership_preset_id_permission_preset"),
        "membership",
        "permission_preset",
        ["preset_id"],
        ["id"],
    )
    op.add_column(
        "membership",
        sa.Column(
            "permission_overrides",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'{}'"),
        ),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("membership", "permission_overrides")
    op.drop_constraint(
        op.f("fk_membership_preset_id_permission_preset"),
        "membership",
        type_="foreignkey",
    )
    op.drop_index(op.f("ix_membership_preset_id"), table_name="membership")
    op.drop_column("membership", "preset_id")
    op.drop_index(
        op.f("ix_permission_preset_association_id"), table_name="permission_preset"
    )
    op.drop_table("permission_preset")
