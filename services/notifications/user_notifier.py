"""
Kullanıcı bildirimleri - E-posta, SMS ile
Yeni sipariş, günlük özet vb. kullanıcıya kendi numarası/epostası üzerinden gider.
"""
import json
import logging
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config import get_settings
from models import User, Order
from services.integration.email import get_smtp_config_for_tenant, _send_with_config

logger = logging.getLogger(__name__)

# Bildirim türleri
NOTIFY_NEW_ORDER = "new_order"
NOTIFY_DAILY_DIGEST = "daily_digest"
NOTIFY_NEW_MESSAGE = "new_message"  # gelecekte


def _parse_notification_settings(settings_json: Optional[str]) -> dict:
    """notification_settings JSON'dan dict döndür"""
    if not settings_json or not str(settings_json).strip():
        return {}
    try:
        return json.loads(settings_json)
    except json.JSONDecodeError:
        return {}


def _user_wants_notification(user: User, event_type: str) -> bool:
    """Kullanıcı bu olay için bildirim istiyor mu?"""
    s = _parse_notification_settings(user.notification_settings)
    if event_type == NOTIFY_NEW_MESSAGE and event_type not in s:
        return True
    return bool(s.get(event_type, False))


def _get_user_channels(settings_json: Optional[str]) -> list[str]:
    """Hangi kanallara gönderilsin: email, sms"""
    s = _parse_notification_settings(settings_json)
    ch = s.get("channels")
    if isinstance(ch, list):
        return [c for c in ch if c in ("email", "sms")]
    return ["email"]  # varsayılan


async def _get_tenant_users_for_notify(db: AsyncSession, tenant_id: int) -> list[User]:
    """Tenant'a bağlı, bildirim almak isteyen aktif kullanıcılar"""
    r = await db.execute(
        select(User).where(
            User.tenant_id == tenant_id,
            User.is_active == True,
        )
    )
    return list(r.scalars().all())


def _normalize_phone(phone: str) -> str:
    """Türkiye formatı: 905321234567"""
    if not phone:
        return ""
    digits = "".join(c for c in str(phone) if c.isdigit())
    if not digits:
        return ""
    if len(digits) == 10 and digits.startswith("5"):
        return "90" + digits
    if len(digits) == 11 and digits.startswith("0"):
        return "9" + digits[1:]
    if len(digits) == 11 and digits.startswith("9"):
        return digits
    return digits


async def send_sms(phone: str, message: str) -> bool:
    """Netgsm ile SMS gönder"""
    settings = get_settings()
    if not settings.netgsm_usercode or not settings.netgsm_password:
        return False
    phone = _normalize_phone(phone)
    if not phone or len(phone) < 10:
        return False
    try:
        import httpx
        url = "https://api.netgsm.com.tr/sms/send/get"
        params = {
            "usercode": settings.netgsm_usercode,
            "password": settings.netgsm_password,
            "gsmno": phone,
            "message": message[:160],  # Tek mesaj sınırı
            "msgheader": (settings.netgsm_msgheader or "EMARE")[:11],
        }
        async with httpx.AsyncClient(timeout=10.0) as c:
            r = await c.get(url, params=params)
        if r.status_code == 200 and "00" in r.text:
            return True
        logger.warning("Netgsm SMS failed: %s %s", r.status_code, r.text[:200])
        return False
    except Exception as e:
        logger.exception("SMS send error: %s", e)
        return False


