"""Idari personel izin talepleri modeli."""
from datetime import datetime

from sqlalchemy import Column, Integer, String, Date, DateTime, ForeignKey

from .database import Base


class LeaveRequest(Base):
    """Calisan izin talebi."""
    __tablename__ = "leave_requests"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    tenant_id = Column(Integer, index=True, nullable=False)
    conversation_id = Column(Integer, ForeignKey("conversations.id"), nullable=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    employee_name = Column(String(255), nullable=False)
    employee_phone = Column(String(20), nullable=True)
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)
    leave_type = Column(String(50), nullable=True)  # yillik, mazeret, rapor vb.
    note = Column(String(500), nullable=True)
    status = Column(String(20), default="pending")  # pending, approved, rejected
    approver_name = Column(String(100), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
