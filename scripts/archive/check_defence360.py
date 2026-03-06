#!/usr/bin/env python3
"""Defence 360 partner ve ilgili kayıtları kontrol eder."""
import asyncio
import sys
sys.path.insert(0, ".")


async def main():
    from models.database import AsyncSessionLocal, init_db
    from models import Tenant, Partner, User
    from sqlalchemy import select

    await init_db()
    async with AsyncSessionLocal() as db:
        r = await db.execute(select(Partner).where(Partner.slug == "defence-360"))
        p = r.scalar_one_or_none()
        if p:
            print("=== DEFENCE 360 PARTNER ===")
            print(f"ID: {p.id}, Ad: {p.name}, Slug: {p.slug}")
            print(f"Settings: {p.settings}")
            print()
        else:
            print("Defence 360 partner bulunamadı!")
            return

        r = await db.execute(select(User).where(User.partner_id == p.id, User.is_partner_admin == True))
        admins = r.scalars().all()
        print("=== PARTNER ADMIN KULLANICILAR ===")
        for u in admins:
            print(f"  {u.email} (id={u.id})")
        if not admins:
            print("  (partner admin kullanıcı yok)")
        print()

        r = await db.execute(select(Tenant).where(Tenant.partner_id == p.id))
        tenants = r.scalars().all()
        print("=== PARTNER'A AIT FIRMALAR ===")
        for t in tenants:
            print(f"  {t.slug} | {t.name} | status={t.status or 'active'}")
        print()
        print(f"Partner giriş: /admin/p/defence-360")
        print(f"Panelim: /admin/partner/panel (partner admin giriş yaptıktan sonra)")


if __name__ == "__main__":
    asyncio.run(main())