async def notify_new_order(
    db: AsyncSession,
    order: Order,
    tenant_id: int,
    tenant_name: str,
) -> None:
    """
    Yeni sipariş bildirimi - tenant kullanıcılarına e-posta/SMS
    """
    users = await _get_tenant_users_for_notify(db, tenant_id)
    smtp_config = await get_smtp_config_for_tenant(tenant_id)
    if not smtp_config:
        from config import get_settings
        s = get_settings()
        smtp_config = {
            "host": s.smtp_host or "",
            "port": s.smtp_port or 587,
            "user": s.smtp_user or "",
            "password": s.smtp_password or "",
            "from_addr": s.smtp_from or "",
            "from_name": "Emare Asistan",
        }

    items_preview = ""
    try:
        items = json.loads(order.items or "[]")
        items_preview = ", ".join(
            f"{i.get('name','?')} x{i.get('quantity',1)}" for i in items[:3]
        )
        if len(items) > 3:
            items_preview += f" (+{len(items)-3} ürün)"
    except Exception:
        items_preview = "Ürünler"

    subject = f"🔔 Yeni sipariş: {order.order_number} - {tenant_name}"
    text_short = f"Yeni sipariş #{order.order_number}: {order.customer_name}, {order.total_amount} TL. {items_preview}"
    html_body = f"""
    <html><head><meta charset="utf-8"></head><body style="font-family:system-ui;line-height:1.6;color:#334155;">
    <h2 style="color:#059669;">Yeni Sipariş</h2>
    <p><strong>Sipariş No:</strong> {order.order_number}</p>
    <p><strong>Müşteri:</strong> {order.customer_name} - {order.customer_phone}</p>
    <p><strong>Tutar:</strong> {order.total_amount} TL</p>
    <p><strong>Ürünler:</strong> {items_preview}</p>
    <p style="margin-top:1.5rem;"><a href="{{app_base}}/admin/orders" style="background:#059669;color:#fff;padding:0.5rem 1rem;text-decoration:none;border-radius:8px;">Siparişlere Git</a></p>
    <p style="font-size:0.85rem;color:#94a3b8;">Emare Asistan</p>
    </body></html>
    """.replace("{{app_base}}", get_settings().app_base_url.rstrip("/"))

    for user in users:
        if not _user_wants_notification(user, NOTIFY_NEW_ORDER):
            continue
        channels = _get_user_channels(user.notification_settings)

        if "email" in channels and user.email:
            if smtp_config and smtp_config.get("host") and smtp_config.get("user"):
                try:
                    _send_with_config(smtp_config, user.email, subject, html_body)
                except Exception as e:
                    logger.exception("Notify email failed for %s: %s", user.email, e)

        if "sms" in channels and user.phone:
            try:
                await send_sms(user.phone, f"Yeni siparis #{order.order_number}: {order.total_amount} TL - {tenant_name}")
            except Exception as e:
                logger.exception("Notify SMS failed for %s: %s", user.phone, e)


async def send_daily_digest(db: AsyncSession) -> int:
    """
    Günlük özet e-postası - daily_digest tercihi açık kullanıcılara.
    Dünkü sipariş, sohbet sayıları vb.
    Returns: gönderilen e-posta sayısı
    """
    from datetime import datetime, timedelta
    from sqlalchemy import select, func
    from models import Order, Conversation, Message

    yesterday_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=1)
    yesterday_end = yesterday_start + timedelta(days=1)
    sent = 0

    r = await db.execute(
        select(User).where(
            User.is_active == True,
            User.tenant_id.isnot(None),
        )
    )
    users = list(r.scalars().all())

    for user in users:
        if not _user_wants_notification(user, NOTIFY_DAILY_DIGEST):
            continue
        channels = _get_user_channels(user.notification_settings)
        if "email" not in channels or not user.email:
            continue

        tenant_id = user.tenant_id
        if not tenant_id:
            continue

        # Dünkü sipariş sayısı
        order_count = await db.execute(
            select(func.count(Order.id)).where(
                Order.tenant_id == tenant_id,
                Order.created_at >= yesterday_start,
                Order.created_at < yesterday_end,
            )
        )
        order_count = order_count.scalar() or 0

        # Dünkü sohbet/mesaj sayısı
        msg_count = await db.execute(
            select(func.count(Message.id))
            .select_from(Message)
            .join(Conversation, Message.conversation_id == Conversation.id)
            .where(
                Conversation.tenant_id == tenant_id,
                Message.created_at >= yesterday_start,
                Message.created_at < yesterday_end,
            )
        )
        msg_count = msg_count.scalar() or 0

        smtp_config = await get_smtp_config_for_tenant(tenant_id)
        if not smtp_config:
            from config import get_settings
            s = get_settings()
            smtp_config = {
                "host": s.smtp_host or "",
                "port": s.smtp_port or 587,
                "user": s.smtp_user or "",
                "password": s.smtp_password or "",
                "from_addr": s.smtp_from or "",
                "from_name": "Emare Asistan",
            }

        if not smtp_config.get("host") or not smtp_config.get("user"):
            continue

        date_str = yesterday_start.strftime("%d.%m.%Y")
        subject = f"📊 Günlük Özet - {date_str} | Emare Asistan"
        html = f"""
        <html><head><meta charset="utf-8"></head><body style="font-family:system-ui;line-height:1.6;color:#334155;">
        <h2>Günlük Özet</h2>
        <p><strong>Tarih:</strong> {date_str}</p>
        <p><strong>Sipariş sayısı:</strong> {order_count}</p>
        <p><strong>Mesaj sayısı:</strong> {msg_count}</p>
        <p style="margin-top:1.5rem;"><a href="{get_settings().app_base_url.rstrip('/')}/admin/dashboard" style="background:#0f172a;color:#fff;padding:0.5rem 1rem;text-decoration:none;border-radius:8px;">Panele Git</a></p>
        <p style="font-size:0.85rem;color:#94a3b8;">Emare Asistan</p>
        </body></html>
        """

        try:
            _send_with_config(smtp_config, user.email, subject, html)
            sent += 1
        except Exception as e:
            logger.exception("Daily digest failed for %s: %s", user.email, e)

    return sent


