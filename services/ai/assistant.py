"""
AI Asistan - Çekirdek mantık (tenant bağımsız)
Müşteri sorularına cevap, ürün önerisi, sipariş ve kargo bilgisi
OpenAI veya Gemini API destekler
"""
from __future__ import annotations
import asyncio
import json
import logging
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional
from zoneinfo import ZoneInfo
from sqlalchemy import select, desc
from models.database import AsyncSessionLocal
from models.audit_log import AuditLog
from config import get_settings

logger = logging.getLogger(__name__)


def _get_system_prompt(tenant_name: str = "Firma", tenant_phone: str = "") -> str:
    """Dinamik sistem talimatı - tenant adı ve telefonu ile"""
    phone = tenant_phone or get_settings().default_tenant_phone
    return f"""Sen {tenant_name}'nin profesyonel müşteri hizmetleri asistanısın.
{tenant_name} bir satış firmasıdır. Ürün kataloğu müşteri mesajına göre sunulacaktır.

Görevlerin:
1. Müşteri sorularına profesyonel, kibar ve kurumsal dille cevap ver
2. Ürün önerisi yap - araç modeli, bütçe veya ihtiyaca göre
3. Sipariş almaya yardım et - ürün adı, adres, iletişim bilgisi topla
4. Kargo takibi hakkında bilgi ver - takip numarası ile sorgulama yapılabilir
5. İade/garanti politikası hakkında bilgi ver
6. Konum/adres istendiğinde {tenant_name} adresini ver ve konum paylaşacağını belirt
7. Montaj/takma sorulduğunda: Montaj işlemleri mağzamızda yapılıyor. Montaj süresi 2-2.5 saat sürebiliyor.

Önemli kurallar:
- Profesyonel ve kurumsal dil kullan. "Siz" hitabı kullan.
- Samimi ama resmi kal. Argo, kısaltma ve aşırı gündelik ifadelerden kaçın.
- Cevapları KISA tut: 2-4 cümle yeterli. Öz, net, anlaşılır. Paragraflardan kaçın.
- Yazım yanlışlarını tolere et (rsm=resim, goster=göster vb.) - mesaj metni düzeltilmiş olarak gelir.
- ASLA ikinci ve sonraki mesajlarda "Merhaba", "Hoş geldiniz" vb. selamlama tekrarlama. Sohbet devam ediyorsa doğrudan yanıtla.
- Montaj VİDEOSU sorulduğunda (montaj videosu var mı, montaj videosu, kurulum videosu, nasıl takılır video, montaj görüntüsü): MUTLAKA sadece şu linki ver: https://www.youtube.com/watch?v=ghKZxRCtwK4 Örnek cevap: "Montaj videomuz burada: https://www.youtube.com/watch?v=ghKZxRCtwK4"
- Montaj fiyatı/süresi/takma (video OLMADAN) sorulduğunda: "Montaj işlemleri mağzamızda yapılıyor. Montaj süresi 2-2.5 saat sürebiliyor" de
- Ürün bilgisi verirken mevcut ürün listesini kullan
- Sipariş alırken ZORUNLU: Ad Soyad, Telefon, Adres ve Ödeme seçeneği (Havale/Kredi Kartı/Kapıda Ödeme) EKSİKSİZ toplanmalı. Eksik bilgi varsa create_order DÖNDÜRME, önce eksik bilgiyi kibarca sor.
- Sohbet gecmisinde musteri ad-soyad, telefon, e-posta veya website bilgisini ONCEDEN paylastiysa AYNI bilgiyi tekrar isteme. Sadece eksik olan alani sor.
- Ozellikle ilk karsilamada Emare Asistan'in ne yaptigini kisaca acikla ve "daha fazla bilgi verebilirim" tonunu kullan.
- Yanitlariniz tatmin edici olsun: mumkunse 1 somut fayda + 1 kisa ornek senaryo ile cevap ver.
- Ayni kalip soruyu her mesajda tekrar etme; soru cumlelerini varyasyonlu kullan ve 2-3 farkli ornekle zenginlestir.
- Musteri "detay", "nasil", "ornek" istediginde daha dolu cevap ver: 3 net madde (fayda, isleyis, sonraki adim) ile ilerle.
- Randevu konusunda DOĞAL ve SOHBET tonunda konuş. İlk randevu sorusunda hemen slot listeleme — önce suggest_replies ile birkaç seçenek sun (Randevu almak istiyorum / Önce bilgi almak istiyorum / Fiyat sormak istiyorum). Müşteri açıkça 'randevu almak istiyorum' dediğinde 2-3 uygun slot öner (hepsini değil). Müşteri slotu onayladıktan sonra ad-soyad ve telefon al, create_appointment döndür. KESINLIKLE ISRARCI OLMA ve randevuyu zorıama.
- Adres yalnızca mahalle/ilçe (örn: "Bulgurlu Üsküdar") ise tam adres iste: sokak, bina no, daire, ilçe, il - kargo teslimi için gerekli.
- Bilmediğin konularda "Detaylı bilgi için {phone} numaralı hattımızdan bizi arayabilirsiniz" de
- Temsilci, insan, canlı görüşme, yetkili istediğinde MUTLAKA şu numarayı ver: {phone}. ASLA sahte/örn numara (0850 xxx, 444 xxx vb.) uydurma.
- Ürün önerisi yaparken SADECE müşteri resim/görsel istemediğinde "İsterseniz ürünlerin resimlerini paylaşabilirim" de. Müşteri AÇIKÇA "resim yolla", "resim gönder", "yolla", "gönder", "paylaş", "göster" dediyse SORMA - kısa onay ver: "İşte ürünlerimiz:" vb.
- Ürün resmi göndermek için JSON'da "send_image" ve "image_url" kullan
- Birden fazla ürün önerirken JSON'da "suggested_products" array'i kullan
- Ürün KARŞILAŞTIRMASI: Müşteri "karşılaştır", "fark", "aralarındaki fark", "hangisi daha iyi", "elit ekonom", "vs" gibi karşılaştırma istediğinde yanıtı TABLO formatında ver. Örnek:
```
| Ürün | Fiyat | Kategori | Özellik |
|------|-------|----------|---------|
| Elit Paspas | 599 TL | 7D | Deri |
| Ekonom Paspas | 399 TL | 7D | Polyester |
```
Kısa giriş cümlesi + tablo (``` ile sar). Sonra "İsterseniz ürünlerin resimlerini paylaşabilirim" ekle.

Yanıt formatı: Önce metin cevabı ver (ürün önerisinde mutlaka "İsterseniz ürünlerin resimlerini paylaşabilirim" de), sonra JSON bloğu ekle:
```json
{{"action": "send_image", "image_url": "url", "caption": "Ürün açıklaması"}}
```
veya
```json
{{"action": "suggest_products", "product_ids": [1,2,3], "message": "İşte size uygun ürünler"}}
```
veya (sadece Ad Soyad, Telefon, Adres, Ödeme seçeneği HEPSİ eksiksiz olduğunda sipariş oluştur):
```json
{{"action": "create_order", "customer_name": "Ad Soyad", "customer_phone": "0532 123 45 67", "customer_address": "Tam adres (il, ilçe, mahalle, sokak, bina no dahil)", "payment_option": "havale" veya "kredi_karti" veya "kapida_odeme", "items": [{{"name": "Ürün adı", "price": 5999, "quantity": 1}}]}}
```
veya (sadece randevu saati + ad soyad + telefon net olduğunda):
```json
{{"action": "create_appointment", "scheduled_at": "YYYY-MM-DD HH:MM", "customer_name": "Ad Soyad", "customer_phone": "0532 123 45 67"}}
```
veya (müşteriye tıklanabilir soru seçenekleri sunmak için - karşılama, "nasıl yardımcı olabilirim" veya net sonraki adımlar için):
```json
{{"action": "suggest_replies", "options": [{{"label": "Kısa etiket", "text": "Müşterinin göndereceği tam metin"}}]}}
```
Örnek: 2-4 seçenek ver. label: "Ürünler", "Sipariş takibi", "Fiyat teklifi", "Demo randevusu" gibi kısa. text: müşteri tıklayınca gönderilecek gerçek mesaj (örn: "Ürünler hakkında bilgi almak istiyorum").
Ödeme seçenekleri: havale (Havale/EFT), kredi_karti (Kredi Kartı), kapida_odeme (Kapıda Ödeme). Müşteri söylemeden create_order döndürme.

Kısa yanıt kuralı: Maksimum 2-4 cümle. Öz, net, anlaşılır. Paragraflardan kaçın.
"""


