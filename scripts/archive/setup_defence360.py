#!/usr/bin/env python3
"""
Defence 360 partner'ını oluşturur ve belirtilen tenant'ı ona atar.
Kullanım: python scripts/setup_defence360.py [tenant_slug]
Örnek:   python scripts/setup_defence360.py test1
"""
import asyncio
import sys
sys.path.insert(0, ".")

PARTNER_NAME = "Defence 360"
PARTNER_SLUG = "defence-360"


async def main():
    tenant_slug = (sys.argv[1].strip() if len(sys.argv) > 1 else "test1")

    from models.database import AsyncSessionLocal, init_db
    from models import Tenant, Partner
    from sqlalchemy import select

    await init_db()
    async with AsyncSessionLocal() as db:
        r = await db.execute(select(Partner).where(Partner.slug == PARTNER_SLUG))
        partner = r.scalar_one_or_none()
        if not partner:
            partner = Partner(name=PARTNER_NAME, slug=PARTNER_SLUG, is_active=True)
            db.add(partner)
            await db.flush()
            print(f"Partner oluşturuldu: {PARTNER_NAME} ({PARTNER_SLUG})")
        else:
            print(f"Partner mevcut: {partner.name} ({partner.slug})")

        r = await db.execute(select(Tenant).where(Tenant.slug == tenant_slug))
        tenant = r.scalar_one_or_none()
        if not tenant:
            print(f"HATA: Tenant bulunamadı: {tenant_slug}")
            r = await db.execute(select(Tenant).order_by(Tenant.id))
            all_tenants = r.scalars().all()
            print("Mevcut tenant'lar:", ", ".join(t.slug for t in all_tenants))
            sys.exit(1)

        tenant.partner_id = partner.id
        await db.commit()
        print(f"OK: {tenant.name or tenant.slug} → {PARTNER_NAME}")
        print(f"Panelde '{PARTNER_NAME} Asistan' görünecek.")
        print(f"Partner giriş: /admin/p/{PARTNER_SLUG}")


if __name__ == "__main__":
    asyncio.run(main())
