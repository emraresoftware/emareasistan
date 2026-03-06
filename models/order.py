"""Sipariş modeli"""
from sqlalchemy import Column, Integer, String, Text, Float, DateTime, Enum
from sqlalchemy.orm import relationship
from datetime import datetime
import enum

from .database import Base


class OrderStatus(str, enum.Enum):
    PENDING = "pending"       # Beklemede
    CONFIRMED = "confirmed"   # Onaylandı
    PROCESSING = "processing" # Hazırlanıyor
    SHIPPED = "shipped"       # Kargoya verildi
    DELIVERED = "delivered"   # Teslim edildi
    CANCELLED = "cancelled"   # İptal


class Order(Base):
    """Müşteri siparişi"""
    __tablename__ = "orders"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, index=True, nullable=True, default=1)
    order_number = Column(String(50), unique=True, index=True)
    customer_name = Column(String(255))  # Ad Soyad
    customer_phone = Column(String(20))
    customer_address = Column(Text)
    payment_option = Column(String(50))  # havale, kredi_karti, kapida_odeme
    items = Column(Text)  # JSON - sipariş kalemleri
    total_amount = Column(Float, default=0)
    status = Column(String(20), default=OrderStatus.PENDING.value)
    cargo_tracking_no = Column(String(100))
    cargo_company = Column(String(50))
    platform = Column(String(20))  # whatsapp, telegram, instagram
    conversation_id = Column(Integer)
    notes = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
