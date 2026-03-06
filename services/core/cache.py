"""
Tenant ayarları cache - Redis veya in-memory fallback.
REDIS_URL boşsa in-memory TTL cache kullanılır.
"""
import json
import time
from typing import Any

from config import get_settings

# In-memory fallback: {tenant_id: (data_dict, expiry_timestamp)}
_memory_cache: dict[int, tuple[dict, float]] = {}
_TTL_SEC = 300  # 5 dakika


async def _get_redis_client():
    """Redis client - lazy init. Redis yoksa veya REDIS_URL boşsa None."""
    try:
        url = (get_settings().redis_url or "").strip()
        if not url:
            return None
        import redis.asyncio as redis
        return redis.from_url(url, decode_responses=True)
    except ImportError:
        return None
    except Exception:
        return None


async def get_tenant_settings_cached(tenant_id: int, fetch_fn) -> dict:
    """
    Önce cache'e bak, yoksa fetch_fn(tenant_id) çağır ve cache'e yaz.
    fetch_fn: async def(tenant_id: int) -> dict
    """
    client = None
    try:
        client = await _get_redis_client()
        if client:
            key = f"tenant_settings:{tenant_id}"
            raw = await client.get(key)
            if raw:
                try:
                    return json.loads(raw)
                finally:
                    await client.aclose()

        # In-memory fallback
        now = time.time()
        if tenant_id in _memory_cache:
            data, expiry = _memory_cache[tenant_id]
            if now < expiry:
                return data
        _memory_cache.pop(tenant_id, None)

        # DB'den al
        data = await fetch_fn(tenant_id)

        # Cache'e yaz
        if client:
            await client.set(
                f"tenant_settings:{tenant_id}",
                json.dumps(data, ensure_ascii=False),
                ex=_TTL_SEC,
            )
        else:
            _memory_cache[tenant_id] = (data, time.time() + _TTL_SEC)

        return data
    except Exception:
        return await fetch_fn(tenant_id)
    finally:
        if client:
            try:
                await client.aclose()
            except Exception:
                pass


async def invalidate_tenant_cache(tenant_id: int) -> None:
    """Tenant ayarları güncellendiğinde cache'i temizle"""
    _memory_cache.pop(tenant_id, None)
    client = None
    try:
        client = await _get_redis_client()
        if client:
            await client.delete(f"tenant_settings:{tenant_id}")
    except Exception:
        pass
    finally:
        if client:
            try:
                await client.aclose()
            except Exception:
                pass
