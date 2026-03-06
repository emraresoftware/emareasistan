"""
Admin paneli – Temsilci paneli, devral/bırak, quick-replies, api/agent, api/debug-session, api/whatsapp-status.
"""
import json
from datetime import datetime, timedelta

from fastapi import APIRouter, Request, HTTPException, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import select, desc, func
import httpx

from config import get_settings
from models.database import AsyncSessionLocal
from models import (
    Conversation,
    Message,
    Contact,
    Reminder,
    ImageAlbum,
    WhatsAppConnection,
    QuickReply,
)

from admin.common import templates, get_tenant_id, _utc_to_iso
from admin import helpers

router = APIRouter()
_apply_sla_auto_takeover = helpers._apply_sla_auto_takeover
_build_sales_insight = helpers._build_sales_insight
_lead_tier = helpers._lead_tier


async def _load_quick_replies_for_tenant(tid: int) -> list[dict]:
    """Tenant'a ait hızlı yanıtları DB'den getir"""
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(QuickReply)
            .where(QuickReply.tenant_id == tid)
            .order_by(QuickReply.sort_order, QuickReply.id)
        )
        rows = result.scalars().all()
    return [{"_id": r.id, "id": r.id, "label": r.label, "text": r.text} for r in rows]


CSAT_QUESTION = (
    "Bu sohbeti 1 (çok kötü) ile 5 (çok iyi) arasında nasıl değerlendirirsiniz? "
    "Lütfen sadece 1, 2, 3, 4 veya 5 yazın."
)


# --- Temsilci Paneli ---

@router.get("/agent", response_class=HTMLResponse)
async def agent_panel(request: Request):
    """Temsilci paneli Ana sayfa - Müsaitlik + sohbet listesi"""
    if request.session.get("admin") != "ok":
        return RedirectResponse(url="/admin", status_code=302)
    tid = get_tenant_id(request)
    agent_name = request.session.get("agent_name", "")
    agent_status = request.session.get("agent_status", "offline")
    async with AsyncSessionLocal() as db:
        sla_auto_count = await _apply_sla_auto_takeover(db, tid)
        result = await db.execute(
            select(Conversation)
            .where(Conversation.tenant_id == tid)
            .order_by(desc(func.coalesce(Conversation.last_message_at, Conversation.created_at)))
            .limit(50)
        )
        conversations = result.scalars().all()
    for c in conversations:
        c.is_taken_over = c.agent_taken_over_at is not None
        c.is_mine = c.agent_name == agent_name and c.is_taken_over
        quick_score = 5
        draft = (c.order_draft or "").lower()
        if c.customer_phone:
            quick_score += 20
        if c.last_message_at and c.last_message_at >= datetime.utcnow() - timedelta(hours=2):
            quick_score += 20
        if any(k in draft for k in ("demo", "randevu", "teklif", "fiyat", "odeme", "ödeme")):
            quick_score += 35
        if c.notes:
            quick_score += 10
        quick_score = max(0, min(100, quick_score))
        c.lead_score = quick_score
        c.lead_tier = _lead_tier(quick_score)
    return templates.TemplateResponse("agent_panel.html", {
        "request": request,
        "conversations": conversations,
        "agent_name": agent_name,
        "agent_status": agent_status,
        "sla_auto_count": sla_auto_count,
    })


@router.post("/agent/set-profile")
async def agent_set_profile(request: Request, name: str = Form(""), status: str = Form("available")):
    """Temsilci adı ve müsaitlik durumunu kaydet"""
    if request.session.get("admin") != "ok":
        raise HTTPException(401)
    request.session["agent_name"] = name.strip() or "Temsilci"
    request.session["agent_status"] = status if status in ("available", "busy", "offline") else "available"
    return RedirectResponse(url="/admin/agent", status_code=302)


