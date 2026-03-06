"""Hızlı yanıt şablonu - temsilci panelinde tek tıkla gönderim"""
from sqlalchemy import Column, Integer, String, Text, DateTime
from datetime import datetime

from .database import Base


class QuickReply(Base):
    """Hazır mesaj şablonu - tenant bazlı"""
    __tablename__ = "quick_replies"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, index=True, nullable=False)
    label = Column(String(100), nullable=False)  # Kısa etiket: "Merhaba", "Fiyat"
    text = Column(Text, nullable=False)  # Gönderilecek tam metin
    sort_order = Column(Integer, default=0)  # Sıralama
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
