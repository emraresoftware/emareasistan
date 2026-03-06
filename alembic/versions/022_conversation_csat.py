"""conversations: CSAT alanları (sohbet sonrası memnuniyet anketi)

Revision ID: 022
Revises: 021
Create Date: 2026-02-17

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "022"
down_revision: Union[str, Sequence[str], None] = "021"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("conversations", sa.Column("csat_sent_at", sa.DateTime(), nullable=True))
    op.add_column("conversations", sa.Column("csat_rating", sa.Integer(), nullable=True))
    op.add_column("conversations", sa.Column("csat_comment", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("conversations", "csat_comment")
    op.drop_column("conversations", "csat_rating")
    op.drop_column("conversations", "csat_sent_at")
