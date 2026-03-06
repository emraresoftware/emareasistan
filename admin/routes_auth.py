"""
Admin paneli — giriş, kayıt, çıkış (auth) route'ları.
"""
import json
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import quote, unquote

from fastapi import APIRouter, Request, HTTPException, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config import get_settings
from models.database import AsyncSessionLocal
from models import Tenant, Partner, User, PendingRegistration

from admin.common import templates, _session_get, _request_client_ip
from services.core.tenant_defaults import create_tenant_defaults

router = APIRouter()


# --- Kayıt (Üye Ol) ---
@router.get("/register", response_class=HTMLResponse)
async def register_page(request: Request, tenant: str = ""):
    """Üye ol sayfası - ?tenant=slug ile mevcut firmaya katıl, yoksa yeni firma kurulumu"""
    if request.session.get("admin") == "ok":
        return RedirectResponse(url="/admin/dashboard", status_code=302)
    tenant_slug = (tenant or "").strip()
    tenant_name = None
    if tenant_slug:
        async with AsyncSessionLocal() as db:
            r = await db.execute(select(Tenant).where(Tenant.slug == tenant_slug))
            t = r.scalar_one_or_none()
            if t:
                tenant_name = t.name or t.slug
    return templates.TemplateResponse("register.html", {
        "request": request,
        "tenant_slug": tenant_slug if tenant_name else None,
        "tenant_name": tenant_name,
    })


@router.post("/api/register/analyze")
async def api_register_analyze(request: Request):
    """URL'yi analiz et - ürünler, firma adı, sektör"""
    body = await request.json()
    url = (body.get("website_url") or "").strip()
    if not url:
        raise HTTPException(400, detail="website_url gerekli")
    from services.ai.website_analyzer import WebsiteAnalyzer
    analyzer = WebsiteAnalyzer(url)
    result = await analyzer.analyze()
    return result


async def _create_tenant_and_user(
    db: AsyncSession,
    slug: str,
    tenant_name: str,
    website_url: str,
    sector: str,
    products: list,
    email: str,
    password_hash: str,
) -> None:
    """Tenant ve kullanıcı oluştur"""
    products_path = f"data/tenants/{slug}/products.json"
    tenant = Tenant(
        name=tenant_name.strip() or slug.replace("-", " ").title(),
        slug=slug,
        website_url=website_url.strip(),
        sector=sector.strip() or "genel",
        products_path=products_path,
        status="active",
    )
    db.add(tenant)
    await db.flush()
    products_dir = Path(__file__).resolve().parent.parent / "data" / "tenants" / slug
    products_dir.mkdir(parents=True, exist_ok=True)
    with open(products_dir / "products.json", "w", encoding="utf-8") as f:
        json.dump(products, f, ensure_ascii=False, indent=2)
    user = User(
        tenant_id=tenant.id,
        name=tenant.name,
        email=email,
        password_hash=password_hash,
        role="admin",
    )
    db.add(user)
    await create_tenant_defaults(tenant.id, db)


