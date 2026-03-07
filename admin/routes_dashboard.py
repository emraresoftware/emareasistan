"""
Admin paneli – Dashboard ve istatistikler (analytics).
"""
from __future__ import annotations
import asyncio
import json
from datetime import datetime, timedelta

from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import select, desc, func

from config import get_settings
from models.database import AsyncSessionLocal
from models import Conversation, Message, Order, ResponseRule, ImageAlbum, Reminder, AuditLog, Tenant

from admin.common import templates, get_tenant_id
from admin import helpers

router = APIRouter()

_get_local_llm_status = helpers._get_local_llm_status
_build_sales_insight = helpers._build_sales_insight
_conversation_sla_state = helpers._conversation_sla_state
SLA_AUTO_AGENT_NAME = helpers.SLA_AUTO_AGENT_NAME
_norm_phone_for_match = helpers._norm_phone_for_match
_compute_local_routing_metrics = helpers._compute_local_routing_metrics
_audit_from_request = helpers._audit_from_request


async def _dashboard_counts(tid: int):
    """Sayaçlar: sohbet, sipariş, kural, albüm, bekleyen sipariş."""
    async with AsyncSessionLocal() as db:
        conv_count = (await db.execute(select(func.count(Conversation.id)).where(Conversation.tenant_id == tid))).scalar() or 0
        order_count = (await db.execute(select(func.count(Order.id)).where(Order.tenant_id == tid))).scalar() or 0
        rule_count = (await db.execute(select(func.count(ResponseRule.id)).where(ResponseRule.tenant_id == tid))).scalar() or 0
        album_count = (await db.execute(select(func.count(ImageAlbum.id)).where(ImageAlbum.tenant_id == tid))).scalar() or 0
        pending_orders = (await db.execute(select(func.count(Order.id)).where(Order.tenant_id == tid, Order.status == "pending"))).scalar() or 0
        return (conv_count, order_count, rule_count, album_count, pending_orders)


async def _dashboard_revenue(tid: int, month_start: datetime, week_ago: datetime):
    """Aylık/haftalık ciro ve sipariş sayıları."""
    async with AsyncSessionLocal() as db:
        monthly_revenue = (await db.execute(
            select(func.coalesce(func.sum(Order.total_amount), 0)).where(
                Order.tenant_id == tid,
                Order.created_at >= month_start,
                Order.status != "cancelled",
            )
        )).scalar() or 0
        weekly_orders = (await db.execute(select(func.count(Order.id)).where(
            Order.tenant_id == tid,
            Order.created_at >= week_ago,
            Order.status != "cancelled",
        ))).scalar() or 0
        weekly_revenue = (await db.execute(select(func.coalesce(func.sum(Order.total_amount), 0)).where(
            Order.tenant_id == tid,
            Order.created_at >= week_ago,
            Order.status != "cancelled",
        ))).scalar() or 0
        return (float(monthly_revenue), weekly_orders, float(weekly_revenue))


async def _dashboard_recent(tid: int, now: datetime):
    """Son siparişler, son sohbetler, yaklaşan hatırlatıcılar."""
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Order).where(Order.tenant_id == tid).order_by(desc(Order.created_at)).limit(8))
        recent_orders = result.scalars().all()
        result = await db.execute(select(Conversation).where(Conversation.tenant_id == tid).order_by(desc(func.coalesce(Conversation.last_message_at, Conversation.created_at))).limit(5))
        recent_conversations = result.scalars().all()
        result = await db.execute(
            select(Reminder)
            .where(Reminder.tenant_id == tid, Reminder.status == "pending", Reminder.due_at <= now + timedelta(days=1))
            .order_by(Reminder.due_at)
            .limit(5)
        )
        pending_reminders = result.scalars().all()
        return (recent_orders, recent_conversations, pending_reminders)


