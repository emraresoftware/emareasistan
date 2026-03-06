"""Bekleyen kayıt - e-posta onayı için"""
from sqlalchemy import Column, Integer, String, Text, DateTime
from datetime import datetime

from .database import Base


class PendingRegistration(Base):
    """E-posta onayı bekleyen kayıt"""
    __tablename__ = "pending_registrations"

    id = Column(Integer, primary_key=True, index=True)
    token = Column(String(64), unique=True, index=True)
    email = Column(String(255), nullable=False)
    password_hash = Column(String(255), nullable=False)
    website_url = Column(String(512), nullable=False)
    tenant_name = Column(String(255))
    tenant_slug = Column(String(100))
    sector = Column(String(100))
    products_json = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=False)
    confirmed_at = Column(DateTime, nullable=True)
