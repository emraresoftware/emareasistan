"""
Sesli mesaj → metin (Speech-to-Text)
Gemini veya OpenAI Whisper ile. WhatsApp sesli mesajları genelde audio/ogg.
"""
import base64
import logging
import tempfile
from pathlib import Path

import httpx

from config import get_settings

logger = logging.getLogger(__name__)


async def transcribe_audio(audio_base64: str, mimetype: str = "audio/ogg") -> str:
    """
    Ses dosyasını metne çevir.
    Önce Gemini dener, yoksa OpenAI Whisper.
    Returns: transkribe edilmiş metin veya boş string.
    """
    try:
        audio_bytes = base64.b64decode(audio_base64)
    except Exception as e:
        logger.warning("Speech-to-text: base64 decode hatası: %s", e)
        return ""

    if not audio_bytes or len(audio_bytes) < 100:
        return ""

    settings = get_settings()

    # 1. Gemini ile dene (zaten kullanılıyor)
    if settings.gemini_api_key:
        try:
            model = settings.gemini_model or "gemini-2.5-flash-lite"
            model_path = model if model.startswith("models/") else f"models/{model}"
            url = f"https://generativelanguage.googleapis.com/v1beta/{model_path}:generateContent?key={settings.gemini_api_key}"

            payload = {
                "contents": [{
                    "parts": [
                        {"text": "Bu ses kaydını Türkçe metne çevir. Sadece konuşulan metni yaz, başka açıklama ekleme."},
                        {"inline_data": {"mime_type": mimetype or "audio/ogg", "data": audio_base64}},
                    ]
                }],
                "generationConfig": {"temperature": 0.1, "maxOutputTokens": 1024},
            }
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(url, json=payload)
            if resp.status_code == 200:
                data = resp.json()
                for c in (data.get("candidates") or []):
                    for p in (c.get("content", {}).get("parts") or []):
                        if "text" in p:
                            text = (p["text"] or "").strip()
                            if text:
                                return text
        except Exception as e:
            logger.warning("Gemini speech-to-text hatası: %s", e)

    # 2. OpenAI Whisper ile dene
    if settings.openai_api_key:
        try:
            with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as f:
                f.write(audio_bytes)
                tmp_path = f.name
            try:
                from openai import AsyncOpenAI
                client = AsyncOpenAI(api_key=settings.openai_api_key)
                with open(tmp_path, "rb") as f:
                    resp = await client.audio.transcriptions.create(
                        model="whisper-1",
                        file=f,
                        language="tr",
                    )
                return (resp.text or "").strip()
            finally:
                Path(tmp_path).unlink(missing_ok=True)
        except Exception as e:
            logger.warning("Whisper speech-to-text hatası: %s", e)

    return ""