async def notify_important_message(
    db: AsyncSession,
    tenant_id: int,
    tenant_name: str,
    source: str,
    sender: str,
    subject: str,
    preview: str,
) -> None:
    """
    Önemli gelen mesaj bildirimi (email/sms).
    Kullanıcının notification_settings içinde new_message etkinse gönderilir.
    """
    users = await _get_tenant_users_for_notify(db, tenant_id)
    smtp_config = await get_smtp_config_for_tenant(tenant_id)
    if not smtp_config:
        s = get_settings()
        smtp_config = {
            "host": s.smtp_host or "",
            "port": s.smtp_port or 587,
            "user": s.smtp_user or "",
            "password": s.smtp_password or "",
            "from_addr": s.smtp_from or "",
            "from_name": "Emare Asistan",
        }

    safe_subject = (subject or "(Konu yok)").strip()[:180]
    safe_sender = (sender or "-").strip()[:180]
    safe_preview = (preview or "").strip().replace("\n", " ")[:220]
    source_name = (source or "mesaj").strip()[:40]

    mail_subject = f"🚨 Önemli {source_name} mesajı - {tenant_name}"
    mail_html = f"""
    <html><head><meta charset=\"utf-8\"></head><body style=\"font-family:system-ui;line-height:1.6;color:#334155;\">
    <h2 style=\"color:#dc2626;\">Önemli Gelen Mesaj</h2>
    <p><strong>Kaynak:</strong> {source_name}</p>
    <p><strong>Gönderen:</strong> {safe_sender}</p>
    <p><strong>Konu:</strong> {safe_subject}</p>
    <p><strong>Önizleme:</strong> {safe_preview}</p>
    <p style=\"margin-top:1.2rem;\"><a href=\"{get_settings().app_base_url.rstrip('/')}/admin/conversations\" style=\"background:#dc2626;color:#fff;padding:0.5rem 1rem;text-decoration:none;border-radius:8px;\">Sohbetlere Git</a></p>
    </body></html>
    """

    sms_text = f"Onemli {source_name} mesaji: {safe_subject} | {safe_sender}"[:160]

    for user in users:
        if not _user_wants_notification(user, NOTIFY_NEW_MESSAGE):
            continue
        channels = _get_user_channels(user.notification_settings)

        if "email" in channels and user.email and smtp_config.get("host") and smtp_config.get("user"):
            try:
                _send_with_config(smtp_config, user.email, mail_subject, mail_html)
            except Exception as e:
                logger.exception("Important message email notify failed for %s: %s", user.email, e)

        if "sms" in channels and user.phone:
            try:
                await send_sms(user.phone, sms_text)
            except Exception as e:
                logger.exception("Important message SMS notify failed for %s: %s", user.phone, e)
