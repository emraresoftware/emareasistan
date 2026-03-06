"""
Tenant (firma) ayarları - her müşteri kendi adres, telefon, konum bilgisi
Redis/in-memory cache ile DB yükü azaltılır.
API anahtarları şifreli saklanır (ENCRYPTION_KEY varsa).
"""
import json

from models.database import AsyncSessionLocal
from services.core.crypto import decrypt_value
from models import Tenant
from sqlalchemy import select
from config import get_settings

from services.core.cache import get_tenant_settings_cached, invalidate_tenant_cache


async def _fetch_tenant_settings_from_db(tenant_id: int) -> dict:
    """
    Tenant için iletişim/konum ayarlarını döndür.
    Tenant.settings JSON: {"address", "phone", "lat", "lng", "maps_url"}
    Boşsa tenant_id=1 için global config'ten (default_tenant_*) doldurulur.
    """
    settings = get_settings()
    fallback = {
        "name": "Firma",
        "address": settings.default_tenant_address,
        "phone": settings.default_tenant_phone,
        "lat": settings.default_tenant_lat,
        "lng": settings.default_tenant_lng,
        "maps_url": settings.default_tenant_maps_url,
    }

    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Tenant).where(Tenant.id == tenant_id))
        tenant = result.scalar_one_or_none()

    if not tenant:
        return fallback

    name = tenant.name or "Firma"
    products_path = tenant.products_path or ""

    raw = tenant.settings
    if not raw:
        if tenant_id == 1:
            return {**fallback, "name": name, "products_path": products_path}
        return {"name": name, "address": "", "phone": "", "lat": 0, "lng": 0, "maps_url": "", "products_path": products_path}

    if isinstance(raw, str):
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            return {**fallback, "name": name, "products_path": products_path} if tenant_id == 1 else {"name": name, "address": "", "phone": "", "lat": 0, "lng": 0, "maps_url": "", "products_path": products_path}
    else:
        data = raw or {}

    module_apis = data.get("module_apis")
    if isinstance(module_apis, dict):
        pass
    else:
        module_apis = {}
    gemini_key = decrypt_value((data.get("gemini_api_key") or "").strip() or None) if data.get("gemini_api_key") else None
    openai_key = decrypt_value((data.get("openai_api_key") or "").strip() or None) if data.get("openai_api_key") else None
    gemini_active = data.get("ai_gemini_active", True)
    openai_active = data.get("ai_openai_active", True)
    ai_primary = (data.get("ai_primary") or "gemini").lower()
    if ai_primary not in ("gemini", "openai"):
        ai_primary = "gemini"
    api_overrides = {}
    if gemini_active and gemini_key:
        api_overrides["gemini_api_key"] = gemini_key
        api_overrides["gemini_model"] = (data.get("gemini_model") or "").strip() or None
    if openai_active and openai_key:
        api_overrides["openai_api_key"] = openai_key
    if api_overrides.get("gemini_api_key") and api_overrides.get("openai_api_key"):
        if ai_primary == "openai":
            del api_overrides["gemini_api_key"]
            del api_overrides["gemini_model"]
        else:
            del api_overrides["openai_api_key"]
    out = {
        "name": data.get("name") or name,
        "ai_prompt_override": (data.get("ai_prompt_override") or "").strip(),
        "address": data.get("address") or (fallback["address"] if tenant_id == 1 else ""),
        "phone": data.get("phone") or (fallback["phone"] if tenant_id == 1 else ""),
        "lat": float(data.get("lat", 0) or fallback["lat"] if tenant_id == 1 else 0),
        "lng": float(data.get("lng", 0) or fallback["lng"] if tenant_id == 1 else 0),
        "maps_url": data.get("maps_url") or (fallback["maps_url"] if tenant_id == 1 else ""),
        "products_path": products_path,
        "module_apis": module_apis,
        "openai_api_key": api_overrides.get("openai_api_key"),
        "gemini_api_key": api_overrides.get("gemini_api_key"),
        "gemini_model": api_overrides.get("gemini_model"),
        "ai_daily_limit": int(data["ai_daily_limit"]) if data.get("ai_daily_limit") not in (None, "") else 500,  # 0 = sınırsız
        "proactive_enabled": bool(data.get("proactive_enabled", False)),
        "proactive_template": (data.get("proactive_template") or "").strip(),
        "proactive_inactivity_hours": int(data["proactive_inactivity_hours"]) if data.get("proactive_inactivity_hours") not in (None, "") else 24,
        "proactive_quiet_hours_start": int(data["proactive_quiet_hours_start"]) if data.get("proactive_quiet_hours_start") not in (None, "") else 23,
        "proactive_quiet_hours_end": int(data["proactive_quiet_hours_end"]) if data.get("proactive_quiet_hours_end") not in (None, "") else 9,
        "proactive_weekly_limit": int(data["proactive_weekly_limit"]) if data.get("proactive_weekly_limit") not in (None, "") else 2,
        "proactive_ab_enabled": bool(data.get("proactive_ab_enabled", False)),
        "proactive_template_b": (data.get("proactive_template_b") or "").strip(),
        "proactive_segment": (data.get("proactive_segment") or "all").strip(),
        "proactive_segment_min_order_total": float(data.get("proactive_segment_min_order_total") or 0),
        "health_alert_email": (data.get("health_alert_email") or "").strip(),
        "health_alert_sms_webhook": (data.get("health_alert_sms_webhook") or "").strip(),
        "local_llm_min_confidence": int(data["local_llm_min_confidence"]) if data.get("local_llm_min_confidence") not in (None, "") else None,
        "welcome_scenarios": data.get("welcome_scenarios") if isinstance(data.get("welcome_scenarios"), dict) else {},
        "ai_response_rules": data.get("ai_response_rules") if isinstance(data.get("ai_response_rules"), list) else [],
        "quick_reply_options": data.get("quick_reply_options") if isinstance(data.get("quick_reply_options"), dict) else {},
        "branding_primary_color": (data.get("branding_primary_color") or "").strip() or None,
        "branding_accent_color": (data.get("branding_accent_color") or "").strip() or None,
        "branding_logo_url": (data.get("branding_logo_url") or "").strip() or None,
        "whatsapp_bridge_url": (data.get("whatsapp_bridge_url") or "").strip() or settings.whatsapp_bridge_url,
    }
    return out


