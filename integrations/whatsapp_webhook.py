"""
WhatsApp Business Cloud API - Webhook handler
Meta Cloud API üzerinden gelen mesajları işler
"""
import logging
import httpx
from time import perf_counter
from fastapi import APIRouter, Request, Response
from pydantic import BaseModel

from config import get_settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/webhook/whatsapp", tags=["whatsapp"])


class WhatsAppChallenge(BaseModel):
    """Meta doğrulama challenge"""
    """GET ile gelen verify_token kontrolü"""


@router.get("")
async def verify_webhook(request: Request):
    """
    Meta webhook doğrulaması - GET isteği
    VERIFY_TOKEN ve challenge ile yanıt ver
    """
    mode = request.query_params.get("hub.mode")
    token = request.query_params.get("hub.verify_token")
    challenge = request.query_params.get("hub.challenge")

    if mode == "subscribe" and token == get_settings().whatsapp_verify_token:
        return Response(content=challenge, media_type="text/plain")
    return Response(status_code=403)


@router.post("")
async def handle_webhook(request: Request):
    """
    WhatsApp mesajları - POST isteği
    Gelen mesajları işleyip yanıt gönder
    """
    body = await request.json()

    if body.get("object") != "whatsapp_business_account":
        return {"status": "ignored"}

    for entry in body.get("entry", []):
        for change in entry.get("changes", []):
            if change.get("field") != "messages":
                continue
            value = change.get("value", {})
            messages = value.get("messages", [])
            for msg in messages:
                await process_whatsapp_message(
                    from_number=msg.get("from"),
                    message_id=msg.get("id"),
                    message_type=msg.get("type"),
                    text=msg.get("text", {}).get("body", "") if msg.get("type") == "text" else "",
                )

    return {"status": "ok"}


def _normalize_phone(phone: str) -> str:
    """Aynı numaranın farklı formatlarda hep aynı sohbete düşmesi için"""
    if not phone:
        return phone or ""
    digits = "".join(c for c in str(phone) if c.isdigit())
    if not digits:
        return phone
    if len(digits) == 10 and digits.startswith("5"):
        return "90" + digits
    if len(digits) == 11 and digits.startswith("0"):
        return "9" + digits
    return digits


async def process_whatsapp_message(
    from_number: str,
    message_id: str,
    message_type: str,
    text: str,
):
    """WhatsApp mesajını işle ve yanıt gönder"""
    if message_type != "text" or not text.strip():
        return

    from_number = _normalize_phone(from_number)

    from models.database import AsyncSessionLocal
    from integrations import ChatHandler
    from services.workflow.metrics import record_chat_response_event

    started = perf_counter()
    ok = True
    try:
        async with AsyncSessionLocal() as db:
            handler = ChatHandler(db)
            # tenant_id parametresi yok → process_message içinde conv.tenant_id = 1 kullanılır.
            # Piramit vb. çok tenant için WhatsApp Bridge (QR) kullanın; orada connection.tenant_id geçer.
            response = await handler.process_message(
                platform="whatsapp",
                user_id=from_number,
                message_text=text,
                conversation_history=[],
                customer_phone=from_number,
            )
    except Exception as e:
        ok = False
        logger.exception("WhatsApp webhook mesaj işleme hatası: %s", e)
        settings = get_settings()
        fallback = f"Üzgünüz, teknik bir gecikme yaşıyoruz. Lütfen daha sonra tekrar deneyin veya {settings.default_tenant_phone} numarasından bize ulaşabilirsiniz."
        await send_whatsapp_message(from_number, fallback)
        return
    finally:
        duration_ms = int((perf_counter() - started) * 1000)
        record_chat_response_event(
            tenant_id=1,
            ok=ok,
            latency_ms=duration_ms,
            channel="whatsapp_cloud",
        )

    # Yanıt gönder - Channel abstraction
    from integrations.channels import get_channel, send_response
    channel = get_channel("whatsapp")
    if channel:
        await channel.send_response(from_number, response)
    else:
        # Fallback: eski yöntem (Cloud API)
        reply_text = response.get("text", "")
        if reply_text:
            await send_whatsapp_message(from_number, reply_text)
        if response.get("location"):
            loc = response["location"]
            await send_whatsapp_location(from_number, lat=loc.get("lat"), lng=loc.get("lng"), name=loc.get("name", "Firma"), address=loc.get("address", ""))
        if response.get("image_url"):
            await send_whatsapp_image(from_number, response["image_url"], response.get("image_caption", ""))
        for img in response.get("product_images", []):
            await send_whatsapp_image(from_number, img["url"], f"{img.get('name', '')} - {img.get('price', 0)} TL")


async def send_whatsapp_message(to: str, text: str):
    """WhatsApp Cloud API ile metin mesajı gönder"""
    settings = get_settings()
    url = f"https://graph.facebook.com/v18.0/{settings.whatsapp_phone_number_id}/messages"
    headers = {"Authorization": f"Bearer {settings.whatsapp_access_token}"}
    payload = {
        "messaging_product": "whatsapp",
        "to": to.replace("+", ""),
        "type": "text",
        "text": {"body": text[:4096]},
    }
    async with httpx.AsyncClient() as client:
        await client.post(url, json=payload, headers=headers)


async def send_whatsapp_image(to: str, image_url: str, caption: str = ""):
    """WhatsApp Cloud API ile resim gönder"""
    settings = get_settings()
    url = f"https://graph.facebook.com/v18.0/{settings.whatsapp_phone_number_id}/messages"
    headers = {"Authorization": f"Bearer {settings.whatsapp_access_token}"}
    payload = {
        "messaging_product": "whatsapp",
        "to": to.replace("+", ""),
        "type": "image",
        "image": {"link": image_url, "caption": caption[:1024]},
    }
    async with httpx.AsyncClient() as client:
        await client.post(url, json=payload, headers=headers)


async def send_whatsapp_location(to: str, lat: float, lng: float, name: str = "", address: str = ""):
    """WhatsApp Cloud API ile konum gönder"""
    if lat is None or lng is None:
        return
    settings = get_settings()
    url = f"https://graph.facebook.com/v18.0/{settings.whatsapp_phone_number_id}/messages"
    headers = {"Authorization": f"Bearer {settings.whatsapp_access_token}"}
    payload = {
        "messaging_product": "whatsapp",
        "to": to.replace("+", ""),
        "type": "location",
        "location": {
            "latitude": lat,
            "longitude": lng,
            "name": name[:100] or "Firma",
            "address": address[:200] or "",
        },
    }
    async with httpx.AsyncClient() as client:
        await client.post(url, json=payload, headers=headers)
