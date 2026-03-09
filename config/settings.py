"""Emare Asistan - Konfigürasyon"""
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """Uygulama ayarları"""
    
    # AI - OpenAI veya Gemini (biri yeterli)
    openai_api_key: str = ""
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.5-flash-lite"  # veya gemini-2.0-flash
    # Local LLM fallback (scripts/local_llm)
    local_llm_enabled: bool = False
    local_llm_base_model: str = "Qwen/Qwen2.5-0.5B-Instruct"
    local_llm_adapter_path: str = "./scripts/local_llm/artifacts/local_lora"
    local_llm_chat_script: str = "./scripts/local_llm/chat.py"
    local_llm_python_bin: str = "./scripts/local_llm/.venv/bin/python"
    local_llm_max_new_tokens: int = 64
    local_llm_timeout_sec: int = 18
    local_llm_min_confidence: int = 55
    
    # Site
    base_url: str = "https://emareasistan.com"

    # Varsayılan tenant iletişim (tenant ayarı yoksa fallback)
    default_tenant_address: str = ""
    default_tenant_phone: str = ""
    default_tenant_lat: float = 0.0
    default_tenant_lng: float = 0.0
    default_tenant_maps_url: str = ""
    
    # Kargo
    yurtici_api_key: str = ""
    aras_api_key: str = ""
    mng_api_key: str = ""
    
    # WhatsApp
    whatsapp_phone_number_id: str = ""
    whatsapp_access_token: str = ""
    whatsapp_verify_token: str = "emare_verify"
    whatsapp_bridge_url: str = "http://localhost:3100"  # Temsilci mesaj gönderimi için (QR bridge)
    
    # Telegram
    telegram_bot_token: str = ""

    # Instagram Messaging API (Meta Graph API - Facebook Page + Instagram Business)
    instagram_page_id: str = ""  # Boşsa "me" kullanılır
    instagram_access_token: str = ""
    instagram_verify_token: str = "emare_verify"
    
    # Database (SQLite varsayılan; PostgreSQL: postgresql+asyncpg://user:pass@host:5432/dbname)
    database_url: str = "sqlite+aiosqlite:///./asistan.db"

    # Cache (opsiyonel - boşsa in-memory kullanılır)
    redis_url: str = ""  # redis://localhost:6379/0

    # Şifreleme (tenant API anahtarları için - opsiyonel)
    encryption_key: str = ""  # .env: ENCRYPTION_KEY=your-secret-key-min-32-chars

    # Cron (abandoned cart vb.) - production'da mutlaka tanımlayın
    cron_secret_key: str = ""  # .env: CRON_SECRET_KEY=random-secret

    # Admin panel / Session
    session_secret_key: str = "emare-asistan-session-change-in-production"  # .env: SESSION_SECRET_KEY
    admin_password: str = "emare123"  # .env ile değiştirin (e-posta boş + şifre)
    super_admin_email: str = "emre@emareas.com"  # Super admin e-posta
    super_admin_password: str = "3673"  # Super admin şifre

    # E-posta (kayıt onayı için)
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = "noreply@emareasistan.com"
    app_base_url: str = "http://localhost:8000"

    # Chat denetim (asenkron AI ile sohbet kalite kontrolü - analitik)
    chat_audit_enabled: bool = False  # .env: CHAT_AUDIT_ENABLED=true
    chat_audit_sample_rate: int = 20   # 0-100, %X olasılıkla denetim (maliyet kontrolü)

    # SMS (kullanıcı bildirimleri - Netgsm vb.)
    netgsm_usercode: str = ""
    netgsm_password: str = ""
    netgsm_msgheader: str = "EMARE"  # Gönderici adı (max 11 karakter)

    class Config:
        """Pydantic ayar yapılandırması. .env dosyasından değişkenleri okur."""
        env_file = ".env"
        extra = "ignore"


@lru_cache
def get_settings() -> Settings:
    """Uygulama ayarlarını döner, önbelleğe alınmış singleton."""
    ayarlar = Settings()

    # Merkezi EmareAPI kasası fallback'i: .env boşsa anahtarı kasadan çek
    try:
        from anahtarlar import anahtar

        if not (ayarlar.gemini_api_key or "").strip():
            for isim in ("GEMINI_API_KEY", "GOOGLE_API_KEY"):
                try:
                    deger = (anahtar(isim) or "").strip()
                    if deger:
                        ayarlar.gemini_api_key = deger
                        break
                except Exception:
                    pass

        if not (ayarlar.openai_api_key or "").strip():
            try:
                deger = (anahtar("OPENAI_API_KEY") or "").strip()
                if deger:
                    ayarlar.openai_api_key = deger
            except Exception:
                pass
    except Exception:
        # EmareAPI hazır değilse mevcut .env davranışıyla devam et
        pass

    return ayarlar
