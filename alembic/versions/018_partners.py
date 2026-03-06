"""partners - Partner modeli + Tenant.partner_id + User.partner_id, is_partner_admin

Revision ID: 018
Revises: 017
Create Date: 2026-02-17

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "018"
down_revision: Union[str, Sequence[str], None] = "017"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    is_sqlite = conn.dialect.name == "sqlite"

    op.create_table(
        "partners",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("slug", sa.String(100), nullable=True),
        sa.Column("settings", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=True, default=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_partners_slug", "partners", ["slug"], unique=True)

    op.add_column("tenants", sa.Column("partner_id", sa.Integer(), nullable=True))
    op.create_index("ix_tenants_partner_id", "tenants", ["partner_id"])
    if not is_sqlite:
        op.create_foreign_key("fk_tenants_partner_id", "tenants", "partners", ["partner_id"], ["id"])

    op.add_column("users", sa.Column("partner_id", sa.Integer(), nullable=True))
    op.add_column("users", sa.Column("is_partner_admin", sa.Boolean(), nullable=True))
    op.create_index("ix_users_partner_id", "users", ["partner_id"])
    if not is_sqlite:
        op.create_foreign_key("fk_users_partner_id", "users", "partners", ["partner_id"], ["id"])


def downgrade() -> None:
    conn = op.get_bind()
    is_sqlite = conn.dialect.name == "sqlite"

    op.drop_index("ix_users_partner_id", table_name="users")
    if not is_sqlite:
        op.drop_constraint("fk_users_partner_id", "users", type_="foreignkey")
    op.drop_column("users", "is_partner_admin")
    op.drop_column("users", "partner_id")

    op.drop_index("ix_tenants_partner_id", table_name="tenants")
    if not is_sqlite:
        op.drop_constraint("fk_tenants_partner_id", "tenants", type_="foreignkey")
    op.drop_column("tenants", "partner_id")

    op.drop_index("ix_partners_slug", table_name="partners")
    op.drop_table("partners")
