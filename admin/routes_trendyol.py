"""
Admin paneli – Trendyol Entegrasyonu
======================================
Soru-Cevap yönetimi, sipariş senkronizasyonu, yorum analizi,
otomatik yanıt kuralları ve AI ayarları.
"""
import json
import logging
from datetime import datetime

from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.database import AsyncSessionLocal
from models import Tenant

from admin.common import templates, get_tenant_id
from admin import helpers

router = APIRouter()
require_module = helpers.require_module
logger = logging.getLogger("admin.trendyol")


# ════════════════════════════════════════════════════════
# YARDIMCI
# ════════════════════════════════════════════════════════

async def _get_trendyol_settings(db: AsyncSession, tenant_id: int) -> dict:
    result = await db.execute(select(Tenant).where(Tenant.id == tenant_id))
    tenant = result.scalar_one_or_none()
    if not tenant:
        return {}
    return (tenant.settings or {}).get("trendyol", {})


async def _save_trendyol_settings(db: AsyncSession, tenant_id: int, settings: dict):
    result = await db.execute(select(Tenant).where(Tenant.id == tenant_id))
    tenant = result.scalar_one_or_none()
    if not tenant:
        return
    s = dict(tenant.settings or {})
    s["trendyol"] = settings
    tenant.settings = s
    await db.commit()


# ════════════════════════════════════════════════════════
# ANA SAYFA — TRENDYOL DASHBOARD
# ════════════════════════════════════════════════════════

@router.get("/trendyol", response_class=HTMLResponse)
async def trendyol_dashboard(request: Request):
    """Trendyol entegrasyon ana sayfası."""
    if request.session.get("admin") != "ok":
        return RedirectResponse(url="/admin", status_code=302)
    await require_module(request, "trendyol")
    tid = get_tenant_id(request)

    async with AsyncSessionLocal() as db:
        settings = await _get_trendyol_settings(db, tid)

    # İstatistikler
    question_log = settings.get("question_log", [])
    pending_questions = settings.get("pending_questions", [])
    auto_responses = settings.get("auto_responses", {})
    reviews_cache = settings.get("reviews_cache", {})

    total_questions = len(question_log)
    answered_count = sum(1 for q in question_log if q.get("answered"))
    pending_count = len([p for p in pending_questions if p.get("status") == "pending"])
    review_count = settings.get("reviews_total", 0)
    review_products = settings.get("reviews_products", 0)
    auto_response_count = len(auto_responses)

    # Yöntem dağılımı
    method_counts = {}
    for q in question_log:
        m = q.get("method", "unknown")
        method_counts[m] = method_counts.get(m, 0) + 1

    # Kategori dağılımı
    category_counts = {}
    for q in question_log:
        c = q.get("category", "diger")
        category_counts[c] = category_counts.get(c, 0) + 1

    last_sync = settings.get("last_sync", "Henüz senkronize edilmedi")
    last_sync_stats = settings.get("last_sync_stats", {})

    return templates.TemplateResponse("trendyol_dashboard.html", {
        "request": request,
        "total_questions": total_questions,
        "answered_count": answered_count,
        "pending_count": pending_count,
        "pending_questions": pending_questions[:50],
        "review_count": review_count,
        "review_products": review_products,
        "auto_response_count": auto_response_count,
        "method_counts": method_counts,
        "category_counts": category_counts,
        "question_log": question_log[-50:][::-1],
        "last_sync": last_sync,
        "last_sync_stats": last_sync_stats,
        "settings": settings,
        "auto_responses": auto_responses,
    })


# ════════════════════════════════════════════════════════
# SORU SENKRONİZASYONU (MANUEL)
# ════════════════════════════════════════════════════════

@router.post("/trendyol/sync-questions")
async def trendyol_sync_questions(request: Request):
    """Trendyol sorularını manuel senkronize et."""
    if request.session.get("admin") != "ok":
        return JSONResponse({"error": "Unauthorized"}, status_code=401)
    await require_module(request, "trendyol")
    tid = get_tenant_id(request)

    from services.trendyol.sync import sync_questions
    stats = await sync_questions(tid)
    return JSONResponse({"ok": True, "stats": stats})


# ════════════════════════════════════════════════════════
# SİPARİŞ SENKRONİZASYONU
# ════════════════════════════════════════════════════════

@router.post("/trendyol/sync-orders")
async def trendyol_sync_orders(request: Request):
    """Trendyol siparişlerini senkronize et."""
    if request.session.get("admin") != "ok":
        return JSONResponse({"error": "Unauthorized"}, status_code=401)
    await require_module(request, "trendyol")
    tid = get_tenant_id(request)

    from services.trendyol.sync import sync_orders
    stats = await sync_orders(tid)
    return JSONResponse({"ok": True, "stats": stats})


# ════════════════════════════════════════════════════════
# YORUM SENKRONİZASYONU
# ════════════════════════════════════════════════════════

@router.post("/trendyol/sync-reviews")
async def trendyol_sync_reviews(request: Request):
    """Trendyol yorumlarını senkronize et."""
    if request.session.get("admin") != "ok":
        return JSONResponse({"error": "Unauthorized"}, status_code=401)
    await require_module(request, "trendyol")
    tid = get_tenant_id(request)

    from services.trendyol.sync import sync_reviews
    stats = await sync_reviews(tid)
    return JSONResponse({"ok": True, "stats": stats})


# ════════════════════════════════════════════════════════
# BEKLEYEN SORU ONAYLA / REDDET
# ════════════════════════════════════════════════════════

