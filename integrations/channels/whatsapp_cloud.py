"""WhatsApp Cloud API kanalı"""
import logging
import httpx

from .base import BaseChannel
from config import get_settings

logger = logging.getLogger(__name__)


class WhatsAppCloudChannel(BaseChannel):
    """Meta WhatsApp Business Cloud API"""

    @property
    def platform_id(self) -> str:
        return "whatsapp"

    def _get_config(self) -> tuple[str, str]:
        s = get_settings()
        return s.whatsapp_phone_number_id, s.whatsapp_access_token

    async def send_text(self, recipient_id: str, text: str) -> None:
        phone_id, token = self._get_config()
        if not phone_id or not token:
            logger.warning("WhatsApp Cloud API not configured")
            return
        url = f"https://graph.facebook.com/v18.0/{phone_id}/messages"
        headers = {"Authorization": f"Bearer {token}"}
        payload = {
            "messaging_product": "whatsapp",
            "to": recipient_id.replace("+", ""),
            "type": "text",
            "text": {"body": text[:4096]},
        }
        async with httpx.AsyncClient() as client:
            r = await client.post(url, json=payload, headers=headers)
            if r.status_code >= 400:
                logger.warning("WhatsApp send failed: %s %s", r.status_code, r.text[:200])

    async def send_image(self, recipient_id: str, image_url: str, caption: str = "") -> None:
        phone_id, token = self._get_config()
        if not phone_id or not token:
            return
        url = f"https://graph.facebook.com/v18.0/{phone_id}/messages"
        headers = {"Authorization": f"Bearer {token}"}
        payload = {
            "messaging_product": "whatsapp",
            "to": recipient_id.replace("+", ""),
            "type": "image",
            "image": {"link": image_url, "caption": caption[:1024]},
        }
        async with httpx.AsyncClient() as client:
            await client.post(url, json=payload, headers=headers)

    async def send_location(
        self,
        recipient_id: str,
        lat: float,
        lng: float,
        name: str = "",
        address: str = "",
    ) -> None:
        if lat is None or lng is None:
            return
        phone_id, token = self._get_config()
        if not phone_id or not token:
            return
        url = f"https://graph.facebook.com/v18.0/{phone_id}/messages"
        headers = {"Authorization": f"Bearer {token}"}
        payload = {
            "messaging_product": "whatsapp",
            "to": recipient_id.replace("+", ""),
            "type": "location",
            "location": {
                "latitude": lat,
                "longitude": lng,
                "name": name[:100] or "Konum",
                "address": address[:200] or "",
            },
        }
        async with httpx.AsyncClient() as client:
            await client.post(url, json=payload, headers=headers)
