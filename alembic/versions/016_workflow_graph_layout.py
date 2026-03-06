"""workflow graph_layout - Görsel akış builder için layout saklama

Revision ID: 016
Revises: 015
Create Date: 2026-02-16

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "016"
down_revision: Union[str, Sequence[str], None] = "015"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "tenant_workflows",
        sa.Column("graph_layout", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("tenant_workflows", "graph_layout")