@router.post("/trendyol/pending/{question_id}/approve")
async def trendyol_approve_question(request: Request, question_id: int):
    """Bekleyen soruyu onayla ve yanıtla."""
    if request.session.get("admin") != "ok":
        return JSONResponse({"error": "Unauthorized"}, status_code=401)
    await require_module(request, "trendyol")
    tid = get_tenant_id(request)

    body = await request.json()
    answer_text = body.get("answer", "").strip()
    if not answer_text:
        return JSONResponse({"error": "Yanıt boş olamaz"}, status_code=400)

    from services.trendyol.api import answer_question
    async with AsyncSessionLocal() as db:
        ok, msg = await answer_question(tid, question_id, answer_text)
        if ok:
            # Bekleyen listeden kaldır
            settings = await _get_trendyol_settings(db, tid)
            pending = settings.get("pending_questions", [])
            settings["pending_questions"] = [
                p for p in pending if p.get("question_id") != question_id
            ]
            # Log'a ekle
            log = settings.get("question_log", [])
            log.append({
                "question_id": question_id,
                "question": body.get("question", ""),
                "answer": answer_text,
                "method": "manual_approved",
                "confidence": 1.0,
                "category": body.get("category", ""),
                "timestamp": datetime.now().isoformat(),
                "answered": True,
            })
            settings["question_log"] = log[-500:]
            await _save_trendyol_settings(db, tid, settings)

    if ok:
        return JSONResponse({"ok": True})
    return JSONResponse({"error": msg}, status_code=500)


@router.post("/trendyol/pending/{question_id}/reject")
async def trendyol_reject_question(request: Request, question_id: int):
    """Bekleyen soruyu reddet / sil."""
    if request.session.get("admin") != "ok":
        return JSONResponse({"error": "Unauthorized"}, status_code=401)
    await require_module(request, "trendyol")
    tid = get_tenant_id(request)

    async with AsyncSessionLocal() as db:
        settings = await _get_trendyol_settings(db, tid)
        pending = settings.get("pending_questions", [])
        settings["pending_questions"] = [
            p for p in pending if p.get("question_id") != question_id
        ]
        await _save_trendyol_settings(db, tid, settings)

    return JSONResponse({"ok": True})


# ════════════════════════════════════════════════════════
# OTOMATİK YANIT KURALLARI CRUD
# ════════════════════════════════════════════════════════

@router.post("/trendyol/auto-responses/add")
async def trendyol_add_auto_response(request: Request):
    """Yeni otomatik yanıt kuralı ekle."""
    if request.session.get("admin") != "ok":
        return JSONResponse({"error": "Unauthorized"}, status_code=401)
    await require_module(request, "trendyol")
    tid = get_tenant_id(request)

    body = await request.json()
    keywords = body.get("keywords", "").strip()
    response = body.get("response", "").strip()
    if not keywords or not response:
        return JSONResponse({"error": "Alanlar boş olamaz"}, status_code=400)

    async with AsyncSessionLocal() as db:
        settings = await _get_trendyol_settings(db, tid)
        auto_resp = settings.get("auto_responses", {})
        auto_resp[keywords] = response
        settings["auto_responses"] = auto_resp
        await _save_trendyol_settings(db, tid, settings)

    return JSONResponse({"ok": True, "total": len(auto_resp)})


@router.post("/trendyol/auto-responses/delete")
async def trendyol_delete_auto_response(request: Request):
    """Otomatik yanıt kuralı sil."""
    if request.session.get("admin") != "ok":
        return JSONResponse({"error": "Unauthorized"}, status_code=401)
    await require_module(request, "trendyol")
    tid = get_tenant_id(request)

    body = await request.json()
    keywords = body.get("keywords", "")

    async with AsyncSessionLocal() as db:
        settings = await _get_trendyol_settings(db, tid)
        auto_resp = settings.get("auto_responses", {})
        auto_resp.pop(keywords, None)
        settings["auto_responses"] = auto_resp
        await _save_trendyol_settings(db, tid, settings)

    return JSONResponse({"ok": True})


# ════════════════════════════════════════════════════════
# TRENDYOL AYARLAR
# ════════════════════════════════════════════════════════

@router.post("/trendyol/settings")
async def trendyol_save_settings(request: Request):
    """Trendyol modül ayarlarını kaydet."""
    if request.session.get("admin") != "ok":
        return JSONResponse({"error": "Unauthorized"}, status_code=401)
    await require_module(request, "trendyol")
    tid = get_tenant_id(request)

    body = await request.json()
    allowed_keys = {
        "auto_send_keyword", "auto_send_fuzzy", "auto_send_ai",
        "confidence_threshold", "fuzzy_threshold",
        "gemini_enabled", "gemini_model", "gemini_temperature", "gemini_max_tokens",
        "system_prompt", "blacklist", "poll_interval",
        "work_hours_start", "work_hours_end",
    }

    async with AsyncSessionLocal() as db:
        settings = await _get_trendyol_settings(db, tid)
        for k, v in body.items():
            if k in allowed_keys:
                settings[k] = v
        await _save_trendyol_settings(db, tid, settings)

    return JSONResponse({"ok": True})


# ════════════════════════════════════════════════════════
# BAĞLANTI TESTİ
# ════════════════════════════════════════════════════════

@router.post("/trendyol/test-connection")
async def trendyol_test_connection(request: Request):
    """Trendyol API bağlantısını test et."""
    if request.session.get("admin") != "ok":
        return JSONResponse({"error": "Unauthorized"}, status_code=401)
    await require_module(request, "trendyol")
    tid = get_tenant_id(request)

    from services.trendyol.api import check_connection
    async with AsyncSessionLocal() as db:
        ok, msg = await check_connection(tid)

    return JSONResponse({"ok": ok, "message": msg})
