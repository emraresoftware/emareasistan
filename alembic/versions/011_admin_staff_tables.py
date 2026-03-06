"""admin staff tables - leave, invoice, purchase order

Revision ID: 012
Revises: 011
Create Date: 2026-02-11
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "012"
down_revision: Union[str, Sequence[str], None] = "011"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "leave_requests",
        sa.Column("id", sa.Integer(), sa.Identity(), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("conversation_id", sa.Integer(), nullable=True),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("employee_name", sa.String(length=255), nullable=False),
        sa.Column("employee_phone", sa.String(length=20), nullable=True),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column("leave_type", sa.String(length=50), nullable=True),
        sa.Column("note", sa.String(length=500), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=True),
        sa.Column("approver_name", sa.String(length=100), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["conversation_id"], ["conversations.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_leave_requests_tenant_id", "leave_requests", ["tenant_id"])
    op.create_index("ix_leave_requests_status", "leave_requests", ["status"])

    op.create_table(
        "invoices",
        sa.Column("id", sa.Integer(), sa.Identity(), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("supplier_name", sa.String(length=255), nullable=False),
        sa.Column("invoice_number", sa.String(length=100), nullable=True),
        sa.Column("total_amount", sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("scanned_text", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_invoices_tenant_id", "invoices", ["tenant_id"])
    op.create_index("ix_invoices_status", "invoices", ["status"])
    op.create_index("ix_invoices_due_date", "invoices", ["due_date"])

    op.create_table(
        "purchase_orders",
        sa.Column("id", sa.Integer(), sa.Identity(), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("requester_name", sa.String(length=255), nullable=False),
        sa.Column("supplier_name", sa.String(length=255), nullable=True),
        sa.Column("items_json", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_purchase_orders_tenant_id", "purchase_orders", ["tenant_id"])
    op.create_index("ix_purchase_orders_status", "purchase_orders", ["status"])


def downgrade() -> None:
    op.drop_index("ix_purchase_orders_status", table_name="purchase_orders")
    op.drop_index("ix_purchase_orders_tenant_id", table_name="purchase_orders")
    op.drop_table("purchase_orders")

    op.drop_index("ix_invoices_due_date", table_name="invoices")
    op.drop_index("ix_invoices_status", table_name="invoices")
    op.drop_index("ix_invoices_tenant_id", table_name="invoices")
    op.drop_table("invoices")

    op.drop_index("ix_leave_requests_status", table_name="leave_requests")
    op.drop_index("ix_leave_requests_tenant_id", table_name="leave_requests")
    op.drop_table("leave_requests")
