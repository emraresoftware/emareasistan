"""
Yazılım Alarm / Hata Bildirimi API
-----------------------------------
Harici uygulamalar bu endpoint'e POST atarak anlık WhatsApp bildirimi alır.

Örnek kullanım:
    curl -X POST https://asistan.emarecloud.tr/api/alert \
         -H "Content-Type: application/json" \
         -d '{
               "api_key": "sk-xxxxx",
               "level": "critical",
               "app": "SatışPaneli",
               "title": "Ödeme servisi yanıt vermiyor",
               "message": "PaymentGateway.charge() TimeoutError (>30s)",
               "trace": "File payments.py line 87 in charge\\n  raise TimeoutError"
             }'
"""
import logging
from datetime import datetime

from fastapi import APIRouter
from pydantic import BaseModel

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["alerts"])

LEVEL_EMOJI = {
    "critical": "🚨",
    "error":    "❌",
    "warning":  "⚠️",
    "info":     "ℹ️",
}
LEVEL_TR = {
    "critical": "KRİTİK",
    "error":    "HATA",
    "warning":  "UYARI",
    "info":     "BİLGİ",
}


class AlertRequest(BaseModel):
    api_key: str
    level: str = "error"            # critical | error | warning | info
    app: str = "Uygulama"           # Hangi yazılımdan geliyor
    title: str                      # Kısa başlık
    message: str = ""               # Detaylı açıklama
    trace: str = ""                 # Stack trace (opsiyonel)
    env: str = ""                   # "production" | "staging" vs.


@router.post("/alert")
async def receive_alert(body: AlertRequest):
    """
    Harici yazılımlardan anlık hata bildirimi alır,
    tenant'ın ayarlarındaki alert_phone'a WhatsApp mesajı gönderir.
    """
    level = body.level.lower().strip()
    emoji = LEVEL_EMOJI.get(level, "⚠️")
    level_tr = LEVEL_TR.get(level, level.upper())

    # ── Tenant eşleştirmesi: api_key → tenant ──
    tenant_id = await _find_tenant_by_api_key(body.api_key)
    if not tenant_id:
        logger.warning("Alert API: geçersiz api_key reddedildi")
        return {"ok": False, "error": "Geçersiz api_key"}

    # ── Hedef telefon / grup ──
    from services.core.tenant import get_tenant_settings
    ts = await get_tenant_settings(tenant_id)
    alert_phone = (ts.get("alert_phone") or "").strip()
    if not alert_phone:
        return {"ok": False, "error": "alert_phone ayarlanmamış — Admin → Ayarlar → API"}

    # ── Mesaj formatı ──
    now = datetime.now().strftime("%d.%m.%Y %H:%M:%S")
    env_label = f" [{body.env.upper()}]" if body.env else ""
    lines = [
        f"{emoji} *{level_tr}{env_label}* — {body.app}",
        "",
        f"📋 *{body.title}*",
        f"🕐 {now}",
    ]
    if body.message:
        lines += ["", body.message]
    if body.trace:
        # Trace'i kırp — WA için makul uzunluk
        trace_short = body.trace.strip()[:600]
        lines += ["", "```", trace_short, "```"]
    lines += ["", "#emare-alert"]

    text = "\n".join(lines)

    # ── Gönder ──
    ok = await _send_whatsapp(tenant_id, alert_phone, text)
    if ok:
        logger.info("Alert gönderildi: tenant=%s app=%s level=%s", tenant_id, body.app, level)
        return {"ok": True}
    else:
        logger.error("Alert gönderilemedi: tenant=%s", tenant_id)
        return {"ok": False, "error": "WhatsApp mesajı gönderilemedi"}


# ── Yardımcı fonksiyonlar ──────────────────────────────────────────────────

async def _find_tenant_by_api_key(api_key: str) -> int | None:
    """api_key değerini tenant ayarlarında arayarak tenant_id döndür."""
    if not api_key or len(api_key) < 8:
        return None
    try:
        import json
        from models.database import AsyncSessionLocal
        from models import Tenant
        from sqlalchemy import select

        async with AsyncSessionLocal() as db:
            # Tenant.is_active yok — status sütunu kullanılır
            result = await db.execute(
                select(Tenant).where(Tenant.status == "active")
            )
            tenants = result.scalars().all()
            for t in tenants:
                if not t.settings:
                    continue
                try:
                    raw = json.loads(t.settings) if isinstance(t.settings, str) else t.settings
                    stored_key = (raw.get("alert_api_key") or "").strip()
                    if stored_key and stored_key == api_key:
                        return t.id
                except Exception:
                    continue
    except Exception as e:
        logger.exception("api_key tenant arama hatası: %s", e)
    return None


async def _send_whatsapp(tenant_id: int, phone_or_group: str, text: str) -> bool:
    """Belirtilen numara/gruba WhatsApp mesajı gönder."""
    try:
        from services.whatsapp.agent import send_agent_message_to_customer, get_connection_id_for_tenant
        conn_id = await get_connection_id_for_tenant(tenant_id)
        return await send_agent_message_to_customer(
            platform="whatsapp",
            user_id=phone_or_group,
            text=text,
            connection_id=conn_id,
            tenant_id=tenant_id,
        )
    except Exception as e:
        logger.exception("_send_whatsapp hatası: %s", e)
        return False
