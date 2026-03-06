"""
Embedding servisi - metin vektörleştirme.
OpenAI veya Gemini ile embedding üretir. OpenAI 1536 dim (pgvector ile uyumlu).
"""
import json
import logging
from typing import Optional

from config import get_settings

logger = logging.getLogger(__name__)

# pgvector embeddings tablosu 1536 dim (OpenAI)
EMBEDDING_DIM = 1536


async def get_embedding(text: str, api_key: Optional[str] = None) -> Optional[list[float]]:
    """
    Metin için embedding vektörü üret.
    OpenAI text-embedding-3-small (1536 dim) kullanır.
    """
    if not text or not text.strip():
        return None
    text = text.strip()[:8000]  # Token limiti

    settings = get_settings()
    key = api_key or settings.openai_api_key
    if not key:
        return None

    try:
        from openai import AsyncOpenAI
        client = AsyncOpenAI(api_key=key)
        r = await client.embeddings.create(
            model="text-embedding-3-small",
            input=text,
        )
        if r.data and len(r.data) > 0:
            return r.data[0].embedding
    except Exception as e:
        logger.warning("OpenAI embedding hatası: %s", e)
    return None
