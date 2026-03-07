"""
Admin paneli – Ayarlar, entegrasyonlar, Yapay Zeka, api/ai-status.
"""
from __future__ import annotations
import json
import re
from datetime import datetime, timedelta
from pathlib import Path


def _update_dotenv_key(key_name: str, new_value: str) -> None:
    """
    .env dosyasındaki KEY=VALUE satırını günceller.
    Satır yoksa sona ekler. new_value boşsa satırı temizler (KEY=).
    """
    env_path = Path(__file__).resolve().parent.parent / ".env"
    if not env_path.exists():
        return
    try:
        lines = env_path.read_text(encoding="utf-8").splitlines()
        found = False
        new_lines = []
        for line in lines:
            stripped = line.strip()
            if stripped.startswith(f"{key_name}=") or stripped.startswith(f"{key_name} ="):
                new_lines.append(f"{key_name}={new_value}")
                found = True
            else:
                new_lines.append(line)
        if not found:
            new_lines.append(f"{key_name}={new_value}")
        env_path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
    except Exception:
        pass

from fastapi import APIRouter, Request, HTTPException, Form, UploadFile, File
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
import httpx

from config import get_settings
from models.database import AsyncSessionLocal
from models import Tenant, User, Conversation, Message
from sqlalchemy import select, func

from admin.common import templates, _session_get, get_tenant_id
from admin import helpers

router = APIRouter()
_module_config_status = helpers._module_config_status
_append_module_sync_log = helpers._append_module_sync_log
_get_local_llm_status = helpers._get_local_llm_status


@router.get("/settings", response_class=HTMLResponse)
async def settings_index(request: Request):
    """Ayarlar ana sayfası – Hesap Sahibi, Yapay Zeka, Entegrasyonlar"""
    if request.session.get("admin") != "ok":
        return RedirectResponse(url="/admin", status_code=302)
    return templates.TemplateResponse("settings_index.html", {"request": request})


@router.get("/settings/account", response_class=HTMLResponse)
async def settings_account(request: Request):
    """Hesap sahibi: ad, e-posta, şifre değiştirme"""
    if request.session.get("admin") != "ok":
        return RedirectResponse(url="/admin", status_code=302)
    if _session_get(request, "super_admin"):
        settings = get_settings()
        return templates.TemplateResponse("settings_account_super.html", {
            "request": request,
            "super_email": settings.super_admin_email or "-",
        })
    user_id = _session_get(request, "user_id")
    if not user_id:
        return RedirectResponse(url="/admin/dashboard", status_code=302)
    tid = get_tenant_id(request)
    async with AsyncSessionLocal() as db:
        if tid is not None:
            r = await db.execute(select(User).where(User.id == int(user_id), User.tenant_id == tid))
        else:
            r = await db.execute(select(User).where(User.id == int(user_id)))
        user = r.scalar_one_or_none()
    if not user:
        if getattr(request.state, "partner_admin", False):
            return RedirectResponse(url="/admin/partner?error=Hesap%20ayari%20icin%20partner%20giris%20linkinizle%20giris%20yapin", status_code=302)
        return RedirectResponse(url="/admin/dashboard", status_code=302)
    notif = {}
    if user.notification_settings:
        try:
            notif = json.loads(user.notification_settings)
        except json.JSONDecodeError:
            pass
    return templates.TemplateResponse("settings_account.html", {
        "request": request,
        "user": user,
        "notif": notif,
        "saved": request.query_params.get("saved") == "1",
    })


