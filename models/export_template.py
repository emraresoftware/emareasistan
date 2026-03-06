"""Veri aktarım şablonu - Asistan verisini dış sistemlere formatlı gönderme"""
from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime
from datetime import datetime

from .database import Base


class ExportTemplate(Base):
    """
    Asistan'dan alınan veriyi belirli formatta dış sisteme (CRM, ERP vb.) aktarma şablonu.
    Kaynak: orders, contacts, reminders
    Tetikleyici: webhook (anlık), manual (manuel export)
    Alan eşlemesi: {"order.customer_name": "musteri_adi", ...}
    """
    __tablename__ = "export_templates"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, index=True, nullable=False, default=1)
    name = Column(String(255), nullable=False)  # Örn: "CRM Sipariş Aktarımı"
    source = Column(String(50), nullable=False)  # orders, contacts, reminders
    trigger = Column(String(30), nullable=False, default="webhook")  # webhook, manual
    output_format = Column(String(20), nullable=False, default="json")  # json, csv
    # Alan eşlemesi: {"asistan_alani": "hedef_alani"} JSON
    # orders için: order_number, customer_name, customer_phone, customer_address, items, total_amount, status, platform, created_at
    # contacts için: name, phone, email, notes, created_at
    # reminders için: customer_name, customer_phone, due_at, note, status
    field_mapping = Column(Text)  # JSON: {"order.customer_name": "musteri_adi", "order.items": "urunler"}
    webhook_url = Column(Text)  # trigger=webhook ise POST edilecek URL
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
