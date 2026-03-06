"""products tablosuna tenant_id ekle

Revision ID: 006
Revises: 005
Create Date: 2026-02-11

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "006"
down_revision: Union[str, Sequence[str], None] = "005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("products", sa.Column("tenant_id", sa.Integer(), nullable=True))
    op.create_index("ix_products_tenant_id", "products", ["tenant_id"])


def downgrade() -> None:
    op.drop_index("ix_products_tenant_id", table_name="products")
    op.drop_column("products", "tenant_id")
