#!/usr/bin/env python3
# Çalıştırma: source venv/bin/activate && python scripts/check_whatsapp.py
"""
WhatsApp bağlantısı ve mesaj akışı kontrolü.
Çalıştırma: python scripts/check_whatsapp.py
"""
import asyncio
import sys
from pathlib import Path

# Proje kökü
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

async def main():
    from config import get_settings
    import httpx

    settings = get_settings()
    bridge_url = settings.whatsapp_bridge_url or "http://localhost:3100"
    api_url = "http://localhost:8000"

    print("=" * 50)
    print("WhatsApp Kontrol")
    print("=" * 50)

    # 1. Bridge durumu
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            r = await client.get(f"{bridge_url}/api/status")
        if r.status_code == 200:
            data = r.json()
            connected = data.get("connected", False)
            print(f"1. Bridge (port 3100): {'✅ Bağlı' if connected else '❌ Bağlı değil'}")
            if not connected:
                print("   → http://localhost:3100 adresinden QR kodu tarayın")
        else:
            print("1. Bridge: ❌ Yanıt alamadı")
    except Exception as e:
        print(f"1. Bridge: ❌ Erişilemiyor ({e})")
        print("   → Bridge çalışıyor mu? npm start veya python run.py")

    # 2. API durumu
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            r = await client.get(f"{api_url}/api/whatsapp/test")
        if r.status_code == 200:
            print("2. API (port 8000): ✅ Çalışıyor")
        else:
            print("2. API: ❌ Yanıt alamadı")
    except Exception as e:
        print(f"2. API: ❌ Erişilemiyor ({e})")
        print("   → API çalışıyor mu? python main.py")

    # 3. AI anahtarları
    has_gemini = bool(settings.gemini_api_key)
    has_openai = bool(settings.openai_api_key)
    if has_gemini or has_openai:
        print(f"3. AI anahtarları: ✅ {'Gemini' if has_gemini else 'OpenAI'}")
    else:
        print("3. AI anahtarları: ❌ .env'de GEMINI_API_KEY veya OPENAI_API_KEY gerekli")

    # 4. Mesaj simülasyonu (API çalışıyorsa)
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            r = await client.post(
                f"{api_url}/api/whatsapp/process",
                json={"from": "905321234567", "text": "Merhaba"},
            )
        if r.status_code == 200:
            data = r.json()
            text = data.get("text", "")
            print(f"4. Mesaj testi: ✅ Yanıt alındı ({len(text)} karakter)")
        else:
            print(f"4. Mesaj testi: ❌ Hata {r.status_code}")
    except Exception as e:
        print(f"4. Mesaj testi: ❌ {e}")

    # 5. Diagnose (olası nedenler)
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            r = await client.get(f"{api_url}/api/whatsapp/diagnose")
        if r.status_code == 200:
            d = r.json()
            if d.get("issues"):
                print("5. Diagnose: ⚠️ Olası sorunlar:")
                for i in d["issues"]:
                    print(f"   • {i}")
            else:
                print("5. Diagnose: ✅ Sorun tespit edilmedi")
    except Exception as e:
        print(f"5. Diagnose: (atlandı) {e}")

    print("=" * 50)
    print("Tüm kontroller tamamlandı.")
    print("Sorun devam ediyorsa: docs/05_OPERASYON.md → WhatsApp Sorun Giderme")
    print("=" * 50)

if __name__ == "__main__":
    asyncio.run(main())