@router.get("/agent/chat/{id}", response_class=HTMLResponse)
async def agent_chat(request: Request, id: int):
    """Temsilci canlı sohbet ekranı"""
    if request.session.get("admin") != "ok":
        return RedirectResponse(url="/admin", status_code=302)
    tid = get_tenant_id(request)
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Conversation).where(Conversation.id == id, Conversation.tenant_id == tid))
        conv = result.scalar_one_or_none()
        if not conv:
            raise HTTPException(404)
        result = await db.execute(
            select(Message).where(Message.conversation_id == id).order_by(Message.created_at)
        )
        messages = result.scalars().all()
        insight = _build_sales_insight(messages, conv)
    last_msg_id = max((m.id for m in messages), default=0)
    quick_replies = await _load_quick_replies_for_tenant(tid)
    return templates.TemplateResponse("agent_chat.html", {
        "request": request,
        "conversation": conv,
        "messages": messages,
        "agent_name": request.session.get("agent_name", "Temsilci"),
        "last_msg_id": last_msg_id,
        "quick_replies": quick_replies,
        "auto_takeover": request.query_params.get("takeover") == "1",
        "sales_insight": insight,
    })


@router.get("/api/agent/contacts")
async def api_agent_contacts(request: Request):
    """Temsilci paneli için kişi listesi"""
    if request.session.get("admin") != "ok":
        raise HTTPException(401)
    tid = get_tenant_id(request)
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Contact).where(Contact.tenant_id == tid).order_by(Contact.name))
        contacts = result.scalars().all()
    return [{"id": c.id, "name": c.name, "phone": c.phone} for c in contacts]


@router.post("/api/agent/start-chat")
async def api_agent_start_chat(request: Request):
    """Kişi veya numara ile WhatsApp sohbeti başlat - bul veya oluştur"""
    if request.session.get("admin") != "ok":
        raise HTTPException(401)
    body = await request.json()
    contact_id = body.get("contact_id")
    phone = (body.get("phone") or "").strip()
    name = (body.get("name") or "").strip()

    def norm_phone(s: str) -> str:
        t = str(s).replace("@s.whatsapp.net", "").replace("@c.us", "").replace("+", "").replace(" ", "")
        if t.startswith("0"):
            t = "90" + t[1:]
        return "".join(c for c in t if c.isdigit())

    tid = get_tenant_id(request)
    async with AsyncSessionLocal() as db:
        if contact_id:
            result = await db.execute(select(Contact).where(Contact.id == int(contact_id), Contact.tenant_id == tid))
            contact = result.scalar_one_or_none()
            if not contact:
                raise HTTPException(404, detail="Kişi bulunamadı")
            phone = norm_phone(contact.phone)
            name = contact.name or name

        if not phone or len(phone) < 10:
            raise HTTPException(400, detail="Geçerli telefon numarası gerekli")

        platform_user_id = norm_phone(phone)
        result = await db.execute(
            select(Conversation).where(
                Conversation.tenant_id == tid,
                Conversation.platform == "whatsapp",
                Conversation.platform_user_id == platform_user_id,
            )
        )
        conv = result.scalar_one_or_none()
        if conv:
            return {"ok": True, "conversation_id": conv.id}

        conv = Conversation(
            tenant_id=tid,
            platform="whatsapp",
            platform_user_id=platform_user_id,
            customer_name=name or None,
            customer_phone=platform_user_id,
        )
        db.add(conv)
        await db.commit()
        await db.refresh(conv)
        return {"ok": True, "conversation_id": conv.id}


@router.get("/api/agent/conversations")
async def api_agent_conversations(request: Request):
    """Temsilci için sohbet listesi - AJAX"""
    if request.session.get("admin") != "ok":
        raise HTTPException(401)
    tid = get_tenant_id(request)
    async with AsyncSessionLocal() as db:
        await _apply_sla_auto_takeover(db, tid)
        result = await db.execute(
            select(Conversation)
            .where(Conversation.tenant_id == tid)
            .order_by(desc(func.coalesce(Conversation.last_message_at, Conversation.created_at)))
            .limit(50)
        )
        conversations = result.scalars().all()
    return [
        {
            "id": c.id,
            "platform": c.platform or "",
            "customer_name": c.customer_name or c.platform_user_id or "Müşteri",
            "customer_phone": c.customer_phone or "",
            "last_message_at": _utc_to_iso(c.last_message_at),
            "agent_taken_over": c.agent_taken_over_at is not None,
            "agent_name": c.agent_name or "",
        }
        for c in conversations
    ]


