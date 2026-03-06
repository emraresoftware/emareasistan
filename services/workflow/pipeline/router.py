"""
MessageRouter - Niyete göre işlem modülü yönlendirmesi.
Intent + mesaj → hangi bağlamlar öncelikli yüklenecek.
"""
from dataclasses import dataclass
from typing import Optional

from .intent_detector import IntentDetector


@dataclass
class RouteInfo:
    """Router çıktısı - hangi modüller öncelikli"""
    intent: str
    primary_module: str  # product | order | appointment | cargo | location | ai
    load_product_context: bool
    load_order_context: bool
    load_location_context: bool
    load_cargo_context: bool


class MessageRouter:
    """
    Intent'e göre bağlam yükleme önceliği belirler.
    ChatHandler bu bilgiyi kullanarak hangi context'leri toplayacağını optimize edebilir.
    """

    def __init__(self):
        self.intent_detector = IntentDetector()

    def route(self, message: str) -> RouteInfo:
        """
        Mesajı analiz et, niyet ve modül önceliklerini döndür.
        """
        intent = self.intent_detector.detect(message or "")
        msg_lower = (message or "").lower()

        # Varsayılan: tüm bağlamları yükle (mevcut davranış)
        load_product = True
        load_order = True
        load_location = True
        load_cargo = True
        primary = "ai"

        if intent == "product_inquiry":
            primary = "product"
            load_product = True
        elif intent == "order":
            primary = "order"
            load_order = True
        elif intent == "appointment":
            primary = "appointment"
        elif intent == "cargo_tracking":
            primary = "cargo"
            load_cargo = True
        elif intent == "location_request":
            primary = "location"
            load_location = True
        elif intent == "human_agent":
            primary = "ai"

        return RouteInfo(
            intent=intent,
            primary_module=primary,
            load_product_context=load_product,
            load_order_context=load_order,
            load_location_context=load_location,
            load_cargo_context=load_cargo,
        )
