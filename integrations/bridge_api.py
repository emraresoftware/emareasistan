"""WhatsApp Bridge API - Bridge bu endpoint'leri kullanır (internal)"""
from fastapi import APIRouter
from models.database import AsyncSessionLocal
from models import WhatsAppConnection
from sqlalchemy import select
from services.core.tenant import get_tenant_settings

router = APIRouter(prefix="/api/bridge", tags=["bridge"])


@router.get("/connections")
async def get_bridge_connections():
    """Bridge başlarken bağlantı listesini alır (tenant izolasyonu: otomatik varsayılan oluşturmaz)."""
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(WhatsAppConnection)
            .where(WhatsAppConnection.is_active == True)
            .order_by(WhatsAppConnection.id)
        )
        conns = result.scalars().all()
        if not conns:
            return []
    tenant_phone_cache: dict[int, str] = {}
    out = []
    for c in conns:
        if c.tenant_id is None:
            # Tenant'siz bağlantı listelenmez (izolasyon).
            continue
        tenant_id = int(c.tenant_id)
        if tenant_id not in tenant_phone_cache:
            settings = await get_tenant_settings(tenant_id)
            tenant_phone_cache[tenant_id] = (settings.get("phone") or "").strip()
        out.append(
            {
                "id": c.id,
                "name": c.name,
                "auth_path": c.auth_path or f"conn_{c.id}",
                "fallback_phone": tenant_phone_cache[tenant_id],
            }
        )
    return out
