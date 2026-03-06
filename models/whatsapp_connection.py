"""WhatsApp bağlantısı - her biri ayrı numara/QR"""
from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime
from datetime import datetime

from .database import Base


class WhatsAppConnection(Base):
    """WhatsApp hesap bağlantısı - QR ile bağlanır, kullanıcılara atanır"""
    __tablename__ = "whatsapp_connections"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, index=True, nullable=True, default=1)
    name = Column(String(100), nullable=False)  # "Satış 1", "Ana Hesap" vb.
    auth_path = Column(String(255), unique=True)  # .wwebjs_auth_conn_1 vb. - Bridge için
    status = Column(String(20), default="disconnected")  # disconnected, qr_pending, connected
    phone_number = Column(String(30), nullable=True)  # Bağlandıktan sonra numara
    bridge_port = Column(Integer, nullable=True)  # Gelecekte multi-bridge için
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
