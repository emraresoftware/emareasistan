#!/usr/bin/env python3
"""
Tenant 6 (Emare Asistan) için AI yanıt kurallarını yükle.
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

RULES = [
    "Kullanıcı ile zaten bir demo veya toplantı randevusu oluşturulmuşsa, sohbetin geri kalanında ASLA tekrar randevu, toplantı veya demo talep etme.",
    "Kullanıcı 'olur', 'tamam', 'evet' gibi bir onay verdiğinde, aynı soruyu tekrar sorma; doğrudan bir sonraki adıma (örneğin iletişim bilgisi istemeye) geç.",
    "Kullanıcı sektör bazlı bir soru sorduğunda (örn: 'Tekstil için neler var?'), kısa cevap verip toplantıya yönlendirmek yerine, sistemdeki mevcut özellikleri (ürün kataloğu, sipariş alma, kargo takibi) kullanarak 3-4 maddelik detaylı ve ikna edici bir açıklama yap.",
    "Kullanıcının ad, soyad, telefon ve e-posta bilgilerini bir kez aldıysan, bu bilgileri hafızada tut ve onay aşaması haricinde tekrar tekrar teyit etme.",
    "'Bilgileriniz zaten mevcut' gibi robotik ifadeler kullanma; bunun yerine 'Teşekkürler Emre Bey, bilgilerinizi kaydettim.' gibi doğal ve insansı yanıtlar ver.",
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

        rules = [{"text": r, "priority": 10} for r in RULES]
        existing["ai_response_rules"] = rules
        tenant.settings = json.dumps(existing, ensure_ascii=False)
        await db.commit()

    await invalidate_tenant_cache(TENANT_ID)
    print(f"✓ Tenant {TENANT_ID} için {len(RULES)} kural yüklendi.")
    for i, r in enumerate(RULES, 1):
        print(f"  {i}. {r[:60]}..." if len(r) > 60 else f"  {i}. {r}")


if __name__ == "__main__":
    asyncio.run(main())
