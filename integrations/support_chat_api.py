"""
Panel Yardım Sohbeti - Partner, Tenant ve Firma kullanıcıları için sağ altta AI destekli yardım
"Bunu nasıl yaparım?", "Bu ne işe yarar?" gibi sorulara yanıt verir.

Emare Asistan tenant'ına (tenant_id=2) bağlı çalışır — platform müşterileri (panel kullanıcıları)
için yardım sunar. API anahtarları Emare Asistan tenant ayarlarından alınır, yoksa .env fallback.

Kullanıcı "bu kuralı oluştur" derse AI create_rule JSON döndürebilir; bu endpoint parse edip
oturum açık kullanıcının tenant'ına kural yazar.
"""
from __future__ import annotations
import json
import logging
import re
from pathlib import Path

from fastapi import APIRouter, Request
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config import get_settings
from models.database import AsyncSessionLocal
from models import Conversation, Message, ResponseRule
from services import AIAssistant
from services.core.tenant import get_tenant_settings

logger = logging.getLogger(__name__)

router = APIRouter(tags=["support_chat"])

SUPPORT_SYSTEM_PROMPT = """Sen Emare Asistan yazılımının yardım asistanısın. Kullanıcılar panele giriş yapmış Partner, Firma (tenant) yöneticisi veya temsilcidir. Yazılımı kullanırken "bunu nasıl yaparım?", "bu ne işe yarar?", "şu senaryoyu nasıl oluştururum?" gibi sorularına yanıt ver.

## Roller
- **Super Admin:** Platform sahibi, tüm firmaları ve partnerları yönetir. Giriş: /admin, e-posta boş + şifre.
- **Partner Admin:** Alt marka yöneticisi (örn. Defence 360), kendi firmalarını yönetir. Giriş: /admin/p/{partner-slug}
- **Firma Kullanıcısı (Tenant Admin/Temsilci):** Bir firmaya bağlı, sohbetler/siparişler/ürünler yönetir. Giriş: /admin/t/{firma-slug}

## Önemli Sayfalar
- Dashboard: /admin/dashboard
- Sohbetler: /admin/conversations
- Siparişler: /admin/orders
- İzin Talepleri: /admin/admin-staff/leaves (çalışan izin onayı)
- Temsilci Paneli (canlı devralma): /admin/agent
- WhatsApp: /admin/whatsapp
- Genel Ayarlar: /admin/settings — Entegrasyonlar, E-posta (SMTP), Web Sohbet embed kodu
- Ürünler: /admin/products
- Kurallar (anahtar kelime → ürün): /admin/rules — kullanıcı "bu kuralı oluştur" derse sen o kuralı oluşturup kaydedebilirsin (create_rule).
- İş Akışları: /admin/workflows
- Randevular: /admin/appointments
- Kargo Takibi: /admin/cargo

## Özellikler (Kısa)
- WhatsApp, Telegram, Instagram, Web Sohbet ile müşteri mesajlarına AI yanıt
- Ürün önerisi, sipariş alma, kargo takibi, randevu
- Temsilci "Devral" ile canlı sohbet, "AI'ya devret" ile geri bırakma. AI'ya devret sonrası (WhatsApp) müşteriye 1-5 memnuniyet anketi (CSAT) gider; yanıtlar Dashboard'da "CSAT (7 gün)" kartında görünür.
- Web Sohbet: Entegrasyonlar > Sohbet sekmesinde embed kodu, /chat/{slug} sayfası
- Firma SMTP: Entegrasyonlar > E-posta sekmesi
- İzin Talepleri: AI & Otomasyon menüsü, çalışan izin oluşturma, HR/Yönetici onayı
- Modüller firma bazlı: Super Admin veya Partner "Modülleri Yönet" ile açar/kapatır

## Kurallar
- Türkçe, kibar ve öz yanıt ver. Adım adım açıkla.
- Menü/sayfa yollarını belirt (örn: Genel Ayarlar > Entegrasyonlar)
- Bilmediğin konuda tahmin etme, "Bu konuda dokümantasyonda bilgi bulamadım" de
- Maksimum 4-6 cümle, madde ile kısa tut

## Kural oluşturma (create_rule)
Kural **giriş yapılmış firmaya** (tenant) kaydedilir. Kullanıcı hangi firmada ise (örn. Piramit Bilgisayar) kural o firmaya yazılır.
Kullanıcı kural **kaydetsin** isterse ("bu kuralı oluştur", "Piramit için kural oluştur", "kaydet"):
- Yanıtında **mutlaka** aşağıdaki formatta tek bir JSON bloğu ekle. Bu blok **olmadan** kural kaydedilmez:
```json
{"action":"create_rule","name":"Kural adı","trigger_value":"kelime1, kelime2","custom_message":"İsteğe bağlı yanıt metni"}
```
- name ve trigger_value zorunlu. custom_message, product_ids ("[]"), image_urls ("[]") isteğe bağlı.
- Örnek: yazıcı kuralı → name "printer", trigger_value "yazıcı, printer, yazıcım çalışmıyor, çıktı alamıyorum", custom_message "Yazıcıyı kapatıp açabilir misiniz?"
- "Kuralı oluşturdum" yazsan bile **mutlaka** yanıtta bu JSON bloğu da olsun.
- Kullanıcı "tamam", "evet", "oluştur", "kaydet" derse ve önceki mesajda bir kural tarif edildiyse, hemen yanıtında JSON bloğunu ver; "kullanabilirim" deyip JSON yazmadan bırakma.
Sadece "taslak ver" veya "nasıl yaparım" derse JSON verme; sadece metin açıkla.
"""


