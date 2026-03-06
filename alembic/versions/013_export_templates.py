"""export_templates - veri aktarım şablonları

Revision ID: 013
Revises: 012
Create Date: 2026-02-15

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "013"
down_revision: Union[str, Sequence[str], None] = "012"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "export_templates",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("source", sa.String(length=50), nullable=False),
        sa.Column("trigger", sa.String(length=30), nullable=False),
        sa.Column("output_format", sa.String(length=20), nullable=False),
        sa.Column("field_mapping", sa.Text(), nullable=True),
        sa.Column("webhook_url", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_export_templates_tenant_id", "export_templates", ["tenant_id"])
    op.create_index("ix_export_templates_source", "export_templates", ["source"])
    op.create_index("ix_export_templates_trigger", "export_templates", ["trigger"])


def downgrade() -> None:
    op.drop_index("ix_export_templates_trigger", table_name="export_templates")
    op.drop_index("ix_export_templates_source", table_name="export_templates")
    op.drop_index("ix_export_templates_tenant_id", table_name="export_templates")
    op.drop_table("export_templates")
