"""Saat dilimi yardımcıları - Türkiye (Europe/Istanbul)"""
from datetime import datetime
from zoneinfo import ZoneInfo

TURKEY_TZ = ZoneInfo("Europe/Istanbul")


def now_turkey() -> datetime:
    """Türkiye saati - randevu, tarih hesaplamaları için (naive datetime)"""
    return datetime.now(TURKEY_TZ).replace(tzinfo=None)
