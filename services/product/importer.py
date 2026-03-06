"""JSON'dan Products tablosuna ürün aktarımı"""
import json
from pathlib import Path
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from models import Product


async def import_products_from_json(
    db: AsyncSession,
    json_path: str | Path,
    tenant_id: int = 1,
    clear_existing: bool = False,
) -> int:
    """
    JSON dosyasından ürünleri Products tablosuna aktar.
    Returns: aktarılan ürün sayısı
    """
    path = Path(json_path)
    if not path.exists():
        raise FileNotFoundError(f"JSON dosyası bulunamadı: {path}")
    with open(path, encoding="utf-8") as f:
        products = json.load(f)
    if not isinstance(products, list):
        products = [products]
    if clear_existing:
        from sqlalchemy import delete
        await db.execute(delete(Product).where(Product.tenant_id == tenant_id))
        await db.commit()
    count = 0
    for p in products:
        name = (p.get("name") or "").strip()
        if not name:
            continue
        vc = p.get("vehicle_compatibility")
        if isinstance(vc, list):
            vc = json.dumps(vc, ensure_ascii=False)
        prod = Product(
            tenant_id=tenant_id,
            name=name,
            slug=(p.get("slug") or "").strip() or None,
            description=(p.get("description") or "").strip() or None,
            category=(p.get("category") or "").strip() or None,
            price=float(p.get("price") or 0),
            image_url=(p.get("image_url") or "").strip() or None,
            vehicle_compatibility=vc,
            external_url=(p.get("external_url") or "").strip() or None,
        )
        db.add(prod)
        count += 1
    await db.commit()
    return count
