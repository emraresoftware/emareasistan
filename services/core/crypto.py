"""
API anahtarları için şifreleme - tenant settings'te hassas verileri korur.
ENCRYPTION_KEY yoksa şifreleme devre dışı (geriye uyumluluk).
"""
import base64
from typing import Optional

from config import get_settings


def _get_fernet():
    """Fernet instance - ENCRYPTION_KEY varsa"""
    key = (get_settings().encryption_key or "").strip()
    if not key or len(key) < 32:
        return None
    try:
        from cryptography.fernet import Fernet
        # 32+ karakter base64 veya raw key - Fernet 44 char base64 bekler
        if len(key) == 44 and key.endswith("="):
            return Fernet(key.encode())
        # Raw key'den türet - 32 byte url-safe base64
        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
        kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=b"emare_asistan", iterations=100000)
        derived = base64.urlsafe_b64encode(kdf.derive(key.encode()))
        return Fernet(derived)
    except Exception:
        return None


def encrypt_value(plain: Optional[str]) -> Optional[str]:
    """Düz metni şifrele. Boş veya None → None. Şifreleme yoksa plain döner."""
    if not plain or not str(plain).strip():
        return None
    f = _get_fernet()
    if not f:
        return plain
    try:
        return f.encrypt(plain.encode()).decode()
    except Exception:
        return plain


def decrypt_value(encrypted: Optional[str]) -> Optional[str]:
    """Şifreli metni çöz. Boş → None. Çözülemezse (eski plain text) olduğu gibi döner."""
    if not encrypted or not str(encrypted).strip():
        return None
    f = _get_fernet()
    if not f:
        return encrypted
    try:
        return f.decrypt(encrypted.encode()).decode()
    except Exception:
        return encrypted  # Eski plain text - geriye uyumluluk


# Masked placeholder - form'da "değiştirme" anlamına gelir
MASKED = "••••••••••••"

SENSITIVE_TOP_LEVEL = ("gemini_api_key", "openai_api_key")


def encrypt_tenant_settings(data: dict) -> dict:
    """Tenant settings dict'teki hassas alanları şifrele (kaydetmeden önce)."""
    out = dict(data)
    for key in SENSITIVE_TOP_LEVEL:
        if key in out and out[key] and str(out[key]).strip() and str(out[key]).strip() != MASKED:
            enc = encrypt_value(str(out[key]).strip())
            if enc:
                out[key] = enc
    module_apis = out.get("module_apis") or {}
    if isinstance(module_apis, dict):
        enc_module = {}
        for mod_id, mod_data in module_apis.items():
            if not isinstance(mod_data, dict):
                enc_module[mod_id] = mod_data
                continue
            enc_mod = {}
            for k, v in mod_data.items():
                if v and str(v).strip() and str(v).strip() != MASKED:
                    if any(sk in k.lower() for sk in ("api_key", "secret_key", "password", "_key")):
                        enc = encrypt_value(str(v).strip())
                        if enc:
                            enc_mod[k] = enc
                            continue
                enc_mod[k] = v
            enc_module[mod_id] = enc_mod
        out["module_apis"] = enc_module
    return out
