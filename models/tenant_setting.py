"""Tenant ayar anahtarları - JSON blob yerine normalleştirilmiş tablo (gelecek geçiş için)"""
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, UniqueConstraint
from datetime import datetime

from .database import Base


class TenantSetting(Base):
    """
    Tenant bazlı ayar anahtarları.
    Geçiş: tenant_service önce bu tabloyu kontrol eder, yoksa Tenant.settings JSON kullanır.
    """
    __tablename__ = "tenant_settings"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False, index=True)
    key = Column(String(100), nullable=False)  # address, phone, gemini_api_key, vb.
    value = Column(Text, nullable=True)  # Şifreli veya düz metin (crypto.encrypt kullanılır)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (UniqueConstraint("tenant_id", "key", name="uq_tenant_setting_key"),)
