#!/usr/bin/env python3
"""
Tenant/User uyumsuzluğu teşhis ve düzeltme.
Kullanım:
  python scripts/fix_tenant_check.py                      # Rapor
  python scripts/fix_tenant_check.py --fix -e x@y.com -t cihan-bilisim  # Düzelt
"""
import asyncio
import argparse
import sys
from pathlib import Path

root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root))

from models.database import AsyncSessionLocal
from models import User, Tenant
from sqlalchemy import select


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--fix", action="store_true", help="Düzeltmeyi uygula")
    parser.add_argument("-e", "--email", type=str, help="Düzeltilecek kullanıcı e-postası")
    parser.add_argument("-t", "--tenant-slug", type=str, help="Hedef tenant slug (örn: cihan-bilisim)")
    args = parser.parse_args()

    async with AsyncSessionLocal() as db:
        r = await db.execute(select(Tenant).order_by(Tenant.id))
        tenants = {t.id: t for t in r.scalars().all()}
        print("\n=== TENANT'LAR ===")
        for tid, t in tenants.items():
            print(f"  {tid}: {t.name} (slug={t.slug})")

        r = await db.execute(select(User).where(User.is_active == True).order_by(User.tenant_id, User.id))
        users = r.scalars().all()
        print("\n=== KULLANICILAR ===")
        for u in users:
            t = tenants.get(u.tenant_id or 1)
            tname = (t.name if t else "?") or "?"
            print(f"  id={u.id} email={u.email} tenant_id={u.tenant_id or 1} → {tname}")

        if args.fix and args.email and args.tenant_slug:
            email = args.email.strip().lower()
            r = await db.execute(select(User).where(User.email == email))
            u = r.scalar_one_or_none()
            tid = next((t.id for t in tenants.values() if t.slug == args.tenant_slug), None)
            if not u:
                print(f"\nHata: {email} bulunamadı.")
                return
            if tid is None:
                print(f"\nHata: tenant slug '{args.tenant_slug}' bulunamadı.")
                return
            old = u.tenant_id or 1
            u.tenant_id = tid
            await db.commit()
            print(f"\nDüzeltildi: {email} tenant_id {old} → {tid} ({tenants[tid].name})")
        elif args.fix:
            print("\nDüzeltme için -e EMAIL ve -t TENANT_SLUG gerekli.")
        print()


if __name__ == "__main__":
    asyncio.run(main())
