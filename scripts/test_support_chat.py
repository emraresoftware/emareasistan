#!/usr/bin/env python3
"""
Panel yardım sohbeti için Gemini API testi.
Sunucuda veya lokalde: python scripts/test_support_chat.py
"""
import asyncio
import os
import sys

# Proje kökü
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()


async def test_gemini():
    import httpx
    from config import get_settings

    settings = get_settings()
    key = settings.gemini_api_key
    model = settings.gemini_model or "gemini-2.5-flash-lite"

    if not key:
        print("HATA: .env içinde GEMINI_API_KEY tanımlı değil")
        return False

    model_path = model if model.startswith("models/") else f"models/{model}"
    url = f"https://generativelanguage.googleapis.com/v1beta/{model_path}:generateContent?key={key}"

    prompt = "[Sistem talimatı]\nTest\n\n[Müşteri]\nMerhaba"
    payload = {"contents": [{"parts": [{"text": prompt}]}]}

    print(f"Model: {model}")
    print(f"URL (key gizli): {url.split('?')[0]}?key=***")
    print("İstek gönderiliyor...")

    try:
        async with httpx.AsyncClient(timeout=25.0) as client:
            resp = await client.post(url, json=payload)
        print(f"HTTP {resp.status_code}")
        if resp.status_code == 200:
            data = resp.json()
            candidates = data.get("candidates") or []
            if candidates:
                text = (candidates[0].get("content", {}).get("parts") or [{}])[0].get("text", "")
                print(f"✓ Başarılı. Yanıt: {text[:150]}...")
                return True
            print("UYARI: candidates boş:", data)
            return False
        print(f"HATA yanıtı: {resp.text[:500]}")
        return False
    except Exception as e:
        print(f"İstisna: {type(e).__name__}: {e}")
        return False


if __name__ == "__main__":
    ok = asyncio.run(test_gemini())
    sys.exit(0 if ok else 1)