async def _dashboard_csat(tid: int, week_ago: datetime):
    """CSAT: toplam sayı/ortalama ve son 7 gün."""
    async with AsyncSessionLocal() as db:
        csat_count, csat_avg, csat_count_7, csat_avg_7 = 0, None, 0, None
        try:
            csat_count = (await db.execute(
                select(func.count(Conversation.id)).where(Conversation.tenant_id == tid, Conversation.csat_rating.isnot(None))
            )).scalar() or 0
            csat_avg_row = (await db.execute(
                select(func.avg(Conversation.csat_rating)).where(Conversation.tenant_id == tid, Conversation.csat_rating.isnot(None))
            )).scalar()
            csat_avg = round(float(csat_avg_row), 1) if csat_avg_row is not None else None
            csat_7_row = (await db.execute(
                select(func.count(Conversation.id), func.avg(Conversation.csat_rating)).where(
                    Conversation.tenant_id == tid,
                    Conversation.csat_rating.isnot(None),
                    Conversation.last_message_at >= week_ago,
                )
            )).one_or_none()
            csat_count_7 = int(csat_7_row[0] or 0) if csat_7_row else 0
            csat_avg_7 = round(float(csat_7_row[1]), 1) if csat_7_row and csat_7_row[1] is not None else None
        except Exception:
            pass
        return (csat_count, csat_avg, csat_count_7, csat_avg_7)


@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    """Dashboard endpoint'i. [GET /dashboard]"""
    if request.session.get("admin") != "ok":
        return RedirectResponse(url="/admin", status_code=302)
    tid = get_tenant_id(request)
    if tid is None and getattr(request.state, "partner_admin", False):
        return RedirectResponse(url="/admin/partner", status_code=302)
    now = datetime.utcnow()
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    week_ago = now - timedelta(days=7)

    # Paralel çalıştır: 4 ayrı oturumda sorgular, toplam süre ≈ en yavaş grup
    r_counts, r_revenue, r_recent, r_csat = await asyncio.gather(
        _dashboard_counts(tid),
        _dashboard_revenue(tid, month_start, week_ago),
        _dashboard_recent(tid, now),
        _dashboard_csat(tid, week_ago),
    )
    conv_count, order_count, rule_count, album_count, pending_orders = r_counts
    monthly_revenue, weekly_orders, weekly_revenue = r_revenue
    recent_orders, recent_conversations, pending_reminders = r_recent
    csat_count, csat_avg, csat_count_7, csat_avg_7 = r_csat

    local_llm_status = _get_local_llm_status()

    # AI key sağlık kontrolü (hızlı, 4sn timeout — dashboard'u yavaşlatmaz)
    ai_key_error: str | None = None
    try:
        from services.core.tenant import get_tenant_settings
        import httpx
        ts = await get_tenant_settings(tid)
        settings = get_settings()
        g_key = ts.get("gemini_api_key") or settings.gemini_api_key or ""
        o_key = ts.get("openai_api_key") or settings.openai_api_key or ""
        if g_key:
            model = ts.get("gemini_model") or settings.gemini_model or "gemini-2.5-flash-lite"
            model_path = model if model.startswith("models/") else f"models/{model}"
            url = f"https://generativelanguage.googleapis.com/v1beta/{model_path}:generateContent?key={g_key}"
            async with httpx.AsyncClient(timeout=4.0) as hx:
                resp = await hx.post(url, json={"contents": [{"parts": [{"text": "ping"}]}]})
            if resp.status_code != 200:
                body = (resp.text or "")[:200]
                if "expired" in body.lower() or "invalid" in body.lower() or "key" in body.lower():
                    ai_key_error = "gemini_invalid"
                elif resp.status_code == 429:
                    ai_key_error = "gemini_quota"
                else:
                    ai_key_error = f"gemini_{resp.status_code}"
    except Exception:
        pass

    return templates.TemplateResponse("dashboard.html", {
        "ai_key_error": ai_key_error,
        "request": request,
        "local_llm_status": local_llm_status,
        "conversation_count": conv_count,
        "order_count": order_count,
        "rule_count": rule_count,
        "album_count": album_count,
        "pending_orders": pending_orders,
        "monthly_revenue": monthly_revenue,
        "monthly_revenue_str": f"{monthly_revenue:,.0f}".replace(",", "."),
        "month_name": ["", "Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran", "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık"][month_start.month],
        "weekly_orders": weekly_orders,
        "weekly_revenue": weekly_revenue,
        "weekly_revenue_str": f"{weekly_revenue:,.0f}".replace(",", "."),
        "recent_orders": recent_orders,
        "recent_conversations": recent_conversations,
        "pending_reminders": pending_reminders,
        "csat_count": csat_count,
        "csat_avg": csat_avg,
        "csat_count_7": csat_count_7,
        "csat_avg_7": csat_avg_7,
    })


