"""
WhatsApp Connection Health Monitor - 5 dakikada bir bridge durumunu kontrol eder,
DB'deki status ve phone_number alanlarını günceller.
"""
import asyncio
import logging
from datetime import datetime, timedelta

import httpx

from config import get_settings
from models.database import AsyncSessionLocal
from models import WhatsAppConnection
from sqlalchemy import select
from services.core.tenant import get_tenant_settings

logger = logging.getLogger(__name__)
_CHECK_INTERVAL = 300  # 5 dakika
_last_alert_at: dict[str, datetime] = {}


def _should_send_alert(key: str, cooldown_minutes: int = 30) -> bool:
    now = datetime.utcnow()
    last = _last_alert_at.get(key)
    if last and now - last < timedelta(minutes=cooldown_minutes):
        return False
    _last_alert_at[key] = now
    return True


async def _notify_health_issue(tenant_id: int, conn: WhatsAppConnection, status: str) -> None:
    settings = await get_tenant_settings(tenant_id)
    email = (settings.get("health_alert_email") or "").strip()
    sms_webhook = (settings.get("health_alert_sms_webhook") or "").strip()
    text = (
        f"WhatsApp baglanti uyarisi\n"
        f"Tenant: {tenant_id}\n"
        f"Baglanti: {conn.name} (id={conn.id})\n"
        f"Durum: {status}\n"
        f"Zaman: {datetime.utcnow().isoformat(timespec='seconds')} UTC"
    )

    if email:
        try:
            import smtplib
            from email.mime.text import MIMEText
            from email.utils import formataddr

            app_cfg = get_settings()
            if app_cfg.smtp_host and app_cfg.smtp_user:
                msg = MIMEText(text, "plain", "utf-8")
                msg["Subject"] = "Emare Asistan - WhatsApp Health Uyarisi"
                msg["From"] = formataddr(("Emare Asistan", app_cfg.smtp_from))
                msg["To"] = email
                with smtplib.SMTP(app_cfg.smtp_host, app_cfg.smtp_port) as server:
                    server.starttls()
                    server.login(app_cfg.smtp_user, app_cfg.smtp_password or "")
                    server.sendmail(app_cfg.smtp_from, email, msg.as_string())
        except Exception as e:
            logger.warning("Health alert email gonderilemedi: %s", e)

    if sms_webhook and (sms_webhook.startswith("http://") or sms_webhook.startswith("https://")):
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                await client.post(sms_webhook, json={"text": text, "tenant_id": tenant_id, "connection_id": conn.id, "status": status})
        except Exception as e:
            logger.warning("Health alert sms webhook gonderilemedi: %s", e)


async def _check_whatsapp_connections():
    """Bridge'den bağlantı durumlarını al, DB'yi güncelle"""
    bridge_url = (get_settings().whatsapp_bridge_url or "http://localhost:3100").rstrip("/")
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.get(f"{bridge_url}/api/connections")
        if r.status_code != 200:
            return
        bridge_list = r.json()
    except Exception as e:
        logger.debug("WhatsApp health check: bridge erişilemedi: %s", e)
        return

    bridge_map = {str(c.get("id")): c for c in bridge_list if c.get("id") is not None}

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(WhatsAppConnection).where(WhatsAppConnection.is_active == True)
        )
        connections = result.scalars().all()

        for conn in connections:
            bc = bridge_map.get(str(conn.id), {})
            new_status = bc.get("status") or "disconnected"
            new_phone = bc.get("phone") or None

            updated = False
            if (conn.status or "disconnected") != new_status:
                conn.status = new_status
                updated = True
            if (conn.phone_number or "") != (new_phone or ""):
                conn.phone_number = new_phone
                updated = True

            if updated:
                await db.commit()
                logger.info("WhatsApp connection %s (%s): status=%s phone=%s", conn.id, conn.name, new_status, new_phone)
                if new_status != "connected":
                    key = f"{conn.id}:{new_status}"
                    if _should_send_alert(key):
                        await _notify_health_issue(conn.tenant_id or 1, conn, new_status)


async def run_health_loop():
    """Arka planda 5 dakikada bir çalışan döngü"""
    await asyncio.sleep(60)  # İlk 1 dk bekle (uygulama ısınsın)
    while True:
        try:
            await _check_whatsapp_connections()
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.warning("WhatsApp health check hatası: %s", e)
        await asyncio.sleep(_CHECK_INTERVAL)
