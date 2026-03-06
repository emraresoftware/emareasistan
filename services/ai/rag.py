"""
Dokuman tabanli RAG yardimcisi.
Kaynak: docs/*.md icerigi; vector varsa semantik, yoksa anahtar kelime fallback.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from services.ai.embeddings import get_embedding
from services.ai.vector_store import is_vector_available, search_similar
from services.ai.vector_store import SOURCE_DOCS

_DOC_CACHE: list[dict[str, Any]] | None = None


def _load_docs() -> list[dict[str, Any]]:
    global _DOC_CACHE
    if _DOC_CACHE is not None:
        return _DOC_CACHE
    docs_dir = Path(__file__).resolve().parent.parent / "docs"
    chunks: list[dict[str, Any]] = []
    for p in sorted(docs_dir.glob("*.md")):
        try:
            text = p.read_text(encoding="utf-8")
        except Exception:
            continue
        if not text.strip():
            continue
        lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
        # Basit chunking: dosyayi 40 satirlik bolumlere ayir
        step = 40
        for i in range(0, len(lines), step):
            part = "\n".join(lines[i : i + step]).strip()
            if part:
                chunks.append({"source": p.name, "content": part})
    _DOC_CACHE = chunks
    return chunks


def _keyword_fallback(query: str, limit: int = 3) -> list[dict[str, str]]:
    q_words = [w.strip().lower() for w in (query or "").split() if len(w.strip()) >= 3]
    if not q_words:
        return []
    scored = []
    for ch in _load_docs():
        text = (ch.get("content") or "").lower()
        score = sum(1 for w in q_words if w in text)
        if score > 0:
            scored.append((score, ch))
    scored.sort(key=lambda x: x[0], reverse=True)
    out = []
    for _, ch in scored[:limit]:
        out.append({"source": ch["source"], "content": ch["content"][:900]})
    return out


async def get_docs_rag_context(
    db: AsyncSession,
    tenant_id: int,
    query: str,
    limit: int = 3,
) -> str:
    """
    AI baglamina eklenecek dokuman RAG metni doner.
    """
    if not (query or "").strip():
        return ""
    chunks = _load_docs()
    if not chunks:
        return ""

    # 1) Vector dene (eger pgvector + embedding kullanilabiliyorsa)
    try:
        if await is_vector_available(db):
            emb = await get_embedding(query)
            if emb:
                rows = await search_similar(db, emb, tenant_id=tenant_id, source=SOURCE_DOCS, limit=limit)
                if rows:
                    parts = ["Dokuman baglami (RAG):"]
                    for r in rows:
                        src = (r.get("meta") or "")
                        if isinstance(src, str) and src.strip().startswith("{"):
                            try:
                                import json
                                src = json.loads(src).get("source", "")
                            except Exception:
                                src = ""
                        parts.append(f"- [{src or 'docs'}] {(r.get('content') or '')[:700]}")
                    return "\n".join(parts)
    except Exception:
        pass

    # 2) Fallback: anahtar kelime
    best = _keyword_fallback(query, limit=limit)
    if not best:
        return ""
    lines = ["Dokuman baglami (RAG fallback):"]
    for b in best:
        lines.append(f"- [{b['source']}] {b['content'][:700]}")
    return "\n".join(lines)
