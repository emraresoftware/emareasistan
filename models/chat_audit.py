"""Chat denetim sonuçları - asenkron AI değerlendirme"""
from datetime import datetime

from sqlalchemy import Column, Integer, String, Text, DateTime, Float, Boolean

from .database import Base


class ChatAudit(Base):
    """Sohbet yanıtı denetim kaydı - analitik amaçlı"""
    __tablename__ = "chat_audits"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, index=True, nullable=False)
    conversation_id = Column(Integer, index=True, nullable=False)
    platform = Column(String(50), nullable=True)  # whatsapp, telegram, web

    # Değerlendirilen içerik
    user_message = Column(Text, nullable=True)
    assistant_response = Column(Text, nullable=True)

    # Denetim sonucu
    score = Column(Float, nullable=True)  # 0-100 genel puan
    passed = Column(Boolean, nullable=True)  # True = sorun yok
    issues = Column(Text, nullable=True)  # JSON: [{"type": "...", "desc": "...", "severity": "low|medium|high"}]
    suggested_correction = Column(Text, nullable=True)  # AI önerdiği düzeltme (varsa)
    audit_notes = Column(Text, nullable=True)  # Denetleyici AI'ın notu

    created_at = Column(DateTime, default=datetime.utcnow)
