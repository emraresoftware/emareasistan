"""Çok kiracılı (multi-tenant) SaaS - Müşteri / organizasyon modeli"""
from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, ForeignKey
from datetime import datetime

from .database import Base


class Tenant(Base):
    """Müşteri organizasyonu - her müşteri kendi tenant'ı"""
    __tablename__ = "tenants"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)  # Firma adı
    slug = Column(String(100), unique=True, index=True)  # URL-safe: firma-adi
    website_url = Column(String(512), nullable=False)  # https://firmaadi.com
    # Otomatik analiz sonucu
    sector = Column(String(100))  # otomobil, mobilya, tekstil, genel
    settings = Column(Text)  # JSON: address, phone, ai_prompt_override, vb.
    # Ürünler JSON path veya DB - tenant bazlı products path
    products_path = Column(String(512))  # data/tenants/{slug}/products.json
    partner_id = Column(Integer, ForeignKey("partners.id"), nullable=True, index=True)  # NULL = doğrudan Emare tenant
    status = Column(String(20), default="active")  # active, suspended, trial
    enabled_modules = Column(Text)  # JSON: ["whatsapp","products",...] - boş = tümü etkin
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