@router.post("/settings/account")
async def settings_account_save(
    request: Request,
    name: str = Form(""),
    email: str = Form(""),
    phone: str = Form(""),
    password: str = Form(""),
    password_confirm: str = Form(""),
    notify_new_order: str = Form(""),
    notify_daily_digest: str = Form(""),
    notify_channel_email: str = Form(""),
    notify_channel_sms: str = Form(""),
):
    """Hesap ayarlarını kaydet"""
    if request.session.get("admin") != "ok":
        raise HTTPException(401)
    if _session_get(request, "super_admin"):
        return RedirectResponse(url="/admin/dashboard", status_code=302)
    user_id = _session_get(request, "user_id")
    if not user_id:
        return RedirectResponse(url="/admin/dashboard", status_code=302)
    tid = get_tenant_id(request)
    name = (name or "").strip()
    email = (email or "").strip().lower()
    password = (password or "").strip()
    if password and password != (password_confirm or "").strip():
        return RedirectResponse(url="/admin/settings/account?error=password_mismatch", status_code=302)
    if password and len(password) < 6:
        return RedirectResponse(url="/admin/settings/account?error=password_short", status_code=302)
    import bcrypt
    async with AsyncSessionLocal() as db:
        if email:
            dup_q = select(User.id).where(User.email == email, User.id != int(user_id))
            if tid is not None:
                dup_q = dup_q.where(User.tenant_id == tid)
            else:
                dup_q = dup_q.where(User.tenant_id.is_(None))
            dup = await db.execute(dup_q)
            if dup.scalar_one_or_none():
                return RedirectResponse(url="/admin/settings/account?error=email_taken", status_code=302)
        if tid is not None:
            r = await db.execute(select(User).where(User.id == int(user_id), User.tenant_id == tid))
        else:
            r = await db.execute(select(User).where(User.id == int(user_id), User.tenant_id.is_(None)))
        user = r.scalar_one_or_none()
        if not user:
            return RedirectResponse(url="/admin/dashboard", status_code=302)
        user.name = name or user.name
        user.email = email or user.email
        user.phone = (phone or "").strip() or None
        channels = []
        if str(notify_channel_email or "").lower() in ("1", "true", "on", "yes"):
            channels.append("email")
        if str(notify_channel_sms or "").lower() in ("1", "true", "on", "yes"):
            channels.append("sms")
        if not channels:
            channels = ["email"]
        notif = {
            "new_order": str(notify_new_order or "").lower() in ("1", "true", "on", "yes"),
            "daily_digest": str(notify_daily_digest or "").lower() in ("1", "true", "on", "yes"),
            "channels": channels,
        }
        user.notification_settings = json.dumps(notif, ensure_ascii=False)
        if password:
            user.password_hash = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
        await db.commit()
    request.session["user_email"] = user.email
    return RedirectResponse(url="/admin/settings/account?saved=1", status_code=302)


@router.get("/settings/branding", response_class=HTMLResponse)
async def settings_branding(request: Request):
    """Görünüm & marka ayarları (renkler, logo)"""
    if request.session.get("admin") != "ok":
        return RedirectResponse(url="/admin", status_code=302)
    tid = get_tenant_id(request)
    from services.core.tenant import get_tenant_settings
    s = await get_tenant_settings(tid)
    return templates.TemplateResponse("settings_branding.html", {
        "request": request,
        "primary_color": s.get("branding_primary_color") or "",
        "accent_color": s.get("branding_accent_color") or "",
        "logo_url": s.get("branding_logo_url") or "",
        "saved": request.query_params.get("saved") == "1",
    })


@router.post("/settings/branding")
async def settings_branding_save(
    request: Request,
    primary_color: str = Form(""),
    accent_color: str = Form(""),
    logo_url: str = Form(""),
    logo_file: UploadFile | None = File(None),
):
    """Branding ayarlarını tenant.settings'e kaydet. Logo URL veya yüklenen resim."""
    if request.session.get("admin") != "ok":
        raise HTTPException(401)
    tid = get_tenant_id(request)
    primary_color = (primary_color or "").strip()
    accent_color = (accent_color or "").strip()
    logo_url = (logo_url or "").strip()
    if logo_file and logo_file.filename:
        uploaded_url = await helpers.save_branding_logo(logo_file, request, tenant_id=tid)
        if uploaded_url:
            logo_url = uploaded_url
    if primary_color and not re.match(r"^#[0-9A-Fa-f]{6}$", primary_color):
        primary_color = ""
    if accent_color and not re.match(r"^#[0-9A-Fa-f]{6}$", accent_color):
        accent_color = ""
    async with AsyncSessionLocal() as db:
        r = await db.execute(select(Tenant).where(Tenant.id == tid))
        tenant = r.scalar_one_or_none()
        if not tenant:
            raise HTTPException(404)
        existing = {}
        if tenant.settings:
            try:
                existing = json.loads(tenant.settings)
            except json.JSONDecodeError:
                pass
        existing["branding_primary_color"] = primary_color or None
        existing["branding_accent_color"] = accent_color or None
        existing["branding_logo_url"] = logo_url or None
        from services.core.crypto import encrypt_tenant_settings
        tenant.settings = json.dumps(encrypt_tenant_settings(existing), ensure_ascii=False)
        await db.commit()
        from services.core.cache import invalidate_tenant_cache
        await invalidate_tenant_cache(tid)
    return RedirectResponse(url="/admin/settings/branding?saved=1", status_code=302)


