#!/usr/bin/env python3
"""
Tenant 6 (Emare Asistan) için Soru Seçenekleri (quick_reply_options) yükle.
"""
import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from models.database import AsyncSessionLocal
from models import Tenant
from sqlalchemy import select
from services.core.cache import invalidate_tenant_cache

TENANT_ID = 6

# Etiket: müşteriye görünen | text: tıklayınca gönderilecek metin
OPTIONS = [
    {"label": "Demo talep et", "text": "Demo veya canlı tanıtım talep etmek istiyorum"},
    {"label": "Özellikler", "text": "Emare Asistan özellikleri ve nasıl çalıştığı hakkında bilgi almak istiyorum"},
    {"label": "Fiyatlandırma", "text": "Fiyatlandırma ve paketler hakkında bilgi almak istiyorum"},
    {"label": "Sektörüm için", "text": "Benim sektörüm için nasıl kullanabilirim, örnek senaryolar görmek istiyorum"},
    {"label": "Randevu al", "text": "Görüşme veya demo randevusu almak istiyorum"},
    {"label": "WhatsApp entegrasyonu", "text": "WhatsApp entegrasyonu ve kurulum hakkında bilgi almak istiyorum"},
]


async def main():
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Tenant).where(Tenant.id == TENANT_ID))
        tenant = result.scalar_one_or_none()
        if not tenant:
            print(f"Tenant {TENANT_ID} bulunamadı.")
            return

        existing = {}
        if tenant.settings:
            try:
                existing = json.loads(tenant.settings)
            except json.JSONDecodeError:
                existing = {}

        existing["quick_reply_options"] = {"enabled": True, "options": OPTIONS}
        tenant.settings = json.dumps(existing, ensure_ascii=False)
        await db.commit()

    await invalidate_tenant_cache(TENANT_ID)
    print(f"✓ Tenant {TENANT_ID} için {len(OPTIONS)} soru seçeneği yüklendi (aktif).")
    for i, o in enumerate(OPTIONS, 1):
        print(f"  {i}. {o['label']} → \"{o['text'][:50]}...\"" if len(o['text']) > 50 else f"  {i}. {o['label']} → \"{o['text']}\"")


if __name__ == "__main__":
    asyncio.run(main())
