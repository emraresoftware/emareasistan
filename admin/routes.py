"""
Yönetim paneli - Kurallar, sohbetler, müşteri detayları
"""
import csv
import io
import json
import uuid
import base64
import re
import smtplib
from datetime import datetime, timedelta
from pathlib import Path
from email.mime.text import MIMEText
from email.utils import formataddr

from fastapi import APIRouter, Request, Depends, HTTPException, Form, UploadFile, File
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select, desc, func
from sqlalchemy.ext.asyncio import AsyncSession
import httpx

from config import get_settings
from models.database import AsyncSessionLocal, get_db
from models import Conversation, Message, Order, ImageAlbum, User, WhatsAppConnection, Contact, Reminder, Tenant, Partner, PendingRegistration, Video, MessageFeedback, Appointment, LeaveRequest, Invoice, PurchaseOrder, AuditLog, ExportTemplate, TenantWorkflow, WorkflowStep, ProcessConfig

from admin.common import (
    templates,
    _to_turkey_str,
    _utc_to_iso,
    _session_get,
    _is_super_admin,
    check_admin,
    get_tenant_id,
    _request_client_ip,
    _is_truthy,
)
from admin.routes_auth import router as auth_router
from admin.routes_dashboard import router as dashboard_router
from admin.routes_settings import router as settings_router
from admin.routes_rules_workflows import router as rules_workflows_router
from admin.routes_orders import router as orders_router
from admin.routes_agent import router as agent_router
from admin.routes_partner_super import router as partner_super_router
from admin.routes_trendyol import router as trendyol_router
from admin import helpers

router = APIRouter(prefix="/admin", tags=["admin"])
router.include_router(auth_router)
router.include_router(dashboard_router)
router.include_router(settings_router)
router.include_router(rules_workflows_router)
router.include_router(orders_router)
router.include_router(agent_router)
router.include_router(partner_super_router)
router.include_router(trendyol_router)

# Kısayollar (routes.py içinde hâlâ kullanılanlar)
get_enabled_modules_for_request = helpers.get_enabled_modules_for_request
require_module = helpers.require_module
_compute_local_routing_metrics = helpers._compute_local_routing_metrics
_suggest_local_conf_threshold = helpers._suggest_local_conf_threshold
SLA_RESPONSE_MINUTES = helpers.SLA_RESPONSE_MINUTES
SLA_AUTO_AGENT_NAME = helpers.SLA_AUTO_AGENT_NAME
_conversation_sla_state = helpers._conversation_sla_state
_should_send_sla_alert = helpers._should_send_sla_alert
_notify_sla_auto_takeover = helpers._notify_sla_auto_takeover
_norm_phone_for_match = helpers._norm_phone_for_match
_audit_from_request = helpers._audit_from_request
PAGE_SIZE = helpers.PAGE_SIZE



# --- Resim Albümleri ---
@router.get("/albums", response_class=HTMLResponse)
async def albums_list(request: Request):
    """Albümler listeler. [GET /albums]"""
    if request.session.get("admin") != "ok":
        return RedirectResponse(url="/admin", status_code=302)
    tid = get_tenant_id(request)
    page = max(1, int(request.query_params.get("page") or 1))
    async with AsyncSessionLocal() as db:
        count_q = select(func.count(ImageAlbum.id)).where(ImageAlbum.tenant_id == tid)
        total = (await db.execute(count_q)).scalar() or 0
        result = await db.execute(
            select(ImageAlbum)
            .where(ImageAlbum.tenant_id == tid)
            .order_by(desc(ImageAlbum.priority), ImageAlbum.id)
            .offset((page - 1) * PAGE_SIZE)
            .limit(PAGE_SIZE)
        )
        albums = result.scalars().all()
    for a in albums:
        try:
            a._image_count = len(json.loads(a.image_urls or "[]"))
        except json.JSONDecodeError:
            a._image_count = 0
    total_pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)
    return templates.TemplateResponse("albums.html", {
        "request": request,
        "albums": albums,
        "page": page,
        "total_pages": total_pages,
        "total": total,
    })


@router.get("/albums/new", response_class=HTMLResponse)
async def album_new(request: Request):
    """Albüm yeni oluşturma formu. [GET /albums/new]"""
    if request.session.get("admin") != "ok":
        return RedirectResponse(url="/admin", status_code=302)
    from services.product.vehicles import get_brands
    return templates.TemplateResponse("album_form.html", {
        "request": request,
        "album": None,
        "album_urls_display": "",
        "brands": get_brands(),
    })


@router.get("/albums/{id}", response_class=HTMLResponse)
async def album_edit(request: Request, id: int):
    """Albüm düzenleme formu. [GET /albums/{id}]"""
    if request.session.get("admin") != "ok":
        return RedirectResponse(url="/admin", status_code=302)
    tid = get_tenant_id(request)
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(ImageAlbum).where(ImageAlbum.id == id, ImageAlbum.tenant_id == tid))
        album = result.scalar_one_or_none()
    if not album:
        raise HTTPException(404)
    try:
        album_urls_display = "\n".join(json.loads(album.image_urls or "[]"))
    except json.JSONDecodeError:
        album_urls_display = album.image_urls or ""
    from services.product.vehicles import get_brands
    return templates.TemplateResponse("album_form.html", {
        "request": request,
        "album": album,
        "album_urls_display": album_urls_display,
        "brands": get_brands(),
    })


@router.post("/albums/save")
async def album_save(
    request: Request,
    id: str = Form(""),
    name: str = Form(""),
    image_urls: str = Form(""),
    vehicle_models: str = Form(""),
    custom_message: str = Form(""),
    is_active: str = Form(""),
    priority: int = Form(0),
):
    """Albüm kaydeder. [POST /albums/save]"""
    if request.session.get("admin") != "ok":
        raise HTTPException(401)
    album_id = int(id) if id and id.isdigit() else None
    urls_list = [u.strip() for u in image_urls.split("\n") if u.strip() and u.strip().startswith("http")]
    image_urls_json = json.dumps(urls_list, ensure_ascii=False)
    tid = get_tenant_id(request)
    async with AsyncSessionLocal() as db:
        if album_id:
            result = await db.execute(select(ImageAlbum).where(ImageAlbum.id == album_id, ImageAlbum.tenant_id == tid))
            album = result.scalar_one_or_none()
            if not album:
                raise HTTPException(404)
        else:
            album = ImageAlbum(tenant_id=get_tenant_id(request))
            db.add(album)
        album.name = name
        album.image_urls = image_urls_json
        album.vehicle_models = (vehicle_models or "").strip()
        album.custom_message = custom_message
        album.is_active = (is_active == "on")
        album.priority = priority
        await db.commit()
    return RedirectResponse(url="/admin/albums", status_code=302)


@router.post("/albums/{id}/delete")
async def album_delete(request: Request, id: int):
    """Albüm siler. [POST /albums/{id}/delete]"""
    if request.session.get("admin") != "ok":
        raise HTTPException(401)
    tid = get_tenant_id(request)
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(ImageAlbum).where(ImageAlbum.id == id, ImageAlbum.tenant_id == tid))
        album = result.scalar_one_or_none()
        if album:
            await db.delete(album)
            await db.commit()
    return RedirectResponse(url="/admin/albums", status_code=302)


def _get_uploads_dir(tid: int) -> Path:
    """Albüm resimleri klasörü - tenant bazlı"""
    d = Path(__file__).resolve().parent.parent / "uploads" / "albums" / str(tid)
    d.mkdir(parents=True, exist_ok=True)
    return d


def _safe_filename(name: str) -> str:
    """Güvenli dosya adı oluştur"""
    ext = Path(name).suffix.lower() or ".jpg"
    if ext not in (".jpg", ".jpeg", ".png", ".gif", ".webp"):
        ext = ".jpg"
    return f"{uuid.uuid4().hex[:12]}{ext}"


@router.post("/albums/upload")
async def album_upload(request: Request, files: list[UploadFile] = File(...)):
    """Resim yükle - tenant bazlı uploads/albums/{tid}/ klasörüne"""
    if request.session.get("admin") != "ok":
        raise HTTPException(401)
    tid = get_tenant_id(request)
    uploads_dir = _get_uploads_dir(tid)
    base_url = str(request.base_url).rstrip("/")
    urls = []
    for f in files:
        if not f.content_type or not f.content_type.startswith("image/"):
            continue
        filename = _safe_filename(f.filename or "image.jpg")
        path = uploads_dir / filename
        content = await f.read()
        path.write_bytes(content)
        urls.append(f"{base_url}/uploads/albums/{tid}/{filename}")
    return JSONResponse({"urls": urls})


@router.get("/api/album-images")
async def api_album_images(request: Request):
    """Tenant'ın uploads/albums/{tid}/ klasöründeki resimleri listele"""
    if request.session.get("admin") != "ok":
        raise HTTPException(401)
    tid = get_tenant_id(request)
    uploads_dir = _get_uploads_dir(tid)
    base_url = str(request.base_url).rstrip("/")
    images = []
    ext_ok = {".jpg", ".jpeg", ".png", ".gif", ".webp"}
    if uploads_dir.exists():
        for f in sorted(uploads_dir.iterdir(), key=lambda x: x.stat().st_mtime, reverse=True):
            if f.is_file() and f.suffix.lower() in ext_ok:
                images.append({
                    "url": f"{base_url}/uploads/albums/{tid}/{f.name}",
                    "name": f.name,
                })
    return images


# --- Videolar ---
def _get_videos_uploads_dir(tid: int) -> Path:
    """Video upload klasörü - tenant bazlı"""
    d = Path(__file__).resolve().parent.parent / "uploads" / "videos" / str(tid)
    d.mkdir(parents=True, exist_ok=True)
    return d


def _safe_video_filename(name: str) -> str:
    ext = Path(name).suffix.lower() or ".mp4"
    if ext not in (".mp4", ".webm", ".mov", ".avi"):
        ext = ".mp4"
    return f"{uuid.uuid4().hex[:12]}{ext}"


@router.get("/videos", response_class=HTMLResponse)
async def videos_list(request: Request):
    """Videolar listeler. [GET /videos]"""
    if request.session.get("admin") != "ok":
        return RedirectResponse(url="/admin", status_code=302)
    tid = get_tenant_id(request)
    page = max(1, int(request.query_params.get("page") or 1))
    async with AsyncSessionLocal() as db:
        count_q = select(func.count(Video.id)).where(Video.tenant_id == tid)
        total = (await db.execute(count_q)).scalar() or 0
        result = await db.execute(
            select(Video).where(Video.tenant_id == tid).order_by(desc(Video.id)).offset((page - 1) * PAGE_SIZE).limit(PAGE_SIZE)
        )
        videos = result.scalars().all()
    total_pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)
    return templates.TemplateResponse("videos_list.html", {
        "request": request,
        "videos": videos,
        "page": page,
        "total_pages": total_pages,
        "total": total,
    })


@router.get("/videos/new", response_class=HTMLResponse)
async def video_new(request: Request):
    """Video yeni oluşturma formu. [GET /videos/new]"""
    if request.session.get("admin") != "ok":
        return RedirectResponse(url="/admin", status_code=302)
    from services.product.vehicles import get_brands
    return templates.TemplateResponse("video_form.html", {"request": request, "video": None, "brands": get_brands()})


