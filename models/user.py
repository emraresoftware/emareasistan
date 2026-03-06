"""Kullanıcı ve temsilci modeli"""
from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, ForeignKey
from datetime import datetime

from .database import Base


class User(Base):
    """Panel kullanıcısı - admin veya temsilci"""
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, index=True, nullable=True, default=1)
    partner_id = Column(Integer, ForeignKey("partners.id"), nullable=True, index=True)  # Partner admin kullanıcıları
    is_partner_admin = Column(Boolean, default=False)  # True = partner'ın super admin'i (kendi tenant'larını yönetir)
    name = Column(String(100), nullable=False)
    email = Column(String(255), unique=True, index=True, nullable=True)
    phone = Column(String(30), nullable=True)  # Bildirimler için (SMS, WhatsApp)
    password_hash = Column(String(255), nullable=True)  # bcrypt veya benzeri
    role = Column(String(20), default="agent")  # admin, agent
    whatsapp_connection_id = Column(Integer, ForeignKey("whatsapp_connections.id"), nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_login = Column(DateTime, nullable=True)  # Son giriş zamanı (her başarılı login'de güncellenir)
    last_seen = Column(DateTime, nullable=True)  # Son aktivite (her admin isteğinde güncellenir, online/offline için)
    notification_settings = Column(Text, nullable=True)  # JSON: { "new_order": true, "daily_digest": true, "new_message": false, "channels": ["email","sms"] }
