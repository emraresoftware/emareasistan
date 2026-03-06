"""
Instagram DM kanalı - Meta Graph API (Messenger Platform).
Facebook Page + Instagram Business hesabı gerekli.
"""
import logging
import httpx

from .base import BaseChannel
from config import get_settings

logger = logging.getLogger(__name__)

# Meta Graph API v18
GRAPH_API_BASE = "https://graph.facebook.com/v18.0"


class InstagramChannel(BaseChannel):
    """Instagram Direct Messages - Meta Messenger Platform API"""

    @property
    def platform_id(self) -> str:
        return "instagram"

    def _get_config(self) -> tuple[str, str]:
        s = get_settings()
        page_id = (s.instagram_page_id or "").strip() or "me"
        return page_id, s.instagram_access_token

    async def send_text(self, recipient_id: str, text: str) -> None:
        page_id, token = self._get_config()
        if not token:
            logger.warning("Instagram Messaging API not configured")
            return
        url = f"{GRAPH_API_BASE}/{page_id}/messages"
        headers = {"Authorization": f"Bearer {token}"}
        payload = {
            "recipient": {"id": recipient_id},
            "message": {"text": text[:4096]},
        }
        async with httpx.AsyncClient() as client:
            r = await client.post(url, json=payload, headers=headers)
            if r.status_code >= 400:
                logger.warning("Instagram send_text failed: %s %s", r.status_code, r.text[:200])

    async def send_image(self, recipient_id: str, image_url: str, caption: str = "") -> None:
        page_id, token = self._get_config()
        if not token:
            return
        url = f"{GRAPH_API_BASE}/{page_id}/messages"
        headers = {"Authorization": f"Bearer {token}"}
        payload = {
            "recipient": {"id": recipient_id},
            "message": {
                "attachment": {
                    "type": "image",
                    "payload": {"url": image_url, "is_reusable": True},
                }
            },
        }
        async with httpx.AsyncClient() as client:
            r = await client.post(url, json=payload, headers=headers)
            if r.status_code >= 400:
                logger.warning("Instagram send_image failed: %s %s", r.status_code, r.text[:200])
            elif caption:
                # Instagram attachment caption ayrı gönderilmez; text sonra gönder
                await self.send_text(recipient_id, caption)
