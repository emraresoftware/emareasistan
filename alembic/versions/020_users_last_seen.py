"""users.last_seen - Son aktivite (online/offline için)

Revision ID: 020
Revises: 019
Create Date: 2026-02-17

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "020"
down_revision: Union[str, Sequence[str], None] = "019"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("last_seen", sa.DateTime(), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "last_seen")
