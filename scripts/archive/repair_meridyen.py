#!/usr/bin/env python3
"""Meridyen Oto tenant ve murat@meridyen.com kullanıcısını oluştur/düzelt"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


async def main():
    from models.database import AsyncSessionLocal, init_db
    from models import Tenant, User
    from sqlalchemy import select
    import json
    import bcrypt

    await init_db()

    settings = __import__("config.settings", fromlist=["get_settings"]).get_settings()

    async with AsyncSessionLocal() as db:
        # Tenant 1 (Meridyen Oto) - yoksa oluştur
        r = await db.execute(select(Tenant).where(Tenant.id == 1))
        t = r.scalar_one_or_none()
        if not t:
            tenant_settings = {
                "name": "Meridyen Oto",
                "address": getattr(settings, "meridyen_address", ""),
                "phone": getattr(settings, "meridyen_phone", ""),
                "lat": getattr(settings, "meridyen_lat", ""),
                "lng": getattr(settings, "meridyen_lng", ""),
                "maps_url": getattr(settings, "meridyen_maps_url", ""),
            }
            t = Tenant(
                name="Meridyen Group",
                slug="meridyen-oto",
                website_url="https://meridyenoto.com",
                sector="otomobil",
                products_path="data/products_scraped.json",
                status="active",
                settings=json.dumps(tenant_settings, ensure_ascii=False),
            )
            db.add(t)
            await db.flush()
            print("Meridyen Oto tenant oluşturuldu (id=1)")
        else:
            print("Meridyen Oto tenant zaten mevcut")

        # murat@meridyen.com kullanıcısı - yoksa oluştur, varsa şifreyi güncelle
        import os
        email = "murat@meridyen.com"
        password = os.environ.get("REPAIR_PASSWORD", "changeme")
        if password == "changeme":
            print("⚠️  UYARI: REPAIR_PASSWORD env değişkeni ayarlanmadı, varsayılan kullanılıyor!")
        pw_hash = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

        r = await db.execute(select(User).where(User.email == email))
        u = r.scalar_one_or_none()
        if not u:
            u = User(
                tenant_id=1,
                name="Murat",
                email=email,
                password_hash=pw_hash,
                role="admin",
            )
            db.add(u)
            print("murat@meridyen.com kullanıcısı oluşturuldu")
        else:
            u.password_hash = pw_hash
            u.tenant_id = 1
            u.role = "admin"
            u.is_active = True
            print("murat@meridyen.com kullanıcısı güncellendi (şifre: 3673)")

        await db.commit()

    print("Tamamlandı.")


if __name__ == "__main__":
    asyncio.run(main())
