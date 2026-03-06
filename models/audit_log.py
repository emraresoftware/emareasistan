"""Audit log - admin aksiyonlarının kaydı"""
from datetime import datetime

from sqlalchemy import Column, Integer, String, Text, DateTime

from .database import Base


class AuditLog(Base):
    """Admin panel aksiyonları - kim, ne zaman, ne yaptı"""
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, index=True, nullable=True)
    user_id = Column(Integer, nullable=True)
    user_email = Column(String(255), nullable=True)
    action = Column(String(100), nullable=False)  # login, delete_order, update_status, vb.
    resource = Column(String(100), nullable=True)  # order, conversation, user, vb.
    resource_id = Column(String(50), nullable=True)
    details = Column(Text, nullable=True)  # JSON veya serbest metin
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(String(512), nullable=True)  # tarayıcı / cihaz bilgisi
    success = Column(Integer, nullable=True, default=1)  # 1=başarılı, 0=başarısız
    created_at = Column(DateTime, default=datetime.utcnow)
