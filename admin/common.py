"""
Admin paneli ortak yardımcılar ve template — route modülleri buradan import eder.
"""
from __future__ import annotations

from pathlib import Path

from fastapi import Request
from fastapi.templating import Jinja2Templates

from config import get_settings

templates = Jinja2Templates(directory=str(Path(__file__).resolve().parent / "templates"))


def _to_turkey_str(dt, fmt="%d.%m.%Y %H:%M"):
    """UTC datetime'ı Türkiye saatine çevirip formatla (admin panelde gösterim için)"""
    if not dt:
        return ""
    from zoneinfo import ZoneInfo
    utc = ZoneInfo("UTC")
    turkey = ZoneInfo("Europe/Istanbul")
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=utc)
    local = dt.astimezone(turkey)
    return local.strftime(fmt)


def _utc_to_iso(dt):
    """Naive UTC datetime'ı ISO string yap (timezone ile) - JS tarafında doğru yerel saate çevrilir"""
    if not dt:
        return None
    from zoneinfo import ZoneInfo
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=ZoneInfo("UTC"))
    return dt.isoformat()


def _api_base_for_support(req):
    """Yardım sohbeti API base URL — tüm tenant sayfalarında aynı endpoint'e gitsin"""
    try:
        if req and hasattr(req, "state"):
            return (getattr(req.state, "api_base", None) or "").strip()
    except Exception:
        pass
    return ""


templates.env.filters["to_turkey"] = _to_turkey_str
templates.env.filters["api_base"] = _api_base_for_support


def _session_get(request: Request, key: str, default=None):
    """Session'dan güvenli okuma - SessionMiddleware yoksa default döner"""
    try:
        if "session" not in getattr(request, "scope", {}):
            return default
        return request.session.get(key, default)
    except Exception:
        return default


def _is_super_admin(request: Request) -> bool:
    """Session'dan super_admin kontrolü - form POST'ta session string/bool uyumluluğu"""
    if _session_get(request, "admin") != "ok":
        return False
    sa = _session_get(request, "super_admin")
    return sa is True or (isinstance(sa, str) and sa.lower() in ("true", "1"))


def check_admin(request: Request) -> bool:
    """Basit admin kontrolü - session veya cookie"""
    return _session_get(request, "admin") == "ok"


def get_tenant_id(request: Request) -> int | None:
    """Tenant id: önce request.state, yoksa session. Partner/Super admin tenant seçmediyse None (1 fallback yok)."""
    try:
        state_tid = getattr(getattr(request, "state", None), "tenant_id", None)
        if state_tid is not None:
            return int(state_tid)
    except (ValueError, TypeError):
        pass
    tid = _session_get(request, "tenant_id")
    try:
        if tid is not None:
            return int(tid)
        if getattr(getattr(request, "state", None), "partner_admin", False) or getattr(getattr(request, "state", None), "super_admin", False):
            return None
        return 1
    except (ValueError, TypeError):
        return 1


def _request_client_ip(request: Request) -> str:
    return (request.headers.get("x-forwarded-for") or "").split(",")[0].strip() or (request.client.host if request.client else "")


def _is_truthy(value) -> bool:
    return str(value or "").strip().lower() in ("1", "true", "on", "yes")