@router.get("/analytics", response_class=HTMLResponse)
async def analytics_page(request: Request):
    """Analitik sayfasını gösterir. [GET /analytics]"""
    if request.session.get("admin") != "ok":
        return RedirectResponse(url="/admin", status_code=302)
    tid = get_tenant_id(request)
    threshold_last_apply = None
    async with AsyncSessionLocal() as db:
        last_apply = await db.execute(
            select(AuditLog)
            .where(
                AuditLog.tenant_id == tid,
                AuditLog.action == "apply_local_threshold",
            )
            .order_by(desc(AuditLog.id))
            .limit(1)
        )
        row = last_apply.scalar_one_or_none()
        if row:
            details = {}
            if row.details:
                try:
                    details = json.loads(row.details)
                except Exception:
                    details = {}
            threshold_last_apply = {
                "user_email": row.user_email or "-",
                "created_at": (row.created_at.strftime("%d.%m.%Y %H:%M") if row.created_at else "-"),
                "from_threshold": details.get("from"),
                "to_threshold": details.get("to"),
            }
    return templates.TemplateResponse(
        "analytics.html",
        {
            "request": request,
            "threshold_applied": request.query_params.get("threshold_applied") == "1",
            "threshold_unchanged": request.query_params.get("threshold_unchanged") == "1",
            "threshold_last_apply": threshold_last_apply,
        },
    )


