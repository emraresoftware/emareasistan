"""
Temsilci mesajlarını müşteriye iletme - WhatsApp Cloud API veya Bridge
"""
import logging
import httpx

from config import get_settings

logger = logging.getLogger(__name__)


async def get_connection_id_for_tenant(tenant_id: int) -> int | None:
    """Tenant'ın ilk aktif WhatsApp bağlantı ID'sini döndür (multi-tenant izolasyonu için)."""
    try:
        from models.database import AsyncSessionLocal
        from models import WhatsAppConnection
        from sqlalchemy import select

        async with AsyncSessionLocal() as db:
            r = await db.execute(
                select(WhatsAppConnection.id)
                .where(
                    WhatsAppConnection.is_active == True,
                    WhatsAppConnection.tenant_id == tenant_id,
                )
                .order_by(WhatsAppConnection.id)
                .limit(1)
            )
            return r.scalar_one_or_none()
    except Exception as e:
        logger.warning("connection_id alınamadı (tenant=%s): %s", tenant_id, e)
        return None


def _normalize_phone(to: str) -> str:
    """Telefon numarasını API formatına çevir"""
    t = str(to).replace("@s.whatsapp.net", "").replace("@c.us", "").replace("+", "").replace(" ", "")
    if t.startswith("0"):
        t = "90" + t[1:]
    return "".join(c for c in t if c.isdigit())


async def _get_bridge_url_for_tenant(tenant_id: int | None) -> str:
    """Tenant için WhatsApp Bridge URL'sini döndür (override varsa onu kullan)."""
    settings = get_settings()
    base_url = settings.whatsapp_bridge_url or "http://localhost:3100"
    if not tenant_id:
        return base_url
    try:
        from services.core.tenant import get_tenant_settings

        t_settings = await get_tenant_settings(tenant_id)
        override = (t_settings.get("whatsapp_bridge_url") or "").strip()
        if override:
            return override
    except Exception as e:
        logger.warning("Tenant whatsapp_bridge_url okunamadi (tenant=%s): %s", tenant_id, e)
    return base_url


async def send_agent_message_to_customer(
    platform: str,
    user_id: str,
    text: str,
    connection_id: int | None = None,
    tenant_id: int | None = None,
) -> bool:
    """
    Müşteriye mesaj gönder.
    Önce Cloud API dener, yoksa WhatsApp Bridge'e POST atar.
    connection_id: Multi-tenant için hangi WhatsApp bağlantısı kullanılacak (tenant karışmasını önler).
    """
    if platform != "whatsapp":
        logger.warning("Sadece WhatsApp destekleniyor, platform=%s", platform)
        return False

    # 1. Cloud API (whatsapp_phone_number_id + access_token varsa)
    settings = get_settings()
    if settings.whatsapp_phone_number_id and settings.whatsapp_access_token:
        try:
            await _send_via_cloud_api(user_id, text)
            return True
        except Exception as e:
            logger.warning("Cloud API mesaj gönderimi başarısız: %s", e)

    # 2. WhatsApp Bridge (Node.js - tenant bazlı veya global)
    bridge_url = await _get_bridge_url_for_tenant(tenant_id)
    try:
        to = str(user_id).replace("@s.whatsapp.net", "").replace("@c.us", "").replace("+", "")
        payload = {"to": to, "text": text[:4096]}
        if connection_id is not None:
            payload["connection_id"] = connection_id
        async with httpx.AsyncClient(timeout=15.0) as client:
            r = await client.post(f"{bridge_url}/send", json=payload)
        if r.status_code == 200:
            return True
        logger.warning("Bridge mesaj gönderimi: %s %s", r.status_code, r.text)
    except Exception as e:
        logger.warning("Bridge mesaj gönderimi başarısız: %s", e)

    return False