@router.get("/settings/api", response_class=HTMLResponse)
async def settings_api(request: Request):
    """Firma admin: Modül bazlı API ayarları – kendi yazılımlarıyla entegrasyon"""
    if request.session.get("admin") != "ok":
        return RedirectResponse(url="/admin", status_code=302)
    tid = get_tenant_id(request)
    from services.core.module_config import get_modules_with_api_config
    from services.core.tenant import get_tenant_settings
    settings = get_settings()
    modules = get_modules_with_api_config()
    tenant_settings = await get_tenant_settings(tid)
    module_apis = tenant_settings.get("module_apis") or {}
    for m in modules:
        mod_data = dict(module_apis.get(m["id"]) or {})
        m["_status"] = _module_config_status(m["id"], m["fields"], mod_data)
        logs = mod_data.get("_sync_logs")
        m["_sync_logs"] = logs[:5] if isinstance(logs, list) else []
        for f in m["fields"]:
            if f.get("type") == "password" and mod_data.get(f["key"]):
                mod_data[f["key"]] = "••••••••••••"
        m["_values"] = mod_data
        groups: dict[str, list[dict]] = {}
        group_order: list[str] = []
        for f in m["fields"]:
            gname = f.get("group")
            if not gname:
                continue
            if gname not in groups:
                groups[gname] = []
                group_order.append(gname)
            groups[gname].append(f)
        if groups:
            m["_groups"] = [{"name": g, "fields": groups[g]} for g in group_order]
    env_channels = [
        {
            "id": "whatsapp",
            "name": "WhatsApp",
            "desc": "WhatsApp Cloud API veya QR Bridge ile mesajlaşma. .env: WHATSAPP_PHONE_NUMBER_ID, WHATSAPP_ACCESS_TOKEN",
            "configured": bool((settings.whatsapp_phone_number_id or "").strip() and (settings.whatsapp_access_token or "").strip()),
            "url": "/admin/whatsapp",
            "setup_url": "/admin/whatsapp",
        },
        {
            "id": "telegram",
            "name": "Telegram",
            "desc": "Telegram Bot API. .env: TELEGRAM_BOT_TOKEN (BotFather'dan alınır)",
            "configured": bool((settings.telegram_bot_token or "").strip()),
            "url": "/admin/conversations?platform=telegram",
            "setup_url": "/admin/settings/api",
        },
        {
            "id": "instagram",
            "name": "Instagram DM",
            "desc": "Meta Instagram Messaging API. .env: INSTAGRAM_PAGE_ID, INSTAGRAM_ACCESS_TOKEN, INSTAGRAM_VERIFY_TOKEN",
            "configured": bool((settings.instagram_access_token or "").strip()),
            "url": "/admin/instagram",
            "setup_url": "/admin/instagram/setup",
        },
        {
            "id": "web_chat",
            "name": "Web Sohbet",
            "desc": "Web sitenize gömülebilen AI destekli sohbet widget'ı. Aşağıdaki embed alanından kodu alın.",
            "configured": True,
            "url": "#embed-kodu",
            "setup_url": "#embed-kodu",
        },
    ]
    api_base = settings.app_base_url.rstrip("/")
    tenant_slug = ""
    embed_code = ""
    if tid is not None:
        async with AsyncSessionLocal() as db:
            r = await db.execute(select(Tenant).where(Tenant.id == tid))
            tenant_obj = r.scalar_one_or_none()
        if tenant_obj:
            tenant_slug = tenant_obj.slug or f"tenant-{tid}"
            embed_code = f'<iframe src="{api_base}/chat/{tenant_slug}" width="100%" height="500" frameborder="0" style="border-radius:12px;max-width:420px;min-height:400px;"></iframe>'
    alert_phone = (tenant_settings.get("alert_phone") or "").strip()
    alert_api_key = (tenant_settings.get("alert_api_key") or "").strip()
    if alert_api_key:
        alert_api_key = "••••••••••••"  # Maskele
    return templates.TemplateResponse("settings_api.html", {
        "request": request,
        "modules": modules,
        "env_channels": env_channels,
        "saved": request.query_params.get("saved") == "1",
        "sync_status": request.query_params.get("sync_status") or "",
        "sync_module": request.query_params.get("sync_module") or "",
        "sync_count": request.query_params.get("sync_count") or "",
        "sync_error": request.query_params.get("sync_error") or "",
        "embed_code": embed_code,
        "tenant_slug": tenant_slug,
        "api_base": api_base,
        "alert_phone": alert_phone,
        "alert_api_key": alert_api_key,
    })


