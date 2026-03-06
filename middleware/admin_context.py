"""
Admin context middleware - tenant_id, tenant_name, enabled_modules, super_admin.
Navbar'da doğru firma adının görünmesi için kritik.
Normal kullanıcı için: session tenant_id yanlışsa user kaydından düzelt.
User.last_seen: Her admin isteğinde güncellenir (online/offline için).
"""
from datetime import datetime, timedelta
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import RedirectResponse


def _session_get(request: Request, key: str, default=None):
    try:
        if "session" not in getattr(request, "scope", {}):
            return default
        return request.session.get(key, default)
    except Exception:
        return default


async def admin_context_middleware(request: Request, call_next):
    """Admin sayfaları ve yardım sohbeti API'si için tenant_id, tenant_name set et"""
    path = getattr(request, "scope", {}).get("path", "").split("?")[0]
    is_support_api = path == "/api/chat/support"
    if not path.startswith("/admin") and not is_support_api:
        return await call_next(request)
    if path.startswith("/admin/register") or "static" in path:
        return await call_next(request)

    # Yardım sohbeti API base — tüm tenant sayfalarında aynı URL kullanılsın (subdomain farklılığı için)
    try:
        from config import get_settings
        ab = (get_settings().app_base_url or "").strip().rstrip("/")
        request.state.api_base = ab if ab else ""
    except Exception:
        request.state.api_base = ""

    # Login olmayan kullanıcılar için tenant çözümleme yapma.
    if _session_get(request, "admin") != "ok":
        return await call_next(request)

    # state varsayılanları
    request.state.enabled_modules = set()
    _sa = _session_get(request, "super_admin")
    request.state.super_admin = _sa is True or str(_sa).lower() == "true"
    _pa = _session_get(request, "partner_admin")
    request.state.partner_admin = _pa is True or str(_pa).lower() == "true"
    request.state.partner_id = _session_get(request, "partner_id")
    request.state.tenant_id = None
    request.state.tenant_name = ""
    request.state.tenant_branding = None
    request.state.partner_name = None  # Tenant partner'a aitse (örn. Defence 360), panel markası
    request.state.partner_logo_url = None  # Partner kendi logosu (partner panelinde)

    # Tenant çözümleme prensibi (izolasyon):
    # - Super admin: aktif tenant seçtiyse session tenant_id kullanılır.
    # - Partner admin: session tenant_id (seçtiyse) veya None (henüz seçmediyse /admin/partner'da).
    # - Normal kullanıcı: SADECE User.tenant_id (DB) otorite.
    tid = None
    if request.state.super_admin:
        try:
            session_tid = _session_get(request, "tenant_id")
            tid = int(session_tid) if session_tid is not None else None
        except (ValueError, TypeError):
            tid = None
    elif request.state.partner_admin:
        # Partner admin: session tenant_id varsa kullan (firma seçtiyse)
        try:
            session_tid = _session_get(request, "tenant_id")
            tid = int(session_tid) if session_tid is not None else None
        except (ValueError, TypeError):
            tid = None
    else:
        user_id = _session_get(request, "user_id")
        if not user_id:
            if is_support_api:
                request.state.tenant_id = None
                request.state.tenant_name = ""
                return await call_next(request)
            try:
                request.session.clear()
            except Exception:
                pass
            return RedirectResponse(url="/admin?error=Oturum%20gecersiz", status_code=302)
        try:
            from models.database import AsyncSessionLocal
            from models import User
            from sqlalchemy import select
            async with AsyncSessionLocal() as db:
                r = await db.execute(select(User).where(User.id == int(user_id), User.is_active == True))
                user = r.scalar_one_or_none()
                if user and user.tenant_id is not None:
                    tid = int(user.tenant_id)
                    try:
                        request.session["tenant_id"] = tid
                        request.session["tenant_from_url"] = False
                    except Exception:
                        pass
        except Exception:
            tid = None

        # Loginli normal kullanıcıda tenant çözülemezse oturumu düşür.
        # Partner admin hariç - onlar /admin/partner'da tenant seçenecek. API ise redirect etme.
        if tid is None and not request.state.partner_admin:
            if is_support_api:
                request.state.tenant_id = None
                request.state.tenant_name = ""
                return await call_next(request)
            try:
                request.session.clear()
            except Exception:
                pass
            return RedirectResponse(url="/admin?error=Tenant%20bulunamadi", status_code=302)

    request.state.tenant_id = tid

    if tid is not None:
        try:
            from models.database import AsyncSessionLocal
            from models import Tenant, Partner
            from sqlalchemy import select
            async with AsyncSessionLocal() as db:
                r = await db.execute(select(Tenant).where(Tenant.id == tid))
                t = r.scalar_one_or_none()
                request.state.tenant_name = (t.name or t.slug or f"Firma {tid}") if t else f"Firma {tid}"
                if t and getattr(t, "partner_id", None):
                    pr = await db.execute(select(Partner).where(Partner.id == t.partner_id))
                    partner = pr.scalar_one_or_none()
                    if partner:
                        request.state.partner_name = partner.name
                        if partner.settings:
                            import json
                            s = partner.settings if isinstance(partner.settings, dict) else json.loads(partner.settings or "{}")
                            request.state.partner_logo_url = (s.get("branding_logo_url") or "").strip() or None
                    else:
                        request.state.partner_name = None
                        request.state.partner_logo_url = None
                else:
                    request.state.partner_name = None
                    request.state.partner_logo_url = None
                if t and t.settings:
                    import json
                    s = t.settings if isinstance(t.settings, dict) else json.loads(t.settings or "{}")
                    request.state.tenant_branding = type("Branding", (), {
                        "logo_url": s.get("branding_logo_url"),
                        "primary_color": s.get("branding_primary_color"),
                        "accent_color": s.get("branding_accent_color"),
                    })()
        except Exception:
            request.state.tenant_name = f"Firma {tid}"
    else:
        request.state.tenant_name = ""
        # Partner admin tenant seçmediyse partner adı ve logosu (navbar markası için)
        if request.state.partner_admin and request.state.partner_id:
            try:
                from models.database import AsyncSessionLocal
                from models import Partner
                from sqlalchemy import select
                async with AsyncSessionLocal() as db:
                    r = await db.execute(select(Partner).where(Partner.id == int(request.state.partner_id)))
                    pr = r.scalar_one_or_none()
                    if pr:
                        request.state.partner_name = pr.name
                        if pr.settings:
                            import json
                            s = pr.settings if isinstance(pr.settings, dict) else json.loads(pr.settings or "{}")
                            request.state.partner_logo_url = (s.get("branding_logo_url") or "").strip() or None
                    else:
                        request.state.partner_name = None
                        request.state.partner_logo_url = None
            except Exception:
                request.state.partner_logo_url = None

    if tid is not None:
        try:
            from services.core.modules import get_enabled_modules
            request.state.enabled_modules = await get_enabled_modules(tid)
        except Exception:
            request.state.enabled_modules = set()
    else:
        request.state.enabled_modules = set()

    # Partner admin tenant seçmediyse: sadece partner paneli ve logout erişilebilir
    if request.state.partner_admin and tid is None:
        allow = path in ("/admin", "/admin/") or path.startswith("/admin/partner") or path.startswith("/admin/logout")
        allow = allow or path.startswith("/admin/register") or "login" in path
        if not allow and path.startswith("/admin"):
            return RedirectResponse(url="/admin/partner", status_code=302)

    # last_seen güncelle (online/offline için) - throttle: 60 sn
    user_id = _session_get(request, "user_id")
    if user_id and not request.state.super_admin:
        try:
            from models.database import AsyncSessionLocal
            from models import User
            from sqlalchemy import select, update
            uid = int(user_id)
            now = datetime.utcnow()
            async with AsyncSessionLocal() as db:
                r = await db.execute(select(User.last_seen).where(User.id == uid))
                row = r.one_or_none()
                if row and (row[0] is None or (now - row[0]) > timedelta(seconds=60)):
                    await db.execute(update(User).where(User.id == uid).values(last_seen=now))
                    await db.commit()
        except Exception:
            pass

    return await call_next(request)