@router.get("/videos/{id}", response_class=HTMLResponse)
async def video_edit(request: Request, id: int):
    """Video düzenleme formu. [GET /videos/{id}]"""
    if request.session.get("admin") != "ok":
        return RedirectResponse(url="/admin", status_code=302)
    tid = get_tenant_id(request)
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Video).where(Video.id == id, Video.tenant_id == tid))
        video = result.scalar_one_or_none()
    if not video:
        raise HTTPException(404)
    from services.product.vehicles import get_brands
    return templates.TemplateResponse("video_form.html", {"request": request, "video": video, "brands": get_brands()})


@router.post("/videos/save")
async def video_save(
    request: Request,
    id: str = Form(""),
    name: str = Form(""),
    trigger_keyword: str = Form(""),
    vehicle_models: str = Form(""),
    video_url: str = Form(""),
    caption: str = Form(""),
    is_active: str = Form(""),
    priority: int = Form(0),
):
    """Video kaydeder. [POST /videos/save]"""
    if request.session.get("admin") != "ok":
        raise HTTPException(401)
    if not trigger_keyword.strip() or not video_url.strip():
        raise HTTPException(400, detail="Tetikleyici ve video URL gerekli")
    vid_id = int(id) if id and id.isdigit() else None
    tid = get_tenant_id(request)
    async with AsyncSessionLocal() as db:
        if vid_id:
            result = await db.execute(select(Video).where(Video.id == vid_id, Video.tenant_id == tid))
            video = result.scalar_one_or_none()
            if not video:
                raise HTTPException(404)
        else:
            video = Video(tenant_id=tid)
            db.add(video)
        video.name = name.strip() or trigger_keyword.strip()
        video.trigger_keyword = trigger_keyword.strip().lower()
        video.vehicle_models = (vehicle_models or "").strip() or None
        video.video_url = video_url.strip()
        video.caption = caption.strip() or None
        video.is_active = (is_active == "on")
        video.priority = priority
        await db.commit()
    return RedirectResponse(url="/admin/videos", status_code=302)


@router.post("/videos/upload")
async def video_upload(request: Request, file: UploadFile = File(...)):
    """Video yükle - tenant bazlı uploads/videos/{tid}/ klasörüne"""
    if request.session.get("admin") != "ok":
        raise HTTPException(401)
    tid = get_tenant_id(request)
    uploads_dir = _get_videos_uploads_dir(tid)
    base_url = str(request.base_url).rstrip("/")
    ct = (file.content_type or "").lower()
    if not any(t in ct for t in ["video", "octet-stream"]):
        raise HTTPException(400, detail="Sadece video dosyası yüklenebilir")
    filename = _safe_video_filename(file.filename or "video.mp4")
    path = uploads_dir / filename
    content = await file.read()
    if len(content) > 100 * 1024 * 1024:  # 100MB
        raise HTTPException(400, detail="Video en fazla 100MB olabilir")
    path.write_bytes(content)
    return JSONResponse({"url": f"{base_url}/uploads/videos/{tid}/{filename}"})


@router.post("/videos/{id}/delete")
async def video_delete(request: Request, id: int):
    """Video siler. [POST /videos/{id}/delete]"""
    if request.session.get("admin") != "ok":
        raise HTTPException(401)
    tid = get_tenant_id(request)
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Video).where(Video.id == id, Video.tenant_id == tid))
        video = result.scalar_one_or_none()
        if video:
            await db.delete(video)
            await db.commit()
    return RedirectResponse(url="/admin/videos", status_code=302)


# --- Sohbetler ---
async def _delete_conversations_by_ids(db: AsyncSession, tenant_id: int, conv_ids: list[int]) -> int:
    """Sohbetleri ve bagli mesaj/reminder/randevu kayitlarini temizle."""
    ids = [int(x) for x in conv_ids if str(x).isdigit()]
    if not ids:
        return 0

    # Guvenlik: sadece bu tenant'a ait sohbet id'leri uzerinde islem yap.
    allowed_rows = await db.execute(
        select(Conversation.id).where(Conversation.tenant_id == tenant_id, Conversation.id.in_(ids))
    )
    allowed_ids = [int(x) for x in allowed_rows.scalars().all()]
    if not allowed_ids:
        return 0

    # Mesaj geri bildirimleri -> mesajlar
    msg_result = await db.execute(select(Message.id).where(Message.conversation_id.in_(allowed_ids)))
    msg_ids = [int(x) for x in msg_result.scalars().all()]
    if msg_ids:
        fb_result = await db.execute(select(MessageFeedback).where(MessageFeedback.message_id.in_(msg_ids)))
        for fb in fb_result.scalars().all():
            await db.delete(fb)

    msg_rows = await db.execute(select(Message).where(Message.conversation_id.in_(allowed_ids)))
    for m in msg_rows.scalars().all():
        await db.delete(m)

    rem_rows = await db.execute(
        select(Reminder).where(Reminder.tenant_id == tenant_id, Reminder.conversation_id.in_(allowed_ids))
    )
    for r in rem_rows.scalars().all():
        await db.delete(r)

    apt_rows = await db.execute(
        select(Appointment).where(Appointment.tenant_id == tenant_id, Appointment.conversation_id.in_(allowed_ids))
    )
    for a in apt_rows.scalars().all():
        await db.delete(a)

    # Siparisleri koru, sadece sohbet bagini kaldir.
    ord_rows = await db.execute(
        select(Order).where(Order.tenant_id == tenant_id, Order.conversation_id.in_(allowed_ids))
    )
    for o in ord_rows.scalars().all():
        o.conversation_id = None

    conv_rows = await db.execute(
        select(Conversation).where(Conversation.tenant_id == tenant_id, Conversation.id.in_(allowed_ids))
    )
    conv_list = conv_rows.scalars().all()
    for c in conv_list:
        await db.delete(c)

    await db.commit()
    return len(conv_list)


@router.get("/conversations", response_class=HTMLResponse)
async def conversations_list(request: Request):
    """Sohbetler listeler. [GET /conversations]"""
    if request.session.get("admin") != "ok":
        return RedirectResponse(url="/admin", status_code=302)
    page = max(1, int(request.query_params.get("page", 1)))
    platform_filter = request.query_params.get("platform", "").strip()
    search_q = request.query_params.get("q", "").strip()
    cleared = max(0, int(request.query_params.get("cleared", 0)))
    tid = get_tenant_id(request)
    async with AsyncSessionLocal() as db:
        from sqlalchemy import or_
        base_q = select(Conversation).where(Conversation.tenant_id == tid).order_by(
            desc(func.coalesce(Conversation.last_message_at, Conversation.created_at))
        )
        count_q = select(func.count(Conversation.id)).where(Conversation.tenant_id == tid)
        if platform_filter:
            base_q = base_q.where(Conversation.platform == platform_filter)
            count_q = count_q.where(Conversation.platform == platform_filter)
        if search_q:
            flt = or_(
                Conversation.customer_name.ilike(f"%{search_q}%"),
                Conversation.customer_phone.ilike(f"%{search_q}%"),
                Conversation.platform_user_id.ilike(f"%{search_q}%"),
            )
            base_q = base_q.where(flt)
            count_q = count_q.where(flt)
        total = (await db.execute(count_q)).scalar() or 0
        result = await db.execute(base_q.offset((page - 1) * PAGE_SIZE).limit(PAGE_SIZE))
        conversations = result.scalars().all()
        conv_ids = [c.id for c in conversations]
        # Son mesaj önizlemesi - her sohbet için son mesaj
        last_previews = {}
        order_links = {}
        if conv_ids:
            subq = select(
                Message.conversation_id,
                Message.content,
                Message.role,
                Message.created_at,
            ).where(Message.conversation_id.in_(conv_ids))
            msg_result = await db.execute(subq.order_by(Message.created_at))
            all_msgs = msg_result.all()
            for m in reversed(all_msgs):
                if m.conversation_id not in last_previews:
                    content = (m.content or "").replace("\n[Ürün resimleri gönderildi]", "").strip()
                    last_previews[m.conversation_id] = (content[:60] + "…") if len(content) > 60 else content
            ord_result = await db.execute(
                select(Order.conversation_id, Order.id, Order.order_number)
                .where(Order.conversation_id.in_(conv_ids))
                .order_by(desc(Order.created_at))
            )
            for row in ord_result.all():
                if row.conversation_id not in order_links:
                    order_links[row.conversation_id] = {"id": row.id, "order_number": row.order_number}
    for c in conversations:
        c.last_message_preview = last_previews.get(c.id, "-")
        c.order_info = order_links.get(c.id)
    total_pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)
    return templates.TemplateResponse("conversations.html", {
        "request": request,
        "conversations": conversations,
        "page": page,
        "total_pages": total_pages,
        "total": total,
        "platform_filter": platform_filter,
        "search_q": search_q,
        "cleared": cleared,
    })


