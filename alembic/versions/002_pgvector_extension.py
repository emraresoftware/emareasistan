"""pgvector extension + embeddings tablosu

Revision ID: 002
Revises: 001
Create Date: 2026-02-13

Sadece PostgreSQL'de çalışır. SQLite kullanılıyorsa atlanır.
RAG / vektör araması için embeddings tablosu (1536 dim = OpenAI ada-002, text-embedding-3-small)
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "002"
down_revision: Union[str, Sequence[str], None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _is_postgres(connection) -> bool:
    return connection.dialect.name == "postgresql"


def upgrade() -> None:
    conn = op.get_bind()
    if not _is_postgres(conn):
        return
    op.execute(sa.text("CREATE EXTENSION IF NOT EXISTS vector"))
    op.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS embeddings (
            id SERIAL PRIMARY KEY,
            tenant_id INTEGER,
            content TEXT NOT NULL,
            embedding vector(1536),
            source VARCHAR(255),
            meta TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """))
    op.execute(sa.text(
        "CREATE INDEX IF NOT EXISTS ix_embeddings_tenant_id ON embeddings (tenant_id)"
    ))
    op.execute(sa.text(
        "CREATE INDEX IF NOT EXISTS ix_embeddings_embedding ON embeddings "
        "USING hnsw (embedding vector_cosine_ops)"
    ))


def downgrade() -> None:
    conn = op.get_bind()
    if not _is_postgres(conn):
        return
    op.execute(sa.text("DROP TABLE IF EXISTS embeddings"))
