#!/usr/bin/env python3
"""Tenant ve Partner listesini gösterir."""
import asyncio
import sys
sys.path.insert(0, ".")

async def main():
    from models.database import AsyncSessionLocal, init_db
    from models import Tenant, Partner
    from sqlalchemy import select

    await init_db()
    async with AsyncSessionLocal() as db:
        r = await db.execute(select(Tenant).order_by(Tenant.id))
        tenants = r.scalars().all()
        r = await db.execute(select(Partner).order_by(Partner.id))
        partners = r.scalars().all()

    print("=== TENANTS ===")
    for t in tenants:
        p = f" (partner_id={t.partner_id})" if t.partner_id else " (partner yok)"
        print(f"  {t.slug} | {t.name or '-'}{p}")

    print("\n=== PARTNERS ===")
    for p in partners:
        print(f"  {p.slug} | {p.name}")

    print("\nÖrnek atama: python scripts/assign_tenant_to_partner.py <tenant_slug> <partner_slug>")

if __name__ == "__main__":
    asyncio.run(main())
