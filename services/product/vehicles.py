"""
Türkiye'de 2000 sonrası satılan araç modelleri
Ürün araması ve AI bağlamı için
"""
from __future__ import annotations
import json
from pathlib import Path
from typing import Optional

_DATA_PATH = Path(__file__).parent.parent / "data" / "vehicle_models.json"

_brands_cache: dict | None = None
_flat_models_cache: list[str] | None = None


def _load() -> dict:
    global _brands_cache
    if _brands_cache is None:
        if _DATA_PATH.exists():
            with open(_DATA_PATH, encoding="utf-8") as f:
                _brands_cache = json.load(f)
        else:
            _brands_cache = {"brands": {}}
    return _brands_cache


def get_brands() -> dict:
    """Marka -> model listesi (admin API için)"""
    return _load().get("brands", {})


def get_all_models() -> list[str]:
    """Tüm model isimlerini döndür (marka + model, küçük harf)"""
    global _flat_models_cache
    if _flat_models_cache is not None:
        return _flat_models_cache
    data = _load()
    models = []
    for brand, model_list in data.get("brands", {}).items():
        for m in model_list:
            models.append(m.lower())
            models.append(f"{brand} {m}".lower())
    _flat_models_cache = models
    return models


# Yaygın yazım hataları (model adı -> doğru yazım)
_TYPO_FIXES = {"riftter": "rifter", "passaat": "passat", "golf": "golf"}


def extract_vehicle_from_message(message: str) -> Optional[str]:
    """
    Mesajdan araç modeli çıkar.
    Örn: "Passat için koltuk kılıfı" -> "Passat"
    """
    msg_lower = message.lower()
    for typo, correct in _TYPO_FIXES.items():
        msg_lower = msg_lower.replace(typo, correct)
    data = _load()
    best_match = None
    best_len = 0

    for brand, model_list in data.get("brands", {}).items():
        for model in model_list:
            m_lower = model.lower()
            b_lower = brand.lower()
            if m_lower in msg_lower or b_lower in msg_lower:
                # Model adı mesajda
                if m_lower in msg_lower and len(m_lower) > best_len:
                    best_match = model
                    best_len = len(m_lower)
                # "BMW 3 serisi" gibi
                if f"{b_lower} {m_lower}" in msg_lower and len(m_lower) > best_len:
                    best_match = f"{brand} {model}"
                    best_len = len(m_lower) + len(b_lower)

    return best_match


def get_context_for_ai() -> str:
    """AI'a verilecek araç modeli listesi (özet)"""
    data = _load()
    lines = []
    for brand, models in data.get("brands", {}).items():
        lines.append(f"{brand}: {', '.join(models[:8])}{'...' if len(models) > 8 else ''}")
    return "Türkiye'de 2000 sonrası yaygın araç modelleri:\n" + "\n".join(lines[:25]) + "\n(Müşteri araç modeli söylediğinde bu listeyi kullan.)"


def get_model_count() -> int:
    """Toplam model sayısı"""
    data = _load()
    return sum(len(m) for m in data.get("brands", {}).values())
