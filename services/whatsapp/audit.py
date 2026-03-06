"""
Chat Denetim Servisi - Asenkron AI ile sohbet yanıtlarını değerlendirir.
Yanıt müşteriye gittikten sonra arka planda çalışır. Analitik amaçlı.
"""
import json
import logging
import random
from typing import Optional

from config import get_settings
from services.core.settings import get_chat_audit_enabled
from models.database import AsyncSessionLocal
from models.chat_audit import ChatAudit

logger = logging.getLogger(__name__)

AUDIT_SYSTEM_PROMPT = """Sen bir müşteri hizmetleri kalite denetçisisin. Verilen müşteri mesajı ve asistan yanıtını değerlendir.

Kontrol et:
1. Yanıt müşteri sorusuna uygun mu?
2. Yanlış bilgi var mı? (fiyat, adres, telefon, link)
3. Kurumsal dil ve ton uygun mu? (kibar, "siz" hitabı)
4. Gereksiz tekrar veya tutarsızlık var mı?
5. Müşteriye yanlış yönlendirme (sahte numara, yanlış link) var mı?

Yanıtı JSON formatında ver. Başka metin yazma, sadece JSON:
```json
{
  "score": 70,
  "passed": true,
  "issues": [],
  "suggested_correction": null,
  "notes": "Kısa değerlendirme notu"
}
```

- score: 0-100 genel kalite puanı
- passed: true ise sorun yok, false ise düzeltme gerekebilir
- issues: Sorun varsa [{"type": "wrong_info|tone|irrelevant|wrong_link", "desc": "açıklama", "severity": "low|medium|high"}]
- suggested_correction: Düzeltilmiş yanıt önerisi (varsa)
- notes: Kısa özet
"""


async def _call_audit_ai(user_message: str, assistant_response: str) -> Optional[dict]:
    """AI ile denetim yap"""
    settings = get_settings()
    if not settings.gemini_api_key and not settings.openai_api_key:
        logger.warning("Chat audit: API key yok, denetim atlanıyor")
        return None

    prompt = f"""Müşteri mesajı:
{user_message[:2000]}

Asistan yanıtı:
{(assistant_response or "")[:2000]}

Değerlendir ve JSON döndür."""

    try:
        if settings.gemini_api_key:
            import google.generativeai as genai
            genai.configure(api_key=settings.gemini_api_key)
            model = genai.GenerativeModel(settings.gemini_model or "gemini-2.5-flash-lite")
            response = await model.generate_content_async(
                [AUDIT_SYSTEM_PROMPT, prompt],
                generation_config=genai.types.GenerationConfig(
                    temperature=0.2,
                    max_output_tokens=512,
                ),
            )
            text = (response.text or "").strip()
        else:
            from openai import AsyncOpenAI
            client = AsyncOpenAI(api_key=settings.openai_api_key)
            r = await client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": AUDIT_SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.2,
                max_tokens=512,
            )
            text = (r.choices[0].message.content or "").strip()

        # JSON parse et
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0].strip()
        elif "```" in text:
            text = text.split("```")[1].split("```")[0].strip()
        data = json.loads(text)
        return data
    except Exception as e:
        logger.exception("Chat audit AI hatası: %s", e)
        return None


async def run_chat_audit(
    tenant_id: int,
    conversation_id: int,
    platform: str,
    user_message: str,
    assistant_response: str,
    sample_rate: int = 20,
) -> Optional[ChatAudit]:
    """
    Asenkron sohbet denetimi. sample_rate 0-100, %X olasılıkla denetim yapar.
    Returns: ChatAudit kaydı veya None (denetim yapılmadıysa)
    """
    if not get_chat_audit_enabled():
        return None

    if sample_rate <= 0 or (sample_rate < 100 and random.randint(1, 100) > sample_rate):
        return None

    if not (user_message or "").strip() or not (assistant_response or "").strip():
        return None

    result = await _call_audit_ai(user_message, assistant_response)
    if not result:
        return None

    audit = ChatAudit(
        tenant_id=tenant_id,
        conversation_id=conversation_id,
        platform=platform or "",
        user_message=(user_message or "")[:4000],
        assistant_response=(assistant_response or "")[:4000],
        score=float(result.get("score", 0)) if result.get("score") is not None else None,
        passed=bool(result.get("passed", True)),
        issues=json.dumps(result.get("issues", [])) if result.get("issues") else None,
        suggested_correction=(result.get("suggested_correction") or "")[:2000] or None,
        audit_notes=(result.get("notes") or "")[:500] or None,
    )

    async with AsyncSessionLocal() as db:
        db.add(audit)
        await db.commit()
        await db.refresh(audit)

    logger.info("Chat audit: conv=%s score=%s passed=%s", conversation_id, audit.score, audit.passed)
    return audit
