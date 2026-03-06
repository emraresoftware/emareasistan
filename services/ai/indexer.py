"""
Docs embedding indexleyici.
docs/*.md icerigini vector store'a yazar.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from models import Embedding
from services.ai.embeddings import get_embedding
from services.ai.vector_store import SOURCE_DOCS, delete_embeddings_by_source, is_vector_available, upsert_embedding


def _load_doc_chunks() -> list[dict[str, Any]]:
    docs_dir = Path(__file__).resolve().parent.parent / "docs"
    chunks: list[dict[str, Any]] = []
    for p in sorted(docs_dir.glob("*.md")):
        try:
            text = p.read_text(encoding="utf-8")
        except Exception:
            continue
        if not text.strip():
            continue
        lines = [ln.rstrip() for ln in text.splitlines()]
        step = 36
        for i in range(0, len(lines), step):
            raw = "\n".join(lines[i : i + step]).strip()
            if not raw:
                continue
            chunks.append(
                {
                    "source": p.name,
                    "chunk_no": i // step,
                    "content": raw[:4000],
                }
            )
    return chunks


async def index_docs_embeddings(db: AsyncSession, tenant_id: int = 1, force_rebuild: bool = False) -> int:
    """
    Returns indexed chunk count.
    """
    if not await is_vector_available(db):
        return 0

    if not force_rebuild:
        q = await db.execute(
            select(func.count(Embedding.id)).where(
                Embedding.tenant_id == tenant_id,
                Embedding.source == SOURCE_DOCS,
            )
        )
        if int(q.scalar() or 0) > 0:
            return 0

    chunks = _load_doc_chunks()
    if not chunks:
        return 0

    await delete_embeddings_by_source(db, SOURCE_DOCS, tenant_id=tenant_id)

    indexed = 0
    for ch in chunks:
        emb = await get_embedding(ch["content"])
        if not emb:
            continue
        meta = {"source": ch["source"], "chunk_no": ch["chunk_no"]}
        rid = await upsert_embedding(
            db,
            content=ch["content"],
            embedding=emb,
            tenant_id=tenant_id,
            source=SOURCE_DOCS,
            meta=meta,
        )
        if rid:
            indexed += 1
    return indexed
