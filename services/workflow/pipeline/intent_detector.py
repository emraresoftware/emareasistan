"""
IntentDetector - Mesaj niyetini kural ve anahtar kelime ile sınıflandırır.
AI çağrısı yapmadan %70-80 oranında doğru tespit → maliyet düşer.
ChatHandler ile uyumlu: product_inquiry, order, cargo_tracking, appointment, general
"""
from __future__ import annotations
import re
from typing import Optional
import logging

logger = logging.getLogger("intent_detector")


class IntentDetector:
    """
    Kural tabanlı niyet tespiti. Önce regex, sonra anahtar kelime.
    AI fallback yok - belirsiz durumda 'general' döner.
    """

    INTENTS = [
    "how_to_test",
        "product_inquiry",
        "order",
        "cargo_tracking",
        "appointment",
        "location_request",
        "human_agent",
        "general",
    ]

    # Regex kuralları - öncelik sırasına göre
    RULES = {
        # High-priority onboarding/test intent - capture variants like "nasıl deneyebilirim", "nasıl denerim"
        "how_to_test": [
            r"(?i)\b(nasıl\s+deney(?:ebilirim|im|ebilirsiniz|ebiliriz)?|nasıl\s+denerim|nasıl\s+deneyelim)\b",
        ],
        "human_agent": [
            r"(?i)(temsilci|insan|yardımcı|yetkili|canlı|konuşmak|bağlan|operatör)",
            r"(?i)(sizinle\s+konuşmak|biriyle\s+konuş)",
        ],
        "cargo_tracking": [
            r"(?i)(kargo|teslimat|gönderi)\s*(nerede|geldi mi|takip)",
            r"(?i)(sipariş.*geldi|siparişim\s+nerede)",
            r"(?i)(takip\s*no|kargo\s*no)\s*[:\s]*\d",
            r"(?i)(\d{10,})\s*(ile|numaralı)\s*(kargo|sipariş)",
        ],
        "order": [
            r"(?i)(sipariş|satın\s*al|alacağım|alayım)\s*(ver|et|edeceğim)",
            r"(?i)(bu\s+olsun|bunu\s+al|bunu\s+istiyorum|şunu\s+al)",
            r"(?i)(sipariş\s+ver|sipariş\s+etmek)",
        ],
        "appointment": [
            r"(?i)(randevu|servis\s*randevusu|bakım\s*randevusu)",
            r"(?i)(müsait\s*saat|boş\s*saat|ne\s*zaman\s*müsait)",
            r"(?i)(yağ\s*değişimi|muayene|servis)\s*(randevu|ne\s*zaman)",
        ],
        "location_request": [
            r"(?i)(adres|konum|nerede|nerde|harita|yol\s*tarifi)",
            r"(?i)(yeriniz|adresiniz|lokasyon|mağaza\s*nerede)",
        ],
        "product_inquiry": [
            r"(?i)(ara|bul|bak|var\s*mı)\s+(.+)",
            r"(?i)(.+)\s+(fiyat|kaç\s*lira|ne\s*kadar)",
            r"(?i)(paspas|koltuk|bagaj)\s*(fiyat|var\s*mı|kaç)",
        ],
    }

    # Anahtar kelime grupları (regex eşleşmezse)
    KEYWORDS = {
        "human_agent": ["temsilci", "insan", "yardımcı", "yetkili", "canlı", "operatör"],
        "cargo_tracking": ["kargo", "teslim", "geldi", "takip", "siparişim", "nerede"],
        "order": ["sipariş", "satın al", "alacağım", "bu olsun", "bunu al"],
        "appointment": ["randevu", "servis", "müsait", "boş saat", "yağ değişimi", "bakım"],
        "location_request": ["adres", "nerede", "konum", "harita", "yol tarifi", "lokasyon"],
        "product_inquiry": [
            "ürün", "parça", "yedek", "koltuk", "paspas", "fiyat", "kılıf",
            "bagaj", "yastık", "zemin", "döşeme", "resim", "foto", "deri",
            "jant", "organizer", "araba", "araç", "model", "7d", "elit", "ekonom",
        ],
    }

    def detect(self, message: str) -> str:
        """
        Mesajın niyetini tespit et. AI çağrısı yapmaz.
        Returns: product_inquiry | order | cargo_tracking | appointment | location_request | human_agent | general
        """
        if not message or not isinstance(message, str):
            return "general"

        msg = message.strip().lower()
        logger.info("IntentDetector input: %s", msg)
        if len(msg) < 2:
            return "general"

        # 1. Regex ile kontrol (öncelik sırası önemli)
        for intent, patterns in self.RULES.items():
            for pattern in patterns:
                if re.search(pattern, msg):
                    logger.info("IntentDetector matched rule: %s -> %s", intent, pattern)
                    return intent

        # 2. Anahtar kelime ile kontrol
        for intent, keywords in self.KEYWORDS.items():
            if any(kw in msg for kw in keywords):
                logger.info("IntentDetector matched keyword intent: %s", intent)
                return intent

        return "general"