@router.get("/settings/web-chat", response_class=HTMLResponse)
async def settings_web_chat(request: Request):
    """Web sohbet embed kodu - firma sitesine iframe ile gömme"""
    if request.session.get("admin") != "ok":
        return RedirectResponse(url="/admin", status_code=302)
    tid = get_tenant_id(request)
    if tid is None:
        return templates.TemplateResponse("settings_web_chat.html", {
            "request": request,
            "tenant": None,
            "api_base": get_settings().app_base_url.rstrip("/"),
            "tenant_slug": "",
            "embed_code": "",
            "no_tenant": True,
        })
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Tenant).where(Tenant.id == tid))
        tenant = result.scalar_one_or_none()
    if not tenant:
        return RedirectResponse(url="/admin/dashboard", status_code=302)
    api_base = get_settings().app_base_url.rstrip("/")
    slug = tenant.slug or f"tenant-{tid}"
    embed_code = f'<iframe src="{api_base}/chat/{slug}" width="100%" height="500" frameborder="0" style="border-radius:12px;max-width:420px;min-height:400px;"></iframe>'
    return templates.TemplateResponse("settings_web_chat.html", {
        "request": request,
        "tenant": tenant,
        "api_base": api_base,
        "tenant_slug": slug,
        "embed_code": embed_code,
        "no_tenant": False,
    })


@router.post("/settings/api")
async def settings_api_save(request: Request):
    """Modül API ayarlarını kaydet"""
    if request.session.get("admin") != "ok":
        raise HTTPException(401)
    tid = get_tenant_id(request)
    form = await request.form()
    from services.core.module_config import MODULE_API_FIELDS
    from services.core.tenant import get_tenant_settings
    existing_settings = await get_tenant_settings(tid)
    existing_apis = existing_settings.get("module_apis") or {}
    module_apis = {}
    for module_id in MODULE_API_FIELDS:
        cfg = MODULE_API_FIELDS[module_id]
        prev = existing_apis.get(module_id) or {}
        data = dict(prev)
        for f in cfg["fields"]:
            key = f["key"]
            if f.get("type") == "checkbox":
                raw_val = form.get(f"module_{module_id}_{key}")
                val = "1" if str(raw_val or "").lower() in ("1", "true", "on", "yes") else ""
            else:
                val = (form.get(f"module_{module_id}_{key}") or "").strip()
            if val == "••••••••••••":
                continue
            if val:
                data[key] = val
            elif key in data:
                del data[key]
        module_apis[module_id] = data
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Tenant).where(Tenant.id == tid))
        tenant = result.scalar_one_or_none()
        if not tenant:
            raise HTTPException(404)
        existing = {}
        if tenant.settings:
            try:
                existing = json.loads(tenant.settings)
            except json.JSONDecodeError:
                pass
        existing["module_apis"] = module_apis
        # Alarm bildirimi ayarları
        new_alert_phone = (form.get("alert_phone") or "").strip()
        if new_alert_phone:
            existing["alert_phone"] = new_alert_phone
        new_alert_key = (form.get("alert_api_key") or "").strip()
        if new_alert_key and new_alert_key != "••••••••••••":
            existing["alert_api_key"] = new_alert_key
        from services.core.crypto import encrypt_tenant_settings
        tenant.settings = json.dumps(encrypt_tenant_settings(existing), ensure_ascii=False)
        await db.commit()
        from services.core.cache import invalidate_tenant_cache
        await invalidate_tenant_cache(tid)
    return RedirectResponse(url="/admin/settings/api?saved=1", status_code=302)


@router.post("/settings/api/test-url")
async def settings_api_test_url(request: Request):
    """URL alanlari icin hizli baglanti testi."""
    if request.session.get("admin") != "ok":
        raise HTTPException(401)
    form = await request.form()
    target = (form.get("url") or "").strip()
    if not target:
        return JSONResponse({"ok": False, "error": "URL bos olamaz"}, status_code=400)
    if not (target.startswith("http://") or target.startswith("https://")):
        return JSONResponse({"ok": False, "error": "URL http:// veya https:// ile baslamali"}, status_code=400)
    try:
        async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
            resp = await client.get(target)
        return JSONResponse(
            {
                "ok": resp.status_code < 500,
                "status_code": resp.status_code,
                "message": "Baglanti kuruldu" if resp.status_code < 500 else "Sunucu hatasi",
            }
        )
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)[:200]}, status_code=200)