@router.get("/conversations/export")
async def conversations_export(
    request: Request,
    ids: str = "",
    scope: str = "",
    format: str = "csv",
    page: int = 1,
    platform: str = "",
    q: str = "",
):
    """Sohbet mesajlarını indir - CSV veya TXT. ids=1,2,3 veya scope=page|filtered"""
    if request.session.get("admin") != "ok":
        raise HTTPException(401)
    tid = get_tenant_id(request)
    conv_ids: list[int] = []

    async with AsyncSessionLocal() as db:
        from sqlalchemy import or_
        base_q = select(Conversation.id).where(Conversation.tenant_id == tid).order_by(
            desc(func.coalesce(Conversation.last_message_at, Conversation.created_at))
        )
        if ids:
            try:
                conv_ids = [int(x.strip()) for x in ids.split(",") if x.strip()]
            except ValueError:
                conv_ids = []
        elif scope in ("page", "filtered"):
            if platform:
                base_q = base_q.where(Conversation.platform == platform)
            if q:
                flt = or_(
                    Conversation.customer_name.ilike(f"%{q}%"),
                    Conversation.customer_phone.ilike(f"%{q}%"),
                    Conversation.platform_user_id.ilike(f"%{q}%"),
                )
                base_q = base_q.where(flt)
            if scope == "page":
                base_q = base_q.offset((page - 1) * PAGE_SIZE).limit(PAGE_SIZE)
            id_result = await db.execute(base_q)
            conv_ids = [int(x) for x in id_result.scalars().all()]

        if not conv_ids:
            raise HTTPException(400, detail="İndirilecek sohbet seçin veya scope belirtin")

        # Tenant kontrolü - sadece kendi sohbetleri
        check = await db.execute(
            select(Conversation.id).where(
                Conversation.id.in_(conv_ids),
                Conversation.tenant_id == tid,
            )
        )
        allowed_ids = [int(r) for r in check.scalars().all()]
        if not allowed_ids:
            raise HTTPException(403)

        # Sohbet + mesajları getir
        conv_result = await db.execute(
            select(Conversation).where(Conversation.id.in_(allowed_ids))
        )
        convs = {c.id: c for c in conv_result.scalars().all()}
        msg_result = await db.execute(
            select(Message)
            .where(Message.conversation_id.in_(allowed_ids))
            .order_by(Message.conversation_id, Message.created_at)
        )
        messages = msg_result.scalars().all()

    fmt = (format or "csv").lower()
    if fmt not in ("csv", "txt"):
        fmt = "csv"

    def _clean_content(t: str) -> str:
        return (t or "").replace("\n[Ürün resimleri gönderildi]", "").replace("[Ürün resimleri gönderildi]", "").strip()

    if fmt == "csv":
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["Sohbet ID", "Platform", "Müşteri", "Telefon", "Rol", "Mesaj", "Tarih"])
        for m in messages:
            c = convs.get(m.conversation_id)
            writer.writerow([
                m.conversation_id,
                c.platform if c else "",
                c.customer_name or c.platform_user_id if c else "",
                c.customer_phone if c else "",
                "Müşteri" if m.role == "user" else "Asistan",
                _clean_content(m.content),
                m.created_at.strftime("%Y-%m-%d %H:%M") if m.created_at else "",
            ])
        content = output.getvalue()
        # Excel UTF-8 BOM
        body = "\ufeff" + content
        filename = f"sohbetler_{datetime.utcnow().strftime('%Y%m%d_%H%M')}.csv"
        media_type = "text/csv; charset=utf-8"
    else:
        lines = []
        for cid in allowed_ids:
            c = convs.get(cid)
            header = f"=== Sohbet #{cid} | {c.platform if c else '-'} | {c.customer_name or c.platform_user_id or '-'} | {c.customer_phone or '-'} ==="
            lines.append(header)
            for m in messages:
                if m.conversation_id != cid:
                    continue
                role = "Müşteri" if m.role == "user" else "Asistan"
                dt = m.created_at.strftime("%d.%m.%Y %H:%M") if m.created_at else ""
                lines.append(f"[{dt}] {role}: {_clean_content(m.content)}")
            lines.append("")
        body = "\n".join(lines)
        filename = f"sohbetler_{datetime.utcnow().strftime('%Y%m%d_%H%M')}.txt"
        media_type = "text/plain; charset=utf-8"

    return StreamingResponse(
        iter([body.encode("utf-8")]),
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/conversations/clear")
async def conversations_clear(request: Request):
    """Filtreye gore sohbetleri toplu temizle."""
    if request.session.get("admin") != "ok":
        raise HTTPException(401)
    form = await request.form()
    platform_filter = (form.get("platform") or "").strip()
    search_q = (form.get("q") or "").strip()
    scope = (form.get("scope") or "filtered").strip().lower()
    page = max(1, int(form.get("page") or 1))
    tid = get_tenant_id(request)

    async with AsyncSessionLocal() as db:
        from sqlalchemy import or_
        base_q = select(Conversation.id).where(Conversation.tenant_id == tid).order_by(
            desc(func.coalesce(Conversation.last_message_at, Conversation.created_at))
        )
        if platform_filter:
            base_q = base_q.where(Conversation.platform == platform_filter)
        if search_q:
            flt = or_(
                Conversation.customer_name.ilike(f"%{search_q}%"),
                Conversation.customer_phone.ilike(f"%{search_q}%"),
                Conversation.platform_user_id.ilike(f"%{search_q}%"),
            )
            base_q = base_q.where(flt)
        if scope == "page":
            base_q = base_q.offset((page - 1) * PAGE_SIZE).limit(PAGE_SIZE)
        id_result = await db.execute(base_q)
        conv_ids = [int(x) for x in id_result.scalars().all()]
        cleared = await _delete_conversations_by_ids(db, tid, conv_ids)

    from urllib.parse import quote
    qs = []
    if search_q:
        qs.append(f"q={quote(search_q, safe='')}")
    if platform_filter:
        qs.append(f"platform={quote(platform_filter, safe='')}")
    qs.append(f"page={page}")
    qs.append(f"cleared={cleared}")
    return RedirectResponse(url=f"/admin/conversations?{'&'.join(qs)}", status_code=302)


@router.post("/conversations/{id}/delete")
async def conversation_delete(request: Request, id: int):
    """Sohbet siler. [POST /conversations/{id}/delete]"""
    if request.session.get("admin") != "ok":
        raise HTTPException(401)
    tid = get_tenant_id(request)
    async with AsyncSessionLocal() as db:
        cleared = await _delete_conversations_by_ids(db, tid, [id])
    return RedirectResponse(url=f"/admin/conversations?cleared={cleared}", status_code=302)


@router.get("/conversations/{id}", response_class=HTMLResponse)
async def conversation_detail(request: Request, id: int):
    """Sohbet detay sayfası. [GET /conversations/{id}]"""
    if request.session.get("admin") != "ok":
        return RedirectResponse(url="/admin", status_code=302)
    tid = get_tenant_id(request)
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Conversation).where(Conversation.id == id, Conversation.tenant_id == tid))
        conv = result.scalar_one_or_none()
        if not conv:
            raise HTTPException(404)
        # Son 500 mesaj (performans: çok uzun sohbetlerde limit)
        result = await db.execute(
            select(Message)
            .where(Message.conversation_id == id)
            .order_by(desc(Message.created_at))
            .limit(500)
        )
        messages = list(reversed(result.scalars().all()))
        msg_ids = [m.id for m in messages if m.role == "assistant"]
        feedback_map = {}
        if msg_ids:
            fb_result = await db.execute(
                select(MessageFeedback).where(MessageFeedback.message_id.in_(msg_ids))
            )
            for fb in fb_result.scalars().all():
                feedback_map[fb.message_id] = fb.feedback
        for m in messages:
            m.feedback = feedback_map.get(m.id)
        order_result = await db.execute(
            select(Order).where(Order.conversation_id == id).order_by(desc(Order.created_at))
        )
        conv_orders = order_result.scalars().all()
    return templates.TemplateResponse("conversation_detail.html", {
        "request": request,
        "conversation": conv,
        "messages": messages,
        "conv_orders": conv_orders,
    })


@router.post("/feedback")
async def message_feedback_post(request: Request, message_id: str = Form(...), feedback: str = Form(...)):
    """Mesaj geri bildirimi - beğen/beğenme"""
    if request.session.get("admin") != "ok":
        raise HTTPException(401)
    if feedback not in ("like", "dislike"):
        raise HTTPException(400, detail="feedback: like veya dislike olmalı")
    try:
        mid = int(message_id)
    except (ValueError, TypeError):
        raise HTTPException(400, detail="Geçersiz mesaj ID")
    tid = get_tenant_id(request)
    async with AsyncSessionLocal() as db:
        msg_result = await db.execute(select(Message).where(Message.id == mid))
        msg = msg_result.scalar_one_or_none()
        if not msg or msg.role != "assistant":
            raise HTTPException(404)
        conv_result = await db.execute(select(Conversation).where(Conversation.id == msg.conversation_id, Conversation.tenant_id == tid))
        if not conv_result.scalar_one_or_none():
            raise HTTPException(404)
        existing = await db.execute(select(MessageFeedback).where(MessageFeedback.message_id == mid))
        fb = existing.scalar_one_or_none()
        if fb:
            fb.feedback = feedback
        else:
            fb = MessageFeedback(message_id=mid, feedback=feedback)
            db.add(fb)
        await db.commit()
    ref = request.headers.get("referer", "/admin/conversations")
    return RedirectResponse(url=ref, status_code=302)


# --- Ürün Yönetimi (JSON) --- tenant bazlı
async def _get_tenant_products_path(tenant_id: int, for_save: bool = False) -> Path:
    """Tenant'ın ürün dosyası yolu"""
    base = Path(__file__).resolve().parent.parent
    if tenant_id == 1:
        if for_save:
            return base / "data" / "products_scraped.json"
        p = base / "data" / "products_scraped.json"
        if not p.exists():
            p = base / "data" / "products_sample.json"
        return p
    async with AsyncSessionLocal() as db:
        r = await db.execute(select(Tenant).where(Tenant.id == tenant_id))
        t = r.scalar_one_or_none()
        if t:
            if t.products_path:
                return base / t.products_path
            # Tenant özel products_path yoksa varsayılan dosyaya düşme;
            # tenant'a özel varsayılan yola yönlendir.
            safe_slug = (t.slug or f"tenant-{tenant_id}").strip().lower()
            safe_slug = "".join(c for c in safe_slug if c.isalnum() or c in "-_") or f"tenant-{tenant_id}"
            return base / "data" / "tenants" / safe_slug / "products.json"
    return base / "data" / "tenants" / f"tenant-{tenant_id}" / "products.json"

async def _load_products(request: Request):
    tid = get_tenant_id(request)
    path = await _get_tenant_products_path(tid)
    if path.exists():
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return []

async def _save_products(request: Request, products: list):
    tid = get_tenant_id(request)
    path = await _get_tenant_products_path(tid, for_save=True)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(products, f, ensure_ascii=False, indent=2)


@router.get("/products", response_class=HTMLResponse)
async def products_list(request: Request):
    """Ürünler listeler. [GET /products]"""
    if request.session.get("admin") != "ok":
        return RedirectResponse(url="/admin", status_code=302)
    products = await _load_products(request)
    for i, p in enumerate(products):
        p["_id"] = i + 1
    # DB'de kaç ürün var?
    from models import Product
    from sqlalchemy import func
    tid = get_tenant_id(request)
    async with AsyncSessionLocal() as db:
        q = select(func.count(Product.id)).where(Product.tenant_id == tid)
        # Tenant 1'de eski global ürün kayıtları için geriye dönük uyumluluk.
        if tid == 1:
            q = select(func.count(Product.id)).where((Product.tenant_id == 1) | (Product.tenant_id.is_(None)))
        db_count = (await db.execute(q)).scalar() or 0
    return templates.TemplateResponse("products.html", {
        "request": request,
        "products": products,
        "db_product_count": db_count,
    })


@router.post("/products/import-to-db")
async def products_import_to_db(request: Request):
    """JSON'dan Products tablosuna aktar - mevcut JSON dosyası kullanılır"""
    if request.session.get("admin") != "ok":
        raise HTTPException(401)
    tid = get_tenant_id(request)
    path = await _get_tenant_products_path(tid)
    if not path.exists():
        raise HTTPException(400, detail="Ürün JSON dosyası bulunamadı")
    try:
        from services.product.importer import import_products_from_json
        async with AsyncSessionLocal() as db:
            count = await import_products_from_json(db, path, tenant_id=tid, clear_existing=True)
        from services.core.cache import invalidate_tenant_cache
        await invalidate_tenant_cache(tid)
    except Exception as e:
        raise HTTPException(500, detail=str(e))
    return RedirectResponse(url=f"/admin/products?imported={count}", status_code=302)


@router.get("/products/gallery", response_class=HTMLResponse)
async def products_gallery(request: Request):
    """Kategorilere göre ürün resimleri galerisi"""
    if request.session.get("admin") != "ok":
        return RedirectResponse(url="/admin", status_code=302)
    products = await _load_products(request)
    category_filter = request.query_params.get("category", "").strip()
    CATEGORY_LABELS = {
        "elit_serisi": "Elit Serisi",
        "ekonom_serisi": "Ekonom Serisi",
        "klas_serisi": "Klas Serisi",
        "modern_serisi": "Modern Serisi",
        "royal_serisi": "Royal Serisi",
        "gt_premium_serisi": "GT Premium Serisi",
        "araca_ozel_tasarim": "Araca Özel Tasarım",
        "7d_zemin_doseme": "7D Zemin Döşeme",
        "oto_paspas_ve_bagaj": "Oto Paspas ve Bagaj",
        "oto_yastik_kolcak_organizer": "Oto Yastık Kolçak ve Organizer",
        "elit_tay_tuyu_serisi": "Elit Tay Tüyü Serisi",
        "genel": "Genel",
    }
    all_categories = sorted(set(p.get("category") or "genel" for p in products))
    if category_filter:
        products = [p for p in products if (p.get("category") or "") == category_filter]
    by_category = {}
    for p in products:
        c = p.get("category") or "genel"
        if c not in by_category:
            by_category[c] = []
        p["_label"] = CATEGORY_LABELS.get(c, c)
        by_category[c].append(p)
    categories = sorted(by_category.keys(), key=lambda x: CATEGORY_LABELS.get(x, x))
    return templates.TemplateResponse("products_gallery.html", {
        "request": request,
        "by_category": by_category,
        "categories": categories,
        "all_categories": all_categories,
        "category_filter": category_filter,
        "category_labels": CATEGORY_LABELS,
    })

