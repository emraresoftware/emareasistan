#!/usr/bin/env python3
"""
Emare Asistan - FastAPI ana uygulama
API, admin panel, webhook'lar
"""
import logging
import shutil
import sys
from contextlib import asynccontextmanager

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import JSONResponse, RedirectResponse

logger = logging.getLogger(__name__)
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.sessions import SessionMiddleware

from config import get_settings
from admin import admin_router, partner_router
from integrations.bridge_api import router as bridge_router
from integrations.cron_api import router as cron_router
from integrations.whatsapp_webhook import router as whatsapp_webhook_router
from integrations.instagram_webhook import router as instagram_webhook_router
from integrations.whatsapp_qr import router as whatsapp_qr_router
from integrations.web_chat_api import router as web_chat_router
from integrations.support_chat_api import router as support_chat_router
from integrations.alert_api import router as alert_router
from fastapi.middleware.cors import CORSMiddleware
from middleware.admin_context import admin_context_middleware
from middleware.rate_limit import RateLimitMiddleware
from middleware.security_headers import SecurityHeadersMiddleware


@asynccontextmanager
async def lifespan(app):
    """Uygulama başlangıcında __pycache__ ve geçici dosyaları temizler."""
    root_dir = Path(__file__).resolve().parent
    cleaned = 0
    for cache_dir in root_dir.rglob("__pycache__"):
        if ".venv" in cache_dir.parts or "node_modules" in cache_dir.parts:
            continue
        shutil.rmtree(cache_dir, ignore_errors=True)
        cleaned += 1
    for db_name in ("test_asistan.db", "test.db"):
        db_file = root_dir / db_name
        if db_file.exists() and db_file.stat().st_size == 0:
            db_file.unlink(missing_ok=True)
    if cleaned:
        logger.info("Startup temizlik: %d __pycache__ silindi", cleaned)
    yield


app = FastAPI(title="Emare Asistan", docs_url="/docs", redoc_url="/redoc", lifespan=lifespan)

# === Emare Feedback ===
from feedback_router import router as feedback_router
app.include_router(feedback_router, prefix="/api/feedback", tags=["feedback"])
# ======================



# Path -> modül eşlemesi (admin route koruması için)
_PATH_MODULES = {
    "/admin/orders": "orders",
    "/admin/appointments": "appointments",
    "/admin/albums": "albums",
    "/admin/videos": "videos",
    "/admin/whatsapp": "whatsapp",
    "/admin/whatsapp/connection": "whatsapp",
    "/admin/whatsapp/settings": "whatsapp",
    "/admin/telegram": "telegram",
    "/admin/telegram/bot": "telegram",
    "/admin/telegram/settings": "telegram",
    "/admin/rules": "rules",
    "/admin/training": "training",
    "/admin/contacts": "contacts",
    "/admin/reminders": "reminders",
    "/admin/analytics": "analytics",
    "/admin/quick-replies": "quick_replies",
    "/admin/agent": "agent",
    "/admin/conversations": "conversations",
    "/admin/products": "products",
    "/admin/products/gallery": "products",
    "/admin/export-templates": "export_templates",
    "/admin/cargo": "cargo",
    "/admin/yurtici": "yurtici",
    "/admin/aras": "aras",
    "/admin/mng": "mng",
    "/admin/ups": "ups",
    "/admin/dhl": "dhl",
    "/admin/ptt": "ptt",
    "/admin/trendyol": "trendyol",
    "/admin/hepsiburada": "hepsiburada",
    "/admin/amazon": "amazon",
    "/admin/payment": "payment",
    "/admin/payment/links": "payment",
    "/admin/payment/settings": "payment",
    "/admin/stripe": "stripe",
    "/admin/stripe/settings": "stripe",
    "/admin/paypal": "paypal",
    "/admin/paypal/settings": "paypal",
    "/admin/instagram": "instagram",
    "/admin/instagram/setup": "instagram",
    "/admin/instagram/settings": "instagram",
    "/admin/workflows": "workflows",
    "/admin/process-config": "workflows",
}


@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """Yakalanmamış hataları logla; 500 yerine JSON dön (sunucu logunda traceback görünsün)."""
    logger.exception("Unhandled error: %s", exc)
    return JSONResponse(
        status_code=500,
        content={"detail": "Sunucu hatası. Lütfen tekrar deneyin."},
    )


# Web sohbet - harici sitelerden API erişimi için CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

# Session (admin panel girişi için) - önce session doldurulmalı ki admin_context okuyabilsin
# add_middleware: son eklenen önce çalışır. SessionMiddleware önce çalışsın diye SON ekleniyor.
settings = get_settings()
app.add_middleware(SecurityHeadersMiddleware)   # Güvenlik header'ları
app.add_middleware(RateLimitMiddleware)          # Rate limiting (IP bazlı)
app.add_middleware(BaseHTTPMiddleware, dispatch=admin_context_middleware)
app.add_middleware(SessionMiddleware, secret_key=settings.session_secret_key or "emare-change-me")

# Static (uploads + website)
root = Path(__file__).resolve().parent
uploads_dir = root / "uploads"
if uploads_dir.exists():
    app.mount("/uploads", StaticFiles(directory=str(uploads_dir)), name="uploads")
static_dir = root / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

# Router'lar
app.include_router(admin_router)
app.include_router(partner_router)
app.include_router(bridge_router)
app.include_router(cron_router)
app.include_router(whatsapp_webhook_router)
app.include_router(instagram_webhook_router)
app.include_router(whatsapp_qr_router)
app.include_router(web_chat_router)
app.include_router(support_chat_router)
app.include_router(alert_router)


@app.get("/")
async def homepage():
    """Ana sayfa — landing page."""
    from fastapi.responses import FileResponse
    index_path = Path(__file__).resolve().parent / "static" / "index.html"
    if index_path.exists():
        return FileResponse(index_path, media_type="text/html")
    return RedirectResponse(url="/admin")


import time as _time
_APP_START_TIME = _time.time()


@app.get("/health")
async def health():
    """Detaylı sağlık kontrolü — DB, bridge, uptime."""
    import httpx

    uptime_sec = int(_time.time() - _APP_START_TIME)
    hours, remainder = divmod(uptime_sec, 3600)
    minutes, seconds = divmod(remainder, 60)

    result = {
        "status": "ok",
        "uptime": f"{hours}h {minutes}m {seconds}s",
        "uptime_seconds": uptime_sec,
    }

    # DB kontrolü
    try:
        from models.database import get_db
        from sqlalchemy import text
        async for db in get_db():
            await db.execute(text("SELECT 1"))
            result["db"] = "ok"
            break
    except Exception as e:
        result["db"] = f"error: {str(e)[:80]}"
        result["status"] = "degraded"

    # Bridge kontrolü
    bridge_url = settings.asistan_api_url if hasattr(settings, 'asistan_api_url') else "http://localhost:3100"
    try:
        async with httpx.AsyncClient(timeout=3) as client:
            resp = await client.get(f"http://localhost:3100/api/status")
            if resp.status_code == 200:
                bridge_data = resp.json()
                result["bridge"] = "connected" if bridge_data.get("connected") else "disconnected"
            else:
                result["bridge"] = f"http {resp.status_code}"
    except Exception:
        result["bridge"] = "unreachable"

    return result


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=False)

