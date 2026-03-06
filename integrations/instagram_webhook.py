"""
Instagram Messaging API - Webhook handler
Meta Graph API üzerinden gelen Instagram DM mesajlarını işler
"""
import logging
from time import perf_counter

from fastapi import APIRouter, Request, Response

from config import get_settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/webhook/instagram", tags=["instagram"])


@router.get("")
async def verify_webhook(request: Request):
    """
    Meta webhook doğrulaması - GET isteği
    VERIFY_TOKEN ve challenge ile yanıt ver
    """
    mode = request.query_params.get("hub.mode")
    token = request.query_params.get("hub.verify_token")
    challenge = request.query_params.get("hub.challenge")

    if mode == "subscribe" and token == get_settings().instagram_verify_token:
        return Response(content=challenge, media_type="text/plain")
    return Response(status_code=403)


@router.post("")
async def handle_webhook(request: Request):
    """
    Instagram DM mesajları - POST isteği
    Gelen mesajları işleyip yanıt gönder
    """
    body = await request.json()

    if body.get("object") != "instagram":
        return {"status": "ignored"}

    for entry in body.get("entry", []):
        for msg_event in entry.get("messaging", []):
            message = msg_event.get("message")
            if not message:
                continue
            sender_id = (msg_event.get("sender") or {}).get("id")
            if not sender_id:
                continue
            text = message.get("text") or ""
            if isinstance(text, dict):
                text = text.get("text", "") or ""
            text = str(text).strip()
            await process_instagram_message(
                sender_id=sender_id,
                message_id=message.get("mid"),
                text=text,
            )

    return {"status": "ok"}


async def process_instagram_message(
    sender_id: str,
    message_id: str | None,
    text: str,
):
    """Instagram mesajını işle ve yanıt gönder"""
    if not text:
        return

    from models.database import AsyncSessionLocal
    from integrations import ChatHandler
    from services.workflow.metrics import record_chat_response_event

    started = perf_counter()
    ok = True
    try:
        async with AsyncSessionLocal() as db:
            handler = ChatHandler(db)
            response = await handler.process_message(
                platform="instagram",
                user_id=sender_id,
                message_text=text,
                conversation_history=[],
                customer_phone=None,
            )
    except Exception as e:
        ok = False
        logger.exception("Instagram webhook mesaj işleme hatası: %s", e)
        settings = get_settings()
        fallback = f"Üzgünüz, teknik bir gecikme yaşıyoruz. Lütfen daha sonra tekrar deneyin."
        await _send_instagram_message(sender_id, fallback)
        return
    finally:
        duration_ms = int((perf_counter() - started) * 1000)
        record_chat_response_event(
            tenant_id=1,
            ok=ok,
            latency_ms=duration_ms,
            channel="instagram",
        )

    from integrations.channels import get_channel, send_response
    channel = get_channel("instagram")
    if channel:
        await channel.send_response(sender_id, response)
    else:
        reply_text = response.get("text", "")
        if reply_text:
            await _send_instagram_message(sender_id, reply_text)
        if response.get("image_url"):
            await _send_instagram_image(sender_id, response["image_url"], response.get("image_caption", ""))
        for img in response.get("product_images", []):
            caption = f"{img.get('name', '')} - {img.get('price', 0)} TL"
            await _send_instagram_image(sender_id, img.get("url", ""), caption)


async def _send_instagram_message(recipient_id: str, text: str):
    """Instagram Messaging API ile metin mesajı gönder"""
    from integrations.channels import get_channel
    channel = get_channel("instagram")
    if channel:
        await channel.send_text(recipient_id, text)


async def _send_instagram_image(recipient_id: str, image_url: str, caption: str = ""):
    """Instagram Messaging API ile resim gönder"""
    from integrations.channels import get_channel
    channel = get_channel("instagram")
    if channel:
        await channel.send_image(recipient_id, image_url, caption)
