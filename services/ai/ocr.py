"""
OCR Servisi - Plaka, ruhsat, VIN (şasi) metin çıkarma.
Gemini Vision ile görselden metin çıkarır.
"""
import base64
import re
from typing import Optional

import httpx

from config import get_settings


async def extract_text_from_image(
    image_base64: str,
    prompt: str = "Bu resimdeki tüm metni oku ve yaz. Plaka, ruhsat, şasi numarası varsa özellikle belirt.",
    api_key: Optional[str] = None,
    mimetype: str = "image/jpeg",
) -> Optional[str]:
    """
    Görselden metin çıkar (Gemini Vision).
    Returns: Çıkarılan metin veya None
    """
    if not image_base64:
        return None
    try:
        decoded = base64.b64decode(image_base64)
    except Exception:
        return None
    if len(decoded) < 50:
        return None

    key = api_key or get_settings().gemini_api_key
    if not key:
        return None

    model = get_settings().gemini_model or "gemini-2.5-flash-lite"
    model_path = model if model.startswith("models/") else f"models/{model}"
    url = f"https://generativelanguage.googleapis.com/v1beta/{model_path}:generateContent?key={key}"

    payload = {
        "contents": [{
            "parts": [
                {"text": prompt},
                {
                    "inline_data": {
                        "mime_type": mimetype,
                        "data": image_base64,
                    }
                },
            ]
        }],
        "generationConfig": {"maxOutputTokens": 500, "temperature": 0.1},
    }

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(url, json=payload)
            if resp.status_code != 200:
                return None
            data = resp.json()
            parts = data.get("candidates", [{}])[0].get("content", {}).get("parts", [])
            if not parts:
                return None
            return (parts[0].get("text") or "").strip()
    except Exception:
        return None


def extract_plate_from_text(text: str) -> Optional[str]:
    """Metinden Türkiye plaka formatı çıkar (34 ABC 123 vb.)"""
    if not text:
        return None
    # 34 ABC 123, 06A1234, 34-ABC-123
    patterns = [
        r"\b(\d{2}\s*[A-Z]{2,3}\s*\d{2,4})\b",
        r"\b(\d{2}[A-Z]\d{3,4})\b",
        r"\b(\d{2}-[A-Z]{2,3}-\d{2,4})\b",
    ]
    for p in patterns:
        m = re.search(p, text.upper().replace(" ", ""), re.IGNORECASE)
        if m:
            return re.sub(r"\s+", " ", m.group(1).strip())
    return None


def extract_vin_from_text(text: str) -> Optional[str]:
    """Metinden VIN (17 karakter şasi numarası) çıkar"""
    if not text:
        return None
    # VIN: 17 karakter, I,O,Q hariç
    vin_pattern = r"\b([A-HJ-NPR-Z0-9]{17})\b"
    m = re.search(vin_pattern, text.upper())
    if m:
        return m.group(1)
    return None


async def extract_plate_or_vin(
    image_base64: str,
    api_key: Optional[str] = None,
) -> dict:
    """
    Görselden plaka veya VIN çıkar.
    Returns: {"plate": str|None, "vin": str|None, "raw_text": str|None}
    """
    prompt = (
        "Bu resim araç plakası veya ruhsat belgesi olabilir. "
        "Tüm okunabilir metni yaz. Plaka numarası (örn: 34 ABC 123) ve şasi/VIN numarası (17 karakter) varsa mutlaka belirt."
    )
    text = await extract_text_from_image(image_base64, prompt, api_key)
    if not text:
        return {"plate": None, "vin": None, "raw_text": None}
    return {
        "plate": extract_plate_from_text(text),
        "vin": extract_vin_from_text(text),
        "raw_text": text[:500],
    }
