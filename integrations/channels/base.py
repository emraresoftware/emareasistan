"""
Kanal base sınıfı - tüm platformlar için ortak interface.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass
class InboundMessage:
    """Gelen mesajın normalize edilmiş hali - tüm platformlardan aynı formatta"""
    platform: str
    user_id: str
    message_text: str
    customer_name: str | None = None
    customer_phone: str | None = None
    image_base64: str | None = None
    image_mimetype: str | None = None
    replied_to_caption: str | None = None
    tenant_id: int | None = None
    raw: Any = None  # Platform-specific raw data (Update, webhook body vb.)


@dataclass
class ChatResponse:
    """ChatHandler.process_message çıktısı - tüm kanallara aynı formatta"""
    text: str = ""
    image_url: str | None = None
    image_caption: str | None = None
    product_images: list[dict] | None = None
    location: dict | None = None
    suggested_products: list | None = None

    @classmethod
    def from_dict(cls, d: dict) -> "ChatResponse":
        return cls(
            text=d.get("text", "") or "",
            image_url=d.get("image_url"),
            image_caption=d.get("image_caption"),
            product_images=d.get("product_images"),
            location=d.get("location"),
            suggested_products=d.get("suggested_products"),
        )


class BaseChannel(ABC):
    """
    Mesaj gönderme interface'i.
    Her platform (WhatsApp, Telegram, Instagram) bu sınıftan türetir.
    """

    @property
    @abstractmethod
    def platform_id(self) -> str:
        """Platform tanımı: whatsapp, telegram, instagram"""
        pass

    @abstractmethod
    async def send_text(self, recipient_id: str, text: str) -> None:
        """Metin mesajı gönder"""
        pass

    @abstractmethod
    async def send_image(self, recipient_id: str, image_url: str, caption: str = "") -> None:
        """Resim gönder"""
        pass

    async def send_location(
        self,
        recipient_id: str,
        lat: float,
        lng: float,
        name: str = "",
        address: str = "",
    ) -> None:
        """Konum gönder - varsayılan boş, override edilebilir"""
        pass

    async def send_response(self, recipient_id: str, response: dict | ChatResponse) -> None:
        """
        ChatHandler yanıtını platforma göre gönder.
        Tüm kanallar için ortak - override gerekmez.
        suggested_replies varsa metne numaralı seçenekler eklenir (müşteri "1" yazınca tam metin gönderilir).
        """
        r = ChatResponse.from_dict(response) if isinstance(response, dict) else response
        text = r.text or ""
        if isinstance(response, dict):
            suggested = response.get("suggested_replies") or []
            if suggested:
                lines = []
                for i, opt in enumerate(suggested, 1):
                    label = (opt.get("label") or opt.get("text", "")) if isinstance(opt, dict) else str(opt)
                    if label:
                        lines.append(f"{i}. {label}")
                if lines:
                    text = (text.rstrip() + "\n\n" + "\n".join(lines) + "\n\nLütfen numara yazarak seçin (örn: 1)").strip()
        if text:
            await self.send_text(recipient_id, text)
        if r.location:
            loc = r.location
            await self.send_location(
                recipient_id,
                loc.get("lat", 0),
                loc.get("lng", 0),
                loc.get("name", ""),
                loc.get("address", ""),
            )
        if r.image_url:
            await self.send_image(recipient_id, r.image_url, r.image_caption or "")
        for img in r.product_images or []:
            caption = f"{img.get('name', '')} - {img.get('price', 0)} TL"
            await self.send_image(recipient_id, img.get("url", ""), caption)
