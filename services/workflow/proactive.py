"""
Proaktif mesajlaşma servisi.
Belirli süre pasif kalan sohbetlere otomatik hatırlatma mesajı gönderir.
"""
import json
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models import Conversation, Message, Order, WhatsAppConnection
from services.whatsapp.agent import send_agent_message_to_customer
from services.core.tenant import get_tenant_settings


DEFAULT_TEMPLATE = "Merhaba {name}, size yardimci olmamizi ister misiniz? Uygun oldugunuzda yazabilirsiniz."


def _render_template(template: str, conv: Conversation) -> str:
    name = (conv.customer_name or "").strip() or "degerli musterimiz"
    return (template or DEFAULT_TEMPLATE).replace("{name}", name)


async def _segment_match(db: AsyncSession, conv: Conversation, settings: dict) -> bool:
    segment = (settings.get("proactive_segment") or "all").strip().lower()
    if segment in ("all", ""):
        return True
    phone = (conv.customer_phone or "").strip()
    if not phone:
        return segment in ("new_customer",)

    if conv.tenant_id is None:
        return False
    q = await db.execute(
        select(Order).where(
            Order.tenant_id == conv.tenant_id,
            Order.customer_phone == phone,
        )
    )
    orders = q.scalars().all()
    if segment == "new_customer":
        return len(orders) == 0
    if segment == "has_order":
        return len(orders) > 0
    if segment == "high_value":
        min_total = float(settings.get("proactive_segment_min_order_total") or 0)
        total = sum(float(o.total_amount or 0) for o in orders)
        return total >= max(0.0, min_total)
    return True


async def send_proactive_messages(db: AsyncSession) -> int:
    """
    Uygun sohbetlere proaktif mesaj gonder.
    Kural:
    - Tenant ayarinda proactive_enabled=true olmali
    - Son mesajdan sonra inactivity_hours (vars. 24) gecmeli
    - Son proaktif mesajin ustunden en az 24 saat gecmeli
    """
    now = datetime.utcnow()
    broad_cutoff = now - timedelta(hours=1)
    result = await db.execute(
        select(Conversation)
        .where(
            Conversation.platform == "whatsapp",
            Conversation.agent_taken_over_at.is_(None),
            Conversation.last_message_at <= broad_cutoff,
        )
        .order_by(Conversation.last_message_at.asc())
        .limit(300)
    )
    conversations = result.scalars().all()
    sent = 0

    for conv in conversations:
        if conv.tenant_id is None:
            # Tenant'siz kayıtlar proaktif akışa alınmaz.
            continue
        tid = int(conv.tenant_id)
        settings = await get_tenant_settings(tid)
        if not settings.get("proactive_enabled"):
            continue
        if not await _segment_match(db, conv, settings):
            continue
        inactivity_hours = int(settings.get("proactive_inactivity_hours") or 24)
        if inactivity_hours < 1:
            inactivity_hours = 24
        if conv.last_message_at and conv.last_message_at > now - timedelta(hours=inactivity_hours):
            continue
        if conv.proactive_message_sent_at and conv.proactive_message_sent_at > now - timedelta(hours=24):
            continue

        # Sessiz saat kuralı (tenant local saat için basit UTC saat kullanımı)
        quiet_start = int(settings.get("proactive_quiet_hours_start") or 23)
        quiet_end = int(settings.get("proactive_quiet_hours_end") or 9)
        now_hour = now.hour
        if quiet_start != quiet_end:
            if quiet_start < quiet_end:
                in_quiet = quiet_start <= now_hour < quiet_end
            else:
                in_quiet = now_hour >= quiet_start or now_hour < quiet_end
            if in_quiet:
                continue

        # Haftalık tenant limiti
        weekly_limit = int(settings.get("proactive_weekly_limit") or 2)
        if weekly_limit > 0:
            week_start = now - timedelta(days=7)
            weekly_q = await db.execute(
                select(Message.id)
                .join(Conversation, Message.conversation_id == Conversation.id)
                .where(
                    Conversation.tenant_id == tid,
                    Message.role == "assistant",
                    Message.created_at >= week_start,
                    Message.extra_data.like('%"proactive": true%'),
                )
            )
            proactive_count = len(weekly_q.scalars().all())
            if proactive_count >= weekly_limit:
                continue

        template = settings.get("proactive_template") or DEFAULT_TEMPLATE
        if settings.get("proactive_ab_enabled"):
            template_b = (settings.get("proactive_template_b") or "").strip()
            if template_b and (conv.id % 2 == 0):
                template = template_b
        text = _render_template(template, conv)
        user_id = (conv.platform_user_id or conv.customer_phone or "").strip()
        if not user_id:
            continue
        connection_id = None
        conn_q = await db.execute(
            select(WhatsAppConnection.id)
            .where(WhatsAppConnection.is_active == True, WhatsAppConnection.tenant_id == tid)
            .order_by(WhatsAppConnection.id)
            .limit(1)
        )
        cid = conn_q.scalar_one_or_none()
        if cid:
            connection_id = cid
        ok = await send_agent_message_to_customer(
            "whatsapp",
            user_id,
            text,
            connection_id=connection_id,
            tenant_id=tid,
        )
        if not ok:
            continue

        db.add(
            Message(
                conversation_id=conv.id,
                role="assistant",
                content=text,
                extra_data=json.dumps({"proactive": True}, ensure_ascii=False),
            )
        )
        conv.proactive_message_sent_at = now
        sent += 1

    if sent:
        await db.commit()
    return sent
