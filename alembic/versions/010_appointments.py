"""appointments tablosu - Randevu modülü

Revision ID: 010
Revises: 009
Create Date: 2026-02-11

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "010"
down_revision: Union[str, Sequence[str], None] = "009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "appointments",
        sa.Column("id", sa.Integer(), sa.Identity(), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("conversation_id", sa.Integer(), nullable=True),
        sa.Column("contact_id", sa.Integer(), nullable=True),
        sa.Column("customer_name", sa.String(255), nullable=True),
        sa.Column("customer_phone", sa.String(20), nullable=True),
        sa.Column("scheduled_at", sa.DateTime(), nullable=False),
        sa.Column("service_type", sa.String(100), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("status", sa.String(20), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["conversation_id"], ["conversations.id"]),
        sa.ForeignKeyConstraint(["contact_id"], ["contacts.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_appointments_tenant_id", "appointments", ["tenant_id"])
    op.create_index("ix_appointments_scheduled_at", "appointments", ["scheduled_at"])
    op.create_index("ix_appointments_status", "appointments", ["status"])


def downgrade() -> None:
    op.drop_index("ix_appointments_status", table_name="appointments")
    op.drop_index("ix_appointments_scheduled_at", table_name="appointments")
    op.drop_index("ix_appointments_tenant_id", table_name="appointments")
    op.drop_table("appointments")
