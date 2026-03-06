"""tenant_workflows - Kurum bazlı iş akışları ve süreç konfigürasyonları

Revision ID: 014
Revises: 013
Create Date: 2026-02-16

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "014"
down_revision: Union[str, Sequence[str], None] = "013"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "tenant_workflows",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("platform", sa.String(length=50), nullable=False),
        sa.Column("workflow_name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_tenant_workflows_tenant_id", "tenant_workflows", ["tenant_id"])
    op.create_index("ix_tenant_workflows_platform", "tenant_workflows", ["platform"])

    op.create_table(
        "workflow_steps",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("workflow_id", sa.Integer(), nullable=False),
        sa.Column("step_name", sa.String(length=255), nullable=False),
        sa.Column("step_type", sa.String(length=30), nullable=False),
        sa.Column("config", sa.Text(), nullable=True),
        sa.Column("order_index", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["workflow_id"], ["tenant_workflows.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_workflow_steps_workflow_id", "workflow_steps", ["workflow_id"])

    op.create_table(
        "process_configs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("process_type", sa.String(length=50), nullable=False),
        sa.Column("platform", sa.String(length=50), nullable=False),
        sa.Column("auto_response", sa.Boolean(), nullable=True),
        sa.Column("escalation_rules", sa.Text(), nullable=True),
        sa.Column("sla_settings", sa.Text(), nullable=True),
        sa.Column("notification_rules", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_process_configs_tenant_id", "process_configs", ["tenant_id"])
    op.create_index("ix_process_configs_platform", "process_configs", ["platform"])
    op.create_index("ix_process_configs_process_type", "process_configs", ["process_type"])


def downgrade() -> None:
    op.drop_index("ix_process_configs_process_type", table_name="process_configs")
    op.drop_index("ix_process_configs_platform", table_name="process_configs")
    op.drop_index("ix_process_configs_tenant_id", table_name="process_configs")
    op.drop_table("process_configs")
    op.drop_index("ix_workflow_steps_workflow_id", table_name="workflow_steps")
    op.drop_table("workflow_steps")
    op.drop_index("ix_tenant_workflows_platform", table_name="tenant_workflows")
    op.drop_index("ix_tenant_workflows_tenant_id", table_name="tenant_workflows")
    op.drop_table("tenant_workflows")
