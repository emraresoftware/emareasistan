"""Sipariş yönetimi"""
import json
import random
import string
from datetime import datetime
from typing import Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models import Order, OrderStatus


class OrderService:
    """Sipariş oluşturma ve takip"""

    def __init__(self, db: AsyncSession):
        self.db = db

    def _generate_order_number(self) -> str:
        """Benzersiz sipariş numarası: MR-20250211-XXXX"""
        date_part = datetime.now().strftime("%Y%m%d")
        random_part = "".join(random.choices(string.digits, k=4))
        return f"MR-{date_part}-{random_part}"

    async def create(
        self,
        customer_name: str,
        customer_phone: str,
        customer_address: str,
        items: list[dict],
        platform: str = "whatsapp",
        conversation_id: Optional[int] = None,
        tenant_id: Optional[int] = None,
        notes: str = "",
        payment_option: str = "",
    ) -> Order:
        """Yeni sipariş oluştur - ad, soyad, telefon, adres, ödeme seçeneği eksiksiz olmalı"""
        total = sum(item.get("price", 0) * item.get("quantity", 1) for item in items)
        order = Order(
            order_number=self._generate_order_number(),
            customer_name=customer_name,
            customer_phone=customer_phone,
            customer_address=customer_address,
            payment_option=payment_option or None,
            items=json.dumps(items, ensure_ascii=False),
            total_amount=total,
            status=OrderStatus.PENDING.value,
            platform=platform,
            conversation_id=conversation_id,
            tenant_id=tenant_id or 1,
            notes=notes,
        )
        self.db.add(order)
        await self.db.flush()
        await self.db.refresh(order)
        return order

    async def get_by_order_number(self, order_number: str) -> Optional[Order]:
        """Sipariş numarası ile getir"""
        result = await self.db.execute(
            select(Order).where(Order.order_number == order_number)
        )
        return result.scalar_one_or_none()

    async def get_by_tracking(self, tracking_no: str) -> Optional[Order]:
        """Kargo takip numarası ile sipariş getir"""
        result = await self.db.execute(
            select(Order).where(Order.cargo_tracking_no == tracking_no)
        )
        return result.scalar_one_or_none()

    async def update_cargo(
        self,
        order_id: int,
        tracking_no: str,
        cargo_company: str,
    ) -> bool:
        """Siparişe kargo bilgisi ekle"""
        result = await self.db.execute(select(Order).where(Order.id == order_id))
        order = result.scalar_one_or_none()
        if order:
            order.cargo_tracking_no = tracking_no
            order.cargo_company = cargo_company
            order.status = OrderStatus.SHIPPED.value
            await self.db.flush()
            return True
        return False

    def get_order_context(self, order: Order) -> str:
        """AI'a verilecek sipariş bağlamı"""
        return f"Sipariş No: {order.order_number}, Durum: {order.status}, Tutar: {order.total_amount} TL"
