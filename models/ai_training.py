"""AI eğitim örnekleri - soru/cevap çiftleri ile asistanı eğitme"""
from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime
from datetime import datetime

from .database import Base


class AITrainingExample(Base):
    """Panelden eklenen örnek soru-cevap çiftleri - AI bu örnekleri takip eder"""
    __tablename__ = "ai_training_examples"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, index=True, nullable=True, default=1)
    question = Column(Text, nullable=False)  # Örn: "Montaj fiyatı ne kadar?"
    expected_answer = Column(Text, nullable=False)  # Örn: "Montaj ücreti 500 TL'dir."
    category = Column(String(100))  # İsteğe bağlı: fiyat, montaj, kargo vb.
    trigger_keywords = Column(String(255))  # Virgülle ayrılmış: "montaj, ücret, fiyat" - mesajda geçerse öncelikli
    is_active = Column(Boolean, default=True)
    priority = Column(Integer, default=0)  # Yüksek = önce kullan
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