@router.post("/api/agent/takeover/{conv_id}")
async def api_agent_takeover(request: Request, conv_id: int):
    """Sohbeti devral"""
    if request.session.get("admin") != "ok":
        raise HTTPException(401)
    tid = get_tenant_id(request)
    agent_name = request.session.get("agent_name", "Temsilci")
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Conversation).where(Conversation.id == conv_id, Conversation.tenant_id == tid))
        conv = result.scalar_one_or_none()
        if not conv:
            raise HTTPException(404)
        conv.agent_taken_over_at = datetime.utcnow()
        conv.agent_name = agent_name
        await db.commit()
    return {"ok": True, "agent_name": agent_name}


@router.post("/api/agent/release/{conv_id}")
async def api_agent_release(request: Request, conv_id: int):
    """Sohbeti AI'a bırak; WhatsApp ise müşteriye CSAT anketi gönder"""
    if request.session.get("admin") != "ok":
        raise HTTPException(401)
    tid = get_tenant_id(request)
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Conversation).where(Conversation.id == conv_id, Conversation.tenant_id == tid))
        conv = result.scalar_one_or_none()
        if not conv:
            raise HTTPException(404)
        conv.agent_taken_over_at = None
        conv.agent_name = None
        if conv.platform == "whatsapp" and getattr(conv, "csat_sent_at", None) is None:
            try:
                from services.whatsapp.agent import send_agent_message_to_customer, get_connection_id_for_tenant
                conn_id = await get_connection_id_for_tenant(tid)
                sent = await send_agent_message_to_customer(
                    "whatsapp",
                    conv.platform_user_id or "",
                    CSAT_QUESTION,
                    connection_id=conn_id,
                    tenant_id=tid,
                )
                if sent:
                    conv.csat_sent_at = datetime.utcnow()
            except Exception:
                pass
        await db.commit()
    return {"ok": True}


@router.get("/api/agent/messages/{conv_id}")
async def api_agent_messages(request: Request, conv_id: int, since_id: int = 0):
    """Mesajları getir (polling için)"""
    if request.session.get("admin") != "ok":
        raise HTTPException(401)
    tid = get_tenant_id(request)
    async with AsyncSessionLocal() as db:
        conv_check = await db.execute(select(Conversation.id).where(Conversation.id == conv_id, Conversation.tenant_id == tid))
        if not conv_check.scalar_one_or_none():
            raise HTTPException(404)
        result = await db.execute(
            select(Message)
            .where(Message.conversation_id == conv_id, Message.id > since_id)
            .order_by(Message.created_at)
        )
        messages = result.scalars().all()
    return [
        {
            "id": m.id,
            "role": m.role,
            "content": (m.content or "").replace("\n[Ürün resimleri gönderildi]", "").strip(),
            "created_at": _utc_to_iso(m.created_at),
        }
        for m in messages
    ]


@router.get("/api/agent/insights/{conv_id}")
async def api_agent_insights(request: Request, conv_id: int):
    """Sohbet icin lead score + sales playbook onerileri"""
    if request.session.get("admin") != "ok":
        raise HTTPException(401)
    tid = get_tenant_id(request)
    async with AsyncSessionLocal() as db:
        conv_res = await db.execute(select(Conversation).where(Conversation.id == conv_id, Conversation.tenant_id == tid))
        conv = conv_res.scalar_one_or_none()
        if not conv:
            raise HTTPException(404)
        msg_res = await db.execute(select(Message).where(Message.conversation_id == conv_id).order_by(Message.created_at))
        messages = msg_res.scalars().all()
    return _build_sales_insight(messages, conv)


