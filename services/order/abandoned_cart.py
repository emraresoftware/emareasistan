"""
Abandoned Cart Recovery - Sipariş akışına girip bırakan müşterilere 1 saat sonra hatırlatma.
Cron ile /api/cron/abandoned-cart çağrılır (örn. her 10 dakikada bir).
"""
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from sqlalchemy import select

from models import Conversation, WhatsAppConnection
from services.core import OrderStateMachine
from services.whatsapp.agent import send_agent_message_to_customer


ABANDONED_AFTER_HOURS = 1
REMINDER_MESSAGE = (
    "Merhaba! Siparişinizi tamamlamadığınızı fark ettik. "
    "Ödeme seçeneğinizi belirleyerek siparişinizi onaylayabilirsiniz. "
    "Yardıma ihtiyacınız varsa yazmanız yeterli."
)


async def find_abandoned_carts(db: AsyncSession) -> list[Conversation]:
    """
    Sepetini terk eden sohbetleri bul:
    - order_draft var, state INIT/CONFIRMED değil
    - last_message_at > 1 saat önce
    - abandoned_cart_reminder_sent_at null
    - agent_taken_over_at null (temsilci devralmadı)
    - platform whatsapp
    """
    cutoff = datetime.utcnow() - timedelta(hours=ABANDONED_AFTER_HOURS)
    result = await db.execute(
        select(Conversation)
        .where(
            Conversation.platform == "whatsapp",
            Conversation.order_draft.isnot(None),
            Conversation.order_draft != "",
            Conversation.last_message_at < cutoff,
            Conversation.abandoned_cart_reminder_sent_at.is_(None),
            Conversation.agent_taken_over_at.is_(None),
        )
    )
    convs = result.scalars().all()
    out = []
    for c in convs:
        sm = OrderStateMachine(c.order_draft)
        state = sm.get_state()
        if state not in (OrderStateMachine.INIT, OrderStateMachine.CONFIRMED):
            out.append(c)
    return out


async def send_abandoned_cart_reminders(db: AsyncSession) -> int:
    """
    Terk edilen sepetlere hatırlatma gönder.
    Returns: gönderilen mesaj sayısı
    """
    convs = await find_abandoned_carts(db)
    count = 0
    for conv in convs:
        to = conv.platform_user_id or conv.customer_phone
        if not to:
            continue
        connection_id = None
        tid = conv.tenant_id or 1
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
            to,
            REMINDER_MESSAGE,
            connection_id=connection_id,
            tenant_id=tid,
        )
        if ok:
            conv.abandoned_cart_reminder_sent_at = datetime.utcnow()
            count += 1
    if count:
        await db.commit()
    return count