async def send_agent_images_to_customer(
    platform: str,
    user_id: str,
    image_urls: list[str],
    caption: str | None = None,
    connection_id: int | None = None,
) -> tuple[bool, str | None]:
    """Müşteriye resim(ler) gönder. Returns (ok, error_message)."""
    if platform != "whatsapp":
        logger.warning("Sadece WhatsApp destekleniyor, platform=%s", platform)
        return False, "Sadece WhatsApp destekleniyor"
    if not image_urls:
        return False, "Resim URL'leri boş"

    settings = get_settings()
    to = _normalize_phone(user_id)

    # 1. Cloud API
    if settings.whatsapp_phone_number_id and settings.whatsapp_access_token:
        try:
            await _send_images_via_cloud_api(to, image_urls, caption)
            return True, None
        except Exception as e:
            logger.warning("Cloud API resim gönderimi başarısız: %s", e)

    # 2. WhatsApp Bridge
    bridge_url = settings.whatsapp_bridge_url or "http://localhost:3100"
    try:
        payload = {"to": to, "image_urls": image_urls}
        if caption:
            payload["caption"] = caption[:1024]
        if connection_id is not None:
            payload["connection_id"] = connection_id
        async with httpx.AsyncClient(timeout=60.0) as client:
            r = await client.post(f"{bridge_url}/send", json=payload)
        if r.status_code == 200:
            return True, None
        err_msg = "Resim gönderilemedi."
        try:
            data = r.json()
            if data.get("error"):
                err_msg = str(data["error"])
        except Exception:
            pass
        logger.warning("Bridge resim gönderimi: %s %s", r.status_code, err_msg)
        return False, err_msg
    except httpx.ConnectError:
        return False, "WhatsApp Bridge'e bağlanılamadı. Bridge çalışıyor mu? (cd whatsapp-bridge && node index.js)"
    except Exception as e:
        logger.warning("Bridge resim gönderimi başarısız: %s", e)
        return False, str(e)


async def _send_images_via_cloud_api(to: str, image_urls: list[str], caption: str | None):
    """WhatsApp Cloud API ile resim gönder"""
    settings = get_settings()
    url = f"https://graph.facebook.com/v18.0/{settings.whatsapp_phone_number_id}/messages"
    headers = {"Authorization": f"Bearer {settings.whatsapp_access_token}"}
    for i, img_url in enumerate(image_urls):
        image_obj = {"link": img_url}
        if i == 0 and caption:
            image_obj["caption"] = caption[:1024]
        payload = {
            "messaging_product": "whatsapp",
            "to": to,
            "type": "image",
            "image": image_obj,
        }
        async with httpx.AsyncClient() as client:
            resp = await client.post(url, json=payload, headers=headers)
            if resp.status_code != 200:
                raise RuntimeError(f"Cloud API {resp.status_code}: {resp.text}")


async def _send_via_cloud_api(to: str, text: str):
    """WhatsApp Cloud API ile mesaj gönder"""
    settings = get_settings()
    url = f"https://graph.facebook.com/v18.0/{settings.whatsapp_phone_number_id}/messages"
    headers = {"Authorization": f"Bearer {settings.whatsapp_access_token}"}
    payload = {
        "messaging_product": "whatsapp",
        "to": to.replace("+", "").replace("@s.whatsapp.net", "").replace("@c.us", ""),
        "type": "text",
        "text": {"body": text[:4096]},
    }
    async with httpx.AsyncClient() as client:
        resp = await client.post(url, json=payload, headers=headers)
        if resp.status_code != 200:
            raise RuntimeError(f"Cloud API {resp.status_code}: {resp.text}")


# Sipariş durumu metinleri
ORDER_STATUS_MESSAGES = {
    "confirmed": "✅ Siparişiniz onaylandı. En kısa sürede hazırlanacaktır.",
    "processing": "📦 Siparişiniz hazırlanıyor.",
    "shipped": "🚚 Siparişiniz kargoya verildi. Takip için kargo numaranızı paylaşacağız.",
    "delivered": "✅ Siparişiniz teslim edildi. Bizi tercih ettiğiniz için teşekkür ederiz.",
    "cancelled": "Siparişiniz iptal edildi. Sorularınız için bize ulaşabilirsiniz.",
}


async def send_order_status_notification(
    order_number: str,
    customer_phone: str,
    status: str,
    tracking_no: str | None = None,
    cargo_company: str | None = None,
    tenant_id: int = 1,
) -> bool:
    """
    Sipariş durumu değiştiğinde müşteriye WhatsApp bildirimi gönder.
    tenant_id: Hangi tenant'ın WhatsApp'ı kullanılacak (karışmayı önler).
    """
    if not customer_phone or not customer_phone.strip():
        return False
    msg = ORDER_STATUS_MESSAGES.get(status)
    if not msg:
        return False
    full_msg = f"Merhaba,\n\n{order_number} numaralı siparişiniz:\n{msg}"
    if status == "shipped" and tracking_no:
        full_msg += f"\n\nTakip No: {tracking_no}"
        if cargo_company:
            full_msg += f"\nKargo: {cargo_company}"
    connection_id = await get_connection_id_for_tenant(tenant_id)
    return await send_agent_message_to_customer(
        "whatsapp",
        customer_phone,
        full_msg,
        connection_id=connection_id,
        tenant_id=tenant_id,
    )
