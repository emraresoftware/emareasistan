"""Idari personel satin alma talebi modeli."""
from datetime import datetime

from sqlalchemy import Column, Integer, String, DateTime, Text

from .database import Base


class PurchaseOrder(Base):
    """Tedarikciye gidecek satin alma talepleri."""
    __tablename__ = "purchase_orders"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    tenant_id = Column(Integer, index=True, nullable=False)
    requester_name = Column(String(255), nullable=False)
    supplier_name = Column(String(255), nullable=True)
    items_json = Column(Text, nullable=False)  # JSON string: [{name, qty, unit_price}]
    status = Column(String(20), default="pending")  # pending, approved, ordered, rejected
    note = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