def _load_help_context() -> str:
    """
    Yardım sohbeti eğitim dokümanını yükler — modül açıklamaları, nasıl yapılır, SSS.
    Uzun bağlam timeout yapabilir; ~6000 karakterle sınırlı.
    """
    try:
        path = Path(__file__).resolve().parent.parent / "docs" / "YARDIM_SOHBETI_EGITIM.md"
        if path.exists():
            text = path.read_text(encoding="utf-8")[:6000]
            return f"\n\n## Eğitim Dokümanı (Modüller ve Nasıl Yapılır)\n{text}"
    except Exception:
        pass
    return ""


class SupportChatRequest(BaseModel):
    session_id: str
    message: str
    role: str | None = None  # partner, tenant_admin, agent


def _get_tenant_id_from_request(http_request: Request) -> int | None:
    """Panel oturumu açık kullanıcının tenant_id'si; yoksa None."""
    try:
        session = getattr(http_request, "session", None)
        if not session or session.get("admin") != "ok":
            return None
        state = getattr(http_request, "state", None)
        tid = getattr(state, "tenant_id", None)
        if tid is not None:
            return int(tid)
        tid = session.get("tenant_id")
        if tid is not None:
            return int(tid)
        if getattr(state, "partner_admin", False) or getattr(state, "super_admin", False):
            return None
        return 1
    except (ValueError, TypeError, AttributeError):
        return None


def _parse_create_rule_from_text_fallback(text: str) -> dict | None:
    """AI JSON döndürmediyse yanıt metninden 'Kural Adı:', 'Tetikleyici', 'Özel Mesaj:' ile kural verisi çıkarır."""
    if not text or not isinstance(text, str):
        return None
    t = text.strip()
    name = ""
    trigger_value = ""
    custom_message = ""
    # Kural Adı: ... (Türkçe karakterler)
    for label in ("Kural Adı:", "Kural adı:", "Kural Adi:"):
        i = t.find(label)
        if i >= 0:
            rest = t[i + len(label) :].strip()
            end = len(rest)
            for stop in ("Tetikleyici", "Özel Mesaj", "Kuralı oluşturdum", "Kural oluşturma", "\n\n"):
                j = rest.find(stop)
                if j >= 0:
                    end = min(end, j)
            name = rest[:end].strip().strip(".,")
            break
    # Tetikleyici Türü: ... veya Tetikleyici Değeri: ...
    for label in ("Tetikleyici Değeri:", "Tetikleyici Degeri:", "Tetikleyici Türü:", "Tetikleyici Turu:", "Tetikleyici:"):
        i = t.find(label)
        if i >= 0:
            rest = t[i + len(label) :].strip()
            end = len(rest)
            for stop in ("Özel Mesaj", "Kural Adı", "Kuralı oluşturdum", "\n\n"):
                j = rest.find(stop)
                if j >= 0:
                    end = min(end, j)
            part = rest[:end].strip().strip(".,")
            if part:
                trigger_value = (trigger_value + ", " + part) if trigger_value else part
    trigger_value = ", ".join(v.strip() for v in trigger_value.split(",") if v.strip()).strip()
    # Özel Mesaj: ...
    for label in ("Özel Mesaj:", "Ozel Mesaj:"):
        i = t.find(label)
        if i >= 0:
            rest = t[i + len(label) :].strip()
            end = len(rest)
            for stop in ("Kuralı oluşturdum", "Kural Adı", "Tetikleyici", "\n\n"):
                j = rest.find(stop)
                if j >= 0:
                    end = min(end, j)
            custom_message = rest[:end].strip().strip(".,")
            break
    if not name and not trigger_value:
        return None
    return {
        "action": "create_rule",
        "name": name or "Yardım sohbeti kuralı",
        "trigger_type": "keyword",
        "trigger_value": trigger_value or "genel",
        "product_ids": "[]",
        "image_urls": "[]",
        "custom_message": custom_message,
        "priority": 0,
    }


