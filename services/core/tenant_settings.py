"""
Tenant ayar deposu - tenant_settings tablosu (normalleştirilmiş).
Geçiş aşamasında: Tenant.settings JSON hâlâ birincil kaynak.
Bu modül ileride JSON'dan tam geçiş için kullanılacak.
"""
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models import TenantSetting


async def get_setting(db: AsyncSession, tenant_id: int, key: str) -> Optional[str]:
    """Tenant ayar değerini getir (tenant_settings tablosundan)"""
    result = await db.execute(
        select(TenantSetting.value).where(
            TenantSetting.tenant_id == tenant_id,
            TenantSetting.key == key,
        )
    )
    row = result.scalar_one_or_none()
    return row[0] if row else None


async def set_setting(db: AsyncSession, tenant_id: int, key: str, value: Optional[str]) -> None:
    """Tenant ayar değerini kaydet"""
    result = await db.execute(
        select(TenantSetting).where(
            TenantSetting.tenant_id == tenant_id,
            TenantSetting.key == key,
        )
    )
    row = result.scalar_one_or_none()
    if row:
        row.value = value
    else:
        db.add(TenantSetting(tenant_id=tenant_id, key=key, value=value))
    await db.commit()