@router.get("/products/new", response_class=HTMLResponse)
async def product_new(request: Request):
    """Ürün yeni oluşturma formu. [GET /products/new]"""
    if request.session.get("admin") != "ok":
        return RedirectResponse(url="/admin", status_code=302)
    return templates.TemplateResponse("product_form.html", {"request": request, "product": None})

@router.get("/products/{id}", response_class=HTMLResponse)
async def product_edit(request: Request, id: int):
    """Ürün düzenleme formu. [GET /products/{id}]"""
    if request.session.get("admin") != "ok":
        return RedirectResponse(url="/admin", status_code=302)
    products = await _load_products(request)
    idx = id - 1
    if idx < 0 or idx >= len(products):
        raise HTTPException(404)
    return templates.TemplateResponse("product_form.html", {"request": request, "product": products[idx], "product_id": id})

@router.post("/products/save")
async def product_save(
    request: Request,
    id: str = Form(""),
    name: str = Form(""),
    slug: str = Form(""),
    description: str = Form(""),
    category: str = Form(""),
    price: float = Form(0),
    image_url: str = Form(""),
    external_url: str = Form(""),
):
    """Ürün kaydeder. [POST /products/save]"""
    if request.session.get("admin") != "ok":
        raise HTTPException(401)
    products = await _load_products(request)
    p = {
        "name": name.strip(),
        "slug": (slug or name).strip().lower().replace(" ", "-"),
        "description": (description or "").strip(),
        "category": (category or "").strip(),
        "price": float(price),
        "image_url": (image_url or "").strip() or None,
        "vehicle_compatibility": [],
        "external_url": (external_url or "").strip() or None,
    }
    if id and id.isdigit():
        idx = int(id) - 1
        if 0 <= idx < len(products):
            p["vehicle_compatibility"] = products[idx].get("vehicle_compatibility", [])
            products[idx] = p
        else:
            products.append(p)
    else:
        products.append(p)
    await _save_products(request, products)
    return RedirectResponse(url="/admin/products", status_code=302)

@router.post("/products/{id}/delete")
async def product_delete(request: Request, id: int):
    """Ürün siler. [POST /products/{id}/delete]"""
    if request.session.get("admin") != "ok":
        raise HTTPException(401)
    products = await _load_products(request)
    idx = id - 1
    if 0 <= idx < len(products):
        products.pop(idx)
        await _save_products(request, products)
    return RedirectResponse(url="/admin/products", status_code=302)


# --- API (AJAX) ---
@router.get("/api/vehicle-models")
async def api_vehicle_models(request: Request):
    """Araç modeli listesi - kural formunda tetikleyici önerisi için"""
    if request.session.get("admin") != "ok":
        raise HTTPException(401)
    from services.product.vehicles import get_brands
    return get_brands()


@router.get("/api/products")
async def api_products(request: Request):
    """Ürün listesi - kural formunda kullanılır"""
    if request.session.get("admin") != "ok":
        raise HTTPException(401)
    products = await _load_products(request)
    for i, p in enumerate(products, 1):
        p.setdefault("id", i)
    return products


# --- WhatsApp Hesapları ---
@router.get("/whatsapp/qr/{conn_id}", response_class=HTMLResponse)
async def whatsapp_qr_proxy(request: Request, conn_id: int):
    """QR iframe proxy - bridge HTML/JSON döndürür, proxy geçirir"""
    if request.session.get("admin") != "ok":
        return RedirectResponse(url="/admin", status_code=302)
    bridge_url = get_settings().whatsapp_bridge_url or "http://localhost:3100"
    try:
        import httpx
        async with httpx.AsyncClient(timeout=15.0) as client:
            await client.post(f"{bridge_url}/api/reload")
            r = await client.get(f"{bridge_url}/api/connections/{conn_id}/qr")
        if r.status_code == 200:
            ct = r.headers.get("content-type", "")
            if "json" in ct:
                data = r.json()
                if data.get("error"):
                    err = data.get("error", "")
                    return HTMLResponse(f"""<!DOCTYPE html><html><head><meta charset="utf-8"><title>WhatsApp QR</title></head><body style="font-family:sans-serif;text-align:center;padding:40px;background:#fef2f2;">
                        <h1>⚠️ QR oluşturulamadı</h1>
                        <p style="color:#991b1b;">{err}</p>
                        <p style="font-size:0.9rem;color:#94a3b8;">Bridge'i yeniden başlatın: <code>python run.py</code></p>
                        <p style="font-size:0.9rem;color:#94a3b8;">Sayfa 5 sn'de yenilenecek.</p>
                        <script>setTimeout(()=>location.reload(),5000)</script>
                    </body></html>""")
            return HTMLResponse(r.text)
    except Exception as e:
        pass
    return HTMLResponse("""<!DOCTYPE html><html><head><meta charset="utf-8"></head><body style="font-family:sans-serif;text-align:center;padding:40px;">
        <h1>⚠️ Bridge'e ulaşılamadı</h1>
        <p>WhatsApp Bridge (port 3100) çalışıyor mu? <code>python run.py</code> ile başlatın.</p>
        <script>setTimeout(()=>location.reload(),5000)</script>
    </body></html>""")


@router.get("/whatsapp", response_class=HTMLResponse)
async def whatsapp_list(request: Request):
    """WhatsApp bağlantısı listeler. [GET /whatsapp]"""
    if request.session.get("admin") != "ok":
        return RedirectResponse(url="/admin", status_code=302)
    bridge_url = get_settings().whatsapp_bridge_url or "http://localhost:3100"
    # Tarayıcı QR linki: Docker internal (whatsapp-bridge) veya localhost ise kullanıcının host'unu kullan
    from urllib.parse import urlparse
    bridge_url_browser = bridge_url
    host = urlparse(str(request.base_url)).hostname or "localhost"
    if host and host not in ("localhost", "127.0.0.1") and ("localhost" in bridge_url or "whatsapp-bridge" in bridge_url):
        bridge_url_browser = f"http://{host}:3100"
    bridge_connections = []
    try:
        import httpx
        async with httpx.AsyncClient(timeout=5.0) as client:
            r = await client.get(f"{bridge_url}/api/connections")
            if r.status_code == 200:
                bridge_connections = r.json()
    except Exception:
        pass
    tid = get_tenant_id(request)
    async with AsyncSessionLocal() as db:
        q = select(WhatsAppConnection).where(WhatsAppConnection.is_active == True, WhatsAppConnection.tenant_id == tid)
        q = q.order_by(WhatsAppConnection.id)
        result = await db.execute(q)
        connections = result.scalars().all()
        result = await db.execute(select(User).where(User.is_active == True, User.tenant_id == tid))
        users = result.scalars().all()
    bridge_map = {str(c["id"]): c for c in bridge_connections}
    has_disconnected = False
    for c in connections:
        c._bridge_status = bridge_map.get(str(c.id), {}).get("status", "disconnected")
        c._bridge_phone = bridge_map.get(str(c.id), {}).get("phone")
        if c._bridge_status != "connected":
            has_disconnected = True
    if has_disconnected:
        try:
            import httpx
            async with httpx.AsyncClient(timeout=5.0) as client:
                await client.post(f"{bridge_url}/api/reload")
        except Exception:
            pass
    return templates.TemplateResponse("whatsapp_list.html", {
        "request": request,
        "connections": connections,
        "users": users,
        "bridge_url": bridge_url_browser.rstrip("/"),
    })


@router.post("/whatsapp/create")
async def whatsapp_create(request: Request, name: str = Form("")):
    """WhatsApp bağlantısı oluşturur. [POST /whatsapp/create]"""
    if request.session.get("admin") != "ok":
        raise HTTPException(401)
    name = name.strip() or "Yeni Hesap"
    async with AsyncSessionLocal() as db:
        tid = get_tenant_id(request)
        conn = WhatsAppConnection(tenant_id=tid, name=name, auth_path=f"conn_{uuid.uuid4().hex[:8]}", status="disconnected")
        db.add(conn)
        await db.commit()
        await db.refresh(conn)
    import httpx
    bridge_url = get_settings().whatsapp_bridge_url or "http://localhost:3100"
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            await client.post(f"{bridge_url}/api/reload")
    except Exception:
        pass
    return RedirectResponse(url="/admin/whatsapp", status_code=302)


@router.post("/whatsapp/{id}/delete")
async def whatsapp_delete(request: Request, id: int):
    """WhatsApp bağlantısı siler. [POST /whatsapp/{id}/delete]"""
    if request.session.get("admin") != "ok":
        raise HTTPException(401)
    tid = get_tenant_id(request)
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(WhatsAppConnection).where(WhatsAppConnection.id == id, WhatsAppConnection.tenant_id == tid))
        conn = result.scalar_one_or_none()
        if conn:
            result = await db.execute(select(User).where(User.whatsapp_connection_id == id))
            for u in result.scalars().all():
                u.whatsapp_connection_id = None
            conn.is_active = False
            await db.commit()
    return RedirectResponse(url="/admin/whatsapp", status_code=302)


# --- Instagram DM ---
@router.get("/instagram", response_class=HTMLResponse)
async def instagram_dashboard(request: Request):
    """Instagram DM genel bakış – durum, istatistikler, hızlı erişim"""
    if request.session.get("admin") != "ok":
        return RedirectResponse(url="/admin", status_code=302)
    await require_module(request, "instagram")
    tid = get_tenant_id(request)
    settings = get_settings()
    configured = bool((settings.instagram_access_token or "").strip())
    base_url = str(request.base_url).rstrip("/")
    webhook_url = f"{base_url}/webhook/instagram"
    verify_token = settings.instagram_verify_token or "emare_verify"
    instagram_conv_count = 0
    instagram_conv_today = 0
    async with AsyncSessionLocal() as db:
        r = await db.execute(
            select(func.count(Conversation.id)).where(
                Conversation.tenant_id == tid,
                Conversation.platform == "instagram",
            )
        )
        instagram_conv_count = r.scalar() or 0
        today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        r2 = await db.execute(
            select(func.count(Conversation.id)).where(
                Conversation.tenant_id == tid,
                Conversation.platform == "instagram",
                Conversation.created_at >= today_start,
            )
        )
        instagram_conv_today = r2.scalar() or 0
    return templates.TemplateResponse("instagram_dashboard.html", {
        "request": request,
        "configured": configured,
        "webhook_url": webhook_url,
        "verify_token": verify_token,
        "instagram_conv_count": instagram_conv_count,
        "instagram_conv_today": instagram_conv_today,
    })


