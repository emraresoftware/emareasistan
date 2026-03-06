"""Kişi/rehber modeli - temsilci panelinden sohbet başlatmak için"""
from sqlalchemy import Column, Integer, String, Text, DateTime
from datetime import datetime

from .database import Base


class Contact(Base):
    """Rehber kişisi - temsilci seçip sohbet başlatabilir"""
    __tablename__ = "contacts"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, index=True, nullable=True, default=1)
    name = Column(String(150), nullable=False)
    phone = Column(String(30), nullable=False, index=True)
    email = Column(String(255), nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
