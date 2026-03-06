"""
Uygulama düzeyi ayarlar - panelden değiştirilebilir.
data/app_settings.json dosyasında saklanır. Yoksa .env değerleri kullanılır.
"""
import json
import logging
from pathlib import Path

from config import get_settings

logger = logging.getLogger(__name__)

_SETTINGS_PATH = Path(__file__).resolve().parent.parent / "data" / "app_settings.json"


def _load_raw() -> dict:
    """JSON dosyasından ayarları oku"""
    if not _SETTINGS_PATH.exists():
        return {}
    try:
        with open(_SETTINGS_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.warning("app_settings okunamadı: %s", e)
        return {}


def _save_raw(data: dict) -> None:
    """Ayarları JSON dosyasına yaz"""
    _SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(_SETTINGS_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def get_chat_audit_enabled() -> bool:
    """Sohbet denetimi açık mı? Önce app_settings, yoksa .env"""
    data = _load_raw()
    if "chat_audit_enabled" in data:
        return bool(data["chat_audit_enabled"])
    return bool(getattr(get_settings(), "chat_audit_enabled", False))


def get_chat_audit_sample_rate() -> int:
    """Örnekleme oranı 0-100. Önce app_settings, yoksa .env"""
    data = _load_raw()
    if "chat_audit_sample_rate" in data:
        v = int(data["chat_audit_sample_rate"])
        return max(0, min(100, v))
    return int(getattr(get_settings(), "chat_audit_sample_rate", 20) or 20)


def set_chat_audit_enabled(enabled: bool) -> None:
    """Sohbet denetimini aç/kapat"""
    data = _load_raw()
    data["chat_audit_enabled"] = enabled
    _save_raw(data)
