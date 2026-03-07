"""
Vector store - RAG / semantik arama için embedding saklama ve arama.
Sadece PostgreSQL + pgvector ile çalışır.
"""
from __future__ import annotations
import json
from typing import Optional

from sqlalchemy import select, text, delete
from sqlalchemy.ext.asyncio import AsyncSession

try:
    from pgvector.sqlalchemy import Vector
    from models import Embedding
    HAS_PGVECTOR = True
except ImportError:
    HAS_PGVECTOR = False

SOURCE_AI_TRAINING = "ai_training"
SOURCE_DOCS = "docs"


async def is_vector_available(db: AsyncSession) -> bool:
    """PostgreSQL + pgvector kullanılabilir mi?"""
    if not HAS_PGVECTOR:
        return False
    try:
        r = await db.execute(text("SELECT 1 FROM pg_extension WHERE extname = 'vector'"))
        return r.scalar() is not None
    except Exception:
        return False


async def upsert_embedding(
    db: AsyncSession,
    content: str,
    embedding: list[float],
    tenant_id: Optional[int] = None,
    source: Optional[str] = None,
    meta: Optional[dict] = None,
) -> Optional[int]:
    """Embedding ekle veya güncelle. Returns id."""
    if not HAS_PGVECTOR or not await is_vector_available(db):
        return None
    import json
    rec = Embedding(
        tenant_id=tenant_id,
        content=content,
        embedding=embedding,
        source=source,
        meta=json.dumps(meta, ensure_ascii=False) if meta else None,
    )
    db.add(rec)
    await db.commit()
    await db.refresh(rec)
    return rec.id


async def search_similar(
    db: AsyncSession,
    embedding: list[float],
    tenant_id: Optional[int] = None,
    source: Optional[str] = None,
    limit: int = 5,
) -> list[dict]:
    """Cosine similarity ile en yakın embedding'leri getir."""
    if not HAS_PGVECTOR or not await is_vector_available(db):
        return []
    q = select(Embedding).where(Embedding.embedding.isnot(None))
    if tenant_id is not None:
        q = q.where(Embedding.tenant_id == tenant_id)
    if source is not None:
        q = q.where(Embedding.source == source)
    q = q.order_by(Embedding.embedding.cosine_distance(embedding)).limit(limit)
    r = await db.execute(q)
    rows = r.scalars().all()
    return [
        {"id": x.id, "content": x.content, "source": x.source, "meta": x.meta}
        for x in rows
    ]


async def delete_embeddings_by_meta(
    db: AsyncSession,
    source: str,
    meta_key: str,
    meta_value: int | str,
) -> int:
    """Belirli meta değerine sahip embedding'leri sil. Returns deleted count."""
    if not HAS_PGVECTOR:
        return 0
    try:
        # meta JSON: {"training_example_id": 123, "expected_answer": "..."}
        if isinstance(meta_value, int):
            # 1 ile 10,12 karışmasın: "training_example_id": 1, veya "training_example_id": 1}
            pattern1 = f'"{meta_key}": {meta_value},'
            pattern2 = f'"{meta_key}": {meta_value}}}'
        else:
            pattern1 = f'"{meta_key}": "{meta_value}"'
            pattern2 = pattern1
        from sqlalchemy import or_
        r = await db.execute(
            delete(Embedding).where(
                Embedding.source == source,
                or_(Embedding.meta.like(f"%{pattern1}%"), Embedding.meta.like(f"%{pattern2}%")),
            )
        )
        await db.commit()
        return r.rowcount or 0
    except Exception:
        return 0


async def delete_embeddings_by_source(
    db: AsyncSession,
    source: str,
    tenant_id: int | None = None,
) -> int:
    """Kaynağa göre embedding temizle."""
    if not HAS_PGVECTOR:
        return 0
    try:
        q = delete(Embedding).where(Embedding.source == source)
        if tenant_id is not None:
            q = q.where(Embedding.tenant_id == tenant_id)
        r = await db.execute(q)
        await db.commit()
        return r.rowcount or 0
    except Exception:
        return 0


async def upsert_training_embedding(
    db: AsyncSession,
    training_example_id: int,
    question: str,
    expected_answer: str,
    embedding: list[float],
    tenant_id: int,
) -> Optional[int]:
    """AI eğitim örneği için embedding ekle. Önce eski varsa sil."""
    if not HAS_PGVECTOR or not await is_vector_available(db):
        return None
    await delete_embeddings_by_meta(db, SOURCE_AI_TRAINING, "training_example_id", training_example_id)
    meta = {"training_example_id": training_example_id, "expected_answer": expected_answer}
    return await upsert_embedding(
        db, content=question, embedding=embedding,
        tenant_id=tenant_id, source=SOURCE_AI_TRAINING, meta=meta,
    )


async def search_similar_training(
    db: AsyncSession,
    embedding: list[float],
    tenant_id: int,
    limit: int = 5,
) -> list[dict]:
    """Benzer eğitim örneklerini getir. meta'dan expected_answer parse edilir."""
    rows = await search_similar(db, embedding, tenant_id=tenant_id, source=SOURCE_AI_TRAINING, limit=limit)
    result = []
    for r in rows:
        meta = r.get("meta")
        if isinstance(meta, str):
            try:
                meta = json.loads(meta)
            except json.JSONDecodeError:
                meta = {}
        expected = (meta or {}).get("expected_answer", "")
        if expected:
            result.append({"question": r["content"], "expected_answer": expected})
    return result
