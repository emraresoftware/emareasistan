"""
Cron API - Arka plan işleri için endpoint'ler.
Sistem cron'u ile periyodik çağrılır (örn. */10 * * * * curl .../api/cron/abandoned-cart?key=SECRET)
"""
from __future__ import annotations
from fastapi import APIRouter, HTTPException, Query

from config import get_settings
from models.database import AsyncSessionLocal
from services.order.abandoned_cart import send_abandoned_cart_reminders
from services.workflow.proactive import send_proactive_messages
from services.notifications import send_daily_digest

router = APIRouter(prefix="/api/cron", tags=["cron"])


def _check_cron_key(key: str | None) -> bool:
    """Cron endpoint'leri için basit anahtar kontrolü"""
    secret = (get_settings().cron_secret_key or "").strip()
    if not secret:
        return True  # Anahtar tanımlanmamışsa herkese açık (güvenlik riski - production'da tanımlayın)
    return key == secret


@router.post("/abandoned-cart")
async def cron_abandoned_cart(key: str | None = Query(None)):
    """
    Sepet terk hatırlatması - 1 saat önce siparişe başlayıp bırakan müşterilere mesaj.
    Cron: */10 * * * * curl -X POST "http://localhost:8000/api/cron/abandoned-cart?key=SECRET"
    """
    if not _check_cron_key(key):
        raise HTTPException(403, detail="Geçersiz cron anahtarı")
    async with AsyncSessionLocal() as db:
        count = await send_abandoned_cart_reminders(db)
    return {"ok": True, "sent": count}


@router.post("/proactive")
async def cron_proactive_messages(key: str | None = Query(None)):
    """
    Proaktif mesajlaşma tetikleyici.
    Cron: */30 * * * * curl -X POST "http://localhost:8000/api/cron/proactive?key=SECRET"
    """
    if not _check_cron_key(key):
        raise HTTPException(403, detail="Geçersiz cron anahtarı")
    async with AsyncSessionLocal() as db:
        count = await send_proactive_messages(db)
    return {"ok": True, "sent": count}


@router.post("/daily-digest")
async def cron_daily_digest(key: str | None = Query(None)):
    """
    Günlük özet e-postası - bildirim tercihinde daily_digest açık kullanıcılara.
    Cron: 0 8 * * * curl -X POST "http://localhost:8000/api/cron/daily-digest?key=SECRET"
    (Her sabah 08:00)
    """
    if not _check_cron_key(key):
        raise HTTPException(403, detail="Geçersiz cron anahtarı")
    async with AsyncSessionLocal() as db:
        count = await send_daily_digest(db)
    return {"ok": True, "sent": count}


@router.post("/trendyol-sync")
async def cron_trendyol_sync(key: str | None = Query(None)):
    """
    Trendyol senkronizasyonu - sorular, siparişler, yorumlar.
    Cron: */15 * * * * curl -X POST "http://localhost:8000/api/cron/trendyol-sync?key=SECRET"
    """
    if not _check_cron_key(key):
        raise HTTPException(403, detail="Geçersiz cron anahtarı")
    from services.trendyol.sync import sync_all_tenants
    results = await sync_all_tenants()
    return {"ok": True, "tenants": len(results), "results": results}


@router.post("/email-poll")
async def cron_email_poll(key: str | None = Query(None)):
    """
    E-posta kutusu tarama — POP3 ile yeni mailleri okur, AI ile yanıtlar.
    Her tenant için ayrı POP3 ayarı gerekir (panel → Ayarlar → E-posta Kanalı).

    Cron: */5 * * * * curl -X POST "http://localhost:8000/api/cron/email-poll?key=SECRET"
    """
    if not _check_cron_key(key):
        raise HTTPException(403, detail="Geçersiz cron anahtarı")
    from integrations.email_channel import poll_all_tenants
    results = await poll_all_tenants()
    total = sum(v for v in results.values() if v > 0)
    return {"ok": True, "total_replied": total, "tenants": results}