@router.post("/api/agent/followup/{conv_id}")
async def api_agent_create_followup(request: Request, conv_id: int):
    """Lead skora gore tek tik follow-up hatirlaticisi olustur"""
    if request.session.get("admin") != "ok":
        raise HTTPException(401)
    tid = get_tenant_id(request)
    body = await request.json()
    requested_minutes = body.get("minutes")
    async with AsyncSessionLocal() as db:
        conv_res = await db.execute(select(Conversation).where(Conversation.id == conv_id, Conversation.tenant_id == tid))
        conv = conv_res.scalar_one_or_none()
        if not conv:
            raise HTTPException(404)
        msg_res = await db.execute(select(Message).where(Message.conversation_id == conv_id).order_by(Message.created_at))
        messages = msg_res.scalars().all()
        insight = _build_sales_insight(messages, conv)
        minutes = insight["followup_minutes"]
        try:
            if requested_minutes is not None:
                minutes = int(requested_minutes)
        except Exception:
            pass
        minutes = max(10, min(7 * 24 * 60, int(minutes)))
        due_at = datetime.utcnow() + timedelta(minutes=minutes)
        r = Reminder(
            tenant_id=tid,
            conversation_id=conv.id,
            customer_name=conv.customer_name or "Müşteri",
            customer_phone=conv.customer_phone or conv.platform_user_id,
            due_at=due_at,
            note=insight["followup_note"],
            status="pending",
        )
        db.add(r)
        await db.commit()
        await db.refresh(r)
    return {"ok": True, "reminder_id": r.id, "due_at": r.due_at.isoformat(), "note": r.note}


@router.post("/api/agent/send-message")
async def api_agent_send_message(request: Request):
    """Temsilci mesaj gönder - müşteriye WhatsApp/Telegram"""
    if request.session.get("admin") != "ok":
        raise HTTPException(401)
    body = await request.json()
    conv_id = int(body.get("conversation_id", 0))
    text = (body.get("text") or "").strip()
    if not conv_id or not text:
        raise HTTPException(400, detail="conversation_id ve text gerekli")
    tid = get_tenant_id(request)
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Conversation).where(Conversation.id == conv_id, Conversation.tenant_id == tid))
        conv = result.scalar_one_or_none()
        if not conv:
            raise HTTPException(404)
        platform = conv.platform or "whatsapp"
        user_id = conv.platform_user_id or ""
        if platform != "whatsapp" or not user_id:
            raise HTTPException(400, detail="Sadece WhatsApp destekleniyor")
        msg = Message(
            conversation_id=conv_id,
            role="assistant",
            content=text,
        )
        db.add(msg)
        conv.last_message_at = datetime.utcnow()
        await db.commit()
        await db.refresh(msg)
        connection_id = None
        tid_conn = conv.tenant_id or 1
        conn_result = await db.execute(
            select(WhatsAppConnection)
            .where(WhatsAppConnection.is_active == True, WhatsAppConnection.tenant_id == tid_conn)
            .order_by(WhatsAppConnection.id)
            .limit(1)
        )
        conn_row = conn_result.scalar_one_or_none()
        if conn_row:
            connection_id = conn_row.id
        from services.whatsapp.agent import send_agent_message_to_customer
        ok = await send_agent_message_to_customer(
            platform,
            user_id,
            text,
            connection_id=connection_id,
            tenant_id=tid_conn,
        )
        if not ok:
            raise HTTPException(503, detail="Mesaj gönderilemedi. WhatsApp bridge çalışıyor mu?")
    return {"ok": True, "message_id": msg.id}


@router.get("/api/agent/albums")
async def api_agent_albums(request: Request):
    """Temsilci paneli için albüm listesi - tek tıkla gönderim dropdown"""
    if request.session.get("admin") != "ok":
        raise HTTPException(401)
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(ImageAlbum)
            .where(ImageAlbum.is_active == True)
            .order_by(desc(ImageAlbum.priority), ImageAlbum.id)
        )
        albums = result.scalars().all()
    return [
        {
            "id": a.id,
            "name": a.name or f"Albüm {a.id}",
            "image_urls": json.loads(a.image_urls or "[]"),
            "image_count": len(json.loads(a.image_urls or "[]")),
        }
        for a in albums
    ]