async def get_tenant_settings(tenant_id: int) -> dict:
    """Tenant ayarları - cache üzerinden (Redis veya in-memory)"""
    return await get_tenant_settings_cached(tenant_id, _fetch_tenant_settings_from_db)


async def get_module_api_settings(tenant_id: int, module_id: str) -> dict:
    """
    Tenant için belirli modülün API ayarlarını döndür.
    Boşsa global config'ten (cargo için) doldurulabilir.
    """
    settings = get_settings()
    fallback = {}
    if module_id == "cargo":
        fallback = {
            "yurtici_api_key": settings.yurtici_api_key or "",
            "aras_api_key": settings.aras_api_key or "",
            "mng_api_key": settings.mng_api_key or "",
        }
    elif module_id == "email":
        fallback = {
            "smtp_host": settings.smtp_host or "",
            "smtp_port": str(settings.smtp_port or 587),
            "smtp_user": settings.smtp_user or "",
            "smtp_password": settings.smtp_password or "",
            "smtp_from": settings.smtp_from or "",
        }

    full = await get_tenant_settings(tenant_id)
    module_apis = full.get("module_apis") or {}
    module_data = module_apis.get(module_id) or {}

    SENSITIVE_KEYS = ("api_key", "secret_key", "password", "_key")
    out = {**fallback}
    for k, v in module_data.items():
        if v is not None and str(v).strip():
            val = str(v).strip()
            if any(sk in k.lower() for sk in SENSITIVE_KEYS):
                dec = decrypt_value(val)
                if dec:
                    val = dec
            out[k] = val
    return out
