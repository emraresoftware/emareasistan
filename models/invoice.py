"""Idari personel fatura modeli."""
from datetime import datetime

from sqlalchemy import Column, Integer, String, Date, DateTime, Numeric, Text

from .database import Base


class Invoice(Base):
    """Tedarikci faturasi kaydi ve onay durumu."""
    __tablename__ = "invoices"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    tenant_id = Column(Integer, index=True, nullable=False)
    supplier_name = Column(String(255), nullable=False)
    invoice_number = Column(String(100), nullable=True)
    total_amount = Column(Numeric(12, 2), nullable=True)
    due_date = Column(Date, nullable=True)
    status = Column(String(20), default="pending")  # pending, approved, paid, rejected
    note = Column(Text, nullable=True)
    scanned_text = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