@router.get("/instagram/setup", response_class=HTMLResponse)
async def instagram_setup(request: Request):
    """Instagram webhook kurulum rehberi – adım adım Meta Developer Console"""
    if request.session.get("admin") != "ok":
        return RedirectResponse(url="/admin", status_code=302)
    await require_module(request, "instagram")
    settings = get_settings()
    base_url = str(request.base_url).rstrip("/")
    webhook_url = f"{base_url}/webhook/instagram"
    verify_token = settings.instagram_verify_token or "emare_verify"
    return templates.TemplateResponse("instagram_setup.html", {
        "request": request,
        "webhook_url": webhook_url,
        "verify_token": verify_token,
    })


# --- Kullanıcılar ---
@router.get("/users", response_class=HTMLResponse)
async def users_list(request: Request, edit: str = ""):
    """Kullanıcılar listeler. [GET /users]"""
    if request.session.get("admin") != "ok":
        return RedirectResponse(url="/admin", status_code=302)
    tid = get_tenant_id(request)
    page = max(1, int(request.query_params.get("page") or 1))
    edit_user = None
    async with AsyncSessionLocal() as db:
        count_q = select(func.count(User.id)).where(User.tenant_id == tid)
        total = (await db.execute(count_q)).scalar() or 0
        result = await db.execute(
            select(User).where(User.tenant_id == tid).order_by(User.id).offset((page - 1) * PAGE_SIZE).limit(PAGE_SIZE)
        )
        users = result.scalars().all()
        result = await db.execute(select(WhatsAppConnection).where(WhatsAppConnection.is_active == True, WhatsAppConnection.tenant_id == tid))
        connections = result.scalars().all()
        if edit and edit.isdigit():
            r = await db.execute(select(User).where(User.id == int(edit), User.tenant_id == tid))
            edit_user = r.scalar_one_or_none()
    total_pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)
    return templates.TemplateResponse("users_list.html", {
        "request": request,
        "users": users,
        "connections": connections,
        "edit_user": edit_user,
        "edit": edit,
        "page": page,
        "total_pages": total_pages,
        "total": total,
    })


@router.post("/users/save")
async def users_save(request: Request, id: str = Form(""), name: str = Form(""), email: str = Form(""), password: str = Form(""), whatsapp_connection_id: str = Form("")):
    """Kullanıcılar kaydeder. [POST /users/save]"""
    if request.session.get("admin") != "ok":
        raise HTTPException(401)
    import bcrypt
    tid = get_tenant_id(request)
    name = name.strip() or "Kullanıcı"
    email = (email or "").strip() or None
    password = (password or "").strip()
    wc_id = int(whatsapp_connection_id) if whatsapp_connection_id and whatsapp_connection_id.isdigit() else None
    async with AsyncSessionLocal() as db:
        if id and id.isdigit():
            result = await db.execute(select(User).where(User.id == int(id), User.tenant_id == tid))
            user = result.scalar_one_or_none()
            if not user:
                raise HTTPException(404)
        else:
            user = User(tenant_id=tid)
            db.add(user)
        user.name = name
        user.email = email
        user.whatsapp_connection_id = wc_id
        if password:
            user.password_hash = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
        await db.commit()
    return RedirectResponse(url="/admin/users", status_code=302)


@router.post("/users/{id}/delete")
async def users_delete(request: Request, id: int):
    """Kullanıcılar siler. [POST /users/{id}/delete]"""
    if request.session.get("admin") != "ok":
        raise HTTPException(401)
    tid = get_tenant_id(request)
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(User).where(User.id == id, User.tenant_id == tid))
        user = result.scalar_one_or_none()
        if user:
            await db.delete(user)
            await db.commit()
    return RedirectResponse(url="/admin/users", status_code=302)


# --- Kişiler (Rehber) ---
@router.get("/contacts", response_class=HTMLResponse)
async def contacts_list(request: Request):
    """Kişiler listeler. [GET /contacts]"""
    if request.session.get("admin") != "ok":
        return RedirectResponse(url="/admin", status_code=302)
    tid = get_tenant_id(request)
    page = max(1, int(request.query_params.get("page") or 1))
    async with AsyncSessionLocal() as db:
        count_q = select(func.count(Contact.id)).where(Contact.tenant_id == tid)
        total = (await db.execute(count_q)).scalar() or 0
        result = await db.execute(
            select(Contact).where(Contact.tenant_id == tid).order_by(Contact.name).offset((page - 1) * PAGE_SIZE).limit(PAGE_SIZE)
        )
        contacts = result.scalars().all()
    total_pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)
    return templates.TemplateResponse("contacts_list.html", {
        "request": request,
        "contacts": contacts,
        "page": page,
        "total_pages": total_pages,
        "total": total,
    })


@router.post("/contacts/save")
async def contacts_save(request: Request, id: str = Form(""), name: str = Form(""), phone: str = Form(""), email: str = Form(""), notes: str = Form("")):
    """Kişiler kaydeder. [POST /contacts/save]"""
    if request.session.get("admin") != "ok":
        raise HTTPException(401)
    name = name.strip() or "İsimsiz"
    phone = (phone or "").strip()
    if not phone:
        raise HTTPException(400, detail="Telefon gerekli")
    tid = get_tenant_id(request)
    async with AsyncSessionLocal() as db:
        if id and id.isdigit():
            result = await db.execute(select(Contact).where(Contact.id == int(id), Contact.tenant_id == tid))
            contact = result.scalar_one_or_none()
            if not contact:
                raise HTTPException(404)
        else:
            contact = Contact(tenant_id=tid)
            db.add(contact)
        contact.name = name
        contact.phone = phone
        contact.email = (email or "").strip() or None
        contact.notes = (notes or "").strip() or None
        await db.commit()
        try:
            from services.workflow.export_trigger import trigger_export_webhooks
            await trigger_export_webhooks("contacts", contact, get_tenant_id(request))
        except Exception:
            pass
    return RedirectResponse(url="/admin/contacts", status_code=302)


@router.post("/contacts/{id}/delete")
async def contacts_delete(request: Request, id: int):
    """Kişiler siler. [POST /contacts/{id}/delete]"""
    if request.session.get("admin") != "ok":
        raise HTTPException(401)
    tid = get_tenant_id(request)
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Contact).where(Contact.id == id, Contact.tenant_id == tid))
        contact = result.scalar_one_or_none()
        if contact:
            await db.delete(contact)
            await db.commit()
    return RedirectResponse(url="/admin/contacts", status_code=302)


# --- Randevular ---
@router.get("/appointments", response_class=HTMLResponse)
async def appointments_list(request: Request):
    """Randevu listesi ve ayarları"""
    if request.session.get("admin") != "ok":
        return RedirectResponse(url="/admin", status_code=302)
    await require_module(request, "appointments")
    tid = get_tenant_id(request)
    status_filter = request.query_params.get("status", "")
    from services.core.tenant import get_tenant_settings
    from services.appointment.service import cleanup_misparsed_date_appointments
    tenant_settings = await get_tenant_settings(tid)
    async with AsyncSessionLocal() as db:
        # Eski tarih->saat parse bug'i ile olusan hatali randevulari listeleme oncesi temizle.
        await cleanup_misparsed_date_appointments(db, tid)
        query = select(Appointment).where(Appointment.tenant_id == tid).order_by(Appointment.scheduled_at)
        if status_filter:
            query = query.where(Appointment.status == status_filter)
        result = await db.execute(query)
        appointments = result.scalars().all()
    return templates.TemplateResponse("appointments_list.html", {
        "request": request,
        "appointments": appointments,
        "status_filter": status_filter,
        "appointment_work_hours": tenant_settings.get("appointment_work_hours") or "09:00-18:00",
        "appointment_slot_minutes": int(tenant_settings.get("appointment_slot_minutes") or 30),
        "appointment_work_days": tenant_settings.get("appointment_work_days") or "1,2,3,4,5",
    })


@router.post("/appointments/settings")
async def appointments_settings_save(
    request: Request,
    appointment_work_hours: str = Form("09:00-18:00"),
    appointment_slot_minutes: str = Form("30"),
    appointment_work_days: str = Form("1,2,3,4,5"),
):
    """Randevu çalışma ayarlarını tenant.settings'e kaydet"""
    if request.session.get("admin") != "ok":
        raise HTTPException(401)
    await require_module(request, "appointments")
    tid = get_tenant_id(request)
    work_hours = (appointment_work_hours or "09:00-18:00").strip() or "09:00-18:00"
    work_days = (appointment_work_days or "1,2,3,4,5").strip() or "1,2,3,4,5"
    try:
        slot_minutes = int((appointment_slot_minutes or "30").strip())
    except ValueError:
        slot_minutes = 30
    if slot_minutes < 15 or slot_minutes > 120:
        slot_minutes = 30

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
                existing = {}
        existing["appointment_work_hours"] = work_hours
        existing["appointment_slot_minutes"] = slot_minutes
        existing["appointment_work_days"] = work_days
        from services.core.crypto import encrypt_tenant_settings
        tenant.settings = json.dumps(encrypt_tenant_settings(existing), ensure_ascii=False)
        await db.commit()
    from services.core.cache import invalidate_tenant_cache
    await invalidate_tenant_cache(tid)
    return RedirectResponse(url="/admin/appointments?saved=1", status_code=302)


@router.post("/appointments/{id}/complete")
async def appointment_complete(request: Request, id: int):
    """Randevu tamamlanmış olarak işaretler. [POST /appointments/{id}/complete]"""
    if request.session.get("admin") != "ok":
        raise HTTPException(401)
    await require_module(request, "appointments")
    tid = get_tenant_id(request)
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Appointment).where(Appointment.id == id, Appointment.tenant_id == tid))
        apt = result.scalar_one_or_none()
        if apt:
            apt.status = "completed"
            apt.updated_at = datetime.utcnow()
            await db.commit()
    return RedirectResponse(url="/admin/appointments", status_code=302)


@router.post("/appointments/{id}/cancel")
async def appointment_cancel(request: Request, id: int):
    """Randevu iptal eder. [POST /appointments/{id}/cancel]"""
    if request.session.get("admin") != "ok":
        raise HTTPException(401)
    await require_module(request, "appointments")
    tid = get_tenant_id(request)
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Appointment).where(Appointment.id == id, Appointment.tenant_id == tid))
        apt = result.scalar_one_or_none()
        if apt:
            apt.status = "cancelled"
            apt.updated_at = datetime.utcnow()
            await db.commit()
    return RedirectResponse(url="/admin/appointments", status_code=302)


# --- İdari İşler (izin, fatura, satın alma) ---
@router.get("/admin-staff/leaves", response_class=HTMLResponse)
async def admin_staff_leaves(request: Request):
    """Personel endpoint'i. [GET /admin-staff/leaves]"""
    if request.session.get("admin") != "ok":
        return RedirectResponse(url="/admin", status_code=302)
    await require_module(request, "admin_staff")
    tid = get_tenant_id(request)
    status_filter = request.query_params.get("status", "")
    page = max(1, int(request.query_params.get("page") or 1))
    async with AsyncSessionLocal() as db:
        base_q = select(LeaveRequest).where(LeaveRequest.tenant_id == tid).order_by(desc(LeaveRequest.created_at))
        if status_filter:
            base_q = base_q.where(LeaveRequest.status == status_filter)
        count_q = select(func.count(LeaveRequest.id)).where(LeaveRequest.tenant_id == tid)
        if status_filter:
            count_q = count_q.where(LeaveRequest.status == status_filter)
        total = (await db.execute(count_q)).scalar() or 0
        result = await db.execute(base_q.offset((page - 1) * PAGE_SIZE).limit(PAGE_SIZE))
        leaves = result.scalars().all()
    total_pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)
    return templates.TemplateResponse("admin_staff_leaves.html", {
        "request": request,
        "leaves": leaves,
        "status_filter": status_filter,
        "page": page,
        "total_pages": total_pages,
        "total": total,
    })


