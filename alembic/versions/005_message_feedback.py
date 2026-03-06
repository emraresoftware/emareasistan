"""message_feedback tablosu - beğen/beğenme

Revision ID: 005
Revises: 004
Create Date: 2026-02-11

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "005"
down_revision: Union[str, Sequence[str], None] = "004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "message_feedback",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("message_id", sa.Integer(), nullable=False),
        sa.Column("feedback", sa.String(10), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["message_id"], ["messages.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_message_feedback_message_id", "message_feedback", ["message_id"])


def downgrade() -> None:
    op.drop_index("ix_message_feedback_message_id", table_name="message_feedback")
    op.drop_table("message_feedback")
