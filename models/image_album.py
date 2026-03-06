"""Resim albümü - araç modeline göre otomatik gönderim"""
from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime
from datetime import datetime

from .database import Base


class ImageAlbum(Base):
    """
    Araç modeline özel resim albümü.
    Örn: "Passat Albümü" -> Passat, B8, CC için bu resimleri gönder
    """
    __tablename__ = "image_albums"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, index=True, nullable=True, default=1)
    name = Column(String(150))  # Albüm adı: "Passat Elit Serisi"
    image_urls = Column(Text)  # JSON: ["url1", "url2", "url3"] - albümdeki resimler
    vehicle_models = Column(Text)  # JSON veya virgülle ayrılmış: ["Passat", "B8", "CC"]
    custom_message = Column(Text)  # Gönderimde kullanılacak mesaj (isteğe bağlı)
    is_active = Column(Boolean, default=True)
    priority = Column(Integer, default=0)  # Yüksek = önce kontrol (aynı araç için birden fazla albüm)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