@router.post("/admin-staff/leaves/save")
async def admin_staff_leave_save(
    request: Request,
    employee_name: str = Form(""),
    employee_phone: str = Form(""),
    start_date: str = Form(""),
    end_date: str = Form(""),
    leave_type: str = Form(""),
    note: str = Form(""),
):
    """Personel kaydeder. [POST /admin-staff/leaves/save]"""
    if request.session.get("admin") != "ok":
        raise HTTPException(401)
    await require_module(request, "admin_staff")
    tid = get_tenant_id(request)
    if not employee_name.strip():
        raise HTTPException(400, detail="Çalışan adı gerekli")
    try:
        start = datetime.strptime(start_date, "%Y-%m-%d").date()
        end = datetime.strptime(end_date, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(400, detail="Geçerli tarih gerekli")
    if end < start:
        raise HTTPException(400, detail="Bitiş tarihi başlangıçtan küçük olamaz")
    async with AsyncSessionLocal() as db:
        rec = LeaveRequest(
            tenant_id=tid,
            employee_name=employee_name.strip(),
            employee_phone=(employee_phone or "").strip() or None,
            start_date=start,
            end_date=end,
            leave_type=(leave_type or "").strip() or None,
            note=(note or "").strip() or None,
            status="pending_hr",
        )
        db.add(rec)
        await db.commit()
        await db.refresh(rec)
    await _audit_from_request(
        request,
        action="admin_staff_leave_create",
        resource="leave_request",
        resource_id=str(rec.id),
        details={"employee_name": rec.employee_name, "status": rec.status},
    )
    return RedirectResponse(url="/admin/admin-staff/leaves", status_code=302)


@router.post("/admin-staff/leaves/{id}/status")
async def admin_staff_leave_status(
    request: Request,
    id: int,
    action: str = Form("approve"),
    approver_role: str = Form("hr"),
    approver_name: str = Form(""),
):
    """Personel durum sorgular. [POST /admin-staff/leaves/{id}/status]"""
    if request.session.get("admin") != "ok":
        raise HTTPException(401)
    await require_module(request, "admin_staff")
    tid = get_tenant_id(request)
    action = (action or "").strip().lower()
    approver_role = (approver_role or "").strip().lower()
    if action not in ("approve", "reject"):
        raise HTTPException(400, detail="Gecersiz islem")
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(LeaveRequest).where(LeaveRequest.id == id, LeaveRequest.tenant_id == tid))
        leave = result.scalar_one_or_none()
        if not leave:
            raise HTTPException(404)
        old_status = leave.status or "pending_hr"
        if action == "reject":
            new_status = "rejected"
        elif old_status in ("pending", "pending_hr") and approver_role == "hr":
            new_status = "pending_manager"
        elif old_status == "pending_manager" and approver_role in ("manager", "admin"):
            new_status = "approved"
        else:
            raise HTTPException(400, detail="Onay sirasi uyusmuyor")

        leave.status = new_status
        leave.approver_name = (approver_name or "").strip() or leave.approver_name
        leave.updated_at = datetime.utcnow()
        await db.commit()
    await _audit_from_request(
        request,
        action="admin_staff_leave_status",
        resource="leave_request",
        resource_id=str(id),
        details={"old_status": old_status, "new_status": new_status, "approver_role": approver_role},
    )
    return RedirectResponse(url="/admin/admin-staff/leaves", status_code=302)


@router.get("/admin-staff/invoices", response_class=HTMLResponse)
async def admin_staff_invoices(request: Request):
    """Personel endpoint'i. [GET /admin-staff/invoices]"""
    if request.session.get("admin") != "ok":
        return RedirectResponse(url="/admin", status_code=302)
    await require_module(request, "admin_staff")
    tid = get_tenant_id(request)
    status_filter = request.query_params.get("status", "")
    page = max(1, int(request.query_params.get("page") or 1))
    async with AsyncSessionLocal() as db:
        base_q = select(Invoice).where(Invoice.tenant_id == tid).order_by(desc(Invoice.created_at))
        if status_filter:
            base_q = base_q.where(Invoice.status == status_filter)
        count_q = select(func.count(Invoice.id)).where(Invoice.tenant_id == tid)
        if status_filter:
            count_q = count_q.where(Invoice.status == status_filter)
        total = (await db.execute(count_q)).scalar() or 0
        result = await db.execute(base_q.offset((page - 1) * PAGE_SIZE).limit(PAGE_SIZE))
        invoices = result.scalars().all()
    total_pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)
    return templates.TemplateResponse("admin_staff_invoices.html", {
        "request": request,
        "invoices": invoices,
        "status_filter": status_filter,
        "page": page,
        "total_pages": total_pages,
        "total": total,
    })


@router.post("/admin-staff/invoices/save")
async def admin_staff_invoice_save(
    request: Request,
    supplier_name: str = Form(""),
    invoice_number: str = Form(""),
    total_amount: str = Form(""),
    due_date: str = Form(""),
    note: str = Form(""),
    invoice_image: UploadFile | None = File(None),
):
    """Personel kaydeder. [POST /admin-staff/invoices/save]"""
    if request.session.get("admin") != "ok":
        raise HTTPException(401)
    await require_module(request, "admin_staff")
    tid = get_tenant_id(request)
    ocr_text = ""
    if invoice_image and (invoice_image.content_type or "").startswith("image/"):
        blob = await invoice_image.read()
        if blob:
            b64 = base64.b64encode(blob).decode("utf-8")
            from services.ai.ocr import extract_text_from_image
            ocr_text = (await extract_text_from_image(b64, prompt="Bu gorsel bir faturadir. Tedarikci, fatura no, toplam tutar ve vade bilgilerini metin olarak cikar.")) or ""
    if not supplier_name.strip() and not ocr_text:
        raise HTTPException(400, detail="Tedarikci adi gerekli")
    if not supplier_name.strip() and ocr_text:
        first_line = next((ln.strip() for ln in ocr_text.splitlines() if ln.strip()), "")
        supplier_name = first_line[:120] if first_line else "OCR Tedarikci"
    amount = None
    raw_amount = (total_amount or "").strip().replace(",", ".")
    if raw_amount:
        try:
            amount = float(raw_amount)
        except ValueError:
            raise HTTPException(400, detail="Geçerli tutar gerekli")
    elif ocr_text:
        m_amt = re.search(r"(\d{1,3}(?:[.,]\d{3})*(?:[.,]\d{2}))", ocr_text.replace(" ", ""))
        if m_amt:
            try:
                amount = float(m_amt.group(1).replace(".", "").replace(",", "."))
            except Exception:
                amount = None
    parsed_due_date = None
    if due_date:
        try:
            parsed_due_date = datetime.strptime(due_date, "%Y-%m-%d").date()
        except ValueError:
            raise HTTPException(400, detail="Geçerli vade tarihi gerekli")
    inv_no = (invoice_number or "").strip() or None
    if not inv_no and ocr_text:
        m_no = re.search(r"(?:FATURA|INVOICE)[^\n:]*[:\s]+([A-Z0-9\-_/]{4,})", ocr_text, re.IGNORECASE)
        if m_no:
            inv_no = m_no.group(1).strip()
    note_text = (note or "").strip() or None
    if ocr_text:
        short_ocr = ocr_text[:500]
        note_text = (note_text + "\n\n" if note_text else "") + f"[OCR]\n{short_ocr}"
    async with AsyncSessionLocal() as db:
        rec = Invoice(
            tenant_id=tid,
            supplier_name=supplier_name.strip(),
            invoice_number=inv_no,
            total_amount=amount,
            due_date=parsed_due_date,
            note=note_text,
            scanned_text=ocr_text[:2000] if ocr_text else None,
            status="pending_finance",
        )
        db.add(rec)
        await db.commit()
        await db.refresh(rec)
    await _audit_from_request(
        request,
        action="admin_staff_invoice_create",
        resource="invoice",
        resource_id=str(rec.id),
        details={"supplier_name": rec.supplier_name, "status": rec.status, "ocr": bool(ocr_text)},
    )
    return RedirectResponse(url="/admin/admin-staff/invoices", status_code=302)


@router.post("/admin-staff/invoices/{id}/status")
async def admin_staff_invoice_status(
    request: Request,
    id: int,
    action: str = Form("approve"),
    approver_role: str = Form("finance"),
):
    """Personel durum sorgular. [POST /admin-staff/invoices/{id}/status]"""
    if request.session.get("admin") != "ok":
        raise HTTPException(401)
    await require_module(request, "admin_staff")
    tid = get_tenant_id(request)
    action = (action or "").strip().lower()
    approver_role = (approver_role or "").strip().lower()
    if action not in ("approve", "paid", "reject"):
        raise HTTPException(400, detail="Gecersiz islem")
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Invoice).where(Invoice.id == id, Invoice.tenant_id == tid))
        invoice = result.scalar_one_or_none()
        if not invoice:
            raise HTTPException(404)
        old_status = invoice.status or "pending_finance"
        if action == "reject":
            new_status = "rejected"
        elif action == "paid":
            if old_status != "approved":
                raise HTTPException(400, detail="Odendi sadece approved kayitta secilebilir")
            new_status = "paid"
        elif old_status in ("pending", "pending_finance") and approver_role == "finance":
            new_status = "pending_manager"
        elif old_status == "pending_manager" and approver_role in ("manager", "admin"):
            new_status = "approved"
        else:
            raise HTTPException(400, detail="Onay sirasi uyusmuyor")

        invoice.status = new_status
        invoice.updated_at = datetime.utcnow()
        await db.commit()
    await _audit_from_request(
        request,
        action="admin_staff_invoice_status",
        resource="invoice",
        resource_id=str(id),
        details={"old_status": old_status, "new_status": new_status, "approver_role": approver_role},
    )
    return RedirectResponse(url="/admin/admin-staff/invoices", status_code=302)


@router.get("/admin-staff/purchase-orders", response_class=HTMLResponse)
async def admin_staff_purchase_orders(request: Request):
    """Personel endpoint'i. [GET /admin-staff/purchase-orders]"""
    if request.session.get("admin") != "ok":
        return RedirectResponse(url="/admin", status_code=302)
    await require_module(request, "admin_staff")
    tid = get_tenant_id(request)
    status_filter = request.query_params.get("status", "")
    page = max(1, int(request.query_params.get("page") or 1))
    async with AsyncSessionLocal() as db:
        base_q = select(PurchaseOrder).where(PurchaseOrder.tenant_id == tid).order_by(desc(PurchaseOrder.created_at))
        if status_filter:
            base_q = base_q.where(PurchaseOrder.status == status_filter)
        count_q = select(func.count(PurchaseOrder.id)).where(PurchaseOrder.tenant_id == tid)
        if status_filter:
            count_q = count_q.where(PurchaseOrder.status == status_filter)
        total = (await db.execute(count_q)).scalar() or 0
        result = await db.execute(base_q.offset((page - 1) * PAGE_SIZE).limit(PAGE_SIZE))
        purchase_orders = result.scalars().all()
    total_pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)
    return templates.TemplateResponse("admin_staff_purchase_orders.html", {
        "request": request,
        "purchase_orders": purchase_orders,
        "status_filter": status_filter,
        "page": page,
        "total_pages": total_pages,
        "total": total,
    })