@router.post("/api/agent/send-image")
async def api_agent_send_image(request: Request):
    """Temsilci müşteriye resim veya albüm gönder"""
    if request.session.get("admin") != "ok":
        raise HTTPException(401)
    body = await request.json()
    conv_id = int(body.get("conversation_id", 0))
    image_urls = body.get("image_urls") or []
    album_id = body.get("album_id")
    caption = (body.get("caption") or "").strip() or None
    if not conv_id:
        raise HTTPException(400, detail="conversation_id gerekli")
    if album_id and not image_urls:
        tid = get_tenant_id(request)
        async with AsyncSessionLocal() as db:
            result = await db.execute(select(ImageAlbum).where(ImageAlbum.id == int(album_id), ImageAlbum.tenant_id == tid))
            album = result.scalar_one_or_none()
            if not album:
                raise HTTPException(404, detail="Albüm bulunamadı")
            image_urls = json.loads(album.image_urls or "[]")
            if not caption and album.custom_message:
                caption = album.custom_message
    if not image_urls:
        raise HTTPException(400, detail="image_urls veya album_id gerekli")
    tid = get_tenant_id(request)
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Conversation).where(Conversation.id == conv_id, Conversation.tenant_id == tid))
        conv = result.scalar_one_or_none()
        if not conv:
            raise HTTPException(404)
        platform = conv.platform or "whatsapp"
        user_id = conv.platform_user_id or ""
        if platform != "whatsapp" or not user_id:
            raise HTTPException(400, detail="Sadece WhatsApp destekleniyor")
        connection_id = None
        tid_conn = conv.tenant_id or 1
        conn_result = await db.execute(
            select(WhatsAppConnection)
            .where(WhatsAppConnection.is_active == True, WhatsAppConnection.tenant_id == tid_conn)
            .order_by(WhatsAppConnection.id)
            .limit(1)
        )
        conn_row = conn_result.scalar_one_or_none()
        if conn_row:
            connection_id = conn_row.id
        from services.whatsapp.agent import send_agent_images_to_customer
        ok, err_msg = await send_agent_images_to_customer(
            platform, user_id, image_urls, caption, connection_id=connection_id
        )
        if not ok:
            msg = err_msg or "Resim gönderilemedi. WhatsApp bridge çalışıyor mu?"
            if "to" in (msg or "").lower() and "text" in (msg or "").lower():
                msg = "Bridge eski sürüm çalışıyor. Lütfen WhatsApp Bridge'i yeniden başlatın: cd whatsapp-bridge && node index.js"
            raise HTTPException(503, detail=msg)
        msg_content = f"[{len(image_urls)} resim gönderildi]"
        msg = Message(conversation_id=conv_id, role="assistant", content=msg_content)
        db.add(msg)
        conv.last_message_at = datetime.utcnow()
        await db.commit()
    return {"ok": True, "count": len(image_urls)}


# --- Hızlı Yanıtlar ---

@router.get("/quick-replies", response_class=HTMLResponse)
async def quick_replies_list(request: Request):
    """Hızlı yanıt şablonları yönetimi - tenant bazlı"""
    if request.session.get("admin") != "ok":
        return RedirectResponse(url="/admin", status_code=302)
    tid = get_tenant_id(request)
    items = await _load_quick_replies_for_tenant(tid)
    return templates.TemplateResponse("quick_replies.html", {
        "request": request,
        "items": items,
    })


