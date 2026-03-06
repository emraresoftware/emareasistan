"""
Admin paneli – Siparişler, kargo.
"""
import csv
import io
import json
from datetime import datetime

from fastapi import APIRouter, Request, HTTPException, Form
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse
from sqlalchemy import select, desc, func
from sqlalchemy import or_

from models.database import AsyncSessionLocal
from models import Order

from admin.common import templates, get_tenant_id
from admin import helpers

router = APIRouter()
PAGE_SIZE = helpers.PAGE_SIZE
require_module = helpers.require_module

CARGO_COMPANY_FILTERS = {
    "yurtici": ["yurtiçi", "yurtici", "yurticikargo"],
    "aras": ["aras"],
    "mng": ["mng", "mngkargo"],
    "ptt": ["ptt"],
    "surat": ["surat"],
    "ups": ["ups"],
    "dhl": ["dhl"],
    "hepsijet": ["hepsijet", "hepsi jet"],
    "sendeo": ["sendeo"],
    "kolaygelsin": ["kolaygelsin", "kolay gelsin"],
    "kargoist": ["kargoist"],
}


@router.get("/cargo", response_class=HTMLResponse)
@router.get("/cargo/{company}", response_class=HTMLResponse)
async def cargo_list(request: Request, company: str | None = None):
    """Kargo listeler. [GET /cargo]"""
    if request.session.get("admin") != "ok":
        return RedirectResponse(url="/admin", status_code=302)
    await require_module(request, "cargo")
    tid = get_tenant_id(request)
    filter_type = request.query_params.get("filter", "with_cargo")
    search_q = request.query_params.get("q", "").strip()
    page = max(1, int(request.query_params.get("page", 1)))
    from services.order.cargo import CargoService
    cargo_company_name = None
    if company and company in CARGO_COMPANY_FILTERS:
        names = {"yurtici": "Yurtiçi Kargo", "aras": "Aras Kargo", "mng": "MNG Kargo", "ptt": "PTT Kargo",
                 "surat": "Surat Kargo", "ups": "UPS", "dhl": "DHL", "hepsijet": "HepsiJet", "sendeo": "Sendeo",
                 "kolaygelsin": "Kolay Gelsin", "kargoist": "Kargoist"}
        cargo_company_name = names.get(company, company)
    async with AsyncSessionLocal() as db:
        base_q = select(Order).where(Order.tenant_id == tid).order_by(desc(Order.created_at))
        count_q = select(func.count(Order.id)).where(Order.tenant_id == tid)
        if filter_type == "with_cargo":
            base_q = base_q.where(Order.cargo_tracking_no.isnot(None), Order.cargo_tracking_no != "")
            count_q = count_q.where(Order.cargo_tracking_no.isnot(None), Order.cargo_tracking_no != "")
        elif filter_type == "no_cargo":
            base_q = base_q.where(
                (Order.cargo_tracking_no.is_(None)) | (Order.cargo_tracking_no == ""),
                Order.status.in_(["confirmed", "processing", "shipped"]),
            )
            count_q = count_q.where(
                (Order.cargo_tracking_no.is_(None)) | (Order.cargo_tracking_no == ""),
                Order.status.in_(["confirmed", "processing", "shipped"]),
            )
        if company and company in CARGO_COMPANY_FILTERS:
            patterns = CARGO_COMPANY_FILTERS[company]
            company_flt = or_(*[Order.cargo_company.ilike(f"%{p}%") for p in patterns])
            base_q = base_q.where(company_flt)
            count_q = count_q.where(company_flt)
        if search_q:
            flt = or_(
                Order.order_number.ilike(f"%{search_q}%"),
                Order.customer_name.ilike(f"%{search_q}%"),
                Order.customer_phone.ilike(f"%{search_q}%"),
                Order.cargo_tracking_no.ilike(f"%{search_q}%"),
            )
            base_q = base_q.where(flt)
            count_q = count_q.where(flt)
        total = (await db.execute(count_q)).scalar() or 0
        result = await db.execute(base_q.offset((page - 1) * PAGE_SIZE).limit(PAGE_SIZE))
        orders = result.scalars().all()
    cargo_svc = CargoService()
    tracking_urls = {}
    for o in orders:
        if o.cargo_tracking_no:
            info = await cargo_svc.track(o.cargo_tracking_no, o.cargo_company or "")
            tracking_urls[o.id] = info.get("tracking_url", "")
    total_pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)
    return templates.TemplateResponse("cargo_list.html", {
        "request": request,
        "orders": orders,
        "tracking_urls": tracking_urls,
        "filter": filter_type,
        "search_q": search_q,
        "page": page,
        "total_pages": total_pages,
        "total": total,
        "cargo_company": company,
        "cargo_company_name": cargo_company_name,
    })