class AIAssistant:
    """AI Asistan - OpenAI veya Gemini (tenant bağımsız)"""

    def __init__(self):
        settings = get_settings()
        self._settings = settings
        self._local_llm_enabled = bool(settings.local_llm_enabled)
        self._local_llm_base_model = settings.local_llm_base_model or "Qwen/Qwen2.5-0.5B-Instruct"
        self._local_llm_adapter_path = settings.local_llm_adapter_path or "./scripts/local_llm/artifacts/local_lora"
        self._local_llm_chat_script = settings.local_llm_chat_script or "./scripts/local_llm/chat.py"
        self._local_llm_python_bin = settings.local_llm_python_bin or "./scripts/local_llm/.venv/bin/python"
        self._local_llm_max_new_tokens = int(settings.local_llm_max_new_tokens or 96)
        self._local_llm_timeout_sec = int(settings.local_llm_timeout_sec or 240)
        self._local_llm_min_confidence = int(settings.local_llm_min_confidence or 55)
        self._local_tune_cache_ttl_sec = 1800
        self._local_threshold_cache: dict[int, tuple[datetime, int]] = {}

        # GEMINI_API_KEY verilmişse Gemini kullan, yoksa OpenAI
        self._use_gemini = bool(settings.gemini_api_key)
        self._openai_client = None
        self._openai_model = "gpt-4o-mini"
        self._gemini_api_key = settings.gemini_api_key
        self._gemini_model = settings.gemini_model or "gemini-2.5-flash-lite"
        if self._use_gemini:
            pass
        else:
            key = settings.openai_api_key
            if key:
                from openai import AsyncOpenAI
                self._openai_client = AsyncOpenAI(api_key=key)
            elif not self._local_llm_enabled:
                raise ValueError("OPENAI_API_KEY veya GEMINI_API_KEY .env dosyasında tanımlanmalı")

    async def chat(
        self,
        user_message: str,
        conversation_history: list[dict] | None = None,
        product_context: str = "",
        order_context: str = "",
        appointment_context: str = "",
        location_context: str = "",
        training_context: str = "",
        tenant_name: str = "Firma",
        tenant_phone: str = "",
        tenant_id: int | None = None,
        prompt_override: str = "",
        api_overrides: dict | None = None,
        response_rules: list[dict] | None = None,
    ) -> dict:
        """
        Müşteri mesajına yanıt üretir.
        Returns: {"text": str, "image_url": str | None, "suggested_products": list | None}
        """
        effective_name = tenant_name or "Firma"
        base_prompt = (prompt_override or "").strip() or _get_system_prompt(effective_name, tenant_phone)
        branding_block = f"""ÖNEMLİ MARKA KURALI:
- Tüm konuşmalarda şirket adını yalnızca \"{effective_name}\" olarak kullan.
- Eski veya farklı marka adları (örn. Defence 360, Emare Asistan, Meridyen Oto vb.) kullanma.
- Müşteri şirkete atıfta bulunduğunda \"{effective_name}\" adıyla cevap ver."""
        system_prompt = f"{base_prompt}\n\n{branding_block}".strip()
        rules = response_rules if isinstance(response_rules, list) else []
        if rules:
            lines = []
            for r in sorted(rules, key=lambda x: (-(x.get("priority") or 0), x.get("text", ""))):
                t = (r.get("text") or "").strip()
                if t:
                    lines.append(f"- {t}")
            if lines:
                system_prompt = f"{system_prompt}\n\nEk yanıt kuralları (panelden yönetilir, mutlaka uygula):\n" + "\n".join(lines)

        # Anlık tarih-saat bilgisi (Türkiye)
        _tr_day_names = ["Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi", "Pazar"]
        _tr_month_names = ["", "Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran",
                           "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık"]
        _now = datetime.now(ZoneInfo("Europe/Istanbul"))
        _datetime_block = (
            f"Şu anki tarih ve saat (Türkiye): "
            f"{_tr_day_names[_now.weekday()]} {_now.day} {_tr_month_names[_now.month]} {_now.year}, "
            f"saat {_now.strftime('%H:%M')}. "
            "Randevu önerisi, bugün ne günü, yarın ne zaman gibi sorularda bu bilgiyi kullan."
        )
        system_prompt = f"{system_prompt}\n\n{_datetime_block}"

        messages = [
            {"role": "system", "content": system_prompt},
        ]

        if product_context:
            messages.append(
                {
                    "role": "system",
                    "content": f"Mevcut ürün bilgileri:\n{product_context}",
                }
            )
        if order_context:
            messages.append(
                {
                    "role": "system",
                    "content": f"Sipariş/Kargo bilgisi:\n{order_context}",
                }
            )
        if appointment_context:
            messages.append(
                {
                    "role": "system",
                    "content": f"Randevu bilgisi:\n{appointment_context}",
                }
            )
        if location_context:
            messages.append(
                {
                    "role": "system",
                    "content": f"Konum/Adres bilgisi (müşteri istediğinde paylaş):\n{location_context}",
                }
            )
        if training_context:
            messages.append(
                {
                    "role": "system",
                    "content": f"Eğitim örnekleri:\n{training_context}",
                }
            )

        if conversation_history:
            messages.append({
                "role": "system",
                "content": "Sohbet devam ediyor. Önceki mesajlarda müşterinin paylaştığı ad, telefon, adres vb. bilgileri tekrar isteme. Selamlama tekrarlama.",
            })
            for msg in conversation_history[-24:]:  # Son 24 mesaj - aynı numara ile tekrar önleme
                messages.append(msg)

        messages.append({"role": "user", "content": user_message})

        fallback_phone = tenant_phone or get_settings().default_tenant_phone
        overrides = api_overrides or {}
        local_enabled = self._local_llm_enabled and not overrides.get("disable_local_llm")
        local_error: str | None = None
        effective_threshold = self._local_llm_min_confidence
        if local_enabled:
            effective_threshold = await self._resolve_local_threshold(
                tenant_id=tenant_id,
                overrides=overrides,
            )
        if local_enabled:
            try:
                local_content = await self._chat_local(messages, overrides)
                if local_content and local_content.strip():
                    local_result = self._parse_response(local_content)
                    local_text = (local_result.get("text") or "").strip()
                    local_score = self._score_local_answer(
                        user_message=user_message,
                        conversation_history=conversation_history or [],
                        reply_text=local_text,
                    )
                    if local_score >= effective_threshold:
                        await self._log_local_route_event(
                            tenant_id=tenant_id,
                            action="ai_local_accepted",
                            details={
                                "confidence": local_score,
                                "threshold": effective_threshold,
                                "base_threshold": self._local_llm_min_confidence,
                            },
                        )
                        return local_result
                    local_error = f"low_confidence:{local_score}"
                    await self._log_local_route_event(
                        tenant_id=tenant_id,
                        action="ai_local_low_confidence",
                        details={
                            "confidence": local_score,
                            "threshold": effective_threshold,
                            "base_threshold": self._local_llm_min_confidence,
                        },
                    )
                    logger.info(
                        "Local LLM confidence dusuk (%s < %s), API fallback",
                        local_score,
                        effective_threshold,
                    )
            except Exception as e:
                local_error = str(e)
                await self._log_local_route_event(
                    tenant_id=tenant_id,
                    action="ai_local_error",
                    details={
                        "error": str(e)[:220],
                        "threshold": effective_threshold,
                        "base_threshold": self._local_llm_min_confidence,
                    },
                )
                logger.warning("Local LLM fallback başarısız, uzak modele dönülüyor: %s", e)

        # Tenant API anahtarı varsa öncelik: gemini > openai
        use_gemini = bool(overrides.get("gemini_api_key")) or (
            not overrides.get("openai_api_key") and self._use_gemini
        )

        try:
            if use_gemini:
                content = await self._chat_gemini(messages, fallback_phone, overrides)
            else:
                content = await self._chat_openai(messages, overrides)
        except Exception as e:
            logger.error("AI API hatası (support/müşteri sohbeti): %s", e, exc_info=True)

            # Gemini geçici olarak erişilemezse OpenAI'a otomatik düş
            if use_gemini:
                has_openai_key = bool((overrides.get("openai_api_key") or "").strip())
                if has_openai_key or self._openai_client is not None:
                    try:
                        logger.warning("Gemini hatası sonrası OpenAI fallback deneniyor")
                        content = await self._chat_openai(messages, overrides)
                        return self._parse_response(content)
                    except Exception as openai_e:
                        logger.error("OpenAI fallback de başarısız: %s", openai_e, exc_info=True)

            if local_error:
                if str(local_error).startswith("low_confidence:"):
                    content = (
                        "Su anda dis AI servisinde gecici bir teknik sorun var. "
                        "Lutfen kisa bir sure sonra tekrar deneyin."
                    )
                else:
                    content = (
                        "Yerel model su an gec cevap veriyor. "
                        "Lutfen daha kisa bir mesajla tekrar deneyin veya birazdan yeniden yazin."
                    )
            else:
                # API koptu, lokal model atlanmisti (WhatsApp vb.) - simdi lokal fallback dene
                # Not: Lokal LLM Emare Asistan verisiyle egitilmis, diger tenantlar icin
                # yanlis icerik uretir. Sadece platform tenantlari (1, 2) icin kullan.
                use_local_fallback = (
                    overrides.get("disable_local_llm")
                    and self._local_llm_enabled
                    and tenant_id in (None, 1, 2)
                )
                if use_local_fallback:
                    logger.info("Uzak API basarisiz, lokal model fallback deneniyor: %s", e)
                    try:
                        fallback_overrides = {k: v for k, v in (overrides or {}).items() if k != "disable_local_llm"}
                        local_content = await self._chat_local(messages, fallback_overrides)
                        if local_content and local_content.strip():
                            local_result = self._parse_response(local_content)
                            if local_result.get("text"):
                                return local_result
                    except Exception as loc_e:
                        logger.warning("Lokal fallback da basarisiz: %s", loc_e)
                phone_part = f" veya {fallback_phone} numarasindan bizi arayabilirsiniz." if fallback_phone else "."
                content = f"Su anda teknik bir gecikme yasiyoruz. Lutfen kisa bir sure sonra tekrar deneyin{phone_part}"

        return self._parse_response(content)

    async def _chat_openai(self, messages: list, overrides: dict | None = None) -> str:
        """OpenAI ile sohbet"""
        overrides = overrides or {}
        if overrides.get("openai_api_key"):
            from openai import AsyncOpenAI
            client = AsyncOpenAI(api_key=overrides["openai_api_key"])
            model = self._openai_model
        else:
            if self._openai_client is None:
                raise RuntimeError("OpenAI istemcisi hazır değil. OPENAI_API_KEY tanımlayın veya local_llm_enabled kullanın.")
            client = self._openai_client
            model = self._openai_model
        response = await client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=0.7,
        )
        return response.choices[0].message.content or ""

    async def _chat_gemini(self, messages: list, fallback_phone: str = "", overrides: dict | None = None) -> str:
        """Gemini ile sohbet - REST API kullanır (SDK gRPC 'Illegal header value' hatası nedeniyle)."""
        import httpx

        overrides = overrides or {}
        gemini_key = overrides.get("gemini_api_key") or self._gemini_api_key
        if not gemini_key:
            raise RuntimeError("Gemini API anahtarı bulunamadı.")
        model_name = overrides.get("gemini_model") or get_settings().gemini_model or "gemini-2.5-flash-lite"
        model_path = model_name if model_name.startswith("models/") else f"models/{model_name}"
        url = f"https://generativelanguage.googleapis.com/v1beta/{model_path}:generateContent?key={gemini_key}"

        # Gemini API: Prompt oluştur - system_instruction ile proje seviyesi talimatları geçersiz kıl
        system_parts = []
        user_parts = []
        for m in messages:
            role = m.get("role", "user")
            content = m.get("content", "")
            if role == "system":
                system_parts.append(content)
            else:
                prefix = "[Müşteri]" if role == "user" else "[Asistan]"
                user_parts.append(f"{prefix}\n{content}")

        system_text = "\n\n".join(system_parts) if system_parts else ""
        conversation_text = "\n\n".join(user_parts) if user_parts else ""

        # system_instruction alanı proje varsayılan talimatlarını geçersiz kılar
        request_body = {
            "system_instruction": {"parts": [{"text": system_text}]} if system_text else None,
            "contents": [{"role": "user", "parts": [{"text": conversation_text}]}],
        }
        # None alanları kaldır
        request_body = {k: v for k, v in request_body.items() if v is not None}

        for attempt in range(2):
            try:
                async with httpx.AsyncClient(timeout=35.0) as client:
                    resp = await client.post(url, json=request_body)
                if resp.status_code != 200:
                    err_text = (resp.text or "")[:500]
                    logger.error(
                        "Gemini API HTTP %s (model=%s): %s",
                        resp.status_code,
                        overrides.get("gemini_model") or model_name,
                        err_text,
                    )
                    if resp.status_code == 429 or "quota" in err_text.lower() or "resourceexhausted" in err_text.lower():
                        retry_sec = 2 + attempt * 2
                        logger.warning("Gemini API kota aşıldı, %s sn sonra tekrar (deneme %d/2)", retry_sec, attempt + 1)
                        await asyncio.sleep(retry_sec)
                        continue
                    # 404/400 model bulunamadı: gemini-2.0-flash ile dene
                    if resp.status_code in (404, 400) and ("model" in err_text.lower() or "not found" in err_text.lower()):
                        fallback_model = "gemini-2.5-flash-lite"
                        if model_name != fallback_model:
                            logger.warning("Gemini model %s bulunamadı, %s deneniyor", model_name, fallback_model)
                            overrides = dict(overrides)
                            overrides["gemini_model"] = fallback_model
                            model_name = fallback_model
                            model_path = f"models/{fallback_model}"
                            url = f"https://generativelanguage.googleapis.com/v1beta/{model_path}:generateContent?key={gemini_key}"
                            continue
                    raise RuntimeError(f"Gemini HTTP {resp.status_code}: {err_text}")
                data = resp.json()
                candidates = data.get("candidates") or []
                if candidates:
                    c = candidates[0]
                    content = c.get("content", {})
                    parts = content.get("parts") or []
                    if parts:
                        return parts[0].get("text", "") or ""
                    finish_reason = str(c.get("finishReason", "")).lower()
                    if "block" in finish_reason:
                        return f"Detaylı bilgi için {fallback_phone} numaralı hattımızdan bizi arayabilirsiniz."
                return "Yanıt oluşturulamadı. Lütfen tekrar deneyin."
            except httpx.TimeoutException:
                retry_sec = 2 + attempt * 2
                logger.warning("Gemini API zaman aşımı, %s sn sonra tekrar (deneme %d/2)", retry_sec, attempt + 1)
                await asyncio.sleep(retry_sec)
            except Exception as e:
                err_str = str(e).lower()
                if "quota" in err_str or "429" in err_str or "resourceexhausted" in err_str or "resourcelimit" in err_str:
                    retry_sec = 2 + attempt * 2
                    logger.warning("Gemini API kota, %s sn sonra tekrar (deneme %d/2)", retry_sec, attempt + 1)
                    await asyncio.sleep(retry_sec)
                else:
                    raise
        return f"Üzgünüz, teknik bir gecikme yaşıyoruz. Lütfen birkaç dakika sonra tekrar deneyin veya bizi {fallback_phone} numarasından arayabilirsiniz."

    async def _chat_local(self, messages: list, overrides: dict | None = None) -> str:
        """Yerel LoRA modeli ile sohbet (scripts/local_llm/chat.py)."""
        overrides = overrides or {}
        base_model = overrides.get("local_llm_base_model") or self._local_llm_base_model
        adapter_path = overrides.get("local_llm_adapter_path") or self._local_llm_adapter_path
        chat_script = overrides.get("local_llm_chat_script") or self._local_llm_chat_script
        python_bin = overrides.get("local_llm_python_bin") or self._local_llm_python_bin
        max_new_tokens = int(overrides.get("local_llm_max_new_tokens") or self._local_llm_max_new_tokens)
        timeout_sec = int(overrides.get("local_llm_timeout_sec") or self._local_llm_timeout_sec)

        prompt_parts = []
        for m in messages:
            role = m.get("role", "user")
            content = m.get("content", "")
            if role == "system":
                prompt_parts.append(f"[Sistem]\n{content}")
            elif role == "assistant":
                prompt_parts.append(f"[Asistan]\n{content}")
            else:
                prompt_parts.append(f"[Musteri]\n{content}")
        # CPU gecikmesini azaltmak icin prompt uzunlugunu sinirla.
        prompt = "\n\n".join(prompt_parts)[-3500:]

        python_path = Path(python_bin)
        script_path = Path(chat_script)
        adapter = Path(adapter_path)
        if not python_path.exists():
            raise FileNotFoundError(f"Local LLM python bulunamadı: {python_path}")
        if not script_path.exists():
            raise FileNotFoundError(f"Local LLM chat script bulunamadı: {script_path}")
        if not adapter.exists():
            raise FileNotFoundError(f"Local LLM adapter bulunamadı: {adapter}")

        proc = await asyncio.create_subprocess_exec(
            str(python_path),
            str(script_path),
            "--base-model",
            str(base_model),
            "--adapter-path",
            str(adapter),
            "--prompt",
            prompt,
            "--max-new-tokens",
            str(max_new_tokens),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout_sec)
        except asyncio.TimeoutError:
            proc.kill()
            await proc.communicate()
            raise RuntimeError("Local LLM timeout")

        if proc.returncode != 0:
            raise RuntimeError((stderr or b"").decode("utf-8", errors="ignore")[:500])
        output = (stdout or b"").decode("utf-8", errors="ignore").strip()
        if not output:
            raise RuntimeError("Local LLM bos yanit dondu")
        return output

    async def _resolve_local_threshold(self, tenant_id: int | None, overrides: dict | None) -> int:
        """Tenant bazli otomatik tuning ile efektif confidence esigi."""
        overrides = overrides or {}
        base = int(overrides.get("local_llm_min_confidence") or self._local_llm_min_confidence)
        if tenant_id is None or bool(overrides.get("disable_local_tuning")):
            return base

        now = datetime.utcnow()
        cached = self._local_threshold_cache.get(int(tenant_id))
        if cached and (now - cached[0]).total_seconds() < self._local_tune_cache_ttl_sec:
            return int(cached[1])

        lookback = now - timedelta(days=7)
        total = accepted = low_conf = errors = 0
        conf_sum = 0
        conf_count = 0
        try:
            async with AsyncSessionLocal() as db:
                rows = await db.execute(
                    select(AuditLog.action, AuditLog.details)
                    .where(
                        AuditLog.tenant_id == int(tenant_id),
                        AuditLog.created_at >= lookback,
                        AuditLog.action.in_(("ai_local_accepted", "ai_local_low_confidence", "ai_local_error")),
                    )
                    .order_by(desc(AuditLog.id))
                    .limit(120)
                )
                for action, details in rows.all():
                    total += 1
                    if action == "ai_local_accepted":
                        accepted += 1
                    elif action == "ai_local_low_confidence":
                        low_conf += 1
                    elif action == "ai_local_error":
                        errors += 1
                    if details:
                        try:
                            data = json.loads(details)
                            conf = data.get("confidence")
                            if conf is not None:
                                conf_sum += int(conf)
                                conf_count += 1
                        except Exception:
                            continue
        except Exception as e:
            logger.debug("Local tuning metrik okunamadi (tenant=%s): %s", tenant_id, e)
            return base

        tuned = base
        if total >= 30:
            low_rate = low_conf / max(1, total)
            err_rate = errors / max(1, total)
            avg_conf = (conf_sum / conf_count) if conf_count else None

            if err_rate >= 0.25:
                tuned = min(85, base + 15)
            elif low_rate >= 0.55:
                tuned = min(82, base + 10)
            elif low_rate >= 0.40:
                tuned = min(78, base + 5)
            elif low_rate <= 0.12 and err_rate <= 0.05 and avg_conf is not None and avg_conf >= 78:
                tuned = max(45, base - 5)

        self._local_threshold_cache[int(tenant_id)] = (now, int(tuned))
        return int(tuned)

    async def _log_local_route_event(self, tenant_id: int | None, action: str, details: dict) -> None:
        if tenant_id is None:
            return
        try:
            from services.core.audit import log_audit

            await log_audit(
                action=action,
                resource="ai_local_routing",
                details=json.dumps(details or {}, ensure_ascii=False)[:700],
                tenant_id=int(tenant_id),
            )
        except Exception:
            pass

    def _score_local_answer(self, user_message: str, conversation_history: list[dict], reply_text: str) -> int:
        """Yerel cevabin guven skorunu 0-100 araliginda hesapla."""
        text = (reply_text or "").strip()
        if not text:
            return 0

        score = 75
        low = text.lower()
        user_low = (user_message or "").lower()

        # Cevap prompt etiketleri tasiyorsa kalitesi dusuktur.
        marker_hits = sum(1 for k in ("### instruction", "### input", "### response", "[sistem]", "[musteri]") if k in low)
        score -= marker_hits * 20

        # Asiri kisa/uzun cevaplar genelde zayif olur.
        char_len = len(text)
        if char_len < 18:
            score -= 35
        elif char_len < 35:
            score -= 15
        elif char_len > 800:
            score -= 10

        # Yerel model alakasiz sabit cevaplara kayabiliyor.
        if "isterseniz urunlerin resimlerini paylasabilirim" in low:
            product_intent = any(k in user_low for k in ("urun", "fiyat", "resim", "gorsel", "katalog", "model"))
            if not product_intent:
                score -= 45

        # Musteri bilgi/randevu sorarken urun odakli cevap alakasizdir.
        asks_contact_or_meeting = any(k in user_low for k in ("eposta", "mail", "telefon", "randevu", "demo", "toplanti"))
        if asks_contact_or_meeting and any(k in low for k in ("urun", "katalog", "resim")):
            score -= 25

        # Son asistan mesaji ile ayni cevabi tekrar etmesi zayif sinyal.
        if conversation_history:
            for msg in reversed(conversation_history):
                if msg.get("role") == "assistant":
                    prev = (msg.get("content") or "").strip().lower()
                    if prev and prev == low:
                        score -= 25
                    break

        # Cok fazla placeholder / sembol.
        if re.search(r"<[a-z_]+>", low):
            score -= 20
        if text.count("#") >= 3 or text.count("|") >= 3:
            score -= 35
        if re.search(r"(python|kurs|programlama|java|javascript)", low) and not re.search(
            r"(python|kurs|programlama|java|javascript)", user_low
        ):
            score -= 35

        # Basit anlamsal bag: kullanici/yanit kelime ortusmesi cok dusukse fallback.
        user_tokens = {t for t in re.findall(r"[a-zA-Z0-9çğıöşüÇĞİÖŞÜ]{4,}", user_low)}
        reply_tokens = {t for t in re.findall(r"[a-zA-Z0-9çğıöşüÇĞİÖŞÜ]{4,}", low)}
        if user_tokens and reply_tokens:
            overlap = len(user_tokens & reply_tokens) / max(1, len(user_tokens))
            if overlap < 0.12:
                score -= 30

        return max(0, min(100, score))

    def _parse_response(self, content: str) -> dict:
        """Yanıttan metin, resim URL ve ürün önerilerini ayıkla"""
        result = {"text": content, "image_url": None, "suggested_products": None}

        if "```json" in content:
            try:
                start = content.find("```json") + 7
                end = content.find("```", start)
                json_str = content[start:end].strip()
                data = json.loads(json_str)

                if data.get("action") == "send_image":
                    result["image_url"] = data.get("image_url")
                    result["image_caption"] = data.get("caption", "")
                elif data.get("action") == "suggest_products":
                    result["suggested_products"] = data.get("product_ids", [])
                    result["suggest_message"] = data.get("message", "")
                elif data.get("action") == "create_order":
                    result["create_order"] = data
                elif data.get("action") == "create_appointment":
                    result["create_appointment"] = data
                elif data.get("action") == "suggest_replies":
                    opts = data.get("options") or []
                    if isinstance(opts, list):
                        result["suggested_replies"] = [
                            {"label": str(o.get("label", "")), "text": str(o.get("text", ""))}
                            for o in opts if isinstance(o, dict) and (o.get("label") or o.get("text"))
                        ][:6]  # En fazla 6 seçenek

                # JSON bloğunu metinden çıkar
                result["text"] = content.split("```json")[0].strip()
            except (json.JSONDecodeError, KeyError):
                pass

        return result

    async def classify_intent(self, message: str) -> str:
        """Mesajın amacını sınıflandır: product_inquiry, order, cargo_tracking, general"""
        if self._use_gemini:
            import httpx
            prompt = "[Sistem] Sadece şunlardan birini döndür: product_inquiry, order, cargo_tracking, general\n[Müşteri]\n" + message
            model_path = self._gemini_model if self._gemini_model.startswith("models/") else f"models/{self._gemini_model}"
            url = f"https://generativelanguage.googleapis.com/v1beta/{model_path}:generateContent?key={self._gemini_api_key}"
            result = "general"
            for attempt in range(3):
                try:
                    async with httpx.AsyncClient(timeout=15.0) as client:
                        resp = await client.post(url, json={"contents": [{"parts": [{"text": prompt}]}]})
                    if resp.status_code == 200:
                        data = resp.json()
                        candidates = data.get("candidates") or []
                        if candidates:
                            parts = (candidates[0].get("content", {}) or {}).get("parts") or []
                            if parts:
                                result = (parts[0].get("text") or "general").strip().lower()
                    break
                except Exception as e:
                    err_str = str(e).lower()
                    if "quota" in err_str or "429" in err_str or "resourceexhausted" in err_str:
                        retry_sec = 3 + attempt * 2
                        logger.warning("Gemini classify_intent kota, %s sn sonra tekrar", retry_sec)
                        await asyncio.sleep(retry_sec)
                    else:
                        raise
        else:
            response = await self._openai_client.chat.completions.create(
                model=self._openai_model,
                messages=[
                    {"role": "system", "content": "Sadece şunlardan birini döndür: product_inquiry, order, cargo_tracking, general"},
                    {"role": "user", "content": message},
                ],
                temperature=0,
            )
            result = response.choices[0].message.content or "general"
        return result.strip().lower()