@router.post("/register")
async def register_submit(
    request: Request,
    website_url: str = Form(""),
    tenant_name: str = Form(""),
    tenant_slug: str = Form(""),
    sector: str = Form("genel"),
    products_json: str = Form("[]"),
    email: str = Form(),
    password: str = Form(),
    join_tenant_slug: str = Form(""),
):
    """Kayıt - mevcut firmaya katıl (join_tenant_slug) veya yeni firma kurulumu"""
    if request.session.get("admin") == "ok":
        return RedirectResponse(url="/admin/dashboard", status_code=302)
    import logging
    logger = logging.getLogger(__name__)
    try:
        return await _register_submit_impl(
            request, website_url, tenant_name, tenant_slug, sector,
            products_json, email, password, join_tenant_slug=(join_tenant_slug or "").strip(),
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Kayıt hatası: %s", e)
        raise HTTPException(500, detail=f"Kayıt sırasında bir hata oluştu. Lütfen tekrar deneyin. ({str(e)[:100]})")


async def _register_submit_impl(
    request: Request,
    website_url: str,
    tenant_name: str,
    tenant_slug: str,
    sector: str,
    products_json: str,
    email: str,
    password: str,
    *,
    join_tenant_slug: str = "",
):
    email = email.strip().lower()
    if not email or "@" not in email:
        raise HTTPException(400, detail="Geçerli e-posta gerekli")
    if len(password) < 6:
        raise HTTPException(400, detail="Şifre en az 6 karakter olmalı")
    import bcrypt
    from services.integration.email import send_confirmation_email

    def _hash_password(pw: str) -> str:
        return bcrypt.hashpw(pw.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

    if join_tenant_slug:
        async with AsyncSessionLocal() as db:
            r = await db.execute(select(Tenant).where(Tenant.slug == join_tenant_slug))
            tenant = r.scalar_one_or_none()
            if not tenant:
                raise HTTPException(400, detail="Firma bulunamadı")
            result = await db.execute(select(User).where(User.email == email, User.tenant_id == tenant.id))
            if result.scalar_one_or_none():
                return RedirectResponse(url="/admin/t/" + join_tenant_slug + "?error=" + quote("Bu e-posta bu firmada zaten kayıtlı"), status_code=302)
            user = User(
                tenant_id=tenant.id,
                name=email.split("@")[0],
                email=email,
                password_hash=_hash_password(password),
                role="admin",
            )
            db.add(user)
            await db.commit()
        return RedirectResponse(url="/admin/t/" + join_tenant_slug + "?registered=1", status_code=302)

    try:
        products = json.loads(products_json or "[]")
    except json.JSONDecodeError:
        products = []

    settings = get_settings()
    smtp_configured = bool(settings.smtp_host and settings.smtp_user)

    async with AsyncSessionLocal() as db:
        slug = (tenant_slug or "site").strip().lower()[:50]
        slug = "".join(c for c in slug if c.isalnum() or c in "-_")
        if not slug:
            slug = "tenant"
        result = await db.execute(select(Tenant).where(Tenant.slug == slug))
        if result.scalar_one_or_none():
            slug = f"{slug}-{uuid.uuid4().hex[:6]}"
        result = await db.execute(select(User).where(User.email == email))
        if result.scalar_one_or_none():
            raise HTTPException(400, detail="Bu e-posta zaten kayıtlı")
        if smtp_configured:
            token = uuid.uuid4().hex
            expires = datetime.utcnow() + timedelta(hours=24)
            pending = PendingRegistration(
                token=token,
                email=email,
                password_hash=_hash_password(password),
                website_url=website_url.strip(),
                tenant_name=tenant_name.strip(),
                tenant_slug=slug,
                sector=sector.strip(),
                products_json=products_json or "[]",
                expires_at=expires,
            )
            db.add(pending)
            await db.commit()
            base_url = (settings.app_base_url or str(request.base_url)).rstrip("/")
            confirm_url = f"{base_url}/admin/register/confirm?token={token}"
            if send_confirmation_email(email, confirm_url, tenant_name or slug):
                return RedirectResponse(url="/admin/register/sent?email=" + quote(email, safe=""), status_code=302)
            raise HTTPException(503, detail="E-posta gönderilemedi. SMTP ayarlarını kontrol edin.")
        else:
            await _create_tenant_and_user(
                db, slug, tenant_name, website_url, sector,
                products, email, _hash_password(password),
            )
            await db.commit()
    return RedirectResponse(url="/admin?registered=1", status_code=302)


@router.get("/register/sent", response_class=HTMLResponse)
async def register_sent(request: Request):
    """Kayıt endpoint'i. [GET /register/sent]"""
    if request.session.get("admin") == "ok":
        return RedirectResponse(url="/admin/dashboard", status_code=302)
    email = unquote(request.query_params.get("email", ""))
    return templates.TemplateResponse("register_sent.html", {"request": request, "email": email})


@router.get("/register/confirm")
async def register_confirm(request: Request, token: str):
    """Kayıt endpoint'i. [GET /register/confirm]"""
    if request.session.get("admin") == "ok":
        return RedirectResponse(url="/admin/dashboard", status_code=302)
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(PendingRegistration).where(
                PendingRegistration.token == token,
                PendingRegistration.confirmed_at.is_(None),
                PendingRegistration.expires_at > datetime.utcnow(),
            )
        )
        pending = result.scalar_one_or_none()
        if not pending:
            return templates.TemplateResponse("register_confirm.html", {
                "request": request,
                "success": False,
                "error": "Link geçersiz veya süresi dolmuş.",
            })
        if (await db.execute(select(User).where(User.email == pending.email))).scalar_one_or_none():
            pending.confirmed_at = datetime.utcnow()
            await db.commit()
            return templates.TemplateResponse("register_confirm.html", {
                "request": request,
                "success": False,
                "error": "Bu e-posta adresi zaten kayıtlı.",
            })
        try:
            products = json.loads(pending.products_json or "[]")
        except json.JSONDecodeError:
            products = []
        slug = pending.tenant_slug or "tenant"
        result = await db.execute(select(Tenant).where(Tenant.slug == slug))
        if result.scalar_one_or_none():
            slug = f"{slug}-{uuid.uuid4().hex[:6]}"
        await _create_tenant_and_user(
            db,
            slug,
            pending.tenant_name or pending.email.split("@")[0],
            pending.website_url,
            pending.sector or "genel",
            products,
            pending.email,
            pending.password_hash,
        )
        pending.confirmed_at = datetime.utcnow()
        await db.commit()
    return RedirectResponse(url="/admin?registered=1", status_code=302)


@router.get("/", response_class=HTMLResponse)
async def admin_index(request: Request):
    """Admin giriş veya dashboard"""
    if _session_get(request, "admin") != "ok":
        registered = request.query_params.get("registered") == "1"
        error = request.query_params.get("error") or ""
        return templates.TemplateResponse("login.html", {"request": request, "registered": registered, "error": error, "tenant_slug": None, "tenant_name": None})
    if _session_get(request, "super_admin"):
        return RedirectResponse(url="/admin/super", status_code=302)
    return RedirectResponse(url="/admin/dashboard", status_code=302)


@router.get("/p/{partner_slug}", response_class=HTMLResponse)
async def admin_login_partner(request: Request, partner_slug: str):
    """Giriş endpoint'i. [GET /p/{partner_slug}]"""
    async with AsyncSessionLocal() as db:
        r = await db.execute(select(Partner).where(Partner.slug == partner_slug))
        partner = r.scalar_one_or_none()
    if not partner:
        return RedirectResponse(url="/admin?error=" + ("Partner bulunamadı: " + partner_slug), status_code=302)
    if _session_get(request, "admin") == "ok":
        if _session_get(request, "super_admin"):
            return RedirectResponse(url="/admin/super", status_code=302)
        if _session_get(request, "partner_admin") and _session_get(request, "partner_id") == partner.id:
            return RedirectResponse(url="/admin/partner", status_code=302)
        return RedirectResponse(url="/admin/dashboard", status_code=302)
    registered = request.query_params.get("registered") == "1"
    error = request.query_params.get("error") or ""
    return templates.TemplateResponse("login.html", {
        "request": request,
        "registered": registered,
        "error": error,
        "tenant_slug": None,
        "tenant_name": partner.name,
        "partner_slug": partner_slug,
    })


@router.get("/t/{tenant_slug}", response_class=HTMLResponse)
async def admin_login_tenant(request: Request, tenant_slug: str):
    """Giriş endpoint'i. [GET /t/{tenant_slug}]"""
    async with AsyncSessionLocal() as db:
        r = await db.execute(select(Tenant).where(Tenant.slug == tenant_slug))
        tenant = r.scalar_one_or_none()
    if not tenant:
        return RedirectResponse(url="/admin?error=" + ("Firma bulunamadı: " + tenant_slug), status_code=302)
    if _session_get(request, "admin") == "ok":
        if _session_get(request, "super_admin"):
            return RedirectResponse(url="/admin/super", status_code=302)
        session_tid = _session_get(request, "tenant_id")
        session_tid = int(session_tid) if session_tid is not None else None
        if session_tid == tenant.id:
            return RedirectResponse(url="/admin/dashboard", status_code=302)
        return RedirectResponse(
            url="/admin/dashboard?error=" + quote("Farklı firma girişi için önce çıkış yapın."),
            status_code=302,
        )
    registered = request.query_params.get("registered") == "1"
    error = request.query_params.get("error") or ""
    return templates.TemplateResponse("login.html", {
        "request": request,
        "registered": registered,
        "error": error,
        "tenant_slug": tenant_slug,
        "tenant_name": tenant.name or tenant.slug,
    })


@router.post("/login")
async def admin_login(request: Request, email: str = Form(""), password: str = Form(""), tenant: str = Form(""), partner: str = Form("")):
    """Giriş endpoint'i. [POST /login]"""
    from urllib.parse import quote
    from services.core.audit import log_audit
    _client_ip = lambda: _request_client_ip(request)
    _client_ua = lambda: request.headers.get("user-agent", "")[:512]
    if not password or not password.strip():
        return RedirectResponse(url="/admin?error=" + quote("Şifre gerekli"), status_code=302)
    settings = get_settings()
    if not email or not email.strip():
        if password == settings.admin_password:
            request.session.clear()
            request.session["admin"] = "ok"
            request.session["super_admin"] = True
            await log_audit("login", resource="super_admin", details="super_admin (şifre)", ip_address=_client_ip(), user_agent=_client_ua(), success=1)
            return RedirectResponse(url="/admin/super", status_code=302)
        await log_audit("login_fail", resource="super_admin", details="yanlış super admin şifresi", ip_address=_client_ip(), user_agent=_client_ua(), success=0)
        return RedirectResponse(url="/admin?error=" + quote("Yanlış şifre"), status_code=302)
    if settings.super_admin_email and email.strip().lower() == settings.super_admin_email.lower():
        if password == settings.super_admin_password:
            request.session.clear()
            request.session["admin"] = "ok"
            request.session["super_admin"] = True
            await log_audit("login", resource="super_admin", user_email=email.strip().lower(), ip_address=_client_ip(), user_agent=_client_ua(), success=1)
            return RedirectResponse(url="/admin/super", status_code=302)
        await log_audit("login_fail", resource="super_admin", user_email=email.strip().lower(), details="yanlış süper admin şifresi", ip_address=_client_ip(), user_agent=_client_ua(), success=0)
        return RedirectResponse(url="/admin?error=" + quote("Yanlış şifre"), status_code=302)
    import bcrypt
    tenant_slug = (tenant or "").strip()
    partner_slug = (partner or "").strip()
    expected_tid = None
    expected_pid = None
    if tenant_slug:
        async with AsyncSessionLocal() as db:
            r = await db.execute(select(Tenant).where(Tenant.slug == tenant_slug))
            t = r.scalar_one_or_none()
            if t:
                expected_tid = t.id
    if partner_slug:
        async with AsyncSessionLocal() as db:
            r = await db.execute(select(Partner).where(Partner.slug == partner_slug))
            p = r.scalar_one_or_none()
            if p:
                expected_pid = p.id
    async with AsyncSessionLocal() as db:
        if expected_tid is not None:
            result = await db.execute(select(User).where(User.email == email.strip().lower(), User.tenant_id == expected_tid, User.is_active == True))
            user = result.scalar_one_or_none()
        elif expected_pid is not None:
            result = await db.execute(select(User).where(User.email == email.strip().lower(), User.partner_id == expected_pid, User.is_active == True))
            user = result.scalar_one_or_none()
        else:
            result = await db.execute(
                select(User, Partner)
                .join(Partner, User.partner_id == Partner.id)
                .where(User.email == email.strip().lower(), User.is_active == True, User.is_partner_admin == True)
            )
            partner_users = result.all()
            if len(partner_users) >= 1:
                valid = []
                for u, p in partner_users:
                    if u and p and u.password_hash:
                        h = u.password_hash.encode("utf-8") if isinstance(u.password_hash, str) else u.password_hash
                        if bcrypt.checkpw(password.encode("utf-8"), h):
                            valid.append((u, p))
                if len(valid) == 1:
                    user, _ = valid[0]
                elif len(valid) > 1:
                    request.session["login_partner_choices"] = [
                        {"user_id": u.id, "partner_id": p.id, "partner_slug": p.slug, "partner_name": p.name}
                        for u, p in valid
                    ]
                    return RedirectResponse(url="/admin/login/choose-partner", status_code=302)
                else:
                    user = None
            else:
                result = await db.execute(select(User).where(User.email == email.strip().lower(), User.is_active == True))
                user = result.scalar_one_or_none()
        if not user or not user.password_hash:
            err = "Yanlış e-posta veya şifre"
            if expected_tid is not None:
                err = "Bu e-posta bu firmaya kayıtlı değil veya şifre yanlış. Firma giriş linkinizi kontrol edin."
            elif expected_pid is not None:
                err = "Bu e-posta bu partner'a kayıtlı değil veya şifre yanlış. Partner giriş linkinizi kontrol edin."
            base = "/admin/p/" + partner_slug if partner_slug else ("/admin/t/" + tenant_slug if tenant_slug else "/admin")
            await log_audit("login_fail", resource="user", user_email=email.strip().lower(), details="kullanıcı bulunamadı", ip_address=_client_ip(), user_agent=_client_ua(), success=0)
            return RedirectResponse(url=base + "?error=" + quote(err), status_code=302)
        pw_hash = user.password_hash
        if isinstance(pw_hash, str):
            pw_hash = pw_hash.encode("utf-8")
        if not bcrypt.checkpw(password.encode("utf-8"), pw_hash):
            base = "/admin/p/" + partner_slug if partner_slug else ("/admin/t/" + tenant_slug if tenant_slug else "/admin")
            await log_audit("login_fail", resource="user", user_email=email.strip().lower(), user_id=user.id, tenant_id=getattr(user, "tenant_id", None), details="yanlış şifre", ip_address=_client_ip(), user_agent=_client_ua(), success=0)
            return RedirectResponse(url=base + "?error=" + quote("Yanlış e-posta veya şifre"), status_code=302)
        if getattr(user, "is_partner_admin", False) and getattr(user, "partner_id", None):
            user.last_login = datetime.utcnow()
            user.last_seen = datetime.utcnow()
            await db.commit()
            request.session.clear()
            request.session["admin"] = "ok"
            request.session["super_admin"] = False
            request.session["partner_admin"] = True
            request.session["partner_id"] = int(user.partner_id)
            request.session["user_id"] = user.id
            request.session["user_email"] = user.email
            request.session["tenant_id"] = None
            await log_audit("login", resource="partner_admin", resource_id=str(user.partner_id), user_id=user.id, user_email=user.email, ip_address=_client_ip(), user_agent=_client_ua(), success=1)
            return RedirectResponse(url="/admin/partner", status_code=302)
        if user.tenant_id is None and not (getattr(user, "is_partner_admin", False) and getattr(user, "partner_id", None)):
            base = "/admin/p/" + partner_slug if partner_slug else ("/admin/t/" + tenant_slug if tenant_slug else "/admin")
            return RedirectResponse(url=base + "?error=" + quote("Kullanıcı tenant kaydı eksik."), status_code=302)
        if expected_tid is not None and int(user.tenant_id) != expected_tid:
            await log_audit("login_fail", resource="user", user_email=email.strip().lower(), user_id=user.id, details="yanlış tenant", ip_address=_client_ip(), user_agent=_client_ua(), success=0)
            return RedirectResponse(url="/admin/t/" + tenant_slug + "?error=" + quote("Bu e-posta bu firmaya kayıtlı değil."), status_code=302)
        user.last_login = datetime.utcnow()
        user.last_seen = datetime.utcnow()
        await db.commit()
        request.session.clear()
        request.session["admin"] = "ok"
        request.session["super_admin"] = False
        request.session["tenant_id"] = expected_tid if expected_tid is not None else int(user.tenant_id)
        request.session["user_id"] = user.id
        request.session["user_email"] = user.email
        request.session["tenant_from_url"] = expected_tid is not None
        await log_audit("login", resource="user", resource_id=str(user.id), tenant_id=user.tenant_id, user_id=user.id, user_email=user.email, ip_address=_client_ip(), user_agent=_client_ua(), success=1)
    return RedirectResponse(url="/admin/dashboard", status_code=302)


@router.get("/login/choose-partner", response_class=HTMLResponse)
async def login_choose_partner(request: Request):
    """Giriş endpoint'i. [GET /login/choose-partner]"""
    choices = _session_get(request, "login_partner_choices") or []
    if not choices:
        return RedirectResponse(url="/admin?error=Oturum%20gecersiz.%20Tekrar%20giris%20yapin.", status_code=302)
    return templates.TemplateResponse("login_choose_partner.html", {"request": request, "choices": choices})


@router.post("/login/complete-partner")
async def login_complete_partner(request: Request, partner_slug: str = Form("")):
    """Giriş endpoint'i. [POST /login/complete-partner]"""
    choices = _session_get(request, "login_partner_choices") or []
    if not choices or not partner_slug:
        try:
            request.session.pop("login_partner_choices", None)
        except Exception:
            pass
        return RedirectResponse(url="/admin?error=Gecersiz%20secim", status_code=302)
    pick = next((c for c in choices if (c.get("partner_slug") or "") == partner_slug), None)
    if not pick:
        return RedirectResponse(url="/admin?error=Gecersiz%20partner", status_code=302)
    try:
        request.session.pop("login_partner_choices", None)
    except Exception:
        pass
    request.session.clear()
    request.session["admin"] = "ok"
    request.session["super_admin"] = False
    request.session["partner_admin"] = True
    request.session["partner_id"] = int(pick["partner_id"])
    request.session["user_id"] = int(pick["user_id"])
    async with AsyncSessionLocal() as db:
        r = await db.execute(select(User).where(User.id == pick["user_id"]))
        u = r.scalar_one_or_none()
        if u:
            request.session["user_email"] = u.email or ""
            u.last_login = datetime.utcnow()
            u.last_seen = datetime.utcnow()
            await db.commit()
    request.session["tenant_id"] = None
    from services.core.audit import log_audit
    await log_audit("login", resource="partner_admin", resource_id=str(pick["partner_id"]), user_id=pick["user_id"], ip_address=_request_client_ip(request))
    return RedirectResponse(url="/admin/partner", status_code=302)


@router.get("/logout")
async def admin_logout(request: Request):
    """Çıkış endpoint'i. [GET /logout]"""
    request.session.clear()
    return RedirectResponse(url="/admin", status_code=302)
