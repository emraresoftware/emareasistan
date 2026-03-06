"""
Kanal yöneticisi - platforma göre kanal döndürür.
Yeni platform eklemek: CHANNELS dict'e ekleyin.
"""
from typing import Any

from .base import BaseChannel, ChatResponse
from .whatsapp_cloud import WhatsAppCloudChannel
from .telegram_channel import TelegramChannel
from .instagram_channel import InstagramChannel

# Platform ID -> Channel class (stateless, singleton kullanılabilir)
CHANNELS: dict[str, type[BaseChannel]] = {
    "whatsapp": WhatsAppCloudChannel,
    "telegram": TelegramChannel,
    "instagram": InstagramChannel,
}


def get_channel(
    platform: str,
    *,
    update: Any = None,
    context: Any = None,
) -> BaseChannel | None:
    """
    Platforma göre kanal instance döndür.
    WhatsApp: get_channel("whatsapp") -> WhatsAppCloudChannel()
    Telegram: get_channel("telegram", update=update, context=context) -> TelegramChannel(update, context)
    """
    platform = (platform or "").strip().lower()
    cls = CHANNELS.get(platform)
    if not cls:
        return None
    if platform == "telegram" and update and context:
        return TelegramChannel.from_update(update, context)
    if platform == "telegram" and (update or context):
        return TelegramChannel(update=update, context=context)
    return cls()


async def send_response(
    platform: str,
    recipient_id: str,
    response: dict | ChatResponse,
    *,
    update: Any = None,
    context: Any = None,
) -> bool:
    """
    ChatHandler yanıtını ilgili kanala gönder.
    Returns: True if sent, False if channel not found or error.
    """
    channel = get_channel(platform, update=update, context=context)
    if not channel:
        return False
    try:
        await channel.send_response(recipient_id, response)
        return True
    except Exception as e:
        import logging
        logging.getLogger(__name__).exception("Channel send_response failed: %s", e)
        return False
