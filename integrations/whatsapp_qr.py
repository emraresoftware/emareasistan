"""
WhatsApp QR Bridge API - Node.js bridge için endpoint
QR ile giriş yapan WhatsApp client bu endpoint'e mesaj gönderir
"""
import logging
from time import perf_counter
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from models.database import AsyncSessionLocal
from integrations import ChatHandler
from services.core.tracing import record_trace_event, check_trace_alarm
from services.workflow.metrics import record_chat_response_event

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/whatsapp", tags=["whatsapp-qr"])


def _normalize_phone_for_conversation(phone: str) -> str:
    """Aynı numaranın farklı formatlarda (0532..., 532..., 90532...) hep aynı sohbete düşmesi için normalizasyon"""
    if not phone:
        return phone or ""
    digits = "".join(c for c in str(phone) if c.isdigit())
    if not digits:
        return phone
    if len(digits) == 10 and digits.startswith("5"):
        return "90" + digits
    if len(digits) == 11 and digits.startswith("0"):
        return "9" + digits
    return digits


class ProcessRequest(BaseModel):
    from_: str = Field(alias="from")  # WhatsApp numarası (jid)
    text: str = ""
    audio_base64: str | None = None  # Sesli mesaj (base64)
    audio_mimetype: str | None = None  # audio/ogg, audio/mpeg vb.
    image_base64: str | None = None  # Resim - Vision AI ürün eşleştirme
    image_mimetype: str | None = None  # image/jpeg, image/png vb.
    replied_to_caption: str | None = None  # Yanıtlanan resmin caption'ı ("bu olsun" eşleşmesi için)
    connection_id: int | str | None = None  # Hangi WhatsApp bağlantısı - tenant eşleşmesi için
    is_group: bool = False  # Grup mesajı mı?
    group_name: str | None = None  # Grup adı (ör: "emare asistan")
    sender: str | None = None  # Grup mesajında gerçek gönderen numarası

    model_config = {"populate_by_name": True}


