"""OrderHandler - Ürün seçimi, sipariş oluşturma, state machine"""
import json
import re
from sqlalchemy import select

from models import Conversation
from services.core import OrderStateMachine


class OrderHandler:
    """Sipariş akışı: ürün seçimi, create_order işleme"""

    def __init__(self, db, orders_svc, save_message_fn, update_timestamp_fn):
        self.db = db
        self.orders = orders_svc
        self._save_message = save_message_fn
        self._update_timestamp = update_timestamp_fn

    def parse_product_selection(
        self,
        message_text: str,
        replied_to_caption: str | None,
        last_products: list[dict],
    ) -> dict | None:
        """
        "Bu olsun", "2 numaralı" vb. seçim ifadelerini algıla.
        """
        selection_phrases = [
            "bu olsun", "bunu olsun", "şunu olsun", "bunu istiyorum", "şunu istiyorum",
            "bunu alayım", "şunu alayım", "bunu seçiyorum", "şunu seçiyorum",
            "bunu seçtim", "şunu seçtim", "bunu ver", "şunu ver", "bunu alacağım",
            "bu iyi", "bu kalsın", "olsun", "bu olsun bana", "bunu istiyorum",
            "bunu alalım", "şunu alalım", "bunu alırım", "şunu alırım",
        ]
        msg_lower = (message_text or "").lower().strip()
        if not msg_lower or not last_products:
            return None

        if replied_to_caption:
            caption_lower = replied_to_caption.lower()
            for i, p in enumerate(last_products):
                name = (p.get("name") or "").lower()
                if name and name in caption_lower:
                    return {"index": i, "product": p}
                cap = f"{p.get('name', '')} - {p.get('price', 0)} TL".lower()
                if cap in caption_lower or (p.get("name") and p.get("price") and str(p.get("price", "")) in (replied_to_caption or "")):
                    return {"index": i, "product": p}

        nums = re.findall(r"\d+", msg_lower)
        if nums:
            i = int(nums[0]) - 1
            if 0 <= i < len(last_products):
                return {"index": i, "product": last_products[i]}

        ordinals = {
            "ilkini": 0, "ilk": 0, "birinci": 0, "birincisi": 0,
            "ikinci": 1, "ikincisi": 1, "ortadaki": 1 if len(last_products) == 3 else 0,
            "üçüncü": 2, "üçüncüsü": 2, "sonuncu": -1, "sonuncuyu": -1,
        }
        for word, idx in ordinals.items():
            if word in msg_lower:
                i = idx if idx >= 0 else len(last_products) - 1
                if 0 <= i < len(last_products):
                    return {"index": i, "product": last_products[i]}

        short_selection = msg_lower in ("bu", "şu", "olsun")
        if any(p in msg_lower for p in selection_phrases) or short_selection:
            return {"index": 0, "product": last_products[0]}
        return None

    async def handle_product_selection(
        self,
        conversation_id: int,
        selected: dict,
    ) -> dict:
        """Ürün seçimi yanıtı oluştur ve order_draft güncelle"""
        p = selected["product"]
        name = p.get("name", "Ürün")
        price = p.get("price")

        text = f"Seçiminiz onaylandı: {name}"
        if price:
            text += f" ({price} TL)"
        text += ".\n\nSiparişinizi tamamlamak için adınızı, telefon numaranızı ve teslimat adresinizi paylaşır mısınız?"

        await self._save_message(
            conversation_id, "assistant", text,
            extra_data=json.dumps({"selected_product": p}),
        )
        sm = OrderStateMachine(None)
        sm.set_product(p)
        result = await self.db.execute(
            select(Conversation).where(Conversation.id == conversation_id)
        )
        conv = result.scalar_one_or_none()
        if conv:
            conv.order_draft = sm.to_json()
            await self.db.commit()
        await self._update_timestamp(conversation_id)

        return {"text": text, "selected_product": p}

    async def process_create_order(
        self,
        response: dict,
        conv,
        sm: OrderStateMachine,
        platform: str,
        tenant_settings: dict,
    ) -> dict:
        """
        AI create_order döndürdüyse sipariş oluştur, webhook, ödeme linki.
        response'u günceller, aynı response döndürür.
        """
        if not response.get("create_order"):
            return response

        order_data = response["create_order"]
        name = (order_data.get("customer_name") or "").strip()
        phone = (order_data.get("customer_phone") or "").strip()
        address = (order_data.get("customer_address") or "").strip()
        payment = (order_data.get("payment_option") or "").strip()
        items = order_data.get("items") or [{"name": "Ürün", "price": 0, "quantity": 1}]

        if sm.get_state() != OrderStateMachine.INIT:
            sm.set_customer_info(name, phone)
            sm.set_address(address)
            sm.set_payment(payment)
            conv.order_draft = sm.to_json()
            await self.db.commit()

        if not (name and phone and address and payment):
            response["text"] = (response.get("text", "").split("```json")[0].strip() or "")
            return response

        tenant_id = getattr(conv, "tenant_id", None) or 1
        order = await self.orders.create(
            customer_name=name,
            customer_phone=phone,
            customer_address=address,
            payment_option=payment,
            items=items,
            platform=platform,
            conversation_id=conv.id,
            tenant_id=tenant_id,
        )
        conv.customer_name = name
        conv.customer_phone = phone
        conv.order_draft = None
        await self.db.commit()

        # Export şablonları - webhook tetikle (alan eşlemeli)
        tenant_id = getattr(conv, "tenant_id", None) or 1
        try:
            from services.workflow.export_trigger import trigger_export_webhooks
            await trigger_export_webhooks("orders", order, tenant_id)
        except Exception:
            pass

        webhook_url = (tenant_settings.get("module_apis") or {}).get("orders", {}).get("webhook_url")
        if webhook_url:
            import asyncio
            async def _send_webhook():
                try:
                    import httpx
                    payload = {
                        "order_number": order.order_number,
                        "customer_name": name,
                        "customer_phone": phone,
                        "customer_address": address,
                        "items": items,
                        "total": sum(i.get("price", 0) * i.get("quantity", 1) for i in items),
                    }
                    async with httpx.AsyncClient(timeout=10.0) as c:
                        await c.post(webhook_url, json=payload)
                except Exception:
                    pass
            asyncio.create_task(_send_webhook())

        # Kullanıcı bildirimleri (e-posta, SMS)
        tenant_name = tenant_settings.get("name", "Firma")
        try:
            from services.notifications import notify_new_order
            await notify_new_order(self.db, order, tenant_id, tenant_name)
        except Exception:
            pass

        payment_label = {"havale": "Havale/EFT", "kredi_karti": "Kredi Kartı", "kapida_odeme": "Kapıda Ödeme"}.get(payment, payment)
        items_list = "\n".join(f"• {i.get('name', 'Ürün')} x{i.get('quantity', 1)} - {i.get('price', 0)} TL" for i in items)
        total = sum(i.get("price", 0) * i.get("quantity", 1) for i in items)
        order_summary = f"""✅ *Siparişiniz Alındı*
Sipariş No: {order.order_number}

*Ürünler:*
{items_list}
Toplam: {total} TL

*Teslimat:* {address}
*Ödeme:* {payment_label}

En kısa sürede sizinle iletişime geçeceğiz."""

        if payment == "kredi_karti":
            from services.order.payment import create_payment_link
            payment_url = await create_payment_link(
                tenant_settings,
                order.order_number,
                items,
                total,
            )
            if payment_url:
                order_summary += f"\n\n💳 *Ödeme linki:* {payment_url}\nBu linkten güvenle ödemenizi tamamlayabilirsiniz."

        response["text"] = (response.get("text", "").split("```json")[0].strip() or "") + f"\n\n{order_summary}"
        return response