@router.get("/api/analytics")
async def api_analytics(request: Request):
    """Analitik endpoint'i. [GET /api/analytics]"""
    if request.session.get("admin") != "ok":
        raise HTTPException(401)
    tid = get_tenant_id(request)
    now = datetime.utcnow()
    week_ago = now - timedelta(days=7)
    async with AsyncSessionLocal() as db:
        conv_7 = (await db.execute(
            select(func.count(Conversation.id)).where(Conversation.tenant_id == tid, Conversation.created_at >= week_ago)
        )).scalar() or 0
        msg_7 = (await db.execute(
            select(func.count(Message.id)).select_from(Message).join(Conversation, Message.conversation_id == Conversation.id).where(Conversation.tenant_id == tid, Message.created_at >= week_ago)
        )).scalar() or 0
        ord_7 = (await db.execute(
            select(func.count(Order.id)).where(
                Order.tenant_id == tid,
                Order.created_at >= week_ago,
                Order.status != "cancelled",
            )
        )).scalar() or 0
        rev_7 = (await db.execute(
            select(func.coalesce(func.sum(Order.total_amount), 0)).where(
                Order.tenant_id == tid,
                Order.created_at >= week_ago,
                Order.status != "cancelled",
            )
        )).scalar() or 0
        rev_7 = float(rev_7)
        taken_over = (await db.execute(
            select(func.count(Conversation.id)).where(Conversation.tenant_id == tid, Conversation.agent_taken_over_at.isnot(None))
        )).scalar() or 0
        daily_labels, daily_conversations, daily_messages, daily_orders, daily_revenue = [], [], [], [], []
        for i in range(13, -1, -1):
            day_start = (now - timedelta(days=i)).replace(hour=0, minute=0, second=0, microsecond=0)
            day_end = day_start + timedelta(days=1)
            daily_labels.append(day_start.strftime("%d.%m"))
            daily_conversations.append((await db.execute(select(func.count(Conversation.id)).where(Conversation.tenant_id == tid, Conversation.created_at >= day_start, Conversation.created_at < day_end))).scalar() or 0)
            daily_messages.append((await db.execute(select(func.count(Message.id)).select_from(Message).join(Conversation, Message.conversation_id == Conversation.id).where(Conversation.tenant_id == tid, Message.created_at >= day_start, Message.created_at < day_end))).scalar() or 0)
            daily_orders.append((await db.execute(select(func.count(Order.id)).where(Order.tenant_id == tid, Order.created_at >= day_start, Order.created_at < day_end, Order.status != "cancelled"))).scalar() or 0)
            daily_revenue.append(float((await db.execute(select(func.coalesce(func.sum(Order.total_amount), 0)).where(Order.tenant_id == tid, Order.created_at >= day_start, Order.created_at < day_end, Order.status != "cancelled"))).scalar() or 0))
        platform_map = {}
        for row in (await db.execute(select(Conversation.platform, func.count(Conversation.id)).where(Conversation.tenant_id == tid, Conversation.created_at >= now - timedelta(days=30)).group_by(Conversation.platform))).all():
            p = row[0] or "unknown"
            platform_map[p] = platform_map.get(p, 0) + row[1]
        LABEL = {"whatsapp": "WhatsApp", "telegram": "Telegram", "instagram": "Instagram", "unknown": "Diğer"}
        platform_labels = [LABEL.get(p, p) for p in ["whatsapp", "telegram", "instagram", "unknown"] if platform_map.get(p, 0) > 0]
        platform_counts = [platform_map[p] for p in ["whatsapp", "telegram", "instagram", "unknown"] if platform_map.get(p, 0) > 0]
        status_map = {}
        for row in (await db.execute(select(Order.status, func.count(Order.id)).where(Order.tenant_id == tid).group_by(Order.status))).all():
            status_map[row[0] or "pending"] = row[1]
        STATUS_LABEL = {"pending": "Beklemede", "confirmed": "Onaylandı", "processing": "Hazırlanıyor", "shipped": "Kargoda", "delivered": "Teslim Edildi", "cancelled": "İptal"}
        status_labels = [STATUS_LABEL.get(s, s) for s in ["pending", "confirmed", "processing", "shipped", "delivered", "cancelled"] if status_map.get(s, 0) > 0]
        status_counts = [status_map[s] for s in ["pending", "confirmed", "processing", "shipped", "delivered", "cancelled"] if status_map.get(s, 0) > 0]
        conversion_rate = (ord_7 / conv_7 * 100) if conv_7 > 0 else 0
        from models import MessageFeedback
        feedback_like = feedback_dislike = 0
        for row in (await db.execute(select(MessageFeedback.feedback, func.count(MessageFeedback.id)).join(Message, MessageFeedback.message_id == Message.id).join(Conversation, Message.conversation_id == Conversation.id).where(Conversation.tenant_id == tid).group_by(MessageFeedback.feedback))).all():
            if row[0] == "like":
                feedback_like = row[1]
            elif row[0] == "dislike":
                feedback_dislike = row[1]
        conv_recent = (await db.execute(select(Conversation).where(Conversation.tenant_id == tid, Conversation.created_at >= week_ago).order_by(desc(func.coalesce(Conversation.last_message_at, Conversation.created_at))).limit(200))).scalars().all()
        vip_leads_7 = warm_leads_7 = auto_sla_taken_over = 0
        source_map = {}
        for conv in conv_recent:
            msg_res = (await db.execute(select(Message).where(Message.conversation_id == conv.id).order_by(Message.created_at.desc()).limit(40))).scalars().all()
            insight = _build_sales_insight(msg_res, conv)
            if insight["tier"] == "vip":
                vip_leads_7 += 1
            elif insight["tier"] == "warm":
                warm_leads_7 += 1
            src = (conv.platform or "unknown").strip().lower()
            source_map[src] = source_map.get(src, 0) + 1
            if conv.agent_name == SLA_AUTO_AGENT_NAME and conv.agent_taken_over_at:
                auto_sla_taken_over += 1
        open_recent = (await db.execute(select(Conversation).where(Conversation.tenant_id == tid).order_by(desc(func.coalesce(Conversation.last_message_at, Conversation.created_at))).limit(120))).scalars().all()
        sla_overdue_open = sum(1 for conv in open_recent if (await _conversation_sla_state(db, conv, now))[0])
        source_names = {"whatsapp": "WhatsApp", "telegram": "Telegram", "instagram": "Instagram", "unknown": "Diger"}
        source_labels = [source_names.get(k, k) for k in ("whatsapp", "telegram", "instagram", "unknown") if source_map.get(k, 0) > 0]
        source_counts = [source_map[k] for k in ("whatsapp", "telegram", "instagram", "unknown") if source_map.get(k, 0) > 0]
        first_response_secs = []
        takeover_conv_7 = takeover_with_order_7 = 0
        conv_phone_map = {}
        source_phone_sets = {"whatsapp": set(), "telegram": set(), "instagram": set(), "unknown": set()}
        for conv in conv_recent:
            conv_phone = _norm_phone_for_match(conv.customer_phone or conv.platform_user_id)
            if conv_phone:
                conv_phone_map[conv.id] = conv_phone
                sk = (conv.platform or "unknown").strip().lower()
                if sk not in source_phone_sets:
                    sk = "unknown"
                source_phone_sets[sk].add(conv_phone)
            if conv.agent_taken_over_at:
                takeover_conv_7 += 1
            first_pair = (await db.execute(select(Message.role, Message.created_at).where(Message.conversation_id == conv.id).order_by(Message.created_at))).all()
            first_user_at = first_assistant_after = None
            for role, created_at in first_pair:
                if role == "user" and first_user_at is None:
                    first_user_at = created_at
                    continue
                if role == "assistant" and first_user_at and created_at >= first_user_at:
                    first_assistant_after = created_at
                    break
            if first_user_at and first_assistant_after:
                delta = (first_assistant_after - first_user_at).total_seconds()
                if 0 <= delta <= 86400:
                    first_response_secs.append(delta)
        order_rows_7 = (await db.execute(select(Order.customer_phone, Order.status).where(Order.tenant_id == tid, Order.created_at >= week_ago))).all()
        order_phone_all = set()
        source_order_counts = {"whatsapp": 0, "telegram": 0, "instagram": 0, "unknown": 0}
        for customer_phone, status in order_rows_7:
            if (status or "").lower() == "cancelled":
                continue
            phone = _norm_phone_for_match(customer_phone)
            if not phone:
                continue
            order_phone_all.add(phone)
            for key in ("whatsapp", "telegram", "instagram", "unknown"):
                if phone in source_phone_sets[key]:
                    source_order_counts[key] += 1
                    break
        for conv in conv_recent:
            if conv.agent_taken_over_at and conv_phone_map.get(conv.id) in order_phone_all:
                takeover_with_order_7 += 1
        avg_first_response_min = round((sum(first_response_secs) / len(first_response_secs)) / 60, 1) if first_response_secs else 0.0
        takeover_to_order_rate = round((takeover_with_order_7 / takeover_conv_7) * 100, 1) if takeover_conv_7 else 0.0
        source_order_list = [source_order_counts.get(k, 0) for k in ("whatsapp", "telegram", "instagram", "unknown") if source_map.get(k, 0) > 0]
        from services.core.tenant import get_tenant_settings
        tenant_settings = await get_tenant_settings(tid)
        local_base_threshold = int(tenant_settings.get("local_llm_min_confidence") or get_settings().local_llm_min_confidence or 55)
        local_metrics = await _compute_local_routing_metrics(db=db, tenant_id=tid, week_ago=week_ago, base_threshold=local_base_threshold)
        from services.workflow.metrics import get_chat_response_metrics
        chat_latency = get_chat_response_metrics(tid, hours=24)
    return {
        "conversations_7": conv_7, "messages_7": msg_7, "orders_7": ord_7, "revenue_7": rev_7,
        "taken_over_count": taken_over,
        "daily_labels": daily_labels, "daily_conversations": daily_conversations, "daily_messages": daily_messages, "daily_orders": daily_orders, "daily_revenue": daily_revenue,
        "platform_labels": platform_labels, "platform_counts": platform_counts,
        "status_labels": status_labels, "status_counts": status_counts,
        "conversion_rate": round(conversion_rate, 1), "feedback_like": feedback_like, "feedback_dislike": feedback_dislike,
        "vip_leads_7": vip_leads_7, "warm_leads_7": warm_leads_7, "sla_overdue_open": sla_overdue_open, "auto_sla_taken_over": auto_sla_taken_over,
        "source_labels": source_labels, "source_counts": source_counts, "source_order_counts": source_order_list,
        "avg_first_response_min": avg_first_response_min, "takeover_to_order_rate": takeover_to_order_rate,
        "takeover_conv_7": takeover_conv_7, "takeover_with_order_7": takeover_with_order_7,
        "local_attempts_7": local_metrics["local_attempts_7"], "local_accepted_7": local_metrics["local_accepted_7"],
        "local_low_conf_7": local_metrics["local_low_conf_7"], "local_error_7": local_metrics["local_error_7"],
        "local_accept_rate_7": local_metrics["local_accept_rate_7"], "local_avg_conf_7": local_metrics["local_avg_conf_7"],
        "local_base_threshold": local_metrics["local_base_threshold"], "local_suggested_threshold": local_metrics["local_suggested_threshold"],
        "avg_response_latency_ms": int(chat_latency.get("avg_latency_ms") or 0),
        "p95_response_latency_ms": int(chat_latency.get("p95_latency_ms") or 0),
        "response_samples_24h": int(chat_latency.get("total") or 0),
    }