def _parse_create_rule(text: str) -> dict | None:
    """Yanıt metninde create_rule JSON bloğu arar; bulursa dict döner."""
    if not text or "create_rule" not in text:
        return None
    # ```json ... ``` veya ``` ... ``` içindeki ilk { ... } bloğunu al (brace matching basit: ilk { ile eşleşen }).
    for marker in ("```json", "```"):
        idx = text.find(marker)
        if idx == -1:
            continue
        start = idx + len(marker)
        end = text.find("```", start)
        if end == -1:
            continue
        chunk = text[start:end].strip()
        brace = chunk.find("{")
        if brace == -1:
            continue
        depth = 0
        for i, c in enumerate(chunk[brace:], start=brace):
            if c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
                if depth == 0:
                    try:
                        data = json.loads(chunk[brace : i + 1])
                        if data.get("action") == "create_rule":
                            return data
                    except json.JSONDecodeError:
                        pass
                    break
    return None


def _apply_create_rule_and_clean_message(text: str, rule_data: dict, rule_name: str) -> str:
    """create_rule JSON bloğunu başarı mesajıyla değiştirir."""
    for pattern in (
        r'```json\s*\{.*?"action"\s*:\s*"create_rule".*?\}\s*```',
        r'```\s*\{.*?"action"\s*:\s*"create_rule".*?\}\s*```',
    ):
        text = re.sub(pattern, f"✅ Kural oluşturuldu: **{rule_name}**. Kurallar sayfasından düzenleyebilirsin: /admin/rules", text, flags=re.DOTALL, count=1)
    return text.strip()


@router.get("/api/chat/support/health")
async def support_chat_health():
    """
    Panel yardım sohbeti sağlık kontrolü — Emare Asistan tenant (id=2) Gemini bağlantısını test eder.
    """
    from services import AIAssistant
    tenant_settings = await get_tenant_settings(2)
    settings = get_settings()
    gemini_key = tenant_settings.get("gemini_api_key") or settings.gemini_api_key
    gemini_model = tenant_settings.get("gemini_model") or settings.gemini_model or "gemini-2.5-flash-lite"
    if not gemini_key:
        return {"ok": False, "error": "Emare Asistan tenant (id=2) veya .env'de GEMINI_API_KEY tanımlı değil"}
    try:
        ai = AIAssistant()
        overrides = {
            "disable_local_llm": True,
            "gemini_api_key": gemini_key,
            "gemini_model": gemini_model,
        }
        r = await ai.chat(
            user_message="Merhaba",
            conversation_history=[],
            tenant_name="Test",
            prompt_override="Kısa cevap ver: tamam",
            api_overrides=overrides,
        )
        text = r.get("text", "")
        if text and ("gecikme" in text.lower() or "alınamadı" in text or "oluşturulamadı" in text):
            return {"ok": False, "error": "Gemini yanıt veremedi", "response_preview": text[:100]}
        return {"ok": True, "model": overrides["gemini_model"]}
    except Exception as e:
        logger.exception("Support chat health check failed")
        return {"ok": False, "error": str(e)[:200]}


