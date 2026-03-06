#!/usr/bin/env python3
"""
Tenant'ı bir partner'a ata. Örnek: test1 firmasını Defence 360'a ata.
Kullanım: python scripts/assign_tenant_to_partner.py test1 defence-360
"""
import asyncio
import sys

sys.path.insert(0, ".")


async def main():
    if len(sys.argv) < 3:
        print("Kullanım: python scripts/assign_tenant_to_partner.py <tenant_slug> <partner_slug>")
        print("Örnek: python scripts/assign_tenant_to_partner.py test1-test defence-360")
        sys.exit(1)
    tenant_slug = sys.argv[1].strip()
    partner_slug = sys.argv[2].strip()

    from models.database import AsyncSessionLocal, init_db
    from models import Tenant, Partner
    from sqlalchemy import select

    await init_db()
    async with AsyncSessionLocal() as db:
        r = await db.execute(select(Tenant).where(Tenant.slug == tenant_slug))
        tenant = r.scalar_one_or_none()
        if not tenant:
            print(f"Tenant bulunamadı: {tenant_slug}")
            sys.exit(1)
        r = await db.execute(select(Partner).where(Partner.slug == partner_slug))
        partner = r.scalar_one_or_none()
        if not partner:
            print(f"Partner bulunamadı: {partner_slug}")
            sys.exit(1)
        tenant.partner_id = partner.id
        await db.commit()
        print(f"OK: {tenant.name or tenant.slug} → {partner.name} partner'ına atandı.")
        print(f"Artık test1 panelinde '{partner.name} Asistan' görünecek.")


if __name__ == "__main__":
    asyncio.run(main())
