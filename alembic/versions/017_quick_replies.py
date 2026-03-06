"""quick_replies - tenant bazlı hızlı yanıt şablonları

Revision ID: 017
Revises: 016
Create Date: 2026-02-17

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "017"
down_revision: Union[str, Sequence[str], None] = "016"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "quick_replies",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("label", sa.String(length=100), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_quick_replies_tenant_id", "quick_replies", ["tenant_id"])

    # Mevcut quick_replies.json dosyasını tenant 1'e aktar
    import json
    from pathlib import Path
    data_path = Path(__file__).resolve().parent.parent.parent / "data" / "quick_replies.json"
    if data_path.exists():
        try:
            with open(data_path, encoding="utf-8") as f:
                items = json.load(f)
            if items and isinstance(items, list):
                conn = op.get_bind()
                for i, item in enumerate(items):
                    if isinstance(item, dict) and item.get("label") and item.get("text"):
                        conn.execute(
                            sa.text(
                                "INSERT INTO quick_replies (tenant_id, label, text, sort_order, created_at, updated_at) "
                                "VALUES (1, :label, :text, :ord, NOW(), NOW())"
                            ),
                            {"label": str(item["label"])[:100], "text": str(item["text"]), "ord": i},
                        )
        except Exception:
            pass


def downgrade() -> None:
    op.drop_index("ix_quick_replies_tenant_id", table_name="quick_replies")
    op.drop_table("quick_replies")