@router.post("/admin-staff/purchase-orders/save")
async def admin_staff_purchase_order_save(
    request: Request,
    requester_name: str = Form(""),
    supplier_name: str = Form(""),
    items_text: str = Form(""),
    note: str = Form(""),
    po_image: UploadFile | None = File(None),
):
    """Personel kaydeder. [POST /admin-staff/purchase-orders/save]"""
    if request.session.get("admin") != "ok":
        raise HTTPException(401)
    await require_module(request, "admin_staff")
    tid = get_tenant_id(request)
    if not requester_name.strip():
        raise HTTPException(400, detail="Talep eden adı gerekli")
    ocr_text = ""
    if po_image and (po_image.content_type or "").startswith("image/"):
        blob = await po_image.read()
        if blob:
            b64 = base64.b64encode(blob).decode("utf-8")
            from services.ai.ocr import extract_text_from_image
            ocr_text = (await extract_text_from_image(b64, prompt="Bu belge satin alma talebi veya liste olabilir. Kalemleri satir satir cikar.")) or ""

    source_text = (items_text or "").strip()
    if not source_text and ocr_text:
        # OCR metninden bos olmayan satirlari kalem olarak al
        source_text = "\n".join([ln.strip() for ln in ocr_text.splitlines() if ln.strip()][:30])

    lines = [ln.strip() for ln in source_text.splitlines() if ln.strip()]
    if not lines:
        raise HTTPException(400, detail="En az bir kalem gerekli")
    items = [{"name": ln} for ln in lines]
    note_text = (note or "").strip() or None
    if ocr_text:
        note_text = (note_text + "\n\n" if note_text else "") + f"[OCR]\n{ocr_text[:500]}"
    async with AsyncSessionLocal() as db:
        rec = PurchaseOrder(
            tenant_id=tid,
            requester_name=requester_name.strip(),
            supplier_name=(supplier_name or "").strip() or None,
            items_json=json.dumps(items, ensure_ascii=False),
            note=note_text,
            status="pending_procurement",
        )
        db.add(rec)
        await db.commit()
        await db.refresh(rec)
    await _audit_from_request(
        request,
        action="admin_staff_purchase_create",
        resource="purchase_order",
        resource_id=str(rec.id),
        details={"requester_name": rec.requester_name, "status": rec.status, "ocr": bool(ocr_text)},
    )
    return RedirectResponse(url="/admin/admin-staff/purchase-orders", status_code=302)


@router.post("/admin-staff/purchase-orders/{id}/status")
async def admin_staff_purchase_order_status(
    request: Request,
    id: int,
    action: str = Form("approve"),
    approver_role: str = Form("procurement"),
):
    """Personel durum sorgular. [POST /admin-staff/purchase-orders/{id}/status]"""
    if request.session.get("admin") != "ok":
        raise HTTPException(401)
    await require_module(request, "admin_staff")
    tid = get_tenant_id(request)
    action = (action or "").strip().lower()
    approver_role = (approver_role or "").strip().lower()
    if action not in ("approve", "ordered", "reject"):
        raise HTTPException(400, detail="Gecersiz islem")
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(PurchaseOrder).where(PurchaseOrder.id == id, PurchaseOrder.tenant_id == tid))
        po = result.scalar_one_or_none()
        if not po:
            raise HTTPException(404)
        old_status = po.status or "pending_procurement"
        if action == "reject":
            new_status = "rejected"
        elif action == "ordered":
            if old_status != "approved":
                raise HTTPException(400, detail="Siparis verildi sadece approved kayitta secilebilir")
            new_status = "ordered"
        elif old_status in ("pending", "pending_procurement") and approver_role == "procurement":
            new_status = "pending_manager"
        elif old_status == "pending_manager" and approver_role in ("manager", "admin"):
            new_status = "approved"
        else:
            raise HTTPException(400, detail="Onay sirasi uyusmuyor")

        po.status = new_status
        po.updated_at = datetime.utcnow()
        await db.commit()
    await _audit_from_request(
        request,
        action="admin_staff_purchase_status",
        resource="purchase_order",
        resource_id=str(id),
        details={"old_status": old_status, "new_status": new_status, "approver_role": approver_role},
    )
    return RedirectResponse(url="/admin/admin-staff/purchase-orders", status_code=302)


# --- Hatırlatıcılar ---
@router.get("/reminders", response_class=HTMLResponse)
async def reminders_list(request: Request):
    """Hatırlatıcılar - müşteriye dönüş takibi"""
    if request.session.get("admin") != "ok":
        return RedirectResponse(url="/admin", status_code=302)
    tid = get_tenant_id(request)
    status_filter = request.query_params.get("status", "pending")
    segment_filter = (request.query_params.get("segment") or "all").strip().lower()
    if segment_filter not in ("all", "new_customer", "has_order", "high_value"):
        segment_filter = "all"
    min_total = float(request.query_params.get("min_total") or 0)
    page = max(1, int(request.query_params.get("page") or 1))
    async with AsyncSessionLocal() as db:
        base_q = select(Reminder).where(Reminder.tenant_id == tid).order_by(Reminder.due_at)
        if status_filter:
            base_q = base_q.where(Reminder.status == status_filter)
        if segment_filter == "all":
            count_q = select(func.count(Reminder.id)).where(Reminder.tenant_id == tid)
            if status_filter:
                count_q = count_q.where(Reminder.status == status_filter)
            total = (await db.execute(count_q)).scalar() or 0
            result = await db.execute(base_q.offset((page - 1) * PAGE_SIZE).limit(PAGE_SIZE))
            reminders = list(result.scalars().all())
        else:
            result = await db.execute(base_q)
            all_reminders = list(result.scalars().all())
            phones = list({(r.customer_phone or "").strip() for r in all_reminders if (r.customer_phone or "").strip()})
            totals: dict[str, float] = {}
            if phones:
                oq = await db.execute(
                    select(Order.customer_phone, func.coalesce(func.sum(Order.total_amount), 0))
                    .where(Order.tenant_id == tid, Order.customer_phone.in_(phones))
                    .group_by(Order.customer_phone)
                )
                totals = {str(p or "").strip(): float(t or 0) for p, t in oq.all()}
            filtered = []
            for r in all_reminders:
                p = (r.customer_phone or "").strip()
                has_order = totals.get(p, 0) > 0
                if segment_filter == "new_customer" and not has_order:
                    filtered.append(r)
                elif segment_filter == "has_order" and has_order:
                    filtered.append(r)
                elif segment_filter == "high_value" and totals.get(p, 0) >= max(0.0, min_total):
                    filtered.append(r)
            total = len(filtered)
            reminders = filtered[(page - 1) * PAGE_SIZE : page * PAGE_SIZE]
    total_pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)
    return templates.TemplateResponse("reminders_list.html", {
        "request": request,
        "reminders": reminders,
        "status_filter": status_filter,
        "segment_filter": segment_filter,
        "min_total": min_total,
        "page": page,
        "total_pages": total_pages,
        "total": total,
    })


@router.get("/reminders/new", response_class=HTMLResponse)
async def reminder_new(request: Request):
    """Hatırlatıcı yeni oluşturma formu. [GET /reminders/new]"""
    if request.session.get("admin") != "ok":
        return RedirectResponse(url="/admin", status_code=302)
    tid = get_tenant_id(request)
    conv_id = request.query_params.get("conv_id", "")
    contact_id = request.query_params.get("contact_id", "")
    async with AsyncSessionLocal() as db:
        conv, contact = None, None
        if conv_id and conv_id.isdigit():
            r = await db.execute(select(Conversation).where(Conversation.id == int(conv_id), Conversation.tenant_id == tid))
            conv = r.scalar_one_or_none()
        if contact_id and contact_id.isdigit():
            r = await db.execute(select(Contact).where(Contact.id == int(contact_id), Contact.tenant_id == tid))
            contact = r.scalar_one_or_none()
    default_due = (datetime.utcnow() + timedelta(days=1)).strftime("%Y-%m-%dT10:00")
    return templates.TemplateResponse("reminder_form.html", {
        "request": request,
        "reminder": None,
        "conv": conv,
        "contact": contact,
        "default_due": default_due,
    })


@router.get("/reminders/{id}", response_class=HTMLResponse)
async def reminder_edit(request: Request, id: int):
    """Hatırlatıcı düzenleme formu. [GET /reminders/{id}]"""
    if request.session.get("admin") != "ok":
        return RedirectResponse(url="/admin", status_code=302)
    tid = get_tenant_id(request)
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Reminder).where(Reminder.id == id, Reminder.tenant_id == tid))
        reminder = result.scalar_one_or_none()
        if not reminder:
            raise HTTPException(404)
        conv, contact = None, None
        rtid = reminder.tenant_id or tid
        if reminder.conversation_id:
            r = await db.execute(select(Conversation).where(Conversation.id == reminder.conversation_id, Conversation.tenant_id == rtid))
            conv = r.scalar_one_or_none()
        if reminder.contact_id:
            r = await db.execute(select(Contact).where(Contact.id == reminder.contact_id, Contact.tenant_id == rtid))
            contact = r.scalar_one_or_none()
    return templates.TemplateResponse("reminder_form.html", {
        "request": request,
        "reminder": reminder,
        "conv": conv,
        "contact": contact,
        "default_due": "",
    })


@router.post("/reminders/save")
async def reminder_save(
    request: Request,
    id: str = Form(""),
    conversation_id: str = Form(""),
    contact_id: str = Form(""),
    customer_name: str = Form(""),
    customer_phone: str = Form(""),
    due_at: str = Form(""),
    note: str = Form(""),
):
    """Hatırlatıcı kaydeder. [POST /reminders/save]"""
    if request.session.get("admin") != "ok":
        raise HTTPException(401)
    tid = get_tenant_id(request)
    async with AsyncSessionLocal() as db:
        if id and id.isdigit():
            result = await db.execute(select(Reminder).where(Reminder.id == int(id), Reminder.tenant_id == tid))
            reminder = result.scalar_one_or_none()
            if not reminder:
                raise HTTPException(404)
        else:
            reminder = Reminder(tenant_id=tid)
            db.add(reminder)
        reminder.conversation_id = int(conversation_id) if conversation_id and conversation_id.isdigit() else None
        reminder.contact_id = int(contact_id) if contact_id and contact_id.isdigit() else None
        reminder.customer_name = customer_name.strip() or None
        reminder.customer_phone = customer_phone.strip() or None
        reminder.note = note.strip() or None
        if due_at:
            try:
                reminder.due_at = datetime.strptime(due_at, "%Y-%m-%dT%H:%M")
            except ValueError:
                try:
                    reminder.due_at = datetime.strptime(due_at, "%Y-%m-%d")
                except ValueError:
                    reminder.due_at = datetime.utcnow() + timedelta(days=1)
        await db.commit()
        try:
            from services.workflow.export_trigger import trigger_export_webhooks
            await trigger_export_webhooks("reminders", reminder, get_tenant_id(request))
        except Exception:
            pass
    return RedirectResponse(url="/admin/reminders", status_code=302)


