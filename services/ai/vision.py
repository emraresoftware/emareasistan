"""
Vision AI - Resim üzerinden ürün eşleştirme.
Gemini ile görsel analiz, katalogdaki en uygun ürünü bul.
"""
import base64
import logging
from typing import Optional

import httpx

from config import get_settings

logger = logging.getLogger(__name__)


async def match_image_to_product(
    image_base64: str,
    product_list: list[dict],
    mimetype: str = "image/jpeg",
    api_key: Optional[str] = None,
) -> Optional[dict]:
    """
    Resimdeki ürünü katalogla eşleştir.
    product_list: [{"id", "name", "description", "category", "price", "image_url"}, ...]
    Returns: en uygun ürün dict veya None
    """
    if not image_base64 or not product_list:
        return None

    try:
        decoded = base64.b64decode(image_base64)
    except Exception:
        return None
    if len(decoded) < 100:
        return None

    key = api_key or get_settings().gemini_api_key
    if not key:
        return None

    # Katalog özeti (çok uzun olmasın)
    catalog_text = "\n".join(
        f"- {p.get('name', '')} (ID:{p.get('id', i)}, {p.get('category', '')}, {p.get('price', 0)} TL)"
        for i, p in enumerate(product_list[:50], 1)
    )

    model = get_settings().gemini_model or "gemini-2.5-flash-lite"
    model_path = model if model.startswith("models/") else f"models/{model}"
    url = f"https://generativelanguage.googleapis.com/v1beta/{model_path}:generateContent?key={key}"

    prompt = f"""Bu resimdeki ürün (koltuk kılıfı, paspas, döşeme vb.) aşağıdaki katalogda hangi ürüne en çok benziyor?
Sadece en uygun ürünün ID numarasını yaz (sadece rakam). Örn: 12
Eşleşme yoksa "0" yaz.

Katalog:
{catalog_text}"""

    payload = {
        "contents": [{
            "parts": [
                {"text": prompt},
                {"inline_data": {"mime_type": mimetype or "image/jpeg", "data": image_base64}},
            ]
        }],
        "generationConfig": {"temperature": 0.1, "maxOutputTokens": 64},
    }

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(url, json=payload)
        if resp.status_code != 200:
            logger.warning("Vision API hatası: %s", resp.status_code)
            return None
        data = resp.json()
        for c in (data.get("candidates") or []):
            for p in (c.get("content", {}).get("parts") or []):
                if "text" in p:
                    raw = (p.get("text") or "").strip()
                    try:
                        pid = int(raw.split()[0]) if raw else 0
                    except (ValueError, IndexError):
                        pid = 0
                    if pid > 0:
                        for prod in product_list:
                            if str(prod.get("id")) == str(pid) or prod.get("id") == pid:
                                return prod
                        if 1 <= pid <= len(product_list):
                            return product_list[pid - 1]
    except Exception as e:
        logger.warning("Vision match hatası: %s", e)
    return None
