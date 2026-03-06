"""Mesaj geri bildirimi - beğen/beğenme"""
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from datetime import datetime

from .database import Base


class MessageFeedback(Base):
    """Asistan yanıtı için kullanıcı/temsilci geri bildirimi"""
    __tablename__ = "message_feedback"

    id = Column(Integer, primary_key=True, index=True)
    message_id = Column(Integer, ForeignKey("messages.id"), nullable=False, index=True)
    feedback = Column(String(10), nullable=False)  # like, dislike
    created_at = Column(DateTime, default=datetime.utcnow)
