"""
Metin → ses (Text-to-Speech)
OpenAI TTS API ile. Sesli mesajla gelen müşteriye sesli yanıt için.
"""
import base64
import logging
from typing import Optional

from config import get_settings

logger = logging.getLogger(__name__)


async def text_to_speech(text: str, voice: str = "alloy") -> tuple[Optional[str], Optional[str]]:
    """
    Metni sese çevir.
    Returns: (audio_base64, mimetype) veya (None, None) hata/anahtar yoksa.
    """
    if not text or not (text := text.strip()):
        return None, None

    # Uzun metinleri kısalt (TTS limit ~4096 karakter, pratikte 500-1000 yeterli)
    if len(text) > 1000:
        text = text[:997] + "..."

    settings = get_settings()
    if not (settings.openai_api_key or "").strip():
        logger.debug("TTS: OpenAI API key yok, atlanıyor")
        return None, None

    try:
        from openai import AsyncOpenAI
        client = AsyncOpenAI(api_key=settings.openai_api_key)
        resp = await client.audio.speech.create(
            model="tts-1",
            voice=voice,
            input=text,
            response_format="mp3",
        )
        audio_bytes = resp.content
        if not audio_bytes:
            return None, None
        return base64.b64encode(audio_bytes).decode("ascii"), "audio/mpeg"
    except Exception as e:
        logger.warning("TTS hatası: %s", e)
        return None, None
