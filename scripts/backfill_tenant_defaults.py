"""
Mevcut tüm tenantlara örnek veri yükle (tek seferlik çalıştır).

Kullanım:
    python scripts/backfill_tenant_defaults.py

Zaten veri olan tenantlara tekrar ekleme yapmaz.
"""
import asyncio
import sys
import os

# Proje kökünü path'e ekle
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select, func
from models.database import AsyncSessionLocal
from models import Tenant
from models.response_rule import ResponseRule
from models.tenant_workflow import ProcessConfig
from services.core.tenant_defaults import create_tenant_defaults


async def backfill():
    async with AsyncSessionLocal() as db:
        # Tüm aktif tenantları al
        result = await db.execute(select(Tenant).where(Tenant.status == "active").order_by(Tenant.id))
        tenants = result.scalars().all()
        print(f"Toplam tenant: {len(tenants)}")

        skipped = 0
        filled = 0
        errors = 0

        for tenant in tenants:
            # Zaten kuralı var mı?
            rule_count_q = await db.execute(
                select(func.count()).where(ResponseRule.tenant_id == tenant.id)
            )
            rule_count = rule_count_q.scalar()

            # Zaten process config'i var mı?
            cfg_count_q = await db.execute(
                select(func.count()).where(ProcessConfig.tenant_id == tenant.id)
            )
            cfg_count = cfg_count_q.scalar()

            if rule_count > 0 or cfg_count > 0:
                print(f"  ↷ SKIP  [{tenant.id:4d}] {tenant.slug:<30} (kural:{rule_count}, config:{cfg_count})")
                skipped += 1
                continue

            try:
                await create_tenant_defaults(tenant.id, db)
                await db.commit()
                print(f"  ✓ OK    [{tenant.id:4d}] {tenant.slug}")
                filled += 1
            except Exception as e:
                await db.rollback()
                print(f"  ✗ HATA  [{tenant.id:4d}] {tenant.slug}: {e}")
                errors += 1

        print(f"\nSonuç: {filled} yüklendi, {skipped} atlandı, {errors} hata")


if __name__ == "__main__":
    asyncio.run(backfill())
