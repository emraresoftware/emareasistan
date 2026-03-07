"""Telegram kanalı - Update veya chat_id + bot ile"""
from __future__ import annotations
import logging
from typing import Union, TYPE_CHECKING

from .base import BaseChannel

if TYPE_CHECKING:
    from telegram import Update
    from telegram.ext import ContextTypes

logger = logging.getLogger(__name__)


class TelegramChannel(BaseChannel):
    """
    Telegram Bot API.
    update veya (bot, chat_id) ile oluşturulur.
    """

    def __init__(self, update: "Update | None" = None, context: "ContextTypes.DEFAULT_TYPE | None" = None):
        self._update = update
        self._context = context
        self._chat_id: int | None = getattr(update.message.chat, "id", None) if update and update.message else None

    @property
    def platform_id(self) -> str:
        return "telegram"

    def _get_sender(self):
        """Mesaj göndermek için update veya context.bot"""
        if self._update and self._update.message:
            return self._update.message
        if self._context and self._context.bot and self._chat_id:
            return self._context.bot
        return None

    async def send_text(self, recipient_id: str, text: str) -> None:
        if self._update and self._update.message:
            await self._update.message.reply_text(text)
            return
        if self._context and self._context.bot:
            chat_id = int(recipient_id) if recipient_id else self._chat_id
            if chat_id:
                await self._context.bot.send_message(chat_id=chat_id, text=text)

    async def send_image(self, recipient_id: str, image_url: str, caption: str = "") -> None:
        if self._update and self._update.message:
            await self._update.message.reply_photo(photo=image_url, caption=caption)
            return
        if self._context and self._context.bot:
            chat_id = int(recipient_id) if recipient_id else self._chat_id
            if chat_id:
                await self._context.bot.send_photo(chat_id=chat_id, photo=image_url, caption=caption)

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
        if self._update and self._update.message:
            await self._update.message.reply_location(latitude=lat, longitude=lng)
            return
        if self._context and self._context.bot:
            chat_id = int(recipient_id) if recipient_id else self._chat_id
            if chat_id:
                await self._context.bot.send_location(chat_id=chat_id, latitude=lat, longitude=lng)

    @classmethod
    def from_update(cls, update: "Update", context: "ContextTypes.DEFAULT_TYPE") -> "TelegramChannel":
        """Update'ten kanal oluştur - reply için"""
        return cls(update=update, context=context)
