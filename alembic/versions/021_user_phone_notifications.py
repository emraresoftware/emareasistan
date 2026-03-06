"""user.phone, user.notification_settings - Asistan bildirimleri

Revision ID: 021
Revises: 020
Create Date: 2026-02-17

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "021"
down_revision: Union[str, Sequence[str], None] = "020"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("phone", sa.String(30), nullable=True))
    op.add_column("users", sa.Column("notification_settings", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "notification_settings")
    op.drop_column("users", "phone")