@router.post("/quick-replies/save")
async def quick_replies_save(
    request: Request,
    id: str = Form(""),
    label: str = Form(""),
    text: str = Form(""),
):
    """Hızlı yanıtlar kaydeder. [POST /quick-replies/save]"""
    if request.session.get("admin") != "ok":
        raise HTTPException(401)
    tid = get_tenant_id(request)
    label = label.strip() or "Şablon"
    text = text.strip() or ""
    if not text:
        raise HTTPException(400, detail="Mesaj metni gerekli")
    async with AsyncSessionLocal() as db:
        if id and id.isdigit():
            result = await db.execute(select(QuickReply).where(QuickReply.id == int(id), QuickReply.tenant_id == tid))
            qr = result.scalar_one_or_none()
            if qr:
                qr.label = label
                qr.text = text
                await db.commit()
        else:
            qr = QuickReply(tenant_id=tid, label=label, text=text)
            db.add(qr)
            await db.commit()
    return RedirectResponse(url="/admin/quick-replies", status_code=302)


@router.post("/quick-replies/{id}/delete")
async def quick_replies_delete(request: Request, id: int):
    """Hızlı yanıtlar siler. [POST /quick-replies/{id}/delete]"""
    if request.session.get("admin") != "ok":
        raise HTTPException(401)
    tid = get_tenant_id(request)
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(QuickReply).where(QuickReply.id == id, QuickReply.tenant_id == tid))
        qr = result.scalar_one_or_none()
        if qr:
            await db.delete(qr)
            await db.commit()
    return RedirectResponse(url="/admin/quick-replies", status_code=302)


@router.get("/api/quick-replies")
async def api_quick_replies(request: Request):
    """Hızlı yanıt listesi - AJAX, tenant bazlı"""
    if request.session.get("admin") != "ok":
        raise HTTPException(401)
    tid = get_tenant_id(request)
    items = await _load_quick_replies_for_tenant(tid)
    return [{"label": x["label"], "text": x["text"]} for x in items]


@router.post("/api/agent/conversation-notes/{conv_id}")
async def api_agent_conversation_notes(request: Request, conv_id: int):
    """Sohbet notunu güncelle"""
    if request.session.get("admin") != "ok":
        raise HTTPException(401)
    tid = get_tenant_id(request)
    body = await request.json()
    notes = (body.get("notes") or "").strip()
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Conversation).where(Conversation.id == conv_id, Conversation.tenant_id == tid))
        conv = result.scalar_one_or_none()
        if not conv:
            raise HTTPException(404)
        conv.notes = notes or None
        await db.commit()
    return {"ok": True}


@router.get("/api/debug-session")
async def api_debug_session(request: Request):
    """Tenant teşhisi - session vs User.tenant_id (giriş yapmış olmalı)"""
    if request.session.get("admin") != "ok":
        raise HTTPException(401)
    from models import User, Tenant
    session_tid = request.session.get("tenant_id")
    user_id = request.session.get("user_id")
    super_admin = request.session.get("super_admin")
    state_tid = getattr(request.state, "tenant_id", None)
    state_name = getattr(request.state, "tenant_name", "")
    out = {"session": {"tenant_id": session_tid, "user_id": user_id, "super_admin": super_admin}, "request.state": {"tenant_id": state_tid, "tenant_name": state_name}}
    if user_id:
        async with AsyncSessionLocal() as db:
            r = await db.execute(select(User).where(User.id == int(user_id)))
            u = r.scalar_one_or_none()
            if u:
                out["user_db"] = {"id": u.id, "email": u.email, "tenant_id": u.tenant_id}
                r2 = await db.execute(select(Tenant).where(Tenant.id == (u.tenant_id or 1)))
                t = r2.scalar_one_or_none()
                out["tenant_from_user"] = (t.name if t else None) or f"Firma {u.tenant_id}"
    return out


@router.get("/api/whatsapp-status")
async def api_whatsapp_status(request: Request):
    """Bridge WhatsApp durumu - temsilci panelinde gösterim"""
    if request.session.get("admin") != "ok":
        raise HTTPException(401)
    bridge_url = get_settings().whatsapp_bridge_url or "http://localhost:3100"
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            r = await client.get(f"{bridge_url}/api/status")
        if r.status_code == 200:
            data = r.json()
            return {"connected": data.get("connected", False)}
    except Exception:
        pass
    return {"connected": False}
