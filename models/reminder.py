"""Hatırlatıcı / müşteriye dönüş takibi"""
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from datetime import datetime

from .database import Base


class Reminder(Base):
    """Müşteriye dönüş hatırlatıcısı"""
    __tablename__ = "reminders"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, index=True, nullable=True, default=1)
    conversation_id = Column(Integer, ForeignKey("conversations.id"), nullable=True)  # İlgili sohbet
    contact_id = Column(Integer, ForeignKey("contacts.id"), nullable=True)  # Alternatif: kişi
    customer_name = Column(String(255))  # Müşteri adı (snapshot)
    customer_phone = Column(String(20))  # Telefon (snapshot)
    due_at = Column(DateTime, nullable=False)  # Hatırlatma tarihi/saati
    note = Column(Text)  # Ne yapılacak
    status = Column(String(20), default="pending")  # pending, done, cancelled
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