@router.post("/api/chat/support")
async def support_chat_send(body: SupportChatRequest, http_request: Request):
    """
    Panel yardım sohbeti - "Nasıl yaparım?", "Bu ne işe yarar?" gibi sorulara AI yanıt.
    "Bu kuralı oluştur" denirse AI create_rule JSON döndürebilir; oturum açık kullanıcının tenant'ına kural yazarız.
    """
    try:
        return await _support_chat_handle(body, http_request)
    except Exception as e:
        logger.exception("Support chat error: %s", e)
        return {"text": "Yardım sohbeti geçici olarak kullanılamıyor. Lütfen biraz sonra tekrar deneyin."}


async def _support_chat_handle(body: SupportChatRequest, http_request: Request):
    if not (body.message or "").strip():
        return {"text": "Lütfen bir soru yazın."}

    tid = _get_tenant_id_from_request(http_request)
    tenant_name = "Genel"
    if tid:
        try:
            t_settings = await get_tenant_settings(tid)
            tenant_name = (t_settings.get("name") or "").strip() or f"Firma {tid}"
        except Exception:
            tenant_name = f"Firma {tid}"

    session_id = (body.session_id or "").strip() or "anon"
    user_id = f"support-{session_id}"

    async with AsyncSessionLocal() as db:
        conv = await _get_or_create_support_conversation(db, user_id)
        history = await _get_history(db, conv.id, limit=20)

        ai = AIAssistant()
        help_ctx = _load_help_context()
        system_prompt = SUPPORT_SYSTEM_PROMPT + help_ctx
        system_prompt += f"\n\n**Şu anki panel:** Kullanıcı **{tenant_name}** firmasının panelinde. Kurallar bu firmaya kaydedilir. Yanıt verirken hangi firmada olduğunu biliyorsun."
        if body.role:
            system_prompt += f"\n\nKullanıcı rolü: {body.role}"

        conv_hist = [{"role": h["role"], "content": h["content"]} for h in history]

        settings = get_settings()
        tenant_settings = await get_tenant_settings(2)
        gemini_key = tenant_settings.get("gemini_api_key") or settings.gemini_api_key
        openai_key = tenant_settings.get("openai_api_key") or settings.openai_api_key
        gemini_model = (tenant_settings.get("gemini_model") or settings.gemini_model or "").strip() or "gemini-2.5-flash-lite"
        key_source = "tenant2" if tenant_settings.get("gemini_api_key") else "env"
        logger.info("Support chat: key_source=%s model=%s key_ok=%s", key_source, gemini_model, bool(gemini_key))

        api_overrides = {"disable_local_llm": True}
        if gemini_key:
            api_overrides["gemini_api_key"] = gemini_key
            api_overrides["gemini_model"] = gemini_model
        elif openai_key:
            api_overrides["openai_api_key"] = openai_key
        else:
            err = "Yardım sohbeti şu an kullanılamıyor. Emare Asistan (tenant 2) ayarlarında veya .env dosyasında GEMINI_API_KEY tanımlanmalı. Lütfen yöneticiyle iletişime geçin."
            logger.warning("Support chat: No API key (tenant 2 or .env). All users need Emare Asistan config.")
            await _save_message(db, conv.id, "user", (body.message or "").strip())
            await _save_message(db, conv.id, "assistant", err)
            await db.commit()
            return {"text": err}

        response = await ai.chat(
            user_message=(body.message or "").strip(),
            conversation_history=conv_hist,
            tenant_name="Emare Asistan Yardım",
            prompt_override=system_prompt,
            api_overrides=api_overrides,
        )

        err_msg = response.get("text", "")
        is_error = err_msg and (
            "teknik bir gecikme" in err_msg.lower()
            or "gecikme yasiyoruz" in err_msg.lower()
            or "alınamadı" in err_msg
            or "oluşturulamadı" in err_msg
        )
        if is_error:
            if gemini_key and gemini_model == "gemini-2.5-flash-lite":
                logger.warning("Support chat Gemini 2.5-flash-lite failed, retrying with gemini-2.0-flash")
                try:
                    r2 = await ai.chat(
                        user_message=(body.message or "").strip(),
                        conversation_history=conv_hist,
                        tenant_name="Emare Asistan Yardım",
                        prompt_override=system_prompt,
                        api_overrides={"disable_local_llm": True, "gemini_api_key": gemini_key, "gemini_model": "gemini-2.5-flash-lite"},
                    )
                    if r2.get("text") and "gecikme" not in (r2.get("text") or "").lower():
                        response = r2
                        is_error = False
                except Exception as e2:
                    logger.warning("Support chat gemini-2.0-flash fallback failed: %s", e2)
            if is_error and gemini_key and openai_key:
                logger.warning("Support chat Gemini failed, retrying with OpenAI")
                try:
                    response = await ai.chat(
                        user_message=(body.message or "").strip(),
                        conversation_history=conv_hist,
                        tenant_name="Emare Asistan Yardım",
                        prompt_override=system_prompt,
                        api_overrides={"disable_local_llm": True, "openai_api_key": openai_key},
                    )
                except Exception as e2:
                    logger.exception("Support chat OpenAI fallback failed: %s", e2)

        response_text = response.get("text", "").strip()
        if not response_text:
            response_text = "Yanıt şu an alınamadı (API gecikmesi veya yoğunluk). Lütfen birkaç saniye sonra tekrar deneyin. Kuralı elle eklemek için Kurallar sayfasından da oluşturabilirsiniz: /admin/rules"
        rule_data = _parse_create_rule(response_text)
        if not rule_data and ("Kuralı oluşturdum" in response_text or "Kural Adı:" in response_text or "Kural adı:" in response_text):
            rule_data = _parse_create_rule_from_text_fallback(response_text)
        if rule_data:
            tid = _get_tenant_id_from_request(http_request)
            if tid is not None:
                try:
                    name = (rule_data.get("name") or "").strip() or "Yardım sohbeti kuralı"
                    trigger_type = (rule_data.get("trigger_type") or "keyword").strip()
                    if trigger_type not in ("vehicle_model", "keyword"):
                        trigger_type = "keyword"
                    trigger_value = (rule_data.get("trigger_value") or "").strip() or "genel"
                    product_ids = rule_data.get("product_ids")
                    if isinstance(product_ids, list):
                        product_ids = json.dumps(product_ids)
                    product_ids = (product_ids or "[]").strip() if isinstance(product_ids, str) else "[]"
                    image_urls = rule_data.get("image_urls")
                    if isinstance(image_urls, list):
                        image_urls = json.dumps(image_urls)
                    image_urls = (image_urls or "[]").strip() if isinstance(image_urls, str) else "[]"
                    custom_message = (rule_data.get("custom_message") or "").strip()
                    priority = int(rule_data.get("priority") or 0)
                    rule = ResponseRule(
                        tenant_id=tid,
                        name=name,
                        trigger_type=trigger_type,
                        trigger_value=trigger_value,
                        product_ids=product_ids,
                        image_urls=image_urls,
                        custom_message=custom_message,
                        is_active=True,
                        priority=priority,
                    )
                    db.add(rule)
                    await db.flush()
                    response_text = f"✅ Kural oluşturuldu: **{name}**. Giriş yaptığınız firmaya kaydedildi. Kurallar sayfasından görebilirsiniz: /admin/rules"
                    logger.info("Support chat created rule id=%s name=%s tenant_id=%s", rule.id, name, tid)
                except Exception as e:
                    logger.exception("Support chat create_rule failed: %s", e)
            else:
                response_text = response_text + "\n\n(Giriş yapılı bir firma panelinde değilsiniz; kural kaydedilemedi. Firma paneline girip tekrar deneyin.)"

        await _save_message(db, conv.id, "user", (body.message or "").strip())
        await _save_message(db, conv.id, "assistant", response_text)
        await db.commit()

    return {"text": response_text}


async def _get_or_create_support_conversation(db: AsyncSession, user_id: str):
    from datetime import datetime

    r = await db.execute(
        select(Conversation).where(
            Conversation.platform == "support",
            Conversation.platform_user_id == user_id,
        )
    )
    conv = r.scalar_one_or_none()
    if conv:
        conv.last_message_at = datetime.utcnow()
        return conv
    conv = Conversation(
        platform="support",
        platform_user_id=user_id,
        tenant_id=2,
    )
    db.add(conv)
    await db.flush()
    return conv


async def _get_history(db: AsyncSession, conversation_id: int, limit: int = 20):
    r = await db.execute(
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.id.desc())
        .limit(limit)
    )
    msgs = list(reversed(r.scalars().all()))
    return [{"role": m.role, "content": (m.content or "").strip()} for m in msgs]


async def _save_message(db: AsyncSession, conversation_id: int, role: str, content: str):
    msg = Message(conversation_id=conversation_id, role=role, content=content)
    db.add(msg)
