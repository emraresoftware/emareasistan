"""Yönetim paneli - Araç/ürün kuralları"""
from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime
from datetime import datetime

from .database import Base


class ResponseRule(Base):
    """
    Araç modeli veya anahtar kelimeye göre otomatik yanıt kuralı.
    Örn: "Passat" yazana -> şu ürün resimlerini gönder
    """
    __tablename__ = "response_rules"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, index=True, nullable=True, default=1)
    name = Column(String(100))  # Kural adı: "Passat için Elit Serisi"
    trigger_type = Column(String(20))  # vehicle_model, keyword
    trigger_value = Column(String(200))  # "Passat", "BMW" veya "elit koltuk"
    product_ids = Column(Text)  # JSON: [1, 2, 3] - gönderilecek ürün ID'leri
    image_urls = Column(Text)  # JSON: ["url1", "url2"] - doğrudan resim URL'leri
    custom_message = Column(Text)  # Özel mesaj (isteğe bağlı)
    is_active = Column(Boolean, default=True)
    priority = Column(Integer, default=0)  # Yüksek = önce kontrol
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
