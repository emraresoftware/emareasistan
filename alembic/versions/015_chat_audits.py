"""chat_audits - Sohbet denetim sonuçları tablosu

Revision ID: 015
Revises: 014
Create Date: 2026-02-16

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "015"
down_revision: Union[str, Sequence[str], None] = "014"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "chat_audits",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("conversation_id", sa.Integer(), nullable=False),
        sa.Column("platform", sa.String(length=50), nullable=True),
        sa.Column("user_message", sa.Text(), nullable=True),
        sa.Column("assistant_response", sa.Text(), nullable=True),
        sa.Column("score", sa.Float(), nullable=True),
        sa.Column("passed", sa.Boolean(), nullable=True),
        sa.Column("issues", sa.Text(), nullable=True),
        sa.Column("suggested_correction", sa.Text(), nullable=True),
        sa.Column("audit_notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_chat_audits_tenant_id", "chat_audits", ["tenant_id"])
    op.create_index("ix_chat_audits_conversation_id", "chat_audits", ["conversation_id"])
    op.create_index("ix_chat_audits_created_at", "chat_audits", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_chat_audits_created_at", table_name="chat_audits")
    op.drop_index("ix_chat_audits_conversation_id", table_name="chat_audits")
    op.drop_index("ix_chat_audits_tenant_id", table_name="chat_audits")
    op.drop_table("chat_audits")