@router.post("/analytics/local-threshold/apply")
async def analytics_apply_local_threshold(request: Request):
    """Analitik endpoint'i. [POST /analytics/local-threshold/apply]"""
    if request.session.get("admin") != "ok":
        raise HTTPException(401)
    tid = get_tenant_id(request)
    now = datetime.utcnow()
    week_ago = now - timedelta(days=7)
    async with AsyncSessionLocal() as db:
        from services.core.tenant import get_tenant_settings
        tenant_settings = await get_tenant_settings(tid)
        current_threshold = int(tenant_settings.get("local_llm_min_confidence") or get_settings().local_llm_min_confidence or 55)
        metrics = await _compute_local_routing_metrics(db=db, tenant_id=tid, week_ago=week_ago, base_threshold=current_threshold)
        suggested = int(metrics["local_suggested_threshold"])
        if suggested == current_threshold:
            return RedirectResponse(url="/admin/analytics?threshold_unchanged=1", status_code=302)
        result = await db.execute(select(Tenant).where(Tenant.id == tid))
        tenant = result.scalar_one_or_none()
        if not tenant:
            raise HTTPException(404)
        existing = json.loads(tenant.settings) if tenant.settings else {}
        existing["local_llm_min_confidence"] = suggested
        from services.core.crypto import encrypt_tenant_settings
        tenant.settings = json.dumps(encrypt_tenant_settings(existing), ensure_ascii=False)
        await db.commit()
        from services.core.cache import invalidate_tenant_cache
        await invalidate_tenant_cache(tid)
    await _audit_from_request(request=request, action="apply_local_threshold", resource="tenant_ai_settings", resource_id=str(tid), details={"from": current_threshold, "to": suggested})
    return RedirectResponse(url="/admin/analytics?threshold_applied=1", status_code=302)


@router.get("/api/new-orders-count")
async def api_new_orders_count(request: Request):
    """New Orders endpoint'i. [GET /api/new-orders-count]"""
    if request.session.get("admin") != "ok":
        raise HTTPException(401)
    tid = get_tenant_id(request)
    now = datetime.utcnow()
    five_min_ago = now - timedelta(minutes=5)
    async with AsyncSessionLocal() as db:
        pending = (await db.execute(select(func.count(Order.id)).where(Order.tenant_id == tid, Order.status == "pending"))).scalar() or 0
        recent_user_msgs = (await db.execute(
            select(func.count(Message.id)).select_from(Message).join(Conversation, Message.conversation_id == Conversation.id).where(
                Conversation.tenant_id == tid, Message.role == "user", Message.created_at >= five_min_ago,
            )
        )).scalar() or 0
    return {"pending": pending, "recent_messages": recent_user_msgs}
