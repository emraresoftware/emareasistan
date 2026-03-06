"""Video - montaj videosu vb. müşteriye gönderilecek videolar"""
from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime
from datetime import datetime

from .database import Base


class Video(Base):
    """Tetikleyici kelimeye göre müşteriye gönderilecek video. Araç modeline göre filtre (albüm gibi)."""
    __tablename__ = "videos"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, index=True, nullable=True, default=1)
    name = Column(String(150))  # Örn: "Montaj Videosu"
    trigger_keyword = Column(String(100))  # montaj, kurulum vb. - mesajda bu geçerse gönder
    vehicle_models = Column(Text)  # Virgülle ayrılmış: Passat, B8 → bu araçlar için bu video (boş = tüm araçlar)
    video_url = Column(Text, nullable=False)  # Video URL (yüklenen veya harici)
    caption = Column(Text)  # Video ile gidecek mesaj
    is_active = Column(Boolean, default=True)
    priority = Column(Integer, default=0)  # Yüksek = önce kontrol (aynı araç için birden fazla video)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
