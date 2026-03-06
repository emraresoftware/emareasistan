"""Randevu modeli"""
from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey

from .database import Base


class Appointment(Base):
    """Müşteri randevusu - servis, kuaför, onarım vb."""
    __tablename__ = "appointments"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    tenant_id = Column(Integer, index=True, nullable=False)
    conversation_id = Column(Integer, ForeignKey("conversations.id"), nullable=True)
    contact_id = Column(Integer, ForeignKey("contacts.id"), nullable=True)
    customer_name = Column(String(255), nullable=True)
    customer_phone = Column(String(20), nullable=True)
    scheduled_at = Column(DateTime, nullable=False)
    service_type = Column(String(100), nullable=True)
    note = Column(Text, nullable=True)
    status = Column(String(20), default="pending")  # pending, confirmed, completed, cancelled
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
