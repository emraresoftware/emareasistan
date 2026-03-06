"""
Admin paneli – Partner ve super admin route'ları.
"""
import json
import uuid
from datetime import datetime, timedelta
from pathlib import Path

from fastapi import APIRouter, Request, HTTPException, Form, UploadFile, File
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import select, func, update
import httpx

from config import get_settings
from models.database import AsyncSessionLocal
from models import Partner, Tenant, User, Order, Conversation, WhatsAppConnection, AuditLog

from admin.common import templates, _session_get, _is_super_admin, get_tenant_id
from admin import helpers

router = APIRouter()


def _parse_enabled_modules(raw) -> set:
    """Tenant.enabled_modules'dan set döndür"""
    if raw is None or raw == "":
        return set()
    if isinstance(raw, str):
        try:
            arr = json.loads(raw)
            return set(str(m) for m in arr if m)
        except Exception:
            return set()
    return set(str(m) for m in raw if m)


# --- Super admin ---

@router.get("/super", response_class=HTMLResponse)
async def super_admin_page(request: Request):
    """Super admin dashboard - firmalar ve sistem geneli istatistikler"""
    if _session_get(request, "admin") != "ok" or not _session_get(request, "super_admin"):
        return RedirectResponse(url="/admin", status_code=302)
    from services.core.settings import get_chat_audit_enabled, get_chat_audit_sample_rate
    audit_enabled = get_chat_audit_enabled()
    audit_sample_rate = get_chat_audit_sample_rate()
    whatsapp_connected = False
    try:
        bridge_url = get_settings().whatsapp_bridge_url or "http://localhost:3100"
        async with httpx.AsyncClient(timeout=3.0) as client:
            r = await client.get(f"{bridge_url}/api/status")
        if r.status_code == 200:
            whatsapp_connected = r.json().get("connected", False)
    except Exception:
        pass
    async with AsyncSessionLocal() as db:
        partners_result = await db.execute(select(Partner).order_by(Partner.name))
        partners = partners_result.scalars().all()
        pa_result = await db.execute(select(User).where(User.is_partner_admin == True, User.partner_id.isnot(None)))
        partner_admins_raw = pa_result.scalars().all()
        partner_admins = {}
        for u in partner_admins_raw:
            pid = u.partner_id or 0
            if pid not in partner_admins:
                partner_admins[pid] = []
            partner_admins[pid].append(u)
        result = await db.execute(select(Tenant).where(Tenant.status != "deleted").order_by(Tenant.name))
        tenants = result.scalars().all()
        total_tenants = len(tenants)
        active_tenants = sum(1 for t in tenants if (t.status or "active") == "active")
        total_orders = (await db.execute(select(func.count(Order.id)))).scalar() or 0
        total_conversations = (await db.execute(select(func.count(Conversation.id)))).scalar() or 0
        month_start = datetime.utcnow().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        monthly_revenue = (await db.execute(
            select(func.coalesce(func.sum(Order.total_amount), 0)).where(
                Order.created_at >= month_start,
                Order.status != "cancelled",
            )
        )).scalar() or 0
        monthly_revenue = float(monthly_revenue)
        month_names = ["", "Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran", "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık"]
        month_name = month_names[month_start.month] if month_start else ""
        wa_result = await db.execute(
            select(WhatsAppConnection).order_by(WhatsAppConnection.id)
        )
        wa_connections = wa_result.scalars().all()
    return templates.TemplateResponse("super_admin.html", {
        "request": request,
        "partners": partners,
        "partner_admins": partner_admins,
        "tenants": tenants,
        "total_tenants": total_tenants,
        "active_tenants": active_tenants,
        "total_orders": total_orders,
        "total_conversations": total_conversations,
        "monthly_revenue": monthly_revenue,
        "month_name": month_name,
        "audit_enabled": audit_enabled,
        "audit_sample_rate": audit_sample_rate,
        "whatsapp_connected": whatsapp_connected,
        "wa_connections": wa_connections,
    })