@router.post("/reminders/{id}/complete")
async def reminder_complete(request: Request, id: int):
    """Hatırlatıcı tamamlanmış olarak işaretler. [POST /reminders/{id}/complete]"""
    if request.session.get("admin") != "ok":
        raise HTTPException(401)
    tid = get_tenant_id(request)
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Reminder).where(Reminder.id == id, Reminder.tenant_id == tid))
        r = result.scalar_one_or_none()
        if r:
            r.status = "done"
            r.completed_at = datetime.utcnow()
            await db.commit()
    return RedirectResponse(url="/admin/reminders", status_code=302)


@router.post("/reminders/{id}/delete")
async def reminder_delete(request: Request, id: int):
    """Hatırlatıcı siler. [POST /reminders/{id}/delete]"""
    if request.session.get("admin") != "ok":
        raise HTTPException(401)
    tid = get_tenant_id(request)
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Reminder).where(Reminder.id == id, Reminder.tenant_id == tid))
        r = result.scalar_one_or_none()
        if r:
            await db.delete(r)
            await db.commit()
    return RedirectResponse(url="/admin/reminders", status_code=302)


@router.get("/api/reminders/pending")
async def api_reminders_pending(request: Request):
    """Bekleyen hatırlatıcılar - dashboard ve agent panel için"""
    if request.session.get("admin") != "ok":
        raise HTTPException(401)
    tid = get_tenant_id(request)
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Reminder)
            .where(Reminder.tenant_id == tid, Reminder.status == "pending", Reminder.due_at <= datetime.utcnow() + timedelta(days=1))
            .order_by(Reminder.due_at)
            .limit(10)
        )
        reminders = result.scalars().all()
    return [
        {
            "id": r.id,
            "customer_name": r.customer_name or "Müşteri",
            "customer_phone": r.customer_phone or "",
            "due_at": r.due_at.isoformat() if r.due_at else None,
            "note": r.note or "",
            "conversation_id": r.conversation_id,
        }
        for r in reminders
    ]


# --- Veri Aktarım Şablonları (Export Templates) ---
@router.get("/export-templates", response_class=HTMLResponse)
async def export_templates_list(request: Request):
    """Veri aktarım şablonları - Asistan verisini dış sistemlere formatlı gönderme"""
    if request.session.get("admin") != "ok":
        return RedirectResponse(url="/admin", status_code=302)
    tid = get_tenant_id(request)
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(ExportTemplate).where(ExportTemplate.tenant_id == tid).order_by(ExportTemplate.id)
        )
        templates_list = result.scalars().all()
    return templates.TemplateResponse("export_templates_list.html", {
        "request": request,
        "templates": templates_list,
    })


@router.get("/export-templates/new", response_class=HTMLResponse)
async def export_template_new(request: Request):
    """Dışa aktarım şablonu yeni oluşturma formu. [GET /export-templates/new]"""
    if request.session.get("admin") != "ok":
        return RedirectResponse(url="/admin", status_code=302)
    return templates.TemplateResponse("export_template_form.html", {
        "request": request,
        "template": None,
        "source_fields": {
            "orders": "order_number, customer_name, customer_phone, customer_address, items, total_amount, status, platform, created_at",
            "contacts": "name, phone, email, notes, created_at",
            "reminders": "customer_name, customer_phone, due_at, note, status, created_at",
        },
    })


@router.get("/export-templates/{id}", response_class=HTMLResponse)
async def export_template_edit(request: Request, id: int):
    """Dışa aktarım şablonu düzenleme formu. [GET /export-templates/{id}]"""
    if request.session.get("admin") != "ok":
        return RedirectResponse(url="/admin", status_code=302)
    tid = get_tenant_id(request)
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(ExportTemplate).where(ExportTemplate.id == id, ExportTemplate.tenant_id == tid))
        template = result.scalar_one_or_none()
    if not template:
        raise HTTPException(404)
    return templates.TemplateResponse("export_template_form.html", {
        "request": request,
        "template": template,
        "source_fields": {
            "orders": "order_number, customer_name, customer_phone, customer_address, items, total_amount, status, platform, created_at",
            "contacts": "name, phone, email, notes, created_at",
            "reminders": "customer_name, customer_phone, due_at, note, status, created_at",
        },
    })


@router.post("/export-templates/save")
async def export_template_save(
    request: Request,
    id: str = Form(""),
    name: str = Form(""),
    source: str = Form(""),
    trigger: str = Form("webhook"),
    output_format: str = Form("json"),
    field_mapping: str = Form(""),
    webhook_url: str = Form(""),
):
    """Dışa aktarım şablonu kaydeder. [POST /export-templates/save]"""
    if request.session.get("admin") != "ok":
        raise HTTPException(401)
    tid = get_tenant_id(request)
    async with AsyncSessionLocal() as db:
        if id and id.isdigit():
            result = await db.execute(select(ExportTemplate).where(ExportTemplate.id == int(id), ExportTemplate.tenant_id == tid))
            t = result.scalar_one_or_none()
            if not t:
                raise HTTPException(404)
        else:
            t = ExportTemplate(tenant_id=tid)
            db.add(t)
        t.name = (name or "").strip() or "Şablon"
        t.source = (source or "orders").strip()[:50]
        t.trigger = (trigger or "webhook").strip()[:30]
        t.output_format = (output_format or "json").strip()[:20]
        fm = (field_mapping or "").strip() or None
        if fm:
            try:
                json.loads(fm)
            except json.JSONDecodeError:
                fm = None
        t.field_mapping = fm
        t.webhook_url = (webhook_url or "").strip() or None
        t.is_active = True
        await db.commit()
    return RedirectResponse(url="/admin/export-templates", status_code=302)


@router.post("/export-templates/{id}/delete")
async def export_template_delete(request: Request, id: int):
    """Dışa aktarım şablonu siler. [POST /export-templates/{id}/delete]"""
    if request.session.get("admin") != "ok":
        raise HTTPException(401)
    tid = get_tenant_id(request)
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(ExportTemplate).where(ExportTemplate.id == id, ExportTemplate.tenant_id == tid))
        t = result.scalar_one_or_none()
        if not t:
            raise HTTPException(404)
        await db.delete(t)
        await db.commit()
    return RedirectResponse(url="/admin/export-templates", status_code=302)


@router.get("/export-templates/{id}/export")
async def export_template_manual_export(request: Request, id: int):
    """Manuel export - CSV veya JSON indir"""
    if request.session.get("admin") != "ok":
        raise HTTPException(401)
    tid = get_tenant_id(request)
    from services.workflow.export import build_payload, SOURCE_FIELDS
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(ExportTemplate).where(ExportTemplate.id == id, ExportTemplate.tenant_id == tid))
        t = result.scalar_one_or_none()
        if not t:
            raise HTTPException(404)
        try:
            mapping = json.loads(t.field_mapping) if t.field_mapping else None
            if mapping is not None and not isinstance(mapping, dict):
                mapping = None
        except (json.JSONDecodeError, TypeError):
            mapping = None
        if t.source == "orders":
            r = await db.execute(select(Order).where(Order.tenant_id == tid).order_by(desc(Order.created_at)).limit(500))
            rows = r.scalars().all()
            payloads = [build_payload(o, "orders", mapping) for o in rows]
        elif t.source == "contacts":
            r = await db.execute(select(Contact).where(Contact.tenant_id == tid).order_by(desc(Contact.created_at)).limit(500))
            rows = r.scalars().all()
            payloads = [build_payload(o, "contacts", mapping) for o in rows]
        elif t.source == "reminders":
            r = await db.execute(select(Reminder).where(Reminder.tenant_id == tid).order_by(desc(Reminder.created_at)).limit(500))
            rows = r.scalars().all()
            payloads = [build_payload(o, "reminders", mapping) for o in rows]
        else:
            payloads = []
    if t.output_format == "csv" and payloads:
        all_keys = set()
        for p in payloads:
            all_keys.update(p.keys())
        headers = sorted(all_keys)
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=headers, extrasaction="ignore")
        writer.writeheader()
        for p in payloads:
            writer.writerow({k: (v if v is None else str(v)) for k, v in p.items()})
        return StreamingResponse(
            iter([output.getvalue()]),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename=export_{t.source}_{datetime.utcnow().strftime('%Y%m%d')}.csv"},
        )
    return JSONResponse(
        content=payloads,
        headers={"Content-Disposition": f"attachment; filename=export_{t.source}_{datetime.utcnow().strftime('%Y%m%d')}.json"},
    )


# --- Redirect routes: Eski/placeholder linkler → mevcut sayfalara ---
@router.get("/whatsapp/connection")
async def _redirect_whatsapp_connection(request: Request):
    """WhatsApp bağlantısı endpoint'i. [GET /whatsapp/connection]"""
    return RedirectResponse(url="/admin/whatsapp", status_code=302)


@router.get("/whatsapp/settings")
async def _redirect_whatsapp_settings(request: Request):
    """WhatsApp bağlantısı ayarlar sayfası. [GET /whatsapp/settings]"""
    return RedirectResponse(url="/admin/settings/api", status_code=302)


@router.get("/telegram")
async def _redirect_telegram(request: Request):
    """Telegram endpoint'i. [GET /telegram]"""
    return RedirectResponse(url="/admin/conversations?platform=telegram", status_code=302)


@router.get("/telegram/bot")
@router.get("/telegram/settings")
async def _redirect_telegram_settings(request: Request):
    """Telegram ayarlar sayfası. [GET /telegram/bot]"""
    return RedirectResponse(url="/admin/settings/api", status_code=302)


@router.get("/instagram/settings")
async def _redirect_instagram_settings(request: Request):
    """Instagram ayarlar sayfası. [GET /instagram/settings]"""
    return RedirectResponse(url="/admin/settings/api", status_code=302)


@router.get("/payment")
@router.get("/payment/links")
@router.get("/payment/settings")
async def _redirect_payment(request: Request):
    """Payment endpoint'i. [GET /payment]"""
    return RedirectResponse(url="/admin/settings/api", status_code=302)


@router.get("/facebook")
@router.get("/facebook/messages")
@router.get("/facebook/settings")
@router.get("/twitter")
@router.get("/twitter/dm")
@router.get("/twitter/settings")
@router.get("/tiktok")
@router.get("/linkedin")
async def _redirect_social_placeholder(request: Request):
    """Social endpoint'i. [GET /facebook]"""
    return RedirectResponse(url="/admin/settings/api", status_code=302)


@router.get("/trendyol")
@router.get("/trendyol/orders")
@router.get("/trendyol/settings")
@router.get("/hepsiburada")
@router.get("/hepsiburada/orders")
@router.get("/hepsiburada/settings")
@router.get("/amazon")
@router.get("/amazon/orders")
@router.get("/amazon/settings")
async def _redirect_marketplace_placeholder(request: Request):
    """Marketplace endpoint'i. [GET /trendyol]"""
    return RedirectResponse(url="/admin/settings/api", status_code=302)


@router.get("/yurtici")
@router.get("/yurtici/settings")
@router.get("/aras")
@router.get("/aras/settings")
@router.get("/mng")
@router.get("/mng/settings")
@router.get("/ups")
@router.get("/dhl")
@router.get("/ptt")
async def _redirect_cargo_placeholder(request: Request):
    """Kargo endpoint'i. [GET /yurtici]"""
    return RedirectResponse(url="/admin/settings/api", status_code=302)


@router.get("/stripe")
@router.get("/stripe/settings")
@router.get("/paypal")
@router.get("/paypal/settings")
async def _redirect_payment_placeholder(request: Request):
    """Payment endpoint'i. [GET /stripe]"""
    return RedirectResponse(url="/admin/settings/api", status_code=302)
