"""
Embedding model - RAG / vektör araması için.
Sadece PostgreSQL + pgvector ile kullanılır. SQLite'da tablo yok.
"""
from datetime import datetime

from sqlalchemy import Column, Integer, String, Text, DateTime

from .database import Base

try:
    from pgvector.sqlalchemy import Vector
    _embedding_col = Column(Vector(1536), nullable=True)
except ImportError:
    _embedding_col = Column(Text, nullable=True)


class Embedding(Base):
    """Metin embedding'leri - RAG, semantik arama için"""
    __tablename__ = "embeddings"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, index=True, nullable=True)
    content = Column(Text, nullable=False)
    embedding = _embedding_col
    source = Column(String(255), nullable=True)
    meta = Column(Text, nullable=True)  # JSON - metadata (metadata reserved by SQLAlchemy)
    created_at = Column(DateTime, default=datetime.utcnow)