@router.get("/super/login-logs", response_class=HTMLResponse)
async def super_admin_login_logs(request: Request, page: int = 1, limit: int = 50, filter: str = "all"):
    """Super admin: Partner ve kullanıcı giriş logları (e-posta, rol, IP, user-agent, başarı durumu)"""
    if _session_get(request, "admin") != "ok" or not _session_get(request, "super_admin"):
        return RedirectResponse(url="/admin", status_code=302)
    limit = min(max(limit, 10), 100)
    offset = (page - 1) * limit
    action_filter = ["login", "login_fail"] if filter == "all" else (["login"] if filter == "success" else ["login_fail"])
    async with AsyncSessionLocal() as db:
        count_result = await db.execute(
            select(func.count(AuditLog.id)).where(AuditLog.action.in_(action_filter))
        )
        total = count_result.scalar() or 0
        result = await db.execute(
            select(AuditLog)
            .where(AuditLog.action.in_(action_filter))
            .order_by(AuditLog.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        logs = result.scalars().all()
        # Başarısız giriş sayısı (son 24 saat)
        since = datetime.utcnow() - timedelta(hours=24)
        fail_count_result = await db.execute(
            select(func.count(AuditLog.id)).where(AuditLog.action == "login_fail", AuditLog.created_at >= since)
        )
        fail_24h = fail_count_result.scalar() or 0
        tenant_ids = {log.tenant_id for log in logs if log.tenant_id}
        tenants_map = {}
        if tenant_ids:
            t_res = await db.execute(select(Tenant).where(Tenant.id.in_(tenant_ids)))
            for t in t_res.scalars().all():
                tenants_map[t.id] = t.name or t.slug
    total_pages = (total + limit - 1) // limit if total else 1
    return templates.TemplateResponse("super_admin_login_logs.html", {
        "request": request,
        "logs": logs,
        "tenants_map": tenants_map,
        "page": page,
        "total_pages": total_pages,
        "total": total,
        "limit": limit,
        "filter": filter,
        "fail_24h": fail_24h,
    })


@router.get("/super/user-status", response_class=HTMLResponse)
async def super_admin_user_status(request: Request):
    """Super admin: Tüm kullanıcıların online/offline durumu"""
    if _session_get(request, "admin") != "ok" or not _session_get(request, "super_admin"):
        return RedirectResponse(url="/admin", status_code=302)
    async with AsyncSessionLocal() as db:
        u_res = await db.execute(select(User).where(User.is_active == True).order_by(User.tenant_id.nullsfirst(), User.name))
        users = u_res.scalars().all()
        tenant_ids = {u.tenant_id for u in users if u.tenant_id}
        partner_ids = {u.partner_id for u in users if u.partner_id}
        tenants_map = {}
        if tenant_ids:
            t_res = await db.execute(select(Tenant).where(Tenant.id.in_(tenant_ids)))
            for t in t_res.scalars().all():
                tenants_map[t.id] = t.name or t.slug
        partners_map = {}
        if partner_ids:
            p_res = await db.execute(select(Partner).where(Partner.id.in_(partner_ids)))
            for p in p_res.scalars().all():
                partners_map[p.id] = p.name or p.slug
    now = datetime.utcnow()
    online_threshold = timedelta(minutes=5)
    users_with_status = []
    for u in users:
        is_online = u.last_seen and (now - u.last_seen) < online_threshold
        firm_or_partner = tenants_map.get(u.tenant_id) if u.tenant_id else (f"{partners_map.get(u.partner_id, '?')} (Partner)" if u.partner_id else "-")
        users_with_status.append({"user": u, "is_online": is_online, "firm_or_partner": firm_or_partner})
    online_count = sum(1 for _ in users_with_status if _["is_online"])
    return templates.TemplateResponse("super_admin_user_status.html", {
        "request": request,
        "users_with_status": users_with_status,
        "online_count": online_count,
    })


# --- Partner admin ---

@router.get("/partner/panel")
async def partner_admin_panel(request: Request):
    """Partner admin: Panelim - partner'ın kendi firma paneline gir (varsayılan tenant)"""
    if _session_get(request, "admin") != "ok" or not _session_get(request, "partner_admin"):
        return RedirectResponse(url="/admin", status_code=302)
    pid = _session_get(request, "partner_id")
    if not pid:
        return RedirectResponse(url="/admin?error=Partner%20bulunamadi", status_code=302)
    async with AsyncSessionLocal() as db:
        r = await db.execute(select(Partner).where(Partner.id == int(pid)))
        partner = r.scalar_one_or_none()
        if not partner:
            return RedirectResponse(url="/admin?error=Partner%20kaydi%20bulunamadi", status_code=302)
        s = partner.settings if isinstance(partner.settings, dict) else json.loads(partner.settings or "{}")
        default_tid = s.get("default_tenant_id")
        if not default_tid:
            tenant_slug = f"{partner.slug}-panel"
            r = await db.execute(select(Tenant).where(Tenant.slug == tenant_slug))
            if r.scalar_one_or_none():
                tenant_slug = f"{partner.slug}-panel-{partner.id}"
            products_path = f"data/tenants/{tenant_slug}/products.json"
            default_tenant = Tenant(
                name=partner.name,
                slug=tenant_slug,
                website_url="https://example.com",
                sector="genel",
                products_path=products_path,
                partner_id=partner.id,
                status="active",
            )
            db.add(default_tenant)
            await db.flush()
            default_tid = default_tenant.id
            s["default_tenant_id"] = default_tid
            partner.settings = json.dumps(s)
            await db.commit()
            base = Path(__file__).resolve().parent.parent
            products_dir = base / "data" / "tenants" / tenant_slug
            products_dir.mkdir(parents=True, exist_ok=True)
            (products_dir / "products.json").write_text("[]", encoding="utf-8")
        r = await db.execute(select(Tenant).where(Tenant.id == default_tid, Tenant.partner_id == int(pid)))
        tenant = r.scalar_one_or_none()
    if not tenant:
        return RedirectResponse(url="/admin/partner?error=Varsayilan%20firma%20bulunamadi", status_code=302)
    request.session["tenant_id"] = tenant.id
    return RedirectResponse(url="/admin/dashboard", status_code=302)


@router.get("/partner", response_class=HTMLResponse)
async def partner_admin_page(request: Request):
    """Partner admin dashboard - kendi tenant'larını listele, firmaya gir"""
    if _session_get(request, "admin") != "ok" or not _session_get(request, "partner_admin"):
        return RedirectResponse(url="/admin", status_code=302)
    pid = _session_get(request, "partner_id")
    if not pid:
        return RedirectResponse(url="/admin?error=Partner%20bulunamadi", status_code=302)
    async with AsyncSessionLocal() as db:
        r = await db.execute(select(Partner).where(Partner.id == int(pid)))
        partner = r.scalar_one_or_none()
        if not partner:
            return RedirectResponse(url="/admin?error=Partner%20kaydi%20bulunamadi", status_code=302)
        result = await db.execute(select(Tenant).where(Tenant.partner_id == int(pid), Tenant.status != "deleted").order_by(Tenant.name))
        tenants = result.scalars().all()
    partner_logo_url = None
    if partner.settings:
        s = partner.settings if isinstance(partner.settings, dict) else json.loads(partner.settings or "{}")
        partner_logo_url = (s.get("branding_logo_url") or "").strip() or None
    return templates.TemplateResponse("partner_admin.html", {
        "request": request,
        "partner": partner,
        "tenants": tenants,
        "partner_logo_url": partner_logo_url,
    })


@router.get("/partner/users", response_class=HTMLResponse)
async def partner_admin_users(request: Request):
    """Partner admin: Kendi firmalarındaki tüm kullanıcıları görüntüle"""
    if _session_get(request, "admin") != "ok" or not _session_get(request, "partner_admin"):
        return RedirectResponse(url="/admin", status_code=302)
    pid = _session_get(request, "partner_id")
    if not pid:
        return RedirectResponse(url="/admin?error=Partner%20bulunamadi", status_code=302)
    async with AsyncSessionLocal() as db:
        r = await db.execute(select(Partner).where(Partner.id == int(pid)))
        partner = r.scalar_one_or_none()
        if not partner:
            return RedirectResponse(url="/admin?error=Partner%20kaydi%20bulunamadi", status_code=302)
        result = await db.execute(
            select(Tenant).where(Tenant.partner_id == int(pid), Tenant.status != "deleted").order_by(Tenant.name)
        )
        tenants = result.scalars().all()
        tenant_ids = [t.id for t in tenants]
        tenants_map = {t.id: t.name or t.slug for t in tenants}
        if tenant_ids:
            u_res = await db.execute(
                select(User)
                .where((User.tenant_id.in_(tenant_ids)) | ((User.partner_id == int(pid)) & (User.is_partner_admin == True)))
                .order_by(User.tenant_id.nullsfirst(), User.name)
            )
        else:
            u_res = await db.execute(
                select(User).where(User.partner_id == int(pid), User.is_partner_admin == True).order_by(User.name)
            )
        users = u_res.scalars().all()
    partner_logo_url = None
    if partner.settings:
        try:
            s = partner.settings if isinstance(partner.settings, dict) else json.loads(partner.settings or "{}")
            partner_logo_url = s.get("branding_logo_url")
        except Exception:
            pass
    now = datetime.utcnow()
    online_threshold = timedelta(minutes=5)
    users_with_status = [(u, u.last_seen and (now - u.last_seen) < online_threshold) for u in users]
    return templates.TemplateResponse("partner_users.html", {
        "request": request,
        "partner": partner,
        "users_with_status": users_with_status,
        "tenants_map": tenants_map,
        "partner_logo_url": partner_logo_url,
    })


@router.post("/partner/tenants")
async def partner_admin_create_tenant(
    request: Request,
    name: str = Form(""),
    slug: str = Form(""),
    website_url: str = Form(""),
    sector: str = Form("genel"),
    admin_email: str = Form(""),
    admin_password: str = Form(""),
):
    """Partner admin: Kendi müşterisi (tenant) ekler, opsiyonel olarak ilk admin kullanıcısı (geçici şifre ile)"""
    if _session_get(request, "admin") != "ok" or not _session_get(request, "partner_admin"):
        raise HTTPException(401)
    pid = _session_get(request, "partner_id")
    if not pid:
        raise HTTPException(403, detail="Partner bilgisi eksik")
    name = (name or "").strip()
    website_url = (website_url or "").strip()
    sector = (sector or "").strip() or "genel"
    if not name:
        return RedirectResponse(url="/admin/partner?error=Firma%20adi%20gerekli", status_code=302)
    slug = (slug or "").strip().lower()[:80]
    slug = "".join(c for c in slug if c.isalnum() or c in "-_") if slug else ""
    if not slug:
        slug = "".join(c for c in name.lower() if c.isalnum() or c in " -_").replace(" ", "-")[:80] or "firma"
    if not website_url:
        website_url = "https://example.com"
    elif not website_url.startswith(("http://", "https://")):
        website_url = "https://" + website_url
    created_admin = False
    async with AsyncSessionLocal() as db:
        r = await db.execute(select(Tenant).where(Tenant.slug == slug))
        if r.scalar_one_or_none():
            slug = f"{slug}-{uuid.uuid4().hex[:6]}"
        products_path = f"data/tenants/{slug}/products.json"
        tenant = Tenant(
            name=name,
            slug=slug,
            website_url=website_url,
            sector=sector,
            products_path=products_path,
            partner_id=int(pid),
            status="active",
        )
        db.add(tenant)
        await db.flush()
        admin_email = (admin_email or "").strip().lower()
        admin_password = (admin_password or "").strip()
        if admin_email and "@" in admin_email and len(admin_password) >= 6:
            import bcrypt
            dup = await db.execute(select(User).where(User.email == admin_email, User.tenant_id == tenant.id))
            if dup.scalar_one_or_none() is None:
                user = User(
                    tenant_id=tenant.id,
                    name=admin_email.split("@")[0],
                    email=admin_email,
                    password_hash=bcrypt.hashpw(admin_password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8"),
                    role="admin",
                )
                db.add(user)
                created_admin = True
        await db.commit()
        await db.refresh(tenant)
    base = Path(__file__).resolve().parent.parent
    products_dir = base / "data" / "tenants" / slug
    products_dir.mkdir(parents=True, exist_ok=True)
    products_file = products_dir / "products.json"
    if not products_file.exists():
        products_file.write_text("[]", encoding="utf-8")
    q = "created=1&with_admin=1" if created_admin else "created=1"
    return RedirectResponse(url="/admin/partner?" + q, status_code=302)


@router.post("/partner/tenants/{tid}/delete")
async def partner_admin_delete_tenant(request: Request, tid: int):
    """Partner admin: Kendi eklediği firmayı sil (soft delete - status=deleted)"""
    if _session_get(request, "admin") != "ok" or not _session_get(request, "partner_admin"):
        raise HTTPException(401)
    pid = _session_get(request, "partner_id")
    if not pid:
        raise HTTPException(403, detail="Partner bilgisi eksik")
    async with AsyncSessionLocal() as db:
        r = await db.execute(
            select(Tenant).where(Tenant.id == tid, Tenant.partner_id == int(pid))
        )
        tenant = r.scalar_one_or_none()
        if not tenant:
            raise HTTPException(403, detail="Bu firmayı silemezsiniz")
        tenant.status = "deleted"
        await db.commit()
    return RedirectResponse(url="/admin/partner?tenant_deleted=1", status_code=302)


@router.post("/partner/enter/{id}")
async def partner_admin_enter(request: Request, id: int):
    """Partner admin: Firmaya gir (sadece kendi partner'ına ait tenant'lara)"""
    if _session_get(request, "admin") != "ok" or not _session_get(request, "partner_admin"):
        raise HTTPException(401)
    pid = _session_get(request, "partner_id")
    if not pid:
        raise HTTPException(403, detail="Partner bilgisi eksik")
    async with AsyncSessionLocal() as db:
        r = await db.execute(select(Tenant).where(Tenant.id == id, Tenant.partner_id == int(pid)))
        tenant = r.scalar_one_or_none()
    if not tenant:
        raise HTTPException(403, detail="Bu firma sizin partner kapsamınızda değil")
    form = await request.form()
    next_url = (form.get("next_url") or "").strip()
    request.session["tenant_id"] = id
    if next_url and next_url.startswith("/admin"):
        return RedirectResponse(url=next_url, status_code=302)
    return RedirectResponse(url="/admin/dashboard", status_code=302)


@router.get("/partner/modules/{tid}", response_class=HTMLResponse)
async def partner_admin_modules(request: Request, tid: int):
    """Partner admin: Alt firmasının modüllerini yönet"""
    if _session_get(request, "admin") != "ok" or not _session_get(request, "partner_admin"):
        return RedirectResponse(url="/admin", status_code=302)
    pid = _session_get(request, "partner_id")
    if not pid:
        return RedirectResponse(url="/admin?error=Partner%20bulunamadi", status_code=302)
    from services.core.modules import AVAILABLE_MODULES
    async with AsyncSessionLocal() as db:
        r = await db.execute(select(Tenant).where(Tenant.id == tid, Tenant.partner_id == int(pid)))
        tenant = r.scalar_one_or_none()
        if not tenant:
            raise HTTPException(403, detail="Bu firma sizin partner kapsamınızda değil")
        r = await db.execute(select(Partner).where(Partner.id == int(pid)))
        partner = r.scalar_one_or_none()
    if not partner:
        raise HTTPException(404)
    enabled = _parse_enabled_modules(tenant.enabled_modules)
    use_all = len(enabled) == 0
    partner_logo_url = None
    if partner.settings:
        s = partner.settings if isinstance(partner.settings, dict) else json.loads(partner.settings or "{}")
        partner_logo_url = (s.get("branding_logo_url") or "").strip() or None
    return templates.TemplateResponse("partner_modules.html", {
        "request": request,
        "partner": partner,
        "tenant": tenant,
        "modules": AVAILABLE_MODULES,
        "enabled": enabled,
        "use_all": use_all,
        "partner_logo_url": partner_logo_url,
    })


@router.post("/partner/modules/{tid}")
async def partner_admin_modules_save(request: Request, tid: int):
    """Partner admin: Alt firmasının modüllerini kaydet"""
    if _session_get(request, "admin") != "ok" or not _session_get(request, "partner_admin"):
        raise HTTPException(401)
    pid = _session_get(request, "partner_id")
    if not pid:
        raise HTTPException(403)
    form = await request.form()
    use_all = form.get("use_all") == "1"
    async with AsyncSessionLocal() as db:
        r = await db.execute(select(Tenant).where(Tenant.id == tid, Tenant.partner_id == int(pid)))
        tenant = r.scalar_one_or_none()
        if not tenant:
            raise HTTPException(403, detail="Bu firma sizin partner kapsamınızda değil")
        if use_all:
            tenant.enabled_modules = None
        else:
            from services.core.modules import AVAILABLE_MODULES, check_module_dependencies
            valid_ids = {m["id"] for m in AVAILABLE_MODULES}
            selected = [k.replace("mod_", "") for k in form.keys() if k.startswith("mod_") and k.replace("mod_", "") in valid_ids]
            enabled_set = set(selected)
            for mid in selected:
                ok, warnings = check_module_dependencies(mid, enabled_set, enabling=True)
                if not ok:
                    msg = " ".join(warnings)
                    return templates.TemplateResponse("partner_modules.html", {
                        "request": request,
                        "tenant": tenant,
                        "modules": AVAILABLE_MODULES,
                        "enabled": enabled_set,
                        "use_all": False,
                        "error": msg,
                    }, status_code=400)
            if "orders" not in selected and "payment" in selected:
                selected = [m for m in selected if m != "payment"]
            tenant.enabled_modules = json.dumps(selected) if selected else None
        await db.commit()
    return RedirectResponse(url=f"/admin/partner/modules/{tid}?saved=1", status_code=302)


@router.get("/partner/settings/branding", response_class=HTMLResponse)
async def partner_branding_page(request: Request):
    """Partner: Kendi kurumsal logosu"""
    if _session_get(request, "admin") != "ok" or not _session_get(request, "partner_admin"):
        return RedirectResponse(url="/admin", status_code=302)
    pid = _session_get(request, "partner_id")
    if not pid:
        return RedirectResponse(url="/admin?error=Partner%20bulunamadi", status_code=302)
    async with AsyncSessionLocal() as db:
        r = await db.execute(select(Partner).where(Partner.id == int(pid)))
        partner = r.scalar_one_or_none()
    if not partner:
        raise HTTPException(404)
    s = {}
    if partner.settings:
        s = partner.settings if isinstance(partner.settings, dict) else json.loads(partner.settings or "{}")
    logo_url = (s.get("branding_logo_url") or "").strip()
    partner_logo_url = logo_url or None
    return templates.TemplateResponse("partner_branding.html", {
        "request": request,
        "partner": partner,
        "logo_url": logo_url,
        "partner_logo_url": partner_logo_url,
    })


@router.post("/partner/settings/branding")
async def partner_branding_save(
    request: Request,
    logo_url: str = Form(""),
    logo_file: UploadFile | None = File(None),
):
    """Partner: Logoyu kaydet (URL veya yüklenen resim)."""
    if _session_get(request, "admin") != "ok" or not _session_get(request, "partner_admin"):
        raise HTTPException(401)
    pid = _session_get(request, "partner_id")
    if not pid:
        raise HTTPException(403)
    logo_url = (logo_url or "").strip()
    if logo_file and logo_file.filename:
        uploaded_url = await helpers.save_branding_logo(logo_file, request, partner_id=int(pid))
        if uploaded_url:
            logo_url = uploaded_url
    async with AsyncSessionLocal() as db:
        r = await db.execute(select(Partner).where(Partner.id == int(pid)))
        partner = r.scalar_one_or_none()
        if not partner:
            raise HTTPException(404)
        existing = {}
        if partner.settings:
            existing = partner.settings if isinstance(partner.settings, dict) else json.loads(partner.settings or "{}")
        existing["branding_logo_url"] = logo_url or None
        partner.settings = json.dumps(existing)
        await db.commit()
    return RedirectResponse(url="/admin/partner/settings/branding?saved=1", status_code=302)


@router.get("/partner/tenant/{tid}/branding", response_class=HTMLResponse)
async def partner_tenant_branding_page(request: Request, tid: int):
    """Partner: Alt firmasının logosu ve markasını ayarla"""
    if _session_get(request, "admin") != "ok" or not _session_get(request, "partner_admin"):
        return RedirectResponse(url="/admin", status_code=302)
    pid = _session_get(request, "partner_id")
    if not pid:
        return RedirectResponse(url="/admin?error=Partner%20bulunamadi", status_code=302)
    async with AsyncSessionLocal() as db:
        r = await db.execute(select(Tenant).where(Tenant.id == tid, Tenant.partner_id == int(pid)))
        tenant = r.scalar_one_or_none()
        if not tenant:
            raise HTTPException(403, detail="Bu firma sizin partner kapsamınızda değil")
        r = await db.execute(select(Partner).where(Partner.id == int(pid)))
        partner = r.scalar_one_or_none()
    if not partner:
        raise HTTPException(404)
    s = {}
    if tenant.settings:
        s = tenant.settings if isinstance(tenant.settings, dict) else json.loads(tenant.settings or "{}")
    partner_logo_url = None
    if partner.settings:
        ps = partner.settings if isinstance(partner.settings, dict) else json.loads(partner.settings or "{}")
        partner_logo_url = (ps.get("branding_logo_url") or "").strip() or None
    return templates.TemplateResponse("partner_tenant_branding.html", {
        "request": request,
        "partner": partner,
        "tenant": tenant,
        "logo_url": (s.get("branding_logo_url") or "").strip(),
        "primary_color": (s.get("branding_primary_color") or "").strip(),
        "accent_color": (s.get("branding_accent_color") or "").strip(),
        "partner_logo_url": partner_logo_url,
    })


@router.post("/partner/tenant/{tid}/branding")
async def partner_tenant_branding_save(
    request: Request, tid: int,
    logo_url: str = Form(""),
    primary_color: str = Form(""),
    accent_color: str = Form(""),
    logo_file: UploadFile | None = File(None),
):
    """Partner: Alt firmasının markasını kaydet (logo URL veya yüklenen resim)."""
    if _session_get(request, "admin") != "ok" or not _session_get(request, "partner_admin"):
        raise HTTPException(401)
    pid = _session_get(request, "partner_id")
    if not pid:
        raise HTTPException(403)
    logo_url = (logo_url or "").strip()
    if logo_file and logo_file.filename:
        uploaded_url = await helpers.save_branding_logo(logo_file, request, tenant_id=tid)
        if uploaded_url:
            logo_url = uploaded_url
    primary_color = (primary_color or "").strip() or None
    accent_color = (accent_color or "").strip() or None
    async with AsyncSessionLocal() as db:
        r = await db.execute(select(Tenant).where(Tenant.id == tid, Tenant.partner_id == int(pid)))
        tenant = r.scalar_one_or_none()
        if not tenant:
            raise HTTPException(403)
        existing = {}
        if tenant.settings:
            existing = tenant.settings if isinstance(tenant.settings, dict) else json.loads(tenant.settings or "{}")
        existing["branding_logo_url"] = logo_url or None
        existing["branding_primary_color"] = primary_color
        existing["branding_accent_color"] = accent_color
        from services.core.crypto import encrypt_tenant_settings
        tenant.settings = json.dumps(encrypt_tenant_settings(existing), ensure_ascii=False)
        await db.commit()
        from services.core.cache import invalidate_tenant_cache
        await invalidate_tenant_cache(tid)
    return RedirectResponse(url=f"/admin/partner/tenant/{tid}/branding?saved=1", status_code=302)


# --- Super admin POST (partners, tenants, enter, modules) ---

@router.post("/super/partners")
async def super_admin_create_partner(
    request: Request,
    name: str = Form(""),
    slug: str = Form(""),
    admin_email: str = Form(default=""),
    admin_password: str = Form(default=""),
):
    """Super admin: Yeni partner oluştur - otomatik kendi firma paneli + opsiyonel ilk admin"""
    if not _is_super_admin(request):
        return RedirectResponse(url="/admin?error=Oturum%20gecersiz.%20Lutfen%20tekrar%20giris%20yapin.", status_code=302)
    try:
        name = (name or "").strip()
        slug = (slug or "").strip().lower()[:80]
        slug = "".join(c for c in slug if c.isalnum() or c in "-_") if slug else ""
        admin_email = (admin_email or "").strip().lower() if admin_email else ""
        admin_password = (admin_password or "").strip() if admin_password else ""
        if not name:
            return RedirectResponse(url="/admin/super?error=Partner%20adi%20gerekli", status_code=302)
        if not slug:
            slug = "".join(c for c in name.lower() if c.isalnum() or c in " -_").replace(" ", "-")[:80] or "partner"
        if admin_email and len(admin_password) < 6:
            return RedirectResponse(url="/admin/super?error=Admin%20sifresi%20en%20az%206%20karakter", status_code=302)
        tenant_slug = None
        created_admin = False
        async with AsyncSessionLocal() as db:
            r = await db.execute(select(Partner).where(Partner.slug == slug))
            if r.scalar_one_or_none():
                return RedirectResponse(url="/admin/super?error=Bu%20slug%20zaten%20var", status_code=302)
            partner = Partner(name=name, slug=slug)
            db.add(partner)
            await db.flush()
            tenant_slug = f"{slug}-panel"
            for attempt in range(100):
                candidate = tenant_slug if attempt == 0 else f"{slug}-panel-{partner.id}-{attempt}"
                r = await db.execute(select(Tenant).where(Tenant.slug == candidate))
                if r.scalar_one_or_none() is None:
                    tenant_slug = candidate
                    break
            else:
                tenant_slug = f"{slug}-panel-{partner.id}-{uuid.uuid4().hex[:8]}"
            products_path = f"data/tenants/{tenant_slug}/products.json"
            default_tenant = Tenant(
                name=name,
                slug=tenant_slug,
                website_url="https://example.com",
                sector="genel",
                products_path=products_path,
                partner_id=partner.id,
                status="active",
            )
            db.add(default_tenant)
            await db.flush()
            partner.settings = json.dumps({"default_tenant_id": default_tenant.id})
            if admin_email and "@" in admin_email and len(admin_password) >= 6:
                r = await db.execute(select(User).where(User.email == admin_email))
                if r.scalar_one_or_none():
                    await db.commit()
                    return RedirectResponse(url="/admin/super?error=Bu%20e-posta%20zaten%20kayitli", status_code=302)
                import bcrypt
                user = User(
                    tenant_id=None,
                    partner_id=partner.id,
                    is_partner_admin=True,
                    name=admin_email.split("@")[0],
                    email=admin_email,
                    password_hash=bcrypt.hashpw(admin_password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8"),
                    role="admin",
                )
                db.add(user)
                created_admin = True
            await db.commit()
        base = Path(__file__).resolve().parent.parent
        products_dir = base / "data" / "tenants" / tenant_slug
        products_dir.mkdir(parents=True, exist_ok=True)
        products_file = products_dir / "products.json"
        if not products_file.exists():
            products_file.write_text("[]", encoding="utf-8")
        q = "partner_created=1&with_admin=1" if created_admin else "partner_created=1"
        return RedirectResponse(url="/admin/super?" + q, status_code=302)
    except Exception as e:
        import traceback
        from urllib.parse import quote
        err = str(e)[:80] if str(e) else "Bilinmeyen hata"
        return RedirectResponse(url="/admin/super?error=" + quote(f"Hata: {err}"), status_code=302)


@router.post("/super/tenants/{tid}/delete")
async def super_admin_delete_tenant(request: Request, tid: int):
    """Super admin: Firmayı sil (soft delete - status=deleted)"""
    if not _is_super_admin(request):
        return RedirectResponse(url="/admin?error=Oturum%20gecersiz.%20Lutfen%20tekrar%20giris%20yapin.", status_code=302)
    async with AsyncSessionLocal() as db:
        r = await db.execute(select(Tenant).where(Tenant.id == tid))
        tenant = r.scalar_one_or_none()
        if not tenant:
            raise HTTPException(404)
        tenant.status = "deleted"
        await db.commit()
    return RedirectResponse(url="/admin/super?tenant_deleted=1", status_code=302)


@router.post("/super/tenants/{tid}/partner")
async def super_admin_assign_tenant_partner(request: Request, tid: int, partner_id: str = Form("")):
    """Super admin: Firmayı partner'a ata"""
    if not _is_super_admin(request):
        return RedirectResponse(url="/admin?error=Oturum%20gecersiz.%20Lutfen%20tekrar%20giris%20yapin.", status_code=302)
    pid = None
    try:
        pid = int(partner_id) if partner_id else None
    except ValueError:
        pid = None
    async with AsyncSessionLocal() as db:
        r = await db.execute(select(Tenant).where(Tenant.id == tid))
        tenant = r.scalar_one_or_none()
        if not tenant:
            raise HTTPException(404)
        tenant.partner_id = pid
        await db.commit()
    return RedirectResponse(url="/admin/super?assigned=1", status_code=302)


@router.post("/super/partners/{pid}/delete")
async def super_admin_delete_partner(request: Request, pid: int):
    """Super admin: Partner sil - tenant'lar partner'dan çıkar, partner admin kullanıcılar sıfırlanır"""
    if not _is_super_admin(request):
        return RedirectResponse(url="/admin?error=Oturum%20gecersiz.%20Lutfen%20tekrar%20giris%20yapin.", status_code=302)
    async with AsyncSessionLocal() as db:
        r = await db.execute(select(Partner).where(Partner.id == pid))
        partner = r.scalar_one_or_none()
        if not partner:
            raise HTTPException(404)
        await db.execute(update(Tenant).where(Tenant.partner_id == pid).values(partner_id=None))
        await db.execute(update(User).where(User.partner_id == pid).values(partner_id=None, is_partner_admin=False))
        await db.delete(partner)
        await db.commit()
    return RedirectResponse(url="/admin/super?partner_deleted=1", status_code=302)


@router.post("/super/partners/{pid}/admin-user")
async def super_admin_create_partner_admin(
    request: Request, pid: int,
    email: str = Form(""), password: str = Form(""),
    new_email: str = Form(""),
):
    """Super admin: Partner için admin ekle veya mevcut admin'in e-posta/şifresini güncelle"""
    if not _is_super_admin(request):
        return RedirectResponse(url="/admin?error=Oturum%20gecersiz.%20Lutfen%20tekrar%20giris%20yapin.", status_code=302)
    email = (email or "").strip().lower()
    password = (password or "").strip()
    new_email = (new_email or "").strip().lower() or None
    if not email or "@" not in email:
        return RedirectResponse(url="/admin/super?error=Gecerli%20e-posta%20gerekli", status_code=302)
    if len(password) < 6:
        return RedirectResponse(url="/admin/super?error=Sifre%20en%20az%206%20karakter", status_code=302)
    if new_email and (new_email == email or "@" not in new_email):
        new_email = None
    import bcrypt
    async with AsyncSessionLocal() as db:
        r = await db.execute(select(Partner).where(Partner.id == pid))
        partner = r.scalar_one_or_none()
        if not partner:
            raise HTTPException(404)
        r = await db.execute(select(User).where(User.email == email))
        existing = r.scalar_one_or_none()
        if existing:
            if existing.partner_id != pid:
                return RedirectResponse(url="/admin/super?error=Bu%20e-posta%20baska%20bir%20hesapla%20kayitli", status_code=302)
            existing.password_hash = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
            if new_email:
                r2 = await db.execute(select(User).where(User.email == new_email))
                if r2.scalar_one_or_none():
                    return RedirectResponse(url="/admin/super?error=Yeni%20e-posta%20zaten%20kullaniliyor", status_code=302)
                existing.email = new_email
                existing.name = new_email.split("@")[0]
            await db.commit()
            return RedirectResponse(url="/admin/super?partner_admin_updated=1", status_code=302)
        r = await db.execute(select(User).where(User.email == email))
        if r.scalar_one_or_none():
            return RedirectResponse(url="/admin/super?error=Bu%20e-posta%20zaten%20kayitli", status_code=302)
        user = User(
            tenant_id=None,
            partner_id=pid,
            is_partner_admin=True,
            name=email.split("@")[0],
            email=email,
            password_hash=bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8"),
            role="admin",
        )
        db.add(user)
        await db.commit()
    return RedirectResponse(url="/admin/super?partner_admin_created=1", status_code=302)


@router.post("/super/enter/{id}")
async def super_admin_enter(request: Request, id: int):
    """Super admin: Firmaya gir, dashboard veya next_url'e yönlendir"""
    if not _is_super_admin(request):
        return RedirectResponse(url="/admin?error=Oturum%20gecersiz.%20Lutfen%20tekrar%20giris%20yapin.", status_code=302)
    form = await request.form()
    next_url = (form.get("next_url") or "").strip()
    request.session["tenant_id"] = id
    if next_url and next_url.startswith("/admin"):
        return RedirectResponse(url=next_url, status_code=302)
    return RedirectResponse(url="/admin/dashboard", status_code=302)


@router.get("/super/modules/{id}", response_class=HTMLResponse)
async def super_admin_modules(request: Request, id: int):
    """Super admin: Firma modüllerini yönet"""
    if _session_get(request, "admin") != "ok" or not _session_get(request, "super_admin"):
        return RedirectResponse(url="/admin", status_code=302)
    from services.core.modules import AVAILABLE_MODULES
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Tenant).where(Tenant.id == id))
        tenant = result.scalar_one_or_none()
    if not tenant:
        raise HTTPException(404, detail="Firma bulunamadı")
    enabled = _parse_enabled_modules(tenant.enabled_modules)
    use_all = len(enabled) == 0
    return templates.TemplateResponse("super_admin_modules.html", {
        "request": request,
        "tenant": tenant,
        "modules": AVAILABLE_MODULES,
        "enabled": enabled,
        "use_all": use_all,
    })


@router.post("/super/modules/{id}")
async def super_admin_modules_save(request: Request, id: int):
    """Super admin: Firma modüllerini kaydet (bağımlılık kontrolü ile)"""
    if not _is_super_admin(request):
        return RedirectResponse(url="/admin?error=Oturum%20gecersiz.%20Lutfen%20tekrar%20giris%20yapin.", status_code=302)
    form = await request.form()
    use_all = form.get("use_all") == "1"
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Tenant).where(Tenant.id == id))
        tenant = result.scalar_one_or_none()
        if not tenant:
            raise HTTPException(404)
        if use_all:
            tenant.enabled_modules = None
        else:
            from services.core.modules import AVAILABLE_MODULES, check_module_dependencies
            valid_ids = {m["id"] for m in AVAILABLE_MODULES}
            selected = [k.replace("mod_", "") for k in form.keys() if k.startswith("mod_") and k.replace("mod_", "") in valid_ids]
            enabled_set = set(selected)
            for mid in selected:
                ok, warnings = check_module_dependencies(mid, enabled_set, enabling=True)
                if not ok:
                    msg = " ".join(warnings)
                    return templates.TemplateResponse("super_admin_modules.html", {
                        "request": request,
                        "tenant": tenant,
                        "modules": AVAILABLE_MODULES,
                        "enabled": enabled_set,
                        "use_all": False,
                        "error": msg,
                    }, status_code=400)
            if "orders" not in selected and "payment" in selected:
                selected = [m for m in selected if m != "payment"]
            tenant.enabled_modules = json.dumps(selected) if selected else None
        await db.commit()
    return RedirectResponse(url=f"/admin/super/modules/{id}?saved=1", status_code=302)
