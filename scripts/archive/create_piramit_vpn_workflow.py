#!/usr/bin/env python3
"""
Piramit Bilgisayar tenant'ına VPN sorunu iş akışı ekler.
Müşteri "vpn sorunu yaşıyorum" vb. yazdığında sabit yanıt: 
"Bilgisayarınızı yeniden başlatın ve internet bağlantınızı kontrol edin."

Kullanım:
  uv run python scripts/create_piramit_vpn_workflow.py
  uv run python scripts/create_piramit_vpn_workflow.py --tenant-id 2
"""
from __future__ import annotations
import asyncio
import argparse
from sqlalchemy import select

from models.database import AsyncSessionLocal
from models import Tenant
from services.workflow.service import create_workflow, add_workflow_step


WORKFLOW_NAME = "VPN sorunu yanıtı"
WORKFLOW_DESCRIPTION = "Müşteri VPN sorunu yaşıyorum dediğinde sabit yanıt verir."
TRIGGER_KEYWORDS = ["vpn sorunu", "vpn sorun", "vpn yaşıyorum", "vpn problemi"]
REPLY_TEXT = "Bilgisayarınızı yeniden başlatın ve internet bağlantınızı kontrol edin."
PLATFORMS = ["whatsapp", "web"]  # telegram, instagram da eklenebilir


# Giriş: /admin/t/piramit-bilgisayar-panel
PIRAMIT_SLUG = "piramit-bilgisayar-panel"


async def find_tenant_by_slug(session, slug: str) -> int | None:
    """Verdiğiniz slug ile tenant bulur."""
    if not (slug or "").strip():
        return None
    result = await session.execute(
        select(Tenant).where(Tenant.slug == (slug or "").strip())
    )
    t = result.scalar_one_or_none()
    return t.id if t else None


async def find_piramit_tenant(session) -> int | None:
    """Slug piramit-bilgisayar-panel veya isim/slug'da 'piramit' geçen tenant'ı bul."""
    result = await session.execute(
        select(Tenant).where(Tenant.slug == PIRAMIT_SLUG)
    )
    t = result.scalar_one_or_none()
    if t:
        return t.id
    result = await session.execute(
        select(Tenant).where(Tenant.name.ilike("%piramit%"))
    )
    t = result.scalar_one_or_none()
    if t:
        return t.id
    result = await session.execute(
        select(Tenant).where(Tenant.slug.ilike("%piramit%")))
    t = result.scalar_one_or_none()
    return t.id if t else None


async def list_tenants():
    """Tüm tenant'ları listele (--tenant-id bulmak için)."""
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Tenant).order_by(Tenant.id))
        for t in result.scalars().all():
            print(f"  id={t.id}  name={t.name!r}  slug={t.slug or ''}")


async def main():
    parser = argparse.ArgumentParser(description="Piramit VPN workflow oluştur")
    parser.add_argument("--tenant-id", type=int, help="Tenant ID (yoksa slug/isminden bulunur)")
    parser.add_argument("--slug", type=str, help="Tenant slug (örn: piramit-bilgisayar-panel). Giriş: /admin/t/<slug>")
    parser.add_argument("--list-tenants", action="store_true", help="Tenant listesini göster ve çık")
    args = parser.parse_args()

    if args.list_tenants:
        print("Tenant listesi:")
        await list_tenants()
        return 0

    tenant_id = args.tenant_id
    if not tenant_id:
        async with AsyncSessionLocal() as db:
            if args.slug:
                tenant_id = await find_tenant_by_slug(db, args.slug)
            else:
                tenant_id = await find_piramit_tenant(db)
        if not tenant_id:
            print("Hata: Tenant bulunamadı.")
            print("  Seçenekler: --tenant-id <id>  veya  --slug piramit-bilgisayar-panel  veya  --list-tenants")
            return 1
        print(f"Tenant_id: {tenant_id}")

    for platform in PLATFORMS:
        w = await create_workflow(
            tenant_id=tenant_id,
            platform=platform,
            workflow_name=WORKFLOW_NAME,
            description=WORKFLOW_DESCRIPTION,
        )
        await add_workflow_step(
            workflow_id=w.id,
            step_name="VPN tetikleyici",
            step_type="trigger",
            config={"type": "keyword", "keywords": TRIGGER_KEYWORDS},
            order_index=0,
        )
        await add_workflow_step(
            workflow_id=w.id,
            step_name="Sabit yanıt",
            step_type="action",
            config={"type": "template", "text": REPLY_TEXT},
            order_index=1,
        )
        print(f"OK: {platform} için workflow oluşturuldu (id={w.id})")

    print("Bitti. Panelden AI & Otomasyon > İş Akışları altında görebilirsiniz.")
    return 0


if __name__ == "__main__":
    exit(asyncio.run(main()))
