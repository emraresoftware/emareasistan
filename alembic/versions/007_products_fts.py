"""products Full-Text Search (tsvector) - PostgreSQL only

Revision ID: 007
Revises: 006
Create Date: 2026-02-11

"""
from typing import Sequence, Union

from alembic import op
from sqlalchemy import text


revision: str = "007"
down_revision: Union[str, Sequence[str], None] = "006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _is_postgresql(connection) -> bool:
    return connection.dialect.name == "postgresql"


def upgrade() -> None:
    conn = op.get_bind()
    if not _is_postgresql(conn):
        return
    # search_vector tsvector sütunu (PostgreSQL 12+)
    op.execute(text("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'products' AND column_name = 'search_vector'
            ) THEN
                ALTER TABLE products ADD COLUMN search_vector tsvector
                GENERATED ALWAYS AS (
                    setweight(to_tsvector('turkish', coalesce(name, '')), 'A') ||
                    setweight(to_tsvector('turkish', coalesce(description, '')), 'B') ||
                    setweight(to_tsvector('turkish', coalesce(category, '')), 'A')
                ) STORED;
            END IF;
        END $$;
    """))
    op.execute(text("CREATE INDEX IF NOT EXISTS ix_products_search_vector ON products USING GIN (search_vector)"))


def downgrade() -> None:
    conn = op.get_bind()
    if not _is_postgresql(conn):
        return
    op.execute(text("DROP INDEX IF EXISTS ix_products_search_vector"))
    op.execute(text("ALTER TABLE products DROP COLUMN IF EXISTS search_vector"))
