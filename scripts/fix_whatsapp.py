#!/usr/bin/env python3
"""
WhatsApp "bağlı ama cevap vermiyor" - Otomatik düzeltme
Temsilci devralmasını sıfırlar, diagnose çalıştırır, API test eder.

Çalıştırma: python scripts/fix_whatsapp.py
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


async def main():
    from models.database import AsyncSessionLocal, init_db
    from models import Conversation
    from sqlalchemy import select
    from config import get_settings
    import httpx

    print("=" * 55)
    print("WhatsApp Otomatik Düzeltme")
    print("=" * 55)

    await init_db()

    # 1. Temsilci devralmasını sıfırla
    async with AsyncSessionLocal() as db:
        r = await db.execute(
            select(Conversation).where(Conversation.agent_taken_over_at.isnot(None))
        )
        convs = r.scalars().all()
        for c in convs:
            c.agent_taken_over_at = None
            c.agent_name = None
        await db.commit()
        if convs:
            print(f"1. Temsilci devralması: {len(convs)} sohbet AI'ya bırakıldı")
        else:
            print("1. Temsilci devralması: Zaten yok")

    # 2. AI anahtarı kontrolü
    settings = get_settings()
    has_ai = bool((settings.gemini_api_key or "").strip()) or bool((settings.openai_api_key or "").strip())
    if has_ai:
        print("2. AI anahtarı: Var")
    else:
        print("2. AI anahtarı: YOK - .env'e GEMINI_API_KEY veya OPENAI_API_KEY ekleyin")

    # 3. API test (çalışıyorsa)
    api_url = "http://localhost:8000"
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            r = await client.get(f"{api_url}/api/whatsapp/test")
        if r.status_code == 200:
            print("3. API: Çalışıyor")
        else:
            print("3. API: Yanıt alamadı (API çalışıyor mu?)")
    except Exception as e:
        print(f"3. API: Erişilemiyor ({e})")
        print("   -> python main.py ile API'yi başlatın")

    # 4. Diagnose
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            r = await client.get(f"{api_url}/api/whatsapp/diagnose")
        if r.status_code == 200:
            d = r.json()
            if d.get("issues"):
                print("4. Diagnose: Olası sorunlar:")
                for i in d["issues"]:
                    print(f"   - {i}")
            else:
                print("4. Diagnose: Sorun tespit edilmedi")
    except Exception:
        print("4. Diagnose: (API çalışmıyorsa atlandı)")

    # 5. Mesaj simülasyonu
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            r = await client.post(
                f"{api_url}/api/whatsapp/process",
                json={"from": "905321234567", "text": "Merhaba"},
            )
        if r.status_code == 200:
            data = r.json()
            text = data.get("text", "")
            if text:
                print(f"5. Mesaj testi: Yanıt alındı ({len(text)} karakter)")
            else:
                print("5. Mesaj testi: Boş yanıt - AI anahtarı veya limit kontrol edin")
        else:
            print(f"5. Mesaj testi: Hata {r.status_code}")
    except Exception as e:
        print(f"5. Mesaj testi: {e}")

    print("=" * 55)
    print("Tamamlandı. Uygulamayı yeniden başlatın: python run.py")
    print("=" * 55)


if __name__ == "__main__":
    asyncio.run(main())