@router.post("/process")
async def process_message(request: ProcessRequest):
    """
    WhatsApp QR bridge'den gelen mesajı işle, yanıt döndür.
    connection_id varsa ilgili firma (tenant) üzerinden işlenir.
    """
    from models import WhatsAppConnection
    from sqlalchemy import select

    raw_from = str(request.from_).replace("@s.whatsapp.net", "").replace("@c.us", "")

    # Grup mesajı: gönderen numarasını kullan, grup JID'ini değil
    is_group = request.is_group or False
    group_name = (request.group_name or "").strip()
    if is_group and request.sender:
        sender_raw = str(request.sender).replace("@s.whatsapp.net", "").replace("@c.us", "")
        sender_number = _normalize_phone_for_conversation(sender_raw)
        # Grup sohbeti: user_id olarak grup JID kullan (tüm grup mesajları aynı conversation'da)
        group_jid = raw_from.replace("@g.us", "").replace("@s.whatsapp.net", "").replace("@c.us", "")
        from_number = f"group_{group_jid}"
        logger.info("Grup mesajı: '%s' grubundan %s (user_id=%s)", group_name, sender_number, from_number)
    else:
        # Grup JID'inde @g.us kalabilir, temizle
        raw_from = raw_from.replace("@g.us", "")
        from_number = _normalize_phone_for_conversation(raw_from)
        sender_number = from_number
    text = (request.text or "").strip()

    # Sesli mesaj: önce transkribe et
    if not text and request.audio_base64:
        from services.ai.stt import transcribe_audio
        text = await transcribe_audio(
            request.audio_base64,
            request.audio_mimetype or "audio/ogg",
        )
        if text:
            logger.info("Sesli mesaj transkribe edildi: %s...", text[:50])
        else:
            logger.warning("Sesli mesaj transkribe edilemedi")
            raise HTTPException(status_code=400, detail="Sesli mesaj anlaşılamadı. Lütfen yazılı mesaj gönderin.")

    # Resim veya metin gerekli
    if not text and not request.image_base64:
        raise HTTPException(status_code=400, detail="Boş mesaj")

    tenant_id = 1  # Varsayılan
    if request.connection_id:
        async with AsyncSessionLocal() as db:
            cid = int(request.connection_id) if str(request.connection_id).isdigit() else None
            conn = None
            if cid:
                r = await db.execute(select(WhatsAppConnection).where(WhatsAppConnection.id == cid))
                conn = r.scalar_one_or_none()
            elif str(request.connection_id).strip().lower() == "default":
                # Bridge API fallback: auth_path='default' ( .wwebjs_auth ) veya ilk bağlantı
                r = await db.execute(
                    select(WhatsAppConnection)
                    .where(WhatsAppConnection.is_active == True, WhatsAppConnection.auth_path == "default")
                    .limit(1)
                )
                conn = r.scalar_one_or_none()
                if not conn:
                    r = await db.execute(
                        select(WhatsAppConnection)
                        .where(WhatsAppConnection.is_active == True)
                        .order_by(WhatsAppConnection.id)
                        .limit(1)
                    )
                    conn = r.scalar_one_or_none()
            if conn:
                tenant_id = conn.tenant_id if conn.tenant_id is not None else 1
                if conn.tenant_id is None:
                    logger.warning("WhatsAppConnection id=%s tenant_id boş, varsayılan 1 kullanılıyor", conn.id)

    try:
        started = perf_counter()
        ok = True
        async with AsyncSessionLocal() as db:
            handler = ChatHandler(db)
            response = await handler.process_message(
                platform="whatsapp",
                user_id=from_number,
                message_text=text or "",
                conversation_history=[],
                customer_phone=sender_number if is_group else from_number,
                replied_to_caption=request.replied_to_caption,
                tenant_id=tenant_id,
                image_base64=request.image_base64,
                image_mimetype=request.image_mimetype,
                is_group=is_group,
                group_name=group_name,
            )
    except Exception as e:
        ok = False
        logger.exception("WhatsApp mesaj işleme hatası: %s", e)
        raise HTTPException(status_code=500, detail=str(e)[:200])
    finally:
        duration_ms = int((perf_counter() - started) * 1000)
        record_trace_event(
            "chat_process",
            ok=ok,
            duration_ms=duration_ms,
            tenant_id=tenant_id,
            meta={"platform": "whatsapp_qr"},
        )
        record_chat_response_event(
            tenant_id=tenant_id,
            ok=ok,
            latency_ms=duration_ms,
            channel="whatsapp_qr",
        )
        check_trace_alarm("chat_process")

    images = []
    if response.get("image_url"):
        images.append({
            "url": response["image_url"],
            "caption": response.get("image_caption", ""),
        })
    for img in response.get("product_images", []):
        # caption alanı varsa doğrudan kullan, yoksa ürün formatı (isim - fiyat TL)
        if img.get("caption"):
            cap = img["caption"]
        else:
            cap = f"{img.get('name', '')} - {img.get('price', 0)} TL"
        images.append({
            "url": img.get("url", ""),
            "caption": cap,
        })

    text = response.get("text", "")
    suggested = response.get("suggested_replies") or []
    if suggested:
        lines = []
        for i, opt in enumerate(suggested, 1):
            if isinstance(opt, dict):
                label = opt.get("label") or opt.get("text", "")
            else:
                label = str(opt)
            if label:
                lines.append(f"{i}. {label}")
        if lines:
            text = (text.rstrip() + "\n\n" + "\n".join(lines) + "\n\nLütfen numara yazarak seçin (örn: 1)").strip()

    result = {
        "text": text,
        "images": images,
        "videos": response.get("videos", []),
    }
    if response.get("location"):
        result["location"] = response["location"]

    # Sesli mesaj geldiyse yanıtı da ses olarak döndür (TTS)
    if request.audio_base64 and text:
        try:
            from services.ai.tts import text_to_speech
            audio_b64, audio_mime = await text_to_speech(text)
            if audio_b64 and audio_mime:
                result["audio_base64"] = audio_b64
                result["audio_mimetype"] = audio_mime
        except Exception as e:
            logger.warning("TTS atlandı: %s", e)

    return result


@router.get("/test")
async def test():
    """API bağlantı testi - bridge çalışıyorsa bu yanıtı alır"""
    return {"status": "ok", "message": "API çalışıyor"}


@router.get("/diagnose")
async def diagnose():
    """
    WhatsApp cevap vermiyor sorun giderme - olası nedenleri listeler.
    curl http://localhost:8000/api/whatsapp/diagnose
    """
    from config import get_settings
    from models.database import AsyncSessionLocal
    from models import Conversation
    from sqlalchemy import select, func

    settings = get_settings()
    issues = []
    ok = []

    # AI anahtarları
    has_gemini = bool((settings.gemini_api_key or "").strip())
    has_openai = bool((settings.openai_api_key or "").strip())
    local_llm = getattr(settings, "local_llm_enabled", False)
    if has_gemini or has_openai or local_llm:
        ok.append("AI anahtarı mevcut")
    else:
        issues.append("AI anahtarı yok: .env'de GEMINI_API_KEY veya OPENAI_API_KEY ekleyin")

    # Temsilci devralma sayısı
    try:
        async with AsyncSessionLocal() as db:
            r = await db.execute(
                select(func.count(Conversation.id)).where(
                    Conversation.agent_taken_over_at.isnot(None)
                )
            )
            taken = r.scalar() or 0
        if taken > 0:
            issues.append(
                f"Temsilci devralmış {taken} sohbet var. AI yanıt vermez. "
                "Admin → Sohbetler → Devralmayı Kaldır veya: python scripts/reset_agent_takeover.py"
            )
        else:
            ok.append("Temsilci devralması yok")
    except Exception as e:
        issues.append(f"Veritabanı kontrolü: {str(e)[:80]}")

    return {
        "status": "ok" if not issues else "issues",
        "ok": ok,
        "issues": issues,
        "hint": "Bridge ASISTAN_API_URL=http://localhost:8000 olmalı. Python API çalışıyor olmalı."
    }