@router.post("/settings/api/preview/{module_id}")
async def settings_api_preview_pull(request: Request, module_id: str):
    """Dis API'den ornek veri cek (DB'ye yazmaz)."""
    if request.session.get("admin") != "ok":
        raise HTTPException(401)
    tid = get_tenant_id(request)
    allowed = {"contacts", "products", "orders", "appointments", "reminders", "admin_staff"}
    if module_id not in allowed:
        raise HTTPException(400, detail="Bu modul icin preview desteklenmiyor")
    from services.integration.sync import preview_module_pull
    async with AsyncSessionLocal() as db:
        result = await preview_module_pull(db, tid, module_id)
    return JSONResponse(result)


@router.post("/settings/api/sync/{module_id}")
async def settings_api_sync_pull(request: Request, module_id: str):
    """Dis API'den modul verisi cek (pull sync)."""
    if request.session.get("admin") != "ok":
        raise HTTPException(401)
    tid = get_tenant_id(request)
    allowed = {"contacts", "products", "orders", "appointments", "reminders", "admin_staff"}
    if module_id not in allowed:
        raise HTTPException(400, detail="Bu modul icin sync desteklenmiyor")
    from services.integration.sync import sync_module_pull
    started = datetime.utcnow()
    async with AsyncSessionLocal() as db:
        result = await sync_module_pull(db, tid, module_id)
    duration_ms = int((datetime.utcnow() - started).total_seconds() * 1000)
    await _append_module_sync_log(
        tid,
        module_id,
        {
            "ts": datetime.utcnow().isoformat(timespec="seconds"),
            "action": "pull",
            "ok": bool(result.get("ok")),
            "count": int(result.get("count") or 0),
            "error": str(result.get("error") or "")[:250],
            "duration_ms": duration_ms,
        },
    )
    if result.get("ok"):
        return RedirectResponse(
            url=f"/admin/settings/api?sync_status=ok&sync_module={module_id}&sync_count={int(result.get('count') or 0)}",
            status_code=302,
        )
    from urllib.parse import quote
    err = quote(str(result.get("error") or "Sync hatasi"))
    return RedirectResponse(
        url=f"/admin/settings/api?sync_status=error&sync_module={module_id}&sync_error={err}",
        status_code=302,
    )


@router.post("/settings/api/push/{module_id}")
async def settings_api_sync_push(request: Request, module_id: str):
    """Local veriyi dis API'ye gonder (push sync)."""
    if request.session.get("admin") != "ok":
        raise HTTPException(401)
    tid = get_tenant_id(request)
    allowed = {"contacts", "products", "orders"}
    if module_id not in allowed:
        raise HTTPException(400, detail="Bu modul icin push desteklenmiyor")
    from services.integration.sync import sync_module_push
    started = datetime.utcnow()
    async with AsyncSessionLocal() as db:
        result = await sync_module_push(db, tid, module_id)
    duration_ms = int((datetime.utcnow() - started).total_seconds() * 1000)
    await _append_module_sync_log(
        tid,
        module_id,
        {
            "ts": datetime.utcnow().isoformat(timespec="seconds"),
            "action": "push",
            "ok": bool(result.get("ok")),
            "count": int(result.get("count") or 0),
            "error": str(result.get("error") or "")[:250],
            "duration_ms": duration_ms,
            "conflicts": int(result.get("conflicts") or 0),
        },
    )
    if result.get("ok"):
        return RedirectResponse(
            url=f"/admin/settings/api?sync_status=ok&sync_module={module_id}&sync_count={int(result.get('count') or 0)}",
            status_code=302,
        )
    from urllib.parse import quote
    err = quote(str(result.get("error") or "Push hatasi"))
    return RedirectResponse(
        url=f"/admin/settings/api?sync_status=error&sync_module={module_id}&sync_error={err}",
        status_code=302,
    )


