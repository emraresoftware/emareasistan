"""CargoHandler - Kargo takip ve sipariş bilgisi bağlamı"""


class CargoHandler:
    """Kargo takip numarası veya sipariş no ile bağlam oluştur"""

    def __init__(self, orders_svc, cargo_svc):
        self.orders = orders_svc
        self.cargo = cargo_svc

    async def build_context(
        self,
        message_text: str,
        intent: str,
        msg_normalized: str,
    ) -> str:
        """
        Mesajda takip no/sipariş no varsa kargo ve sipariş bağlamı döndür.
        """
        context = ""
        keywords = ["kargo", "takip", "sipariş", "siparişi"]
        if intent != "cargo_tracking" and not any(k in msg_normalized for k in keywords):
            return context

        words = (message_text or "").replace(",", " ").split()
        for w in words:
            if len(w) >= 10 and (w.isdigit() or w.startswith("MR-")):
                order = await self.orders.get_by_order_number(w) or await self.orders.get_by_tracking(w)
                if order:
                    context = self.orders.get_order_context(order)
                    tracking_no = order.cargo_tracking_no or w
                    cargo_info = await self.cargo.track(tracking_no, order.cargo_company or "")
                    context += f"\nKargo: {cargo_info.get('tracking_url', '')}"
                else:
                    cargo_info = await self.cargo.track(w, "")
                    context = f"Kargo takip: {cargo_info.get('tracking_url', '')}"
                break
        return context
