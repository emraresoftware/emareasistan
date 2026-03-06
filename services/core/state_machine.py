"""
OrderStateMachine - Sipariş akışı state yönetimi.
INIT → PRODUCT_SELECTED → CUSTOMER_INFO → ADDRESS → PAYMENT → CONFIRMED
"""
import json
from typing import Any


class OrderStateMachine:
    """
    Sipariş taslağı state machine.
    State'ler: INIT, PRODUCT_SELECTED, CUSTOMER_INFO, ADDRESS, PAYMENT, CONFIRMED
    """

    INIT = "INIT"
    PRODUCT_SELECTED = "PRODUCT_SELECTED"
    CUSTOMER_INFO = "CUSTOMER_INFO"
    ADDRESS = "ADDRESS"
    PAYMENT = "PAYMENT"
    CONFIRMED = "CONFIRMED"

    def __init__(self, order_draft_json: str | None):
        """order_draft: Conversation.order_draft (JSON string)"""
        self._data = self._parse(order_draft_json or "{}")

    def _parse(self, s: str) -> dict:
        try:
            return json.loads(s) if s else {}
        except json.JSONDecodeError:
            return {}

    def get_state(self) -> str:
        return self._data.get("state") or self.INIT

    def get_data(self) -> dict:
        return dict(self._data)

    def to_json(self) -> str:
        return json.dumps(self._data, ensure_ascii=False)

    def set_state(self, state: str, **kwargs) -> None:
        self._data["state"] = state
        for k, v in kwargs.items():
            if v is not None:
                self._data[k] = v

    def set_product(self, product: dict) -> None:
        """Ürün seçildi - PRODUCT_SELECTED state"""
        items = [{"name": product.get("name", "Ürün"), "price": product.get("price", 0), "quantity": 1}]
        self.set_state(self.PRODUCT_SELECTED, items=items)

    def set_customer_info(self, name: str = "", phone: str = "") -> None:
        self._data["customer_name"] = (name or self._data.get("customer_name", "")).strip()
        self._data["customer_phone"] = (phone or self._data.get("customer_phone", "")).strip()
        if self._data.get("customer_name") and self._data.get("customer_phone"):
            self._data["state"] = self.CUSTOMER_INFO

    def set_address(self, address: str = "") -> None:
        self._data["customer_address"] = (address or self._data.get("customer_address", "")).strip()
        if self._data.get("customer_address"):
            self._data["state"] = self.ADDRESS

    def set_payment(self, payment: str = "") -> None:
        self._data["payment_option"] = (payment or self._data.get("payment_option", "")).strip()
        if self._data.get("payment_option"):
            self._data["state"] = self.PAYMENT

    def is_complete(self) -> bool:
        """Tüm bilgiler eksiksiz mi? (create_order için)"""
        d = self._data
        return bool(
            d.get("items")
            and (d.get("customer_name") or "").strip()
            and (d.get("customer_phone") or "").strip()
            and (d.get("customer_address") or "").strip()
            and (d.get("payment_option") or "").strip()
        )

    def get_create_order_payload(self) -> dict | None:
        """create_order JSON için hazır veri"""
        if not self.is_complete():
            return None
        return {
            "customer_name": self._data.get("customer_name", "").strip(),
            "customer_phone": self._data.get("customer_phone", "").strip(),
            "customer_address": self._data.get("customer_address", "").strip(),
            "payment_option": self._data.get("payment_option", "").strip(),
            "items": self._data.get("items", []),
        }

    def get_missing_fields(self) -> list[str]:
        """Eksik alanlar"""
        missing = []
        if not (self._data.get("customer_name") or "").strip():
            missing.append("Ad Soyad")
        if not (self._data.get("customer_phone") or "").strip():
            missing.append("Telefon")
        if not (self._data.get("customer_address") or "").strip():
            missing.append("Adres")
        if not (self._data.get("payment_option") or "").strip():
            missing.append("Ödeme seçeneği")
        return missing

    def reset(self) -> None:
        """Sipariş sıfırla"""
        self._data = {"state": self.INIT}

    def get_context_for_ai(self) -> str:
        """AI için order_context metni"""
        state = self.get_state()
        if state == self.INIT:
            return ""
        lines = [f"[Sipariş durumu: {state}]"]
        if self._data.get("items"):
            lines.append(f"Seçilen ürün: {self._data['items']}")
        if self._data.get("customer_name"):
            lines.append(f"Ad Soyad: {self._data['customer_name']}")
        if self._data.get("customer_phone"):
            lines.append(f"Telefon: {self._data['customer_phone']}")
        if self._data.get("customer_address"):
            lines.append(f"Adres: {self._data['customer_address']}")
        if self._data.get("payment_option"):
            lines.append(f"Ödeme: {self._data['payment_option']}")
        missing = self.get_missing_fields()
        if missing:
            lines.append(f"Eksik: {', '.join(missing)} - bunları kibarca sor.")
        return "\n".join(lines)
