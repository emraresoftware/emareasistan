"""
RuleEngine - Yönetim kurallarına göre ürün/resim eşleştirme.
ResponseRule tablosundan tenant bazlı kuralları değerlendirir.
"""
from __future__ import annotations
import json
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models import ResponseRule


class RuleEngine:
    """
    Mesaj → ResponseRule eşleşmesi → ürün/resim listesi.
    Öncelik sırasına göre ilk eşleşen kural kullanılır.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def match(
        self,
        message_text: str,
        tenant_id: int,
        get_product_by_id,
    ) -> list[dict]:
        """
        Mesaja göre eşleşen ürün/resim listesi döndür.
        get_product_by_id: async (id: int) -> dict | None - ProductService.get_by_id
        Returns: [{"url": str, "name": str, "price": float|None, "custom_message": str|None}, ...]
        """
        result = await self.db.execute(
            select(ResponseRule)
            .where(ResponseRule.tenant_id == tenant_id, ResponseRule.is_active == True)
            .order_by(ResponseRule.priority.desc(), ResponseRule.id)
        )
        rules = result.scalars().all()
        msg_lower = (message_text or "").lower()

        for rule in rules:
            trigger = (rule.trigger_value or "").lower()
            if not trigger:
                continue
            values = [v.strip() for v in trigger.split(",") if v.strip()]
            matched = any(v in msg_lower for v in values)
            if not matched:
                continue

            images = []
            try:
                ids = json.loads(rule.product_ids or "[]")
                for pid in ids[:6]:
                    p = await get_product_by_id(int(pid))
                    if p and p.get("image_url"):
                        images.append({
                            "url": p["image_url"],
                            "name": p.get("name", ""),
                            "price": p.get("price"),
                            "custom_message": rule.custom_message if not images else None,
                        })
            except (json.JSONDecodeError, ValueError):
                pass
            try:
                urls = json.loads(rule.image_urls or "[]")
                for url in urls[:6]:
                    if isinstance(url, str) and url.startswith("http"):
                        images.append({
                            "url": url,
                            "name": rule.name or "",
                            "price": None,
                            "custom_message": rule.custom_message if not images else None,
                        })
            except json.JSONDecodeError:
                pass
            if images:
                return images
            # Sadece özel mesajlı kural (ürün/resim yok): yine de tetikle, metin yanıta eklenir
            if (rule.custom_message or "").strip():
                return [{"url": "", "name": "", "price": None, "custom_message": (rule.custom_message or "").strip()}]
        return []
