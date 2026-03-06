"""Sohbet ve mesaj modelleri"""
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime

from .database import Base


class Conversation(Base):
    """Müşteri sohbet oturumu"""
    __tablename__ = "conversations"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, index=True, nullable=True, default=1)  # Null = eski veri
    platform = Column(String(20))  # whatsapp, telegram, instagram
    platform_user_id = Column(String(100), index=True)
    customer_name = Column(String(255))
    customer_phone = Column(String(20))
    last_message_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow)
    # Temsilci devralma - null ise AI yanıt verir
    agent_taken_over_at = Column(DateTime, nullable=True)
    agent_name = Column(String(100), nullable=True)  # Devralan temsilci adı
    notes = Column(Text, nullable=True)  # Temsilci sohbet notları
    order_draft = Column(Text, nullable=True)  # JSON - sipariş taslağı state: INIT|PRODUCT_SELECTED|CUSTOMER_INFO|ADDRESS|PAYMENT|CONFIRMED
    abandoned_cart_reminder_sent_at = Column(DateTime, nullable=True)  # Sepet terk hatırlatması gönderildi
    proactive_message_sent_at = Column(DateTime, nullable=True)  # Proaktif mesaj son gönderim zamanı
    csat_sent_at = Column(DateTime, nullable=True)  # Memnuniyet anketi gönderildi (AI'ya devret sonrası)
    csat_rating = Column(Integer, nullable=True)  # 1-5 müşteri puanı
    csat_comment = Column(Text, nullable=True)  # İsteğe bağlı yorum


class ChatMessage(Base):
    """Sohbet mesajı - telegram.Message ile çakışmasın diye ChatMessage"""
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, index=True)
    conversation_id = Column(Integer, ForeignKey("conversations.id"))
    role = Column(String(20))  # user, assistant, system
    content = Column(Text)
    extra_data = Column(Text)  # JSON - ek veriler (ürün ID, resim URL vb.)
    created_at = Column(DateTime, default=datetime.utcnow)
