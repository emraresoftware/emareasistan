"""conversations abandoned_cart_reminder_sent_at

Revision ID: 008
Revises: 007
Create Date: 2026-02-11

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "008"
down_revision: Union[str, Sequence[str], None] = "007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "conversations",
        sa.Column("abandoned_cart_reminder_sent_at", sa.DateTime(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("conversations", "abandoned_cart_reminder_sent_at")
