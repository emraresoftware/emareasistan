"""
ChatResponse ve InboundMessage dataclass testleri.
"""
import pytest
from integrations.channels.base import InboundMessage, ChatResponse


class TestInboundMessage:
    """InboundMessage dataclass testleri."""

    def test_create_basic(self):
        """Temel InboundMessage oluşturulur."""
        msg = InboundMessage(
            platform="whatsapp",
            user_id="905551234567",
            message_text="Merhaba",
        )
        assert msg.platform == "whatsapp"
        assert msg.user_id == "905551234567"
        assert msg.message_text == "Merhaba"

    def test_optional_fields_default_none(self):
        """Opsiyonel alanlar None olarak başlar."""
        msg = InboundMessage(platform="web", user_id="u1", message_text="test")
        assert msg.customer_name is None
        assert msg.customer_phone is None
        assert msg.image_base64 is None
        assert msg.tenant_id is None

    def test_full_message(self):
        """Tüm alanları dolu mesaj oluşturulur."""
        msg = InboundMessage(
            platform="telegram",
            user_id="123456",
            message_text="Ürün fiyatı?",
            customer_name="Ali",
            customer_phone="905551234567",
            tenant_id=1,
        )
        assert msg.customer_name == "Ali"
        assert msg.tenant_id == 1


class TestChatResponse:
    """ChatResponse dataclass testleri."""

    def test_create_text_only(self):
        """Sadece metin yanıtı oluşturulur."""
        resp = ChatResponse(text="Merhaba!")
        assert resp.text == "Merhaba!"
        assert resp.image_url is None
        assert resp.product_images is None

    def test_from_dict(self):
        """Dict'ten ChatResponse oluşturulur."""
        d = {
            "text": "Fiyatımız 500 TL",
            "image_url": "https://example.com/img.jpg",
            "image_caption": "Ürün resmi",
        }
        resp = ChatResponse.from_dict(d)
        assert resp.text == "Fiyatımız 500 TL"
        assert resp.image_url == "https://example.com/img.jpg"
        assert resp.image_caption == "Ürün resmi"

    def test_from_dict_empty(self):
        """Boş dict'ten ChatResponse oluşturulur."""
        resp = ChatResponse.from_dict({})
        assert resp.text == ""
        assert resp.image_url is None

    def test_with_products(self):
        """Ürün resimleri içeren yanıt."""
        resp = ChatResponse(
            text="İşte ürünler:",
            product_images=[
                {"name": "Ürün A", "price": 100, "url": "https://x.com/a.jpg"},
                {"name": "Ürün B", "price": 200, "url": "https://x.com/b.jpg"},
            ],
        )
        assert len(resp.product_images) == 2
        assert resp.product_images[0]["name"] == "Ürün A"

    def test_with_location(self):
        """Konum içeren yanıt."""
        resp = ChatResponse(
            text="Konumumuz:",
            location={"lat": 39.925, "lng": 32.837, "name": "Ankara", "address": "Kızılay"},
        )
        assert resp.location["lat"] == 39.925
