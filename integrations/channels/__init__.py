"""
Kanal soyutlaması - WhatsApp, Telegram, Instagram vb. için ortak interface.
Yeni platform eklemek için BaseChannel'dan türetip CHANNELS'a kaydedin.
"""
from .base import BaseChannel, InboundMessage
from .manager import get_channel, send_response, CHANNELS

__all__ = [
    "BaseChannel",
    "InboundMessage",
    "get_channel",
    "send_response",
    "CHANNELS",
]