@router.get("/settings/ai", response_class=HTMLResponse)
async def settings_ai(request: Request):
    """Yapay Zeka API ayarları – Gemini, OpenAI, aktif/pasif, öncelik"""
    if request.session.get("admin") != "ok":
        return RedirectResponse(url="/admin", status_code=302)
    tid = get_tenant_id(request)
    from services.core.tenant import get_tenant_settings
    tenant_settings = await get_tenant_settings(tid)
    raw = {}
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Tenant).where(Tenant.id == tid))
        tenant = result.scalar_one_or_none()
        if tenant and tenant.settings:
            try:
                raw = json.loads(tenant.settings)
            except json.JSONDecodeError:
                pass
    gemini_key = (raw.get("gemini_api_key") or "").strip()
    openai_key = (raw.get("openai_api_key") or "").strip()
    gemini_model = (raw.get("gemini_model") or "").strip() or "gemini-2.5-flash-lite"
    gemini_active = raw.get("ai_gemini_active", True)
    openai_active = raw.get("ai_openai_active", True)
    ai_primary = (raw.get("ai_primary") or "gemini").lower()
    if ai_primary not in ("gemini", "openai"):
        ai_primary = "gemini"
    gemini_key_display = "••••••••••••" if gemini_key else ""
    openai_key_display = "••••••••••••" if openai_key else ""
    gemini_status = "active" if (gemini_active and gemini_key) and (ai_primary == "gemini" or not (openai_active and openai_key)) else ("configured" if gemini_key else "none")
    openai_status = "active" if (openai_active and openai_key) and (ai_primary == "openai" or not (gemini_active and gemini_key)) else ("configured" if openai_key else "none")
    if gemini_active and gemini_key and (not openai_active or not openai_key or ai_primary == "gemini"):
        current_ai = "gemini"
    elif openai_active and openai_key:
        current_ai = "openai"
    else:
        current_ai = "env"
    ai_daily_limit = int(raw.get("ai_daily_limit") or 0) or 500
    proactive_enabled = bool(raw.get("proactive_enabled", False))
    proactive_template = (raw.get("proactive_template") or "").strip() or "Merhaba {name}, size yardımcı olmamızı ister misiniz? Uygun olduğunuzda yazabilirsiniz."
    proactive_inactivity_hours = int(raw.get("proactive_inactivity_hours") or 24)
    proactive_quiet_hours_start = int(raw.get("proactive_quiet_hours_start") or 23)
    proactive_quiet_hours_end = int(raw.get("proactive_quiet_hours_end") or 9)
    proactive_weekly_limit = int(raw.get("proactive_weekly_limit") or 2)
    proactive_ab_enabled = bool(raw.get("proactive_ab_enabled", False))
    proactive_template_b = (raw.get("proactive_template_b") or "").strip()
    proactive_segment = (raw.get("proactive_segment") or "all").strip().lower()
    if proactive_segment not in ("all", "new_customer", "has_order", "high_value"):
        proactive_segment = "all"
    proactive_segment_min_order_total = float(raw.get("proactive_segment_min_order_total") or 0)
    health_alert_email = (raw.get("health_alert_email") or "").strip()
    health_alert_sms_webhook = (raw.get("health_alert_sms_webhook") or "").strip()
    # Tenant bazlı WhatsApp Bridge URL (opsiyonel) – yoksa global settings.whatsapp_bridge_url kullanılır
    whatsapp_bridge_url = (tenant_settings.get("whatsapp_bridge_url") or "").strip()

    today = datetime.utcnow().date()
    day_labels: list[str] = []
    day_counts_map: dict[str, int] = {}
    async with AsyncSessionLocal() as db:
        seven_days_ago = datetime.utcnow() - timedelta(days=7)
        day_q = await db.execute(
            select(func.date(Message.created_at), func.count(Message.id))
            .select_from(Message)
            .join(Conversation, Message.conversation_id == Conversation.id)
            .where(
                Conversation.tenant_id == tid,
                Message.role == "user",
                Message.created_at >= seven_days_ago,
            )
            .group_by(func.date(Message.created_at))
        )
        for day_key, c in day_q.all():
            day_counts_map[str(day_key)] = int(c or 0)
    usage_7d: list[dict] = []
    for i in range(6, -1, -1):
        d = today - timedelta(days=i)
        key = str(d)
        count = int(day_counts_map.get(key) or 0)
        usage_7d.append({"date": key, "label": d.strftime("%d.%m"), "count": count})
        day_labels.append(d.strftime("%d.%m"))
    usage_today = usage_7d[-1]["count"] if usage_7d else 0

    from services.workflow.metrics import get_pipeline_metrics_snapshot
    pipeline_metrics = get_pipeline_metrics_snapshot(tid, hours=24)

    local_llm_status = _get_local_llm_status()

    return templates.TemplateResponse("settings_ai.html", {
        "request": request,
        "local_llm_status": local_llm_status,
        "gemini_key_display": gemini_key_display,
        "openai_key_display": openai_key_display,
        "gemini_model": gemini_model,
        "gemini_active": gemini_active,
        "openai_active": openai_active,
        "ai_primary": ai_primary,
        "gemini_status": gemini_status,
        "openai_status": openai_status,
        "current_ai": current_ai,
        "ai_daily_limit": ai_daily_limit,
        "proactive_enabled": proactive_enabled,
        "proactive_template": proactive_template,
        "proactive_inactivity_hours": proactive_inactivity_hours,
        "proactive_quiet_hours_start": proactive_quiet_hours_start,
        "proactive_quiet_hours_end": proactive_quiet_hours_end,
        "proactive_weekly_limit": proactive_weekly_limit,
        "proactive_ab_enabled": proactive_ab_enabled,
        "proactive_template_b": proactive_template_b,
        "proactive_segment": proactive_segment,
        "proactive_segment_min_order_total": proactive_segment_min_order_total,
        "health_alert_email": health_alert_email,
        "health_alert_sms_webhook": health_alert_sms_webhook,
        "whatsapp_bridge_url": whatsapp_bridge_url,
        "usage_7d": usage_7d,
        "usage_today": usage_today,
        "pipeline_metrics": pipeline_metrics,
        "saved": request.query_params.get("saved") == "1",
    })


