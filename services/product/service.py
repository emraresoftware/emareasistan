"""Ürün arama ve öneri servisi - JSON veya Products tablosu"""
from __future__ import annotations
import json
from pathlib import Path
from typing import Optional
from sqlalchemy import select, func, text
from sqlalchemy.ext.asyncio import AsyncSession

from config import get_settings
from models import Product


class ProductService:
    """Ürün katalogu ve arama - tenant bazlı. DB'de ürün varsa oradan, yoksa JSON."""

    def __init__(self, db: AsyncSession | None = None, tenant_id: int = 1, products_path: str | None = None):
        self.db = db
        self.tenant_id = tenant_id
        self.products_path = products_path
        self._sample_products = self._load_sample_products()
        self._from_db: bool = False

    def _load_sample_products(self) -> list[dict]:
        """Ürün verisini yükle - tenant products_path veya varsayılan"""
        base = Path(__file__).parent.parent
        data_dir = base / "data"

        if self.products_path:
            path = base / self.products_path
            if path.exists():
                with open(path, encoding="utf-8") as f:
                    products = json.load(f)
            else:
                products = []
        else:
            scraped = data_dir / "products_scraped.json"
            sample = data_dir / "products_sample.json"
            if scraped.exists():
                with open(scraped, encoding="utf-8") as f:
                    products = json.load(f)
            elif sample.exists():
                with open(sample, encoding="utf-8") as f:
                    products = json.load(f)
            else:
                products = []

        # Her ürüne index tabanlı id ekle (get_by_id için)
        for i, p in enumerate(products, 1):
            p.setdefault("id", i)
        return products

    async def _ensure_products(self) -> None:
        """DB'de ürün varsa onları kullan (JSON'dan öncelikli)"""
        if self._from_db or not self.db:
            return
        result = await self.db.execute(
            select(func.count(Product.id)).where(
                (Product.tenant_id == self.tenant_id) | (Product.tenant_id.is_(None))
            )
        )
        count = result.scalar() or 0
        if count > 0:
            r = await self.db.execute(
                select(Product)
                .where((Product.tenant_id == self.tenant_id) | (Product.tenant_id.is_(None)))
                .order_by(Product.id)
            )
            rows = r.scalars().all()
            self._sample_products = []
            for i, p in enumerate(rows, 1):
                vc = p.vehicle_compatibility
                if isinstance(vc, str):
                    try:
                        vc = json.loads(vc) if vc else []
                    except json.JSONDecodeError:
                        vc = []
                self._sample_products.append({
                    "id": p.id,
                    "name": p.name,
                    "slug": p.slug,
                    "description": p.description or "",
                    "category": p.category or "",
                    "price": float(p.price or 0),
                    "image_url": p.image_url or "",
                    "vehicle_compatibility": vc,
                    "external_url": p.external_url or "",
                })
            self._from_db = True

    async def _search_fts(
        self,
        query: str,
        category: str = "",
        vehicle: str = "",
        max_price: Optional[float] = None,
        limit: int = 10,
    ) -> list[dict] | None:
        """PostgreSQL FTS + typo tolerant (pg_trgm) arama. Başarısızsa None."""
        if not self.db or not query or len(query.strip()) < 2:
            return None
        url = get_settings().database_url
        if "postgresql" not in url:
            return None
        try:
            q = query.strip()
            conditions = ["(tenant_id = :tid OR tenant_id IS NULL)"]
            # pg_trgm varsa similarity(...) devreye girer; yoksa except bloğunda ilike fallback var
            conditions.append(
                "("
                "search_vector @@ plainto_tsquery('turkish', :q) "
                "OR similarity(name, :q) > 0.22 "
                "OR similarity(coalesce(description,''), :q) > 0.18 "
                "OR name ILIKE :likeq "
                "OR description ILIKE :likeq"
                ")"
            )
            params = {"tid": self.tenant_id, "q": q, "likeq": f"%{q}%", "lim": limit}
            if category:
                conditions.append("category = :cat")
                params["cat"] = category
            if max_price:
                conditions.append("price <= :maxp")
                params["maxp"] = max_price
            where = " AND ".join(conditions)
            sql = f"""
                SELECT id, name, slug, description, category, price, image_url, vehicle_compatibility, external_url
                FROM products
                WHERE {where}
                ORDER BY
                    GREATEST(similarity(name, :q), similarity(coalesce(description,''), :q)) DESC,
                    ts_rank(search_vector, plainto_tsquery('turkish', :q)) DESC
                LIMIT :lim
            """
            result = await self.db.execute(text(sql), params)
            rows = result.fetchall()
            out = []
            for r in rows:
                vc = r.vehicle_compatibility
                if isinstance(vc, str):
                    try:
                        vc = json.loads(vc) if vc else []
                    except json.JSONDecodeError:
                        vc = []
                out.append({
                    "id": r.id,
                    "name": r.name,
                    "slug": r.slug,
                    "description": r.description or "",
                    "category": r.category or "",
                    "price": float(r.price or 0),
                    "image_url": r.image_url or "",
                    "vehicle_compatibility": vc,
                    "external_url": r.external_url or "",
                })
            if vehicle and out:
                out = [p for p in out if vehicle.lower() in str(p.get("vehicle_compatibility", [])).lower()]
            return out if out else None
        except Exception:
            # pg_trgm yoksa güvenli fallback: ILIKE + rank yok
            try:
                q = query.strip()
                conditions = [
                    "(tenant_id = :tid OR tenant_id IS NULL)",
                    "(name ILIKE :likeq OR description ILIKE :likeq OR category ILIKE :likeq)",
                ]
                params = {"tid": self.tenant_id, "likeq": f"%{q}%", "lim": limit}
                if category:
                    conditions.append("category = :cat")
                    params["cat"] = category
                if max_price:
                    conditions.append("price <= :maxp")
                    params["maxp"] = max_price
                where = " AND ".join(conditions)
                sql = f"""
                    SELECT id, name, slug, description, category, price, image_url, vehicle_compatibility, external_url
                    FROM products
                    WHERE {where}
                    ORDER BY updated_at DESC
                    LIMIT :lim
                """
                result = await self.db.execute(text(sql), params)
                rows = result.fetchall()
                out = []
                for r in rows:
                    vc = r.vehicle_compatibility
                    if isinstance(vc, str):
                        try:
                            vc = json.loads(vc) if vc else []
                        except json.JSONDecodeError:
                            vc = []
                    out.append({
                        "id": r.id,
                        "name": r.name,
                        "slug": r.slug,
                        "description": r.description or "",
                        "category": r.category or "",
                        "price": float(r.price or 0),
                        "image_url": r.image_url or "",
                        "vehicle_compatibility": vc,
                        "external_url": r.external_url or "",
                    })
                if vehicle and out:
                    out = [p for p in out if vehicle.lower() in str(p.get("vehicle_compatibility", [])).lower()]
                return out if out else None
            except Exception:
                return None

    async def search(
        self,
        query: str = "",
        category: str = "",
        vehicle: str = "",
        max_price: Optional[float] = None,
    ) -> list[dict]:
        """Arama kriterlerine göre ürün listesi - PostgreSQL FTS veya Python filter"""
        await self._ensure_products()
        if query and self._from_db:
            fts_result = await self._search_fts(query, category, vehicle, max_price, limit=10)
            if fts_result is not None:
                return fts_result
        products = self._sample_products

        if query:
            words = [w.strip() for w in query.lower().split() if len(w.strip()) > 2]
            words = words or [query.lower()]
            products = [
                p
                for p in products
                if any(
                    w in p.get("name", "").lower()
                    or w in p.get("description", "").lower()
                    or w in p.get("category", "").lower()
                    for w in words
                )
            ]
        if category:
            products = [p for p in products if p.get("category") == category]
        if vehicle:
            products = [
                p for p in products
                if vehicle.lower() in str(p.get("vehicle_compatibility", [])).lower()
            ]
        if max_price:
            products = [p for p in products if p.get("price", 0) <= max_price]

        return products[:10]

    async def get_all_for_vision(self, max_count: int = 50) -> list[dict]:
        """Vision AI için tüm ürünler - eşleştirme katalogu"""
        await self._ensure_products()
        return self._sample_products[:max_count]

    async def get_diverse_products(self, max_count: int = 12, vehicle: str = "") -> list[dict]:
        """Farklı kategorilerden ürün getir - resim yolla/tüm ürünler için"""
        await self._ensure_products()
        products = self._sample_products
        if vehicle:
            vehicle_matched = [
                p for p in products
                if vehicle.lower() in str(p.get("vehicle_compatibility", [])).lower()
                or "tüm araçlar" in str(p.get("vehicle_compatibility", [])).lower()
                or "evrensel" in str(p.get("vehicle_compatibility", [])).lower()
            ]
            if vehicle_matched:
                products = vehicle_matched
        by_category: dict[str, list] = {}
        for p in products:
            cat = p.get("category") or "genel"
            if cat not in by_category:
                by_category[cat] = []
            by_category[cat].append(p)
        result = []
        for cat_products in by_category.values():
            for p in cat_products[:2]:
                if p.get("image_url") and len(result) < max_count:
                    result.append(p)
        seen_ids = {id(p) for p in result}
        if len(result) < max_count:
            for p in products:
                if p.get("image_url") and id(p) not in seen_ids:
                    result.append(p)
                    seen_ids.add(id(p))
                    if len(result) >= max_count:
                        break
        return result[:max_count]

    def get_product_context(self, products: list[dict]) -> str:
        """AI'a verilecek ürün bağlamı metni"""
        lines = []
        for i, p in enumerate(products, 1):
            lines.append(
                f"- {i}. {p.get('name')} | {p.get('category')} | {p.get('price')} TL | {p.get('description', '')[:100]}..."
            )
        return "\n".join(lines) if lines else "Ürün bulunamadı."

    async def get_by_id(self, product_id: int) -> Optional[dict]:
        """ID ile ürün getir (index veya id alanı)"""
        await self._ensure_products()
        for p in self._sample_products:
            if p.get("id") == product_id:
                return p
        idx = product_id - 1
        if 0 <= idx < len(self._sample_products):
            return self._sample_products[idx]
        return None
