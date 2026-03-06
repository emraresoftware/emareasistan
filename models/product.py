"""Ürün modeli - Multi-tenant katalog yapısı"""
from sqlalchemy import Column, Integer, String, Text, Float, ForeignKey, DateTime, Enum
from sqlalchemy.orm import relationship
from datetime import datetime
import enum

from .database import Base


class ProductCategory(str, enum.Enum):
    """Ürün kategorileri"""
    ELIT_SERISI = "elit_serisi"
    GT_PREMIUM = "gt_premium_serisi"
    EKONOM = "ekonom_serisi"
    KLAS = "klas_serisi"
    MODERN = "modern_serisi"
    ROYAL = "royal_serisi"
    ELIT_TAY_TUYU = "elit_tay_tuyu_serisi"
    PASPAS_BAGAJ = "oto_paspas_ve_bagaj"
    YASTIK_KOLCAK = "oto_yastik_kolcak_organizer"
    YEDI_D_ZEMIN = "7d_zemin_doseme"
    OZEL_TASARIM = "araca_ozel_tasarim"


class Product(Base):
    """Ürün modeli"""
    __tablename__ = "products"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, index=True, nullable=True, default=1)
    name = Column(String(255), nullable=False)
    slug = Column(String(255), unique=True, index=True)
    description = Column(Text)
    category = Column(String(50), index=True)
    price = Column(Float, default=0)
    image_url = Column(String(512))
    image_urls = Column(Text)  # JSON string - birden fazla resim
    vehicle_compatibility = Column(Text)  # Uyumlu araç listesi (JSON)
    stock_status = Column(String(20), default="in_stock")  # in_stock, out_of_stock
    external_url = Column(String(512))  # Ürün sayfası URL
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
