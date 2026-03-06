"""Partner / alt marka modeli - Piramit Bilgisayar gibi kendi tenant'larını yöneten kurumlar"""
from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean
from datetime import datetime

from .database import Base


class Partner(Base):
    """Alt marka / partner - kendi tenant'larını yöneten kurum"""
    __tablename__ = "partners"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)  # Piramit Bilgisayar
    slug = Column(String(100), unique=True, index=True)  # piramit-bilgisayar
    settings = Column(Text)  # JSON: branding, ayarlar vb.
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