@router.post("/settings/ai")
async def settings_ai_save(request: Request):
    """Yapay Zeka ayarlarını kaydet"""
    if request.session.get("admin") != "ok":
        raise HTTPException(401)
    tid = get_tenant_id(request)
    form = await request.form()
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Tenant).where(Tenant.id == tid))
        tenant = result.scalar_one_or_none()
        if not tenant:
            raise HTTPException(404)
        existing = {}
        if tenant.settings:
            try:
                existing = json.loads(tenant.settings)
            except json.JSONDecodeError:
                pass
        gemini_key = (form.get("gemini_api_key") or "").strip()
        openai_key = (form.get("openai_api_key") or "").strip()
        if gemini_key == "••••••••••••":
            gemini_key = (existing.get("gemini_api_key") or "").strip()
        if openai_key == "••••••••••••":
            openai_key = (existing.get("openai_api_key") or "").strip()
        existing["gemini_api_key"] = gemini_key or None
        existing["openai_api_key"] = openai_key or None
        existing["gemini_model"] = (form.get("gemini_model") or "").strip() or "gemini-2.5-flash-lite"
        existing["ai_gemini_active"] = form.get("gemini_active") == "1"
        existing["ai_openai_active"] = form.get("openai_active") == "1"
        existing["ai_primary"] = (form.get("ai_primary") or "gemini").lower()
        if existing["ai_primary"] not in ("gemini", "openai"):
            existing["ai_primary"] = "gemini"
        try:
            existing["ai_daily_limit"] = int((form.get("ai_daily_limit") or "500").strip()) or 500
        except ValueError:
            existing["ai_daily_limit"] = 500
        existing["proactive_enabled"] = form.get("proactive_enabled") == "1"
        existing["proactive_template"] = (form.get("proactive_template") or "").strip() or "Merhaba {name}, size yardımcı olmamızı ister misiniz? Uygun olduğunuzda yazabilirsiniz."
        try:
            existing["proactive_inactivity_hours"] = int((form.get("proactive_inactivity_hours") or "24").strip()) or 24
        except ValueError:
            existing["proactive_inactivity_hours"] = 24
        if existing["proactive_inactivity_hours"] < 1:
            existing["proactive_inactivity_hours"] = 24
        try:
            existing["proactive_quiet_hours_start"] = int((form.get("proactive_quiet_hours_start") or "23").strip())
        except ValueError:
            existing["proactive_quiet_hours_start"] = 23
        try:
            existing["proactive_quiet_hours_end"] = int((form.get("proactive_quiet_hours_end") or "9").strip())
        except ValueError:
            existing["proactive_quiet_hours_end"] = 9
        try:
            existing["proactive_weekly_limit"] = int((form.get("proactive_weekly_limit") or "2").strip())
        except ValueError:
            existing["proactive_weekly_limit"] = 2
        existing["proactive_quiet_hours_start"] = max(0, min(23, int(existing["proactive_quiet_hours_start"])))
        existing["proactive_quiet_hours_end"] = max(0, min(23, int(existing["proactive_quiet_hours_end"])))
        existing["proactive_weekly_limit"] = max(0, min(50, int(existing["proactive_weekly_limit"])))
        existing["proactive_ab_enabled"] = form.get("proactive_ab_enabled") == "1"
        existing["proactive_template_b"] = (form.get("proactive_template_b") or "").strip()
        seg = (form.get("proactive_segment") or "all").strip().lower()
        existing["proactive_segment"] = seg if seg in ("all", "new_customer", "has_order", "high_value") else "all"
        try:
            existing["proactive_segment_min_order_total"] = float((form.get("proactive_segment_min_order_total") or "0").strip().replace(",", "."))
        except ValueError:
            existing["proactive_segment_min_order_total"] = 0
        existing["health_alert_email"] = (form.get("health_alert_email") or "").strip()
        existing["health_alert_sms_webhook"] = (form.get("health_alert_sms_webhook") or "").strip()
        # Tenant bazlı WhatsApp Bridge URL – boş bırakılırsa global ayar kullanılır
        bridge_url_raw = (form.get("whatsapp_bridge_url") or "").strip()
        existing["whatsapp_bridge_url"] = bridge_url_raw or None
        from services.core.crypto import encrypt_tenant_settings
        tenant.settings = json.dumps(encrypt_tenant_settings(existing), ensure_ascii=False)
        await db.commit()
        from services.core.cache import invalidate_tenant_cache
        await invalidate_tenant_cache(tid)

    # .env dosyasını da güncelle — yeniden başlatmada eski key dönmesin
    if gemini_key:
        _update_dotenv_key("GEMINI_API_KEY", gemini_key)
    if openai_key:
        _update_dotenv_key("OPENAI_API_KEY", openai_key)

    return RedirectResponse(url="/admin/settings/ai?saved=1", status_code=302)