@router.get("/orders", response_class=HTMLResponse)
async def orders_list(request: Request):
    """Siparişler listeler. [GET /orders]"""
    if request.session.get("admin") != "ok":
        return RedirectResponse(url="/admin", status_code=302)
    tid = get_tenant_id(request)
    status_filter = request.query_params.get("status", "")
    search_q = request.query_params.get("q", "").strip()
    page = max(1, int(request.query_params.get("page", 1)))
    async with AsyncSessionLocal() as db:
        base_q = select(Order).where(Order.tenant_id == tid).order_by(desc(Order.created_at))
        count_q = select(func.count(Order.id)).where(Order.tenant_id == tid)
        if status_filter:
            base_q = base_q.where(Order.status == status_filter)
            count_q = count_q.where(Order.status == status_filter)
        if search_q:
            flt = or_(
                Order.order_number.ilike(f"%{search_q}%"),
                Order.customer_name.ilike(f"%{search_q}%"),
                Order.customer_phone.ilike(f"%{search_q}%"),
            )
            base_q = base_q.where(flt)
            count_q = count_q.where(flt)
        total = (await db.execute(count_q)).scalar() or 0
        result = await db.execute(base_q.offset((page - 1) * PAGE_SIZE).limit(PAGE_SIZE))
        orders = result.scalars().all()
    total_pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)
    return templates.TemplateResponse("orders.html", {
        "request": request,
        "orders": orders,
        "status_filter": status_filter,
        "search_q": search_q,
        "page": page,
        "total_pages": total_pages,
        "total": total,
    })


@router.get("/orders/{id}", response_class=HTMLResponse)
async def order_detail(request: Request, id: int):
    """Sipariş detay sayfası. [GET /orders/{id}]"""
    if request.session.get("admin") != "ok":
        return RedirectResponse(url="/admin", status_code=302)
    tid = get_tenant_id(request)
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Order).where(Order.id == id, Order.tenant_id == tid))
        order = result.scalar_one_or_none()
    if not order:
        raise HTTPException(404)
    items = []
    if order.items:
        try:
            items = json.loads(order.items)
        except json.JSONDecodeError:
            pass
    return templates.TemplateResponse("order_detail.html", {
        "request": request,
        "order": order,
        "items": items,
    })


@router.post("/orders/{id}/update-status")
async def order_update_status(request: Request, id: int, status: str = Form()):
    """Sipariş durum sorgular. [POST /orders/{id}/update-status]"""
    if request.session.get("admin") != "ok":
        raise HTTPException(401)
    valid = ["pending", "confirmed", "processing", "shipped", "delivered", "cancelled"]
    if status not in valid:
        raise HTTPException(400, detail="Geçersiz durum")
    tid = get_tenant_id(request)
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Order).where(Order.id == id, Order.tenant_id == tid))
        order = result.scalar_one_or_none()
        if order:
            order.status = status
            await db.commit()
            if status != "pending" and order.customer_phone:
                try:
                    from services.whatsapp.agent import send_order_status_notification
                    await send_order_status_notification(
                        order.order_number,
                        order.customer_phone,
                        status,
                        order.cargo_tracking_no,
                        order.cargo_company,
                        tenant_id=order.tenant_id or 1,
                    )
                except Exception:
                    pass
    return RedirectResponse(url=f"/admin/orders/{id}", status_code=302)


@router.post("/orders/{id}/update-notes")
async def order_update_notes(request: Request, id: int, notes: str = Form("")):
    """Sipariş endpoint'i. [POST /orders/{id}/update-notes]"""
    if request.session.get("admin") != "ok":
        raise HTTPException(401)
    tid = get_tenant_id(request)
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Order).where(Order.id == id, Order.tenant_id == tid))
        order = result.scalar_one_or_none()
        if order:
            order.notes = notes.strip() or None
            await db.commit()
    return RedirectResponse(url=f"/admin/orders/{id}", status_code=302)


@router.get("/orders/export")
async def orders_export(request: Request):
    """Siparişler dışa aktarır. [GET /orders/export]"""
    if request.session.get("admin") != "ok":
        raise HTTPException(401)
    tid = get_tenant_id(request)
    status_filter = request.query_params.get("status", "")
    async with AsyncSessionLocal() as db:
        q = select(Order).where(Order.tenant_id == tid).order_by(desc(Order.created_at))
        if status_filter:
            q = q.where(Order.status == status_filter)
        result = await db.execute(q)
        orders = result.scalars().all()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Sipariş No", "Müşteri", "Telefon", "Adres", "Tutar", "Ödeme", "Durum", "Platform", "Tarih"])
    for o in orders:
        writer.writerow([
            o.order_number,
            o.customer_name or "",
            o.customer_phone or "",
            (o.customer_address or "").replace("\n", " "),
            o.total_amount,
            o.payment_option or "",
            o.status or "",
            o.platform or "",
            o.created_at.strftime("%Y-%m-%d %H:%M") if o.created_at else "",
        ])
    output.seek(0)
    filename = f"siparisler_{datetime.now().strftime('%Y%m%d_%H%M')}.csv"
    return StreamingResponse(
        iter([output.getvalue().encode("utf-8-sig")]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.post("/orders/{id}/update-cargo")
async def order_update_cargo(
    request: Request,
    id: int,
    tracking_no: str = Form(""),
    cargo_company: str = Form(""),
):
    """Sipariş endpoint'i. [POST /orders/{id}/update-cargo]"""
    if request.session.get("admin") != "ok":
        raise HTTPException(401)
    tid = get_tenant_id(request)
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Order).where(Order.id == id, Order.tenant_id == tid))
        order = result.scalar_one_or_none()
        if order:
            order.cargo_tracking_no = tracking_no or None
            order.cargo_company = cargo_company or None
            if tracking_no:
                order.status = "shipped"
            await db.commit()
            if tracking_no and order.customer_phone:
                try:
                    from services.whatsapp.agent import send_order_status_notification
                    await send_order_status_notification(
                        order.order_number,
                        order.customer_phone,
                        "shipped",
                        tracking_no,
                        order.cargo_company,
                        tenant_id=order.tenant_id or 1,
                    )
                except Exception:
                    pass
    return RedirectResponse(url=f"/admin/orders/{id}", status_code=302)
