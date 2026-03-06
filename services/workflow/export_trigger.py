"""
Export şablonlarını tetikle - sipariş/kişi/hatırlatıcı oluşunca webhook gönder.
"""
import asyncio
import json
import logging
from sqlalchemy import select

from models.database import AsyncSessionLocal
from models import ExportTemplate, Order, Contact, Reminder
from services.workflow.export import build_payload, send_webhook

logger = logging.getLogger(__name__)


async def trigger_export_webhooks(source: str, obj, tenant_id: int) -> None:
    """
    Kaynak oluşunca aktif webhook şablonlarını tetikle.
    source: "orders" | "contacts" | "reminders"
    obj: Order, Contact veya Reminder instance
    """
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(ExportTemplate).where(
                ExportTemplate.tenant_id == tenant_id,
                ExportTemplate.source == source,
                ExportTemplate.trigger == "webhook",
                ExportTemplate.is_active == True,
                ExportTemplate.webhook_url.isnot(None),
                ExportTemplate.webhook_url != "",
            )
        )
        templates = result.scalars().all()

    for t in templates:
        try:
            mapping = None
            if t.field_mapping:
                try:
                    m = json.loads(t.field_mapping)
                    mapping = m if isinstance(m, dict) else None
                except (json.JSONDecodeError, TypeError):
                    pass
            payload = build_payload(obj, source, mapping)
            if payload:
                asyncio.create_task(send_webhook(t.webhook_url, payload))
        except Exception as e:
            logger.exception("Export webhook template %s failed: %s", t.id, e)