@router.get("/api/ai-status")
async def api_ai_status(request: Request):
    """Yapay Zeka API bağlantı durumunu test et – JSON döner"""
    if request.session.get("admin") != "ok":
        raise HTTPException(401)
    import asyncio
    tid = get_tenant_id(request)
    from services.core.tenant import get_tenant_settings
    tenant_settings = await get_tenant_settings(tid)
    gemini_key = tenant_settings.get("gemini_api_key")
    openai_key = tenant_settings.get("openai_api_key")
    settings = get_settings()
    if not gemini_key:
        gemini_key = settings.gemini_api_key or ""
    if not openai_key:
        openai_key = settings.openai_api_key or ""
    result = {"gemini": {"configured": bool(gemini_key), "ok": False, "error": None}, "openai": {"configured": bool(openai_key), "ok": False, "error": None}}
    if gemini_key:
        try:
            model_name = tenant_settings.get("gemini_model") or settings.gemini_model or "gemini-2.5-flash-lite"
            model_path = model_name if model_name.startswith("models/") else f"models/{model_name}"
            url = f"https://generativelanguage.googleapis.com/v1beta/{model_path}:generateContent?key={gemini_key}"
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.post(url, json={"contents": [{"parts": [{"text": "Say OK"}]}]})
                if resp.status_code == 200:
                    data = resp.json()
                    result["gemini"]["ok"] = bool(data.get("candidates") and data["candidates"][0].get("content", {}).get("parts"))
                else:
                    result["gemini"]["error"] = f"HTTP {resp.status_code}: {(resp.text or '')[:150]}"
        except asyncio.TimeoutError:
            result["gemini"]["error"] = "Zaman aşımı (15 sn)"
        except Exception as e:
            result["gemini"]["error"] = str(e)[:200]
    if openai_key:
        try:
            from openai import AsyncOpenAI
            client = AsyncOpenAI(api_key=openai_key)
            r = await asyncio.wait_for(
                client.chat.completions.create(model="gpt-4o-mini", messages=[{"role": "user", "content": "Say OK"}], max_tokens=5),
                timeout=15.0
            )
            result["openai"]["ok"] = bool(r and r.choices)
        except asyncio.TimeoutError:
            result["openai"]["error"] = "Zaman aşımı (15 sn)"
        except Exception as e:
            result["openai"]["error"] = str(e)[:200]
    return JSONResponse(result)
