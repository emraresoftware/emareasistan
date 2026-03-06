#!/usr/bin/env python3
"""Tenant için web_chat modülünü etkinleştirir. Örn: python scripts/enable_web_chat_tenant.py cihan-bilisim"""
import asyncio
import json
import sys

sys.path.insert(0, ".")


async def main():
    from models.database import AsyncSessionLocal, init_db
    from models import Tenant
    from sqlalchemy import select, update

    slug = (sys.argv[1] if len(sys.argv) > 1 else "").strip()
    if not slug:
        print("Kullanım: python scripts/enable_web_chat_tenant.py <tenant_slug>")
        print("Örnek: python scripts/enable_web_chat_tenant.py cihan-bilisim")
        return 1

    await init_db()
    async with AsyncSessionLocal() as db:
        r = await db.execute(select(Tenant).where(Tenant.slug == slug, Tenant.status == "active"))
        t = r.scalar_one_or_none()
        if not t:
            print(f"Tenant bulunamadı: {slug}")
            return 1

        raw = t.enabled_modules
        if raw is None or raw == "":
            print(f"{t.name} ({slug}): Zaten tüm modüller etkin (enabled_modules=null)")
            return 0

        try:
            arr = json.loads(raw) if isinstance(raw, str) else raw
        except Exception:
            arr = []
        mods = set(str(m) for m in arr if m)

        if "web_chat" in mods:
            print(f"{t.name} ({slug}): web_chat zaten etkin")
            return 0

        mods.add("web_chat")
        new_list = sorted(mods)
        t.enabled_modules = json.dumps(new_list)
        await db.commit()
        print(f"{t.name} ({slug}): web_chat eklendi. Etkin modüller: {', '.join(new_list[:10])}{'...' if len(new_list) > 10 else ''}")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
