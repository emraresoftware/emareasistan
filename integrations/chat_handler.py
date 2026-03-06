"""
Birleşik sohbet işleyici - WhatsApp, Telegram vb. platformlardan gelen mesajları işler
AI asistanı ile entegre, ürün resmi gönderimi, sipariş, kargo takibi, konum paylaşımı
Yönetim paneli kuralları (ResponseRule) ile araç modeli/anahtar kelimeye göre otomatik ürün gönderimi
"""
import asyncio

from services.core.time_utils import now_turkey
import json
import hashlib
import re
import secrets
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import urlparse
from typing import Optional
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from config import get_settings
from models import Conversation, Message, AITrainingExample, Video, Tenant, User, Appointment
from services import AIAssistant, ProductService, OrderService, CargoService, RuleEngine
from services.product.vehicles import extract_vehicle_from_message, get_context_for_ai
from services.core.tenant import get_tenant_settings
from services.workflow.pipeline import MessagePipeline
from services.core import OrderStateMachine
from integrations.handlers import HumanHandler, OrderHandler, ProductHandler, CargoHandler, AppointmentHandler
from services.appointment.service import create_appointment as create_appointment_svc
from services.whatsapp.audit import run_chat_audit
from services.workflow.engine import run_workflows


class ChatHandler:
    """Platform bağımsız sohbet işleyici"""
    DEMO_TRIAL_DAYS = 7
    DEMO_DAILY_LIMIT_PER_SOURCE = 1

    def __init__(self, db: AsyncSession):
        self.db = db
        self.ai = AIAssistant()
        self.products = ProductService(db)
        self.orders = OrderService(db)
        self.cargo = CargoService()
        self.pipeline = MessagePipeline()
        self.rule_engine = RuleEngine(db)
        self._order_handler = OrderHandler(
            db, self.orders,
            self._save_message, self._update_conversation_timestamp,
        )
        self._product_handler = ProductHandler(db, self.rule_engine)
        self._cargo_handler = CargoHandler(self.orders, self.cargo)
        self._appointment_handler = AppointmentHandler(db)

    async def process_message(
        self,
        platform: str,
        user_id: str,
        message_text: str,
        conversation_history: list[dict] | None = None,
        customer_name: str | None = None,
        customer_phone: str | None = None,
        replied_to_caption: str | None = None,
        tenant_id: int | None = None,  # WhatsApp connection_id ile gelen - None ise 1
        image_base64: str | None = None,  # Vision AI - resimden ürün eşleştirme
        image_mimetype: str | None = None,
        is_group: bool = False,  # Grup mesajı mı?
        group_name: str | None = None,  # Grup adı (ör: "emare asistan")
    ) -> dict:
        """
        Gelen mesajı işle, AI yanıtı üret ve ek aksiyonları (resim, ürün) belirle.
        Sohbet ve mesajları veritabanına kaydeder. Yönetim kurallarına göre ürün/resim gönderir.
        Returns: {
            "text": str,
            "image_url": str | None,
            "image_caption": str | None,
            "suggested_products": list | None,
            "product_images": list | None,
        }
        """
        # Sohbet getir veya oluştur (tenant_id: WhatsApp connection'dan veya 1)
        conv = await self._get_or_create_conversation(
            platform, user_id, customer_name, customer_phone, tenant_id
        )
        tid = conv.tenant_id or 1

        # CSAT: Memnuniyet anketi yanıtı (1-5) ise kaydet, teşekkür mesajı dön
        if (
            getattr(conv, "csat_sent_at", None)
            and getattr(conv, "csat_rating", None) is None
            and (message_text or "").strip()
            and not image_base64
        ):
            raw = (message_text or "").strip()
            if len(raw) >= 1 and raw[0] in "12345" and (len(raw) == 1 or raw[1:2] in (" ", "\t", ".", ",", ")")):
                rating = int(raw[0])
                comment = raw[1:].strip() or None
                conv.csat_rating = rating
                conv.csat_comment = comment
                await self.db.commit()
                display = (message_text or "").strip()
                await self._save_message(conv.id, "user", display)
                thanks = "Teşekkürler! Geri bildiriminiz kaydedildi."
                await self._save_message(conv.id, "assistant", thanks)
                await self._update_conversation_timestamp(conv.id)
                return {"text": thanks}

        # Soru seçeneklerinden numara ile yanıt (1, 2, 3...) → seçeneğin tam metnine çevir
        if (message_text or "").strip() and not image_base64:
            expanded_from_options = await self._expand_suggested_reply_selection(conv.id, (message_text or "").strip())
            if expanded_from_options:
                message_text = expanded_from_options

        # AI günlük mesaj limiti (kullanıcı mesajı kaydetmeden önce kontrol)
        tenant_settings = await get_tenant_settings(tid)
        daily_limit = tenant_settings.get("ai_daily_limit") or 500
        if daily_limit > 0:
            count = await self._count_tenant_messages_today(tid)
            if count >= daily_limit:
                limit_msg = f"Günlük mesaj limitiniz ({daily_limit}) doldu. Yarın tekrar deneyebilirsiniz. Acil durumda {tenant_settings.get('phone', '')} numarasından bize ulaşabilirsiniz."
                await self._save_message(conv.id, "assistant", limit_msg)
                await self._update_conversation_timestamp(conv.id)
                return {"text": limit_msg}

        # Pipeline: Sanitizer → Intent → Router
        pipeline_out = self.pipeline.process_input(message_text, image_base64, tenant_id=tid)
        display_text = pipeline_out.display_message or message_text or ("[Resim gönderildi]" if image_base64 else "")
        await self._save_message(conv.id, "user", display_text)

        # HumanHandler - temsilci devraldıysa AI yanıt vermez
        if HumanHandler.should_hand_over(conv):
            await self._update_conversation_timestamp(conv.id)
            return HumanHandler.get_response()

        # OrderHandler - "Bu olsun" / "Bunu seçiyorum" ürün seçimi
        last_products = await self._get_last_sent_products(conv.id)
        if last_products:
            selected = self._order_handler.parse_product_selection(
                message_text, replied_to_caption, last_products
            )
            if selected:
                return await self._order_handler.handle_product_selection(conv.id, selected)

        # Tenant ayarları (tenant_settings yukarıda alındı)
        tenant_id = tid
        products_svc = ProductService(
            self.db,
            tenant_id=tenant_id,
            products_path=tenant_settings.get("products_path") or None,
        )

        # Bağlam topla
        msg_normalized = pipeline_out.sanitized_message
        intent = pipeline_out.route_info.intent
        msg_lower = msg_normalized or (message_text or "").lower()
        history = await self._get_conversation_history(conv.id, limit=50)
        has_history = len(history) > 0

        # Kisa/eksik baglamli sorulari onceki mesaja gore netlestir (orn: "nasil?")
        expanded_msg = self._expand_elliptic_user_message(
            raw_text=message_text,
            normalized_text=msg_normalized,
            replied_to_caption=replied_to_caption,
            history=history,
        )
        if expanded_msg and expanded_msg != (msg_normalized or message_text):
            message_text = expanded_msg
            msg_normalized = expanded_msg
            msg_lower = expanded_msg.lower()
            pipeline_out = self.pipeline.process_input(message_text, image_base64, tenant_id=tid)
            intent = pipeline_out.route_info.intent

        # Workflow Engine - aktif workflow'lar template yanıt döndürürse kullan
        try:
            workflow_response = await run_workflows(tid, platform, message_text, msg_lower)
            if workflow_response:
                await self._save_message(conv.id, "assistant", workflow_response.get("text", ""))
                await self._update_conversation_timestamp(conv.id)
                return workflow_response
        except Exception:
            pass  # Hata durumunda normal akışa devam et

        # Senaryo görselleri: "örnek senaryo" istendiğinde resimlerle destekle
        scenario_response = self._get_scenario_images_response(msg_lower, msg_normalized)
        if scenario_response:
            await self._save_message(conv.id, "assistant", scenario_response["text"])
            await self._update_conversation_timestamp(conv.id)
            return scenario_response

        # Demo onboarding shortcut: "demo hesabi ac" gibi taleplerde otomatik hesap olustur.
        demo_reply = await self._handle_demo_account_request(conv, message_text, msg_lower)
        if demo_reply:
            response = {"text": demo_reply}
            await self._save_message(conv.id, "assistant", demo_reply)
            await self._update_conversation_timestamp(conv.id)
            return response

        # ProductHandler - ürün araması + vision
        product_context, searched_products = await self._product_handler.build_product_context(
            products_svc,
            message_text,
            msg_normalized,
            intent,
            image_base64,
            image_mimetype,
        )
        if image_base64 and not message_text:
            message_text = "Resimdeki ürünü bul" if searched_products else "Resimdeki ürünü katalogda bulamadım."

        order_context = ""
        appointment_context = ""
        location_context = ""
        location_keywords = ["konum", "adres", "nerede", "nerde", "harita", "yol tarifi", "lokasyon", "yeriniz", "adresiniz", "neredeyiz", "neredesiniz"]
        if intent == "location_request" or any(k in msg_normalized for k in location_keywords):
            loc = tenant_settings
            if loc.get("address") or loc.get("phone"):
                location_context = f"{loc.get('name', 'Firma')} adresi: {loc.get('address', '')}. Telefon: {loc.get('phone', '')}. Harita: {loc.get('maps_url', '')}"

        # CargoHandler - kargo takip bağlamı
        order_context = await self._cargo_handler.build_context(
            message_text, intent, msg_normalized
        )
        appointment_context = await self._appointment_handler.build_context(
            tenant_id,
            tenant_settings,
            message_text,
            intent,
            msg_normalized,
        )

        # Araç modeli bağlamı (AI için - sadece otomotiv sektörü tenantlar için)
        if product_context and tenant_settings.get("sector", "").lower() in ("otomotiv", "auto", ""):
            if tenant_id in (1, 2) or tenant_settings.get("sector", "").lower() in ("otomotiv", "auto"):
                vehicle_context = get_context_for_ai()
                product_context = vehicle_context + "\n\n" + product_context

        # Sipariş state machine - seçilmiş ürün varsa order_draft kullan
        selected_product = await self._get_last_selected_product(conv.id)
        sm = OrderStateMachine(conv.order_draft)
        if selected_product and sm.get_state() == OrderStateMachine.INIT:
            sm.set_product(selected_product)
            conv.order_draft = sm.to_json()
            await self.db.commit()
        if sm.get_state() != OrderStateMachine.INIT:
            order_context += "\n" + sm.get_context_for_ai()
            order_context += "\nSipariş tamamlamak için Ad Soyad, Telefon, TAM ADRES (sokak, bina no, ilçe, il) ve Ödeme seçeneği (Havale/Kredi Kartı/Kapıda Ödeme) HEPSİNİ eksiksiz al. Eksik varsa create_order döndürme."
        # Son gönderilen ürünler - AI bağlamı için ("bunu alalım" belirsizse)
        if last_products and not selected_product:
            prod_names = ", ".join(p.get("name", "") for p in last_products[:5] if p.get("name"))
            if prod_names:
                order_context += f"\nMüşteriye az önce şu ürünlerin resimleri gönderildi: {prod_names}. Müşteri 'bunu alalım', 'bu olsun' derse bunlardan birini kastediyor olabilir."

        # Toplanti/randevu fallback:
        # Kullanici "tamam/olur" gibi onay verdiginde ve akista saat + isim + telefon varsa
        # AI JSON olusturmasa bile randevuyu kaydedelim.
        fallback_appointment_text = await self._maybe_create_meeting_appointment(
            conv=conv,
            tenant_id=tenant_id,
            history=history,
            message_text=message_text,
        )
        if fallback_appointment_text:
            response = {"text": fallback_appointment_text}
            await self._save_message(conv.id, "assistant", fallback_appointment_text)
            await self._update_conversation_timestamp(conv.id)
            return response

        # AI eğitim örnekleri (panelden eklenen soru-cevap çiftleri)
        training_context = ""

        # Montaj/kurulum videosu istendiğinde - panelde video varsa AI'a bildir (YouTube link vermesin)
        video_keywords_pre = ["montaj videosu", "montaj video", "kurulum videosu", "kurulum video", "video", "videosu"]
        if any(k in msg_normalized for k in video_keywords_pre):
            for kw in ["montaj", "kurulum", "video"]:
                if kw in msg_normalized:
                    v_res = await self.db.execute(
                        select(Video).where(
                            Video.tenant_id == tenant_id,
                            Video.is_active == True,
                            Video.trigger_keyword == kw,
                        )
                    )
                    if v_res.scalar_one_or_none():
                        training_context = (training_context + "\n\n" if training_context else "") + "Panelde video yüklü, doğrudan gönderilecek. Sadece 'İşte montaj videomuz' veya 'İşte videomuz' gibi kısa mesaj ver. YouTube link verme."
                        break

        # Eğitim örnekleri: 1) Anahtar kelime tetikleyici 2) pgvector benzerlik 3) öncelik
        training_context = ""
        msg_for_match = msg_normalized or (message_text or "").lower()
        # Anahtar kelime tetikleyicisi - mesajda geçen kelimeleri olan örnekler öncelikli
        kw_result = await self.db.execute(
            select(AITrainingExample)
            .where(
                AITrainingExample.tenant_id == tenant_id,
                AITrainingExample.is_active == True,
                AITrainingExample.trigger_keywords.isnot(None),
                AITrainingExample.trigger_keywords != "",
            )
            .order_by(desc(AITrainingExample.priority), AITrainingExample.id)
        )
        kw_examples = kw_result.scalars().all()
        matched_keyword_examples = []
        for ex in kw_examples:
            keywords = [k.strip().lower() for k in (ex.trigger_keywords or "").split(",") if k.strip()]
            if any(kw in msg_for_match for kw in keywords):
                matched_keyword_examples.append(ex)
        if matched_keyword_examples:
            lines = ["Panelden eklenen örnek cevaplar (anahtar kelime eşleşmesi - BUNLARI referans al):"]
            for ex in matched_keyword_examples[:5]:
                lines.append(f"- Soru: {ex.question}")
                lines.append(f"  Cevap: {ex.expected_answer}")
            training_context = "\n".join(lines)
        if not training_context:
            from services.ai.vector_store import is_vector_available, search_similar_training
            from services.ai.embeddings import get_embedding
            openai_key = tenant_settings.get("openai_api_key") or get_settings().openai_api_key
            use_vector = await is_vector_available(self.db) and bool(openai_key)
            if use_vector:
                emb = await get_embedding(msg_normalized or message_text or "", api_key=openai_key)
                if emb:
                    similar = await search_similar_training(self.db, emb, tenant_id, limit=5)
                    if similar:
                        lines = ["Panelden eklenen örnek cevaplar (benzer sorularda BUNLARI referans al):"]
                        for s in similar:
                            lines.append(f"- Soru: {s['question']}")
                            lines.append(f"  Cevap: {s['expected_answer']}")
                        training_context = "\n".join(lines)
        if not training_context:
            ex_result = await self.db.execute(
                select(AITrainingExample)
                .where(AITrainingExample.tenant_id == tenant_id, AITrainingExample.is_active == True)
                .order_by(desc(AITrainingExample.priority), AITrainingExample.id)
                .limit(15)
            )
            examples = ex_result.scalars().all()
            if examples:
                lines = ["Panelden eklenen örnek cevaplar (benzer sorularda BUNLARI referans al):"]
                for ex in examples:
                    lines.append(f"- Soru: {ex.question}")
                    lines.append(f"  Cevap: {ex.expected_answer}")
                training_context = "\n".join(lines)

        # Smart Escalation - hayal kırıklığı tespiti (mevcut mesaj dahil)
        from services.whatsapp.escalation import detect_frustration, get_escalation_context
        hist_for_esc = list(history or [])
        if (message_text or "").strip():
            hist_for_esc.append({"role": "user", "content": (message_text or "").strip()})
        if detect_frustration(hist_for_esc):
            training_context = (training_context or "") + get_escalation_context()

        # Dokuman tabanli RAG baglami (docs/*.md) - sadece platform tenantlari icin
        # Diger tenantlara (musteri firmalara) Emare Asistan dokumanlarini enjekte etme
        if tenant_id in (1, 2):
            from services.ai.rag import get_docs_rag_context
            docs_ctx = await get_docs_rag_context(self.db, tenant_id, msg_normalized or message_text or "", limit=2)
            if docs_ctx:
                training_context = (training_context + "\n\n" if training_context else "") + docs_ctx

        # Müşteri daha önce paylaştığı bilgiler - tekrar isteme (aynı numara sohbet hafızası)
        profile = self._extract_contact_profile_from_history(history)
        if conv.customer_phone:
            profile["phone"] = profile.get("phone") or conv.customer_phone
        if conv.customer_name:
            profile["name"] = profile.get("name") or conv.customer_name
        known_parts = []
        if profile.get("name"):
            known_parts.append(f"Ad: {profile['name']}")
        if profile.get("phone"):
            known_parts.append(f"Telefon: {profile['phone']}")
        if profile.get("email"):
            known_parts.append(f"E-posta: {profile['email']}")
        if known_parts:
            known_info = "Müşteri daha önce paylaştı: " + ", ".join(known_parts) + ". Bu bilgileri tekrar isteme."
            training_context = (training_context + "\n\n" if training_context else "") + known_info

        api_overrides = {}
        if tenant_settings.get("openai_api_key"):
            api_overrides["openai_api_key"] = tenant_settings["openai_api_key"]
        if tenant_settings.get("gemini_api_key"):
            api_overrides["gemini_api_key"] = tenant_settings["gemini_api_key"]
            if tenant_settings.get("gemini_model"):
                api_overrides["gemini_model"] = tenant_settings["gemini_model"]
        # Tenant API anahtarı yoksa Emare Asistan (tenant 2) fallback — web sohbet vb. çalışsın
        if not api_overrides.get("gemini_api_key") and not api_overrides.get("openai_api_key"):
            emare = await get_tenant_settings(2)
            if emare.get("gemini_api_key"):
                api_overrides["gemini_api_key"] = emare["gemini_api_key"]
                if emare.get("gemini_model"):
                    api_overrides["gemini_model"] = emare["gemini_model"]
            elif emare.get("openai_api_key"):
                api_overrides["openai_api_key"] = emare["openai_api_key"]
        if tenant_settings.get("local_llm_min_confidence") not in (None, ""):
            api_overrides["local_llm_min_confidence"] = int(tenant_settings["local_llm_min_confidence"])
        # Canli mesaj kanallarinda gecikmeyi azaltmak icin lokal model bekleme adimini atla.
        if (platform or "").strip().lower() in {"whatsapp", "telegram", "instagram", "web"}:
            api_overrides["disable_local_llm"] = True

        # Grup mesajı: kısa ve profesyonel yanıtlar (yazılım ekibi grubu)
        group_prompt_override = None
        if is_group and group_name:
            group_context = (
                "\n\n⚠️ GRUP MESAJI — Bu mesaj WhatsApp grubu içinden geldi. Grup adı: "
                f'"{group_name}". '
                "Bu grupta yazılım geliştirme ekibi var. KESİNLİKLE şu kurallara uy:\n"
                "1. KISA ve NET yanıtlar ver (en fazla 2-3 cümle)\n"
                "2. Profesyonel ve teknik ol\n"
                "3. Gereksiz selamlama, tanıtım veya pazarlama yapma\n"
                "4. Ürün resmi, soru seçenekleri (suggested_replies) gönderme\n"
                "5. Sadece sorulan soruyu direkt cevapla\n"
                "6. Emoji kullanımını minimumda tut\n"
                "7. Emare Asistan yazılımının yeteneklerini kısaca ve doğru anlat\n"
            )
            training_context = (training_context + group_context) if training_context else group_context

        response = await self.ai.chat(
            user_message=msg_normalized or message_text,
            conversation_history=conversation_history or history,
            product_context=product_context,
            order_context=order_context,
            appointment_context=appointment_context,
            location_context=location_context,
            training_context=training_context,
            tenant_name=tenant_settings.get("name", "Firma"),
            tenant_phone=tenant_settings.get("phone", ""),
            tenant_id=tenant_id,
            prompt_override=tenant_settings.get("ai_prompt_override", ""),
            api_overrides=api_overrides if api_overrides else None,
            response_rules=tenant_settings.get("ai_response_rules") or [],
        )

        # OrderHandler - sipariş oluşturma (AI create_order döndürdüyse)
        response = await self._order_handler.process_create_order(
            response, conv, sm, platform, tenant_settings
        )
        response = await self._appointment_handler.process_create_appointment(
            response, conv, tenant_id
        )

        # ProductHandler - ürün resimleri (albüm, diverse, arama sonuçları)
        rule_images = await self.rule_engine.match(
            msg_normalized, tenant_id, products_svc.get_by_id
        )
        product_images = await self._product_handler.get_product_images_for_response(
            products_svc,
            msg_normalized,
            message_text,
            searched_products,
            response,
            tenant_id,
        )
        if rule_images:
            custom_msg = rule_images[0].pop("custom_message", None)
            if custom_msg:
                response["text"] = custom_msg + "\n\n" + (response.get("text") or "")
            # Sadece URL'ü olanları resim listesine ekle (sadece custom_message olan kural boş url döner)
            rule_with_urls = [x for x in rule_images if (x.get("url") or "").strip()]
            product_images = rule_with_urls + product_images
        if product_images:
            response["product_images"] = product_images

        # Video isteği - montaj videosu vb. istendiğinde panelden eklenen videoyu gönder (araç modeline göre filtre - albüm gibi)
        video_keywords = ["montaj videosu", "montaj video", "kurulum videosu", "kurulum video", "video", "videosu"]
        if any(k in msg_normalized for k in video_keywords):
            tenant_id = conv.tenant_id or 1
            vehicle = extract_vehicle_from_message(message_text)
            vehicle_lower = (vehicle or "").strip().lower()
            for kw in ["montaj", "kurulum", "video"]:
                if kw in msg_normalized:
                    v_result = await self.db.execute(
                        select(Video)
                        .where(
                            Video.tenant_id == tenant_id,
                            Video.is_active == True,
                            Video.trigger_keyword == kw,
                        )
                        .order_by(Video.priority.desc(), Video.id)
                    )
                    videos = v_result.scalars().all()
                    fallback_general = None  # vehicle_models boş olan (tüm araçlar için)
                    for v in videos:
                        if not v or not v.video_url:
                            continue
                        models_str = v.vehicle_models or ""
                        values = [m.strip().lower() for m in models_str.split(",") if m.strip()]
                        if not values:
                            if not fallback_general:
                                fallback_general = v
                        elif vehicle_lower:
                            matched = any(
                                m == vehicle_lower or m in vehicle_lower or vehicle_lower in m
                                for m in values
                            )
                            if matched:
                                response["videos"] = [{"url": v.video_url, "caption": v.caption or ""}]
                                break
                    else:
                        if fallback_general:
                            response["videos"] = [{"url": fallback_general.video_url, "caption": fallback_general.caption or ""}]
                    if response.get("videos"):
                        break

        # Konum isteği - WhatsApp konum mesajı gönder (tenant'a göre)
        if location_context:
            loc = tenant_settings
            if loc.get("lat") and loc.get("lng"):
                response["location"] = {
                    "lat": loc["lat"],
                    "lng": loc["lng"],
                    "name": loc.get("name", "Firma"),
                    "address": loc.get("address", ""),
                }

        # Sohbet devam ediyorsa tekrarlanan "Merhaba" vb. selamlamaları kaldır
        reply_text = response.get("text", "")
        if has_history and reply_text:
            history_for_reply_filters = list(history or [])
            if (display_text or "").strip():
                history_for_reply_filters.append({"role": "user", "content": display_text.strip()})
            txt_lower = reply_text.lower().strip()
            for prefix in ["merhaba!", "merhaba,", "merhaba.", "merhaba ", "hoş geldiniz!", "hoş geldiniz,", "hoş geldiniz.", "hoş geldiniz ", "selam!", "selam,", "selam "]:
                if txt_lower.startswith(prefix):
                    reply_text = reply_text[len(prefix):].strip()
                    if reply_text and reply_text[0].islower():
                        reply_text = reply_text[0].upper() + reply_text[1:]
                    break
            reply_text = self._dedupe_repeated_questions(reply_text, history_for_reply_filters)
            reply_text = self._avoid_reasking_known_contact_fields(reply_text, history_for_reply_filters)
        # İlk mesaj satış zenginleştirmesi - sadece platform tenantları (Emare Asistan) için
        # Müşteri tenantları kendi AI prompt'larıyla yönetilir, SaaS satış içeriği eklenmemeli
        # Grup mesajlarında satış zenginleştirmesi yapma
        if not has_history and tenant_id in (1, 2) and not is_group:
            reply_text = self._enhance_first_reply_for_sales(
                reply_text=reply_text,
                tenant_name=tenant_settings.get("name", "Emare Asistan"),
                user_message=message_text,
                variant_seed=conv.id,
                welcome_scenarios=tenant_settings.get("welcome_scenarios"),
            )
        response["text"] = reply_text

        # Grup mesajı: ürün resimleri, soru seçenekleri, video vb. gönderme
        if is_group:
            response.pop("product_images", None)
            response.pop("suggested_replies", None)
            response.pop("videos", None)
            response.pop("location", None)
            response.pop("image_url", None)
            response.pop("image_caption", None)

        # Panelden tanımlı soru seçenekleri varsa onları kullan; yoksa AI'nın önerdiğini
        qr_cfg = tenant_settings.get("quick_reply_options") or {}
        if isinstance(qr_cfg, dict) and qr_cfg.get("enabled") and qr_cfg.get("options"):
            tenant_opts = [
                {"label": str(o.get("label", "")), "text": str(o.get("text", ""))}
                for o in qr_cfg["options"] if isinstance(o, dict) and (o.get("label") or o.get("text"))
            ][:6]
            if tenant_opts:
                response["suggested_replies"] = tenant_opts

        # Asistan yanıtını kaydet (ürün resimleri + soru seçenekleri extra_data'da)
        if response.get("product_images"):
            reply_text += "\n[Ürün resimleri gönderildi]"
        extra = {}
        if response.get("product_images"):
            extra["product_images"] = response["product_images"]
        if response.get("suggested_replies"):
            extra["suggested_replies"] = response["suggested_replies"]
        await self._save_message(
            conv.id, "assistant", reply_text,
            extra_data=json.dumps(extra, ensure_ascii=False) if extra else None
        )
        await self._update_conversation_timestamp(conv.id)

        # Asenkron chat denetim (analitik - müşteriye gecikme yok)
        from services.core.settings import get_chat_audit_enabled, get_chat_audit_sample_rate
        if get_chat_audit_enabled():
            sample_rate = get_chat_audit_sample_rate()
            asyncio.create_task(
                run_chat_audit(
                    tenant_id=tid,
                    conversation_id=conv.id,
                    platform=platform or "",
                    user_message=message_text or "",
                    assistant_response=reply_text or "",
                    sample_rate=sample_rate,
                )
            )

        return response

    def _normalize_typos(self, text: str) -> str:
        """Yaygın yazım yanlışlarını düzelt (resim, göster, koltuk vb.)"""
        if not text or not isinstance(text, str):
            return text or ""
        text = text.lower().strip()
        typos = {
            # resim
            "rsm": "resim", "res": "resim", "resime": "resim", "resimler": "resim",
            "resimleri": "resim", "resimlerini": "resim", "resimlerr": "resim",
            # göster
            "goster": "göster", "gösterir": "göster", "göstermi": "göster",
            "gostermi": "göster", "gösterirmisin": "göster", "gösterir misin": "göster",
            # koltuk
            "koltuğ": "koltuk", "koltuğu": "koltuk", "koltuklar": "koltuk",
            "koltukları": "koltuk", "koltu": "koltuk",
            # paspas
            "paspaş": "paspas", "paspaşlar": "paspas", "paspaşları": "paspas",
            # fiyat
            "fiyatlar": "fiyat", "fiyatları": "fiyat", "fiyat": "fiyat",
            # bakayım
            "bakayim": "bakayım", "bakaym": "bakayım", "bakayim": "bakayım",
            # foto
            "fotolar": "foto", "fotoları": "foto", "fotoraft": "foto",
            "fotoğraf": "foto", "fotograf": "foto", "fotoraflar": "foto",
            # araç
            "araba": "araç", "arabam": "araç", "arabalar": "araç",
            # paspas/döşeme
            "döşem": "döşeme", "döseme": "döşeme", "doseme": "döşeme",
        }
        # Kelime bazlı düzeltme (boşlukla ayrılmış)
        words = text.split()
        for i, w in enumerate(words):
            for wrong, correct in typos.items():
                if wrong in w or w == wrong:
                    words[i] = w.replace(wrong, correct)
        return " ".join(words)

    def _normalize_question_text(self, text: str) -> str:
        t = self._to_ascii_lower(text)
        t = re.sub(r"[^a-z0-9\s]", " ", t)
        t = re.sub(r"\s+", " ", t).strip()
        return t

    def _expand_elliptic_user_message(
        self,
        raw_text: str,
        normalized_text: str,
        replied_to_caption: str | None,
        history: list[dict],
    ) -> str:
        """
        "Nasil?", "detay?" gibi kisa mesajlari onceki asistan cumlesine gore anlamlandir.
        Ozellikle demo/teklif/randevu baglaminda soru niyetini netlestirir.
        """
        raw = (raw_text or "").strip()
        norm = (normalized_text or raw or "").strip()
        if not norm:
            return norm
        n_ascii = self._to_ascii_lower(norm)
        short_like = len(n_ascii.split()) <= 3
        is_elliptic = short_like and (
            n_ascii in {"nasil", "nasil?", "detay", "detay?", "olur", "tamam", "evet", "yani"}
            or n_ascii.startswith("nasil")
        )
        if not is_elliptic:
            return norm

        ctx = (replied_to_caption or "").strip()
        if not ctx:
            for item in reversed(history or []):
                if item.get("role") == "assistant":
                    ctx = (item.get("content") or "").strip()
                    if ctx:
                        if len(ctx.split()) <= 3:
                            continue
                        break
        if not ctx:
            return norm

        c_ascii = self._to_ascii_lower(ctx)
        # Randevu/demo onay baglaminda "evet"/"onay" i expand etme - fallback onay algilasin
        if n_ascii in {"evet", "onay", "e", "onayliyorum", "kesin", "dogruluyorum", "ok", "tamam", "olur"}:
            if any(k in c_ascii for k in ("onay icin", "son bir onay", "onayliyorsaniz", "onay yazin", "evet yazin", "iptal icin")):
                return norm
        if n_ascii in {"evet", "yani"} and any(k in c_ascii for k in ("gun ve saat", "gün ve saat", "uygun zaman", "zamaninizi", "zamanınızı")):
            return "Kesif gorusmesi icin uygun gun ve saati paylasiyorum."
        if any(k in c_ascii for k in ("demo", "kesif gorusmesi", "keşif görüşmesi", "demo plan", "demo hesap")):
            return "Demo surecini nasil yapacagiz, adim adim anlatir misiniz?"
        if any(k in c_ascii for k in ("teklif", "fiyat", "paket", "cozum")):
            return "Teklif surecini nasil yurutuyorsunuz, hangi adimlar var?"
        if any(k in c_ascii for k in ("randevu", "toplanti", "gorusme", "görüşme")):
            return "Randevuyu nasil planliyoruz, hangi bilgileri paylasmaliyim?"
        if any(k in c_ascii for k in ("teknik", "mimari", "altyapi", "api")):
            return "Teknik olarak nasil calisiyor, mimariyi kisaca anlatir misiniz?"
        return norm

    def _extract_question_candidates(self, text: str) -> list[str]:
        if not text:
            return []
        raw_parts = [p.strip() for p in re.split(r"[\n\r]+", text) if p.strip()]
        out = []
        for p in raw_parts:
            if "?" in p:
                out.append(p)
                continue
            p_ascii = self._to_ascii_lower(p)
            if any(k in p_ascii for k in ("yazar misiniz", "paylasir misiniz", "alabilir miyim", "soyler misiniz", "rica edeyim", "gonderir misiniz")):
                out.append(p)
        return out

    def _similar_question_already_asked(self, question: str, history: list[dict]) -> bool:
        qn = self._normalize_question_text(question)
        if not qn:
            return False
        q_words = set(qn.split())
        if not q_words:
            return False
        for item in reversed(history or []):
            if item.get("role") != "assistant":
                continue
            prev = item.get("content") or ""
            for cand in self._extract_question_candidates(prev):
                pn = self._normalize_question_text(cand)
                if not pn:
                    continue
                if qn == pn:
                    return True
                p_words = set(pn.split())
                if not p_words:
                    continue
                overlap = len(q_words & p_words) / max(1, min(len(q_words), len(p_words)))
                if overlap >= 0.8:
                    return True
        return False

    def _dedupe_repeated_questions(self, reply_text: str, history: list[dict]) -> str:
        if not reply_text:
            return reply_text
        lines = [x for x in re.split(r"(\n+)", reply_text)]
        changed = False
        for i, part in enumerate(lines):
            if not part or part.startswith("\n"):
                continue
            if not self._extract_question_candidates(part):
                continue
            if self._similar_question_already_asked(part, history):
                lines[i] = ""
                changed = True
        cleaned = "".join(lines)
        cleaned = re.sub(r"\n{3,}", "\n\n", cleaned).strip()
        if cleaned:
            return cleaned
        if changed:
            return "Bilgilerinizi daha once paylastiginiz icin tekrar istemiyorum. Hazir oldugunuzda bir sonraki adima gecelim."
        return reply_text

    def _extract_contact_profile_from_history(self, history: list[dict]) -> dict:
        return {
            "name": (self._extract_name_from_history(history) or "").strip(),
            "phone": (self._extract_phone_from_history(history) or "").strip(),
            "email": (self._extract_email_from_history(history) or "").strip(),
        }

    def _latest_user_text(self, history: list[dict]) -> str:
        for item in reversed(history or []):
            if item.get("role") == "user":
                return (item.get("content") or "").strip()
        return ""

    def _infer_sector_hint(self, text: str) -> str:
        t = self._to_ascii_lower(text or "")
        if any(k in t for k in ("servis", "randevu", "oto", "otomotiv", "bakim")):
            return "otomotiv"
        if any(k in t for k in ("e-ticaret", "eticaret", "sepet", "siparis", "kargo")):
            return "e_ticaret"
        if any(k in t for k in ("klinik", "hasta", "doktor", "muayene", "saglik")):
            return "saglik"
        if any(k in t for k in ("okul", "kurs", "ogrenci", "egitim")):
            return "egitim"
        if any(k in t for k in ("hotel", "otel", "rezervasyon", "konaklama")):
            return "turizm"
        return "genel"

    def _is_social_smalltalk(self, text: str) -> bool:
        t = self._to_ascii_lower(text)
        if not t:
            return False
        # Kisa nezaket/sosyal mesajlar - bu durumda erken randevu formuna gecmeyelim.
        exact = {
            "nasilsiniz",
            "nasilsin",
            "naber",
            "naptin",
            "iyi misiniz",
            "iyi misin",
            "selam nasilsiniz",
            "merhaba nasilsiniz",
            "merhaba nasilsin",
            "napıyorsunuz",
            "nasil gidiyor",
        }
        if t in exact:
            return True
        if len(t.split()) <= 4 and any(k in t for k in ("nasil", "iyi misin", "iyi misiniz", "naber")):
            return True
        return False

    def _avoid_reasking_known_contact_fields(self, reply_text: str, history: list[dict]) -> str:
        text = (reply_text or "").strip()
        if not text:
            return text
        t_ascii = self._to_ascii_lower(text)
        latest_user = self._latest_user_text(history)
        user_is_smalltalk = self._is_social_smalltalk(latest_user)
        profile = self._extract_contact_profile_from_history(history)
        has_name = bool(profile.get("name"))
        has_phone = bool(profile.get("phone"))
        has_email = bool(profile.get("email"))

        asks_name = any(k in t_ascii for k in ("ad soyad", "adinizi", "adınızı", "isminizi", "ad soyadinizi", "ad soyadınızı"))
        asks_phone = any(k in t_ascii for k in ("telefon", "numara", "telefon bilginizi", "telefonunuzu"))
        asks_email = any(k in t_ascii for k in ("e-posta", "eposta", "email", "mail adres"))
        asked_any = asks_name or asks_phone or asks_email
        is_meeting_like = any(k in t_ascii for k in ("toplanti", "gorusme", "randevu", "kesif", "demo"))
        # "Bilgileriniz mevcut" dediyse ama ad/telefon eksikse - yanlis, eksikleri sor
        if is_meeting_like and (not has_name or not has_phone):
            if "mevcut" in t_ascii and ("bilgileriniz" in t_ascii or "bilgilerin" in t_ascii):
                missing = []
                if not has_name:
                    missing.append("ad soyad")
                if not has_phone:
                    missing.append("telefon numaraniz")
                return f"Randevuyu netlestirmek icin {' ve '.join(missing)} paylasir misiniz?"
        # Sosyal/nezaket mesajina iletişim formu ile yanit vermeyelim.
        if user_is_smalltalk and asked_any:
            return (
                "Tesekkurler, iyiyiz. Siz nasilsiniz? "
                "Isterseniz sektorunuze uygun kullanim senaryolarini kisaca paylasayim."
            )
        if not asked_any:
            return text

        asked_missing = []
        if asks_name and not has_name:
            asked_missing.append("name")
        if asks_phone and not has_phone:
            asked_missing.append("phone")
        if asks_email and not has_email:
            asked_missing.append("email")
        if asked_missing and is_meeting_like:
            labels = {
                "name": "ad soyad",
                "phone": "telefon numaraniz",
                "email": "e-posta adresiniz",
            }
            missing_fields = [labels[k] for k in ("name", "phone", "email") if k in asked_missing]
            if len(missing_fields) == 1:
                missing_text = missing_fields[0]
            elif len(missing_fields) == 2:
                missing_text = f"{missing_fields[0]} ve {missing_fields[1]}"
            else:
                missing_text = f"{missing_fields[0]}, {missing_fields[1]} ve {missing_fields[2]}"

            prefix = ""
            first_sentence = re.split(r"(?<=[.!?])\s+", text, maxsplit=1)[0].strip()
            first_ascii = self._to_ascii_lower(first_sentence)
            mentions_contact_in_first = any(
                k in first_ascii
                for k in ("ad soyad", "adiniz", "adiniz", "isminiz", "telefon", "numara", "e-posta", "eposta", "email", "mail")
            )
            if first_sentence and not mentions_contact_in_first:
                prefix = first_sentence
            if prefix and not prefix.endswith((".", "!", "?")):
                prefix = f"{prefix}."

            ask_line = f"Randevuyu netlestirmek icin sadece {missing_text} paylasir misiniz?"
            return f"{prefix} {ask_line}".strip()
        if asked_missing:
            return text

        if is_meeting_like:
            # Eksik bilgi varken eksikleri sor
            if not has_name or not has_phone:
                missing = []
                if not has_name:
                    missing.append("ad soyad")
                if not has_phone:
                    missing.append("telefon numaraniz")
                missing_text = " ve ".join(missing)
                return f"Randevuyu netlestirmek icin {missing_text} paylasir misiniz?"
            return "Uygun gun ve saatinizi paylasirsaniz toplantiyi hemen planlayabilirim."
        return "Bilgilerinizi daha once paylastiginiz icin tekrar istemiyorum. Bir sonraki adima gecelim."

    def _enhance_first_reply_for_sales(
        self,
        reply_text: str,
        tenant_name: str,
        user_message: str = "",
        variant_seed: int | None = None,
        welcome_scenarios: dict | None = None,
        sector_override: str | None = None,
    ) -> str:
        # Sosyal selamlama (merhaba nasılsın, iyi misiniz vb.) icin kisa cevap - uzun tanitim verme
        if self._is_social_smalltalk(user_message):
            return (
                "Tesekkurler, iyiyiz. Siz nasilsiniz? "
                f"{tenant_name} ile musteri iletisimini tek panelde yonetebilirsiniz. "
                "Hangi sektordesiniz, kisaca anlatir misiniz?"
            )
        intro_variants = [
            (
                f"{tenant_name}; WhatsApp, web ve diger kanallardan gelen musteri mesajlarini tek panelde toplar, "
                "otomatik yanitlar, lead takipleri, randevu/siparis surecleri ve temsilci devralma adimlarini uctan uca yonetir. "
                "Boylece hem satis hizi artar hem de operasyon yukunuz azalir."
            ),
            (
                f"{tenant_name}, musteri iletisimi ve satis operasyonunu tek merkezden yonetmeniz icin tasarlandi. "
                "Mesajlari onceliklendirir, tekrar eden sorulari otomatik yanitlar, kacan talepleri yakalar ve ekip devrini hizlandirir."
            ),
            (
                f"{tenant_name} ile ekibiniz; gelen mesaj, takip, teklif, randevu ve donusum surecini birlikte gorur. "
                "Bu sayede yanit kalitesi standardize olur, geri donus suresi kisalir, musteri deneyimi guclenir."
            ),
        ]
        examples_by_sector = {
            "otomotiv": [
                "Merak ettiginiz bir ozelligimiz var mi? Ornegin: \"Servis randevularimi takip edebilir miyim?\", \"Arac tipine gore otomatik cevap akisi kurabilir miyim?\", \"Musterilerime nasil daha iyi hizmet verebilirim?\"",
                "Isterseniz otomotiv tarafinda detaylandirayim: \"Bakim ve montaj sorularina hazir yanit tanimlayabilir miyim?\", \"Usta/temsilci devrini gecikmeden yapabilir miyim?\", \"Randevu teyitlerini otomatiklestirebilir miyim?\"",
            ],
            "e_ticaret": [
                "Ornek sorularla anlatabilirim: \"Siparis ve kargo sorularini otomatik yanitlayabilir miyim?\", \"Sepet terk eden musterilere takip akisi kurabilir miyim?\", \"Musteri mesajlarini tek ekran uzerinden yonetebilir miyim?\"",
                "Isterseniz e-ticaret senaryosuna inelim: \"Kampanya bazli donusumleri gorebilir miyim?\", \"Urun sorularinda hizli yonlendirme yapabilir miyim?\", \"Ayni sorulara standart cevap seti tanimlayabilir miyim?\"",
            ],
            "saglik": [
                "Saglik tarafinda su sorulari netlestirebiliriz: \"Randevu taleplerini kacirmadan yonetebilir miyim?\", \"Sik sorulan sorulari otomatik yanitlayabilir miyim?\", \"Hasta iletisimi icin hizli geri donus duzeni kurabilir miyim?\"",
                "Isterseniz detaylandirayim: \"Uygun saat oneri akisini otomatiklestirebilir miyim?\", \"Gorusme oncesi gerekli bilgileri adim adim toplayabilir miyim?\", \"Memnuniyet icin takip mesajlari planlayabilir miyim?\"",
            ],
            "egitim": [
                "Egitim kurumlari icin ornek: \"Kayit/on gorusme taleplerini tek panelde toplayabilir miyim?\", \"Veli ve ogrenci sorularina hizli donus verebilir miyim?\", \"Program bilgilerini standart sekilde iletebilir miyim?\"",
                "Isterseniz egitim akisini acayim: \"Sinif/kur bazli sik sorulanlara otomatik yanit kurabilir miyim?\", \"Gorusme planlamayi hizlandirabilir miyim?\", \"Takip sureclerini olculebilir hale getirebilir miyim?\"",
            ],
            "turizm": [
                "Turizm/otel senaryosunda su sorulara cevap verebilirim: \"Rezervasyon taleplerini hizli yonetebilir miyim?\", \"Konaklama ve fiyat sorularini otomatik yanitlayabilir miyim?\", \"Kanal bazli performansi gorebilir miyim?\"",
                "Isterseniz detayli anlatalim: \"Musteri talebini dogru ekibe otomatik aktarabilir miyim?\", \"Yogun saatlerde gecikmeyi azaltabilir miyim?\", \"Sik sorulan sorulari tek cevap setiyle yonetebilir miyim?\"",
            ],
            "genel": [
                "Isterseniz Emare Asistan hakkinda daha fazla bilgi verebilirim. Ornegin su sorulari birlikte netlestirebiliriz: \"Musterilerime nasil daha iyi hizmet verebilirim?\", \"Kacirilan mesajlari otomatik yakalayabilir miyim?\", \"Satis surecini panelden uc uca takip edebilir miyim?\"",
                "Sizin senaryonuza gore en uygun akisi cikarabilirim. Ornek sorular: \"Ilk geri donus suremi nasil dusururum?\", \"Randevu ve teklif surecini nasil kisaltirim?\", \"Ekibin performansini hangi metriklerle takip ederim?\"",
            ],
        }
        custom_cfg = welcome_scenarios if isinstance(welcome_scenarios, dict) else {}
        if custom_cfg.get("enabled") is False:
            return (reply_text or "").strip()
        sector_hint = (sector_override or "").strip().lower() or self._infer_sector_hint(user_message)
        custom_intro = custom_cfg.get("intro_variants")
        if isinstance(custom_intro, list):
            custom_intro = [x.strip() for x in custom_intro if isinstance(x, str) and x.strip()]
            if custom_intro:
                intro_variants = custom_intro
        custom_sector = custom_cfg.get("sector_examples")
        if isinstance(custom_sector, dict):
            for key, value in custom_sector.items():
                if isinstance(value, list):
                    lines = [x.strip() for x in value if isinstance(x, str) and x.strip()]
                    if lines:
                        examples_by_sector[str(key)] = lines
        variant_src = f"{tenant_name}|{user_message}|{variant_seed or 0}|{sector_hint}"
        variant_hash = hashlib.md5(variant_src.encode("utf-8")).hexdigest()
        intro_idx = int(variant_hash[:8], 16) % len(intro_variants)
        intro = intro_variants[intro_idx]
        pool = examples_by_sector.get(sector_hint) or examples_by_sector["genel"]
        example_idx = int(variant_hash[8:16], 16) % len(pool)
        example_questions = pool[example_idx]
        sector_question = (
            "Hangi sektordesiniz? (ornegin e-ticaret, otomotiv, finans, saglik, egitim). "
            "Sektorunuze gore 3-5 somut kullanim senaryosu ve hizli kazanim planini cikarayim.\n\n"
            f"{example_questions}"
        )
        follow_question = (
            "Onceliginiz hangisi: yeni musteri kazanimi, donusum artisi, ilk yanit suresi, yoksa operasyonel verimlilik?"
        )
        text = (reply_text or "").strip()
        user_ascii = self._to_ascii_lower(user_message or "")
        is_greeting_like = (
            len(user_ascii.split()) <= 3
            and user_ascii in {"merhaba", "selam", "mrb", "merhaba!", "selam!", "hey", "iyi gunler", "iyi gunler."}
        )
        if not text:
            return f"{intro}\n\n{sector_question}"

        t_ascii = self._to_ascii_lower(text)
        generic_starters = (
            "emare asistan olarak size nasil yardimci olabilirim",
            "tesekkur ederiz",
            "sizi nasil daha iyi taniyabiliriz",
            "kesif gorusmesi",
            "ihtiyaclarinizi konusalim",
        )
        if is_greeting_like or any(g in t_ascii for g in generic_starters):
            return f"{intro}\n\n{sector_question}"

        needs_intro = not any(
            k in t_ascii
            for k in ("whatsapp", "web", "lead", "randevu", "siparis", "otomasyon", "panel")
        )
        if needs_intro:
            text = f"{intro}\n\n{text}"

        if "sektor" not in t_ascii and "sektordesiniz" not in t_ascii:
            text = f"{text}\n\n{sector_question}"
        elif "?" not in text:
            text = f"{text}\n\n{follow_question}"
        return text

    async def _get_or_create_conversation(
        self,
        platform: str,
        user_id: str,
        customer_name: str | None = None,
        customer_phone: str | None = None,
        tenant_id: int | None = None,
    ) -> Conversation:
        """Sohbet getir veya oluştur (tenant_id: belirtilmezse 1)"""
        tid = tenant_id if tenant_id is not None else 1
        result = await self.db.execute(
            select(Conversation).where(
                Conversation.tenant_id == tid,
                Conversation.platform == platform,
                Conversation.platform_user_id == user_id,
            )
        )
        conv = result.scalar_one_or_none()
        if not conv:
            conv = Conversation(
                tenant_id=tid,
                platform=platform,
                platform_user_id=user_id,
                customer_name=customer_name,
                customer_phone=customer_phone,
            )
            self.db.add(conv)
            await self.db.commit()
            await self.db.refresh(conv)
        elif customer_name or customer_phone:
            conv.customer_name = customer_name or conv.customer_name
            conv.customer_phone = customer_phone or conv.customer_phone
            await self.db.commit()
        return conv

    async def _save_message(
        self,
        conversation_id: int,
        role: str,
        content: str,
        extra_data: str | None = None,
    ):
        """Mesaj kaydet"""
        msg = Message(
            conversation_id=conversation_id,
            role=role,
            content=content,
            extra_data=extra_data,
        )
        self.db.add(msg)
        await self.db.commit()

    async def _get_conversation_history(self, conversation_id: int, limit: int = 50) -> list[dict]:
        """Son mesajları getir (AI için conversation_history formatında)"""
        result = await self.db.execute(
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(desc(Message.created_at))
            .limit(limit + 1)
        )
        messages = list(result.scalars().all())
        if messages:
            messages = messages[1:]  # En son mesajı (şu an işlenen) atla
        messages = list(reversed(messages))
        history = []
        for m in messages:
            role = "user" if m.role == "user" else "assistant"
            content = (m.content or "").replace("\n[Ürün resimleri gönderildi]", "").strip()
            if content:
                history.append({"role": role, "content": content})
        return history[-limit:]

    async def _get_last_selected_product(self, conversation_id: int) -> dict | None:
        """Son seçilen ürünü getir (sipariş için)"""
        result = await self.db.execute(
            select(Message)
            .where(
                Message.conversation_id == conversation_id,
                Message.role == "assistant",
                Message.extra_data.isnot(None),
            )
            .order_by(desc(Message.created_at))
            .limit(5)
        )
        for msg in result.scalars().all():
            try:
                data = json.loads(msg.extra_data or "{}")
                if data.get("selected_product"):
                    return data["selected_product"]
            except json.JSONDecodeError:
                continue
        return None

    async def _expand_suggested_reply_selection(self, conversation_id: int, message_text: str) -> str | None:
        """Kullanıcı '1', '2' vb. yazdıysa son asistan mesajındaki suggested_replies'ten metni al."""
        txt = (message_text or "").strip()
        if not txt or len(txt) > 3:
            return None
        # Sadece rakam veya "1." gibi kısa format
        num_match = re.match(r"^(\d+)\s*\.?\s*$", txt)
        if not num_match:
            return None
        idx = int(num_match.group(1))
        if idx < 1:
            return None
        result = await self.db.execute(
            select(Message)
            .where(
                Message.conversation_id == conversation_id,
                Message.role == "assistant",
                Message.extra_data.isnot(None),
            )
            .order_by(desc(Message.created_at))
            .limit(1)
        )
        msg = result.scalar_one_or_none()
        if not msg or not msg.extra_data:
            return None
        try:
            data = json.loads(msg.extra_data or "{}")
            opts = data.get("suggested_replies") or []
            if not opts or idx > len(opts):
                return None
            chosen = opts[idx - 1]
            if isinstance(chosen, dict):
                return (chosen.get("text") or "").strip() or None
            if isinstance(chosen, str):
                return chosen.strip() or None
        except json.JSONDecodeError:
            pass
        return None

    async def _get_last_sent_products(self, conversation_id: int) -> list[dict]:
        """Son gönderilen ürün resimlerini getir (assistant mesajlarından)"""
        result = await self.db.execute(
            select(Message)
            .where(
                Message.conversation_id == conversation_id,
                Message.role == "assistant",
                Message.extra_data.isnot(None),
            )
            .order_by(desc(Message.created_at))
            .limit(1)
        )
        msg = result.scalar_one_or_none()
        if not msg or not msg.extra_data:
            return []
        try:
            data = json.loads(msg.extra_data)
            return data.get("product_images") or []
        except json.JSONDecodeError:
            return []

    async def _count_tenant_messages_today(self, tenant_id: int) -> int:
        """Tenant'ın bugünkü kullanıcı mesaj sayısı (AI limit kontrolü)"""
        from datetime import datetime, timedelta
        from sqlalchemy import func
        today_start = datetime.utcnow() - timedelta(hours=24)  # Son 24 saat
        result = await self.db.execute(
            select(func.count(Message.id))
            .select_from(Message)
            .join(Conversation, Message.conversation_id == Conversation.id)
            .where(
                Conversation.tenant_id == tenant_id,
                Message.role == "user",
                Message.created_at >= today_start,
            )
        )
        return result.scalar() or 0

    async def _update_conversation_timestamp(self, conversation_id: int):
        """Son mesaj zamanını güncelle"""
        result = await self.db.execute(
            select(Conversation).where(Conversation.id == conversation_id)
        )
        conv = result.scalar_one_or_none()
        if conv:
            conv.last_message_at = datetime.utcnow()
            await self.db.commit()

    def _is_demo_account_request(self, text: str) -> bool:
        """Demo hesap acilis niyetini tespit et"""
        if not text:
            return False
        t = text.lower().strip()
        tr_map = str.maketrans("çğıöşü", "cgiosu")
        t_ascii = t.translate(tr_map)
        has_demo = ("demo" in t) or ("deneme" in t)
        has_account_intent = ("hesap" in t_ascii) or ("uyelik" in t_ascii) or ("kayit" in t_ascii)
        has_open_intent = ("ac" in t_ascii) or ("olustur" in t_ascii) or ("ver" in t_ascii) or ("isterim" in t_ascii)
        phrases = [
            "demo hesabi ac",
            "demo hesap ac",
            "deneme hesabi ac",
            "demo uyelik",
        ]
        return any(p in t_ascii for p in phrases) or (has_demo and has_account_intent and has_open_intent)

    # ── Senaryo Görselleri ──────────────────────────────────────────

    SCENARIO_CARDS = [
        {
            "name": "Müşteri Karşılama",
            "desc": "7/24 otomatik karşılama, sektöre özel selamlama",
            "image": "musteri_karsilama.png",
        },
        {
            "name": "Sipariş & Kargo Takibi",
            "desc": "Otomatik kargo sorgulama, anlık durum bildirimi",
            "image": "siparis_takip.png",
        },
        {
            "name": "Randevu Planlama",
            "desc": "Takvim entegrasyonu, WhatsApp/SMS teyit",
            "image": "randevu_planlama.png",
        },
        {
            "name": "Trendyol Soru-Cevap",
            "desc": "Pazar yeri otomatik yanıt, ürün bilgi eşleştirme",
            "image": "trendyol_soru_cevap.png",
        },
        {
            "name": "Temsilci Devralma",
            "desc": "Tek tıkla temsilci devri, sohbet notları aktarımı",
            "image": "temsilci_devir.png",
        },
        {
            "name": "Çoklu Kanal Yönetimi",
            "desc": "WhatsApp + Instagram + Web + Telegram → Tek panel",
            "image": "coklu_kanal.png",
        },
    ]

    _SCENARIO_KEYWORDS = [
        "ornek senaryo", "örnek senaryo", "senaryo goster",
        "senaryo göster", "senaryo yolla", "senaryo gönder",
        "senaryo ornekleri", "senaryo örnekleri",
        "nasil calisiyor goster", "nasıl çalışıyor göster",
        "kullanim ornekleri", "kullanım örnekleri",
        "ornek goster", "örnek göster",
        "ornekleri gonder", "örnekleri gönder",
    ]

    def _get_scenario_images_response(self, msg_lower: str, msg_normalized: str) -> dict | None:
        """Senaryo görseli istendi mi? İstendiyse resimli yanıt döndür."""
        check = (msg_normalized or msg_lower or "").lower().strip()
        check_ascii = self._to_ascii_lower(check)
        if not any(kw in check or kw in check_ascii for kw in self._SCENARIO_KEYWORDS):
            return None

        base = get_settings().app_base_url.rstrip("/")
        images = []
        lines = ["İşte Emare Asistan kullanım senaryolarından örnekler:\n"]
        for i, sc in enumerate(self.SCENARIO_CARDS, 1):
            lines.append(f"{i}. *{sc['name']}* — {sc['desc']}")
            images.append({
                "url": f"{base}/static/scenarios/{sc['image']}",
                "caption": f"{sc['name']} — {sc['desc']}",
            })
        lines.append("\nDetaylı bilgi veya demo için 'demo hesabı aç' yazabilirsiniz.")

        return {
            "text": "\n".join(lines),
            "product_images": images,
        }

    async def _handle_demo_account_request(self, conv: Conversation, raw_text: str, normalized_text: str) -> str | None:
        """
        Demo hesap acilisi:
        - Ad Soyad
        - E-posta (kullanici adi)
        - Website URL
        bilgilerini toplayip demo tenant + admin olusturur.
        """
        text = (normalized_text or raw_text or "").strip()
        state = self._get_demo_onboarding_state(conv)

        # Aktif bir onboarding yoksa tetikleyici bekle
        if not state and not self._is_demo_account_request(text):
            return None

        # Iptal
        t_ascii = self._to_ascii_lower(text)
        if state and any(k in t_ascii for k in ("iptal", "vazgec", "dur")):
            self._set_demo_onboarding_state(conv, None)
            await self.db.commit()
            return "Demo hesap acilisini iptal ettim. Yeniden baslatmak icin 'demo hesabi ac' yazabilirsiniz."

        # Baslangic
        if not state:
            state = {"step": "name", "name": "", "email": "", "website": ""}
            state = await self._prefill_demo_onboarding_state(conv, state, raw_text)
            next_step = self._next_missing_demo_step(state)
            if next_step is None:
                return await self._finalize_demo_onboarding(conv, state)
            state["step"] = next_step
            self._set_demo_onboarding_state(conv, state)
            await self.db.commit()
            if next_step == "name":
                return "Demo hesap acilisi baslatalim. Once ad soyad bilginizi yazar misiniz?"
            if next_step == "email":
                return "Ad soyad bilginizi aldim. Simdi e-posta adresinizi yazar misiniz? (Bu adres kullanici adiniz olacak.)"
            return "Ad-soyad ve e-posta bilginizi aldim. Son adim olarak web sitenizi yazar misiniz? Ornek: https://firma.com"

        state = await self._prefill_demo_onboarding_state(conv, state, raw_text)
        next_step = self._next_missing_demo_step(state)
        if next_step is None:
            return await self._finalize_demo_onboarding(conv, state)
        state["step"] = next_step
        step = next_step
        user_input = (raw_text or "").strip()

        if step == "name":
            if len(user_input.split()) < 2:
                return "Ad soyad bilgisini tam alabilir miyim? Ornek: Ahmet Yilmaz"
            state["name"] = user_input[:120]
            state["step"] = "email"
            self._set_demo_onboarding_state(conv, state)
            await self.db.commit()
            return "Tesekkurler. Simdi e-posta adresinizi yazar misiniz? (Bu adres kullanici adiniz olacak.)"

        if step == "email":
            if not self._is_valid_email(user_input):
                return "Gecerli bir e-posta adresi rica edeyim. Ornek: ad@firma.com"
            state["email"] = user_input.lower()
            state["step"] = "website"
            self._set_demo_onboarding_state(conv, state)
            await self.db.commit()
            return "Harika. Son adim olarak web sitenizi yazar misiniz? Ornek: https://firma.com"

        if step == "website":
            website = self._normalize_website(user_input)
            if not website:
                return "Web site adresini tam formatta yazar misiniz? Ornek: https://firma.com"
            state["website"] = website

            return await self._finalize_demo_onboarding(conv, state)

        return None

    def _to_ascii_lower(self, s: str) -> str:
        tr_map = str.maketrans("çğıöşü", "cgiosu")
        return (s or "").lower().translate(tr_map).strip()

    def _is_valid_email(self, email: str) -> bool:
        if not email:
            return False
        return bool(re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email.strip().lower()))

    def _extract_email_from_text(self, text: str) -> str | None:
        if not text:
            return None
        m = re.search(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", text)
        if not m:
            return None
        email = (m.group(0) or "").strip().lower()
        return email if self._is_valid_email(email) else None

    def _extract_email_from_history(self, history: list[dict]) -> str | None:
        for item in reversed(history):
            if item.get("role") != "user":
                continue
            email = self._extract_email_from_text(item.get("content") or "")
            if email:
                return email
        return None

    def _normalize_website(self, website: str) -> str | None:
        v = (website or "").strip()
        if not v:
            return None
        if not v.startswith(("http://", "https://")):
            v = "https://" + v
        try:
            parsed = urlparse(v)
            if not parsed.netloc or "." not in parsed.netloc:
                return None
            return f"{parsed.scheme}://{parsed.netloc}"
        except Exception:
            return None

    def _extract_website_from_text(self, text: str) -> str | None:
        if not text:
            return None
        candidates = re.findall(r"(https?://[^\s,;]+|www\.[^\s,;]+|[A-Za-z0-9.-]+\.[A-Za-z]{2,})", text)
        for c in candidates:
            token = (c or "").strip(".,;:!?()[]{}<>\"'")
            if "@" in token:
                continue
            website = self._normalize_website(token)
            if website:
                return website
        return None

    def _extract_website_from_history(self, history: list[dict]) -> str | None:
        for item in reversed(history):
            if item.get("role") != "user":
                continue
            website = self._extract_website_from_text(item.get("content") or "")
            if website:
                return website
        return None

    def _extract_demo_name_from_text(self, text: str) -> str | None:
        raw = (text or "").strip()
        if not raw:
            return None
        t_ascii = self._to_ascii_lower(raw)
        if any(k in t_ascii for k in ("demo", "hesap", "uyelik", "kayit", "website", "site", "eposta", "mail")):
            return None
        if "@" in raw or "http://" in raw.lower() or "https://" in raw.lower() or "www." in raw.lower():
            return None
        words = [w for w in re.split(r"\s+", raw) if w]
        if len(words) < 2:
            return None
        if any(any(ch.isdigit() for ch in w) for w in words):
            return None
        return " ".join(words[:3])[:120]

    def _next_missing_demo_step(self, state: dict) -> str | None:
        if not (state.get("name") or "").strip():
            return "name"
        if not self._is_valid_email(state.get("email") or ""):
            return "email"
        if not self._normalize_website(state.get("website") or ""):
            return "website"
        return None

    async def _prefill_demo_onboarding_state(self, conv: Conversation, state: dict, raw_text: str) -> dict:
        history = await self._get_conversation_history(conv.id, limit=60)
        history_with_current = list(history)
        if raw_text:
            history_with_current.append({"role": "user", "content": raw_text})

        if not (state.get("name") or "").strip():
            name = self._extract_demo_name_from_text(raw_text) or self._extract_name_from_history(history_with_current)
            if name:
                state["name"] = name
        if not self._is_valid_email(state.get("email") or ""):
            email = self._extract_email_from_text(raw_text) or self._extract_email_from_history(history_with_current)
            if email:
                state["email"] = email
        if not self._normalize_website(state.get("website") or ""):
            website = self._extract_website_from_text(raw_text) or self._extract_website_from_history(history_with_current)
            if website:
                state["website"] = website
        return state

    async def _finalize_demo_onboarding(self, conv: Conversation, state: dict) -> str:
        source = self._extract_demo_source(conv)
        today_count = await self._count_demo_accounts_today(source)
        if today_count >= self.DEMO_DAILY_LIMIT_PER_SOURCE:
            self._set_demo_onboarding_state(conv, None)
            await self.db.commit()
            return (
                "Bugun bu numara icin demo hesap limiti doldu. "
                "Yarin tekrar deneyebilir veya mevcut demo hesabinizla devam edebilirsiniz."
            )

        result = await self._create_or_update_demo_account(
            full_name=(state.get("name") or "").strip(),
            email=(state.get("email") or "").strip().lower(),
            website=self._normalize_website(state.get("website") or "") or "",
            source=source,
        )
        self._set_demo_onboarding_state(conv, None)
        await self.db.commit()

        base_url = (get_settings().app_base_url or "").strip() or "http://77.92.152.3:8000"
        return (
            "Demo hesabinizi hazirladim. Giris bilgileri:\n"
            f"- Panel: {base_url.rstrip('/')}/admin\n"
            f"- Kullanici adi: {result['email']}\n"
            f"- E-posta: {result['email']}\n"
            f"- Sifre: {result['password']}\n"
            f"- Website: {result['website']}\n"
            f"- Demo bitis: {result['trial_expires_at']}\n"
            "Web sitenizdeki hizmet/urun yapisini da demo hesabiniza otomatik tanimladim."
        )

    def _read_order_draft_dict(self, conv: Conversation) -> dict:
        try:
            return json.loads(conv.order_draft or "{}")
        except Exception:
            return {}

    def _get_demo_onboarding_state(self, conv: Conversation) -> dict | None:
        data = self._read_order_draft_dict(conv)
        state = data.get("__demo_onboarding")
        return state if isinstance(state, dict) else None

    def _set_demo_onboarding_state(self, conv: Conversation, state: dict | None) -> None:
        data = self._read_order_draft_dict(conv)
        if state is None:
            data.pop("__demo_onboarding", None)
        else:
            data["__demo_onboarding"] = state
        conv.order_draft = json.dumps(data, ensure_ascii=False)

    def _extract_demo_source(self, conv: Conversation) -> str:
        raw = (conv.customer_phone or conv.platform_user_id or "").strip()
        digits = "".join(ch for ch in raw if ch.isdigit())
        return digits[-12:] if digits else "unknown"

    async def _count_demo_accounts_today(self, source: str) -> int:
        start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        res = await self.db.execute(
            select(Tenant).where(
                Tenant.status == "trial",
                Tenant.created_at >= start,
            )
        )
        tenants = res.scalars().all()
        total = 0
        for t in tenants:
            try:
                data = json.loads(t.settings or "{}") if isinstance(t.settings, str) else (t.settings or {})
            except Exception:
                data = {}
            if (data.get("demo_source") or "") == source:
                total += 1
        return total

    async def _create_or_update_demo_account(self, full_name: str, email: str, website: str, source: str) -> dict:
        import bcrypt
        from services.ai.website_analyzer import WebsiteAnalyzer

        password_plain = "Demo1234"
        pw_hash = bcrypt.hashpw(password_plain.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
        trial_expires_at = datetime.utcnow() + timedelta(days=self.DEMO_TRIAL_DAYS)
        trial_expires_txt = trial_expires_at.strftime("%d.%m.%Y %H:%M")

        # Website analiz - hizmet/urunleri direkt tasimak icin
        analysis = await WebsiteAnalyzer(website).analyze()
        products = analysis.get("products") or []
        sector = analysis.get("sector") or "genel"
        base_name = (analysis.get("name") or "").strip() or f"{full_name} Demo"
        suggested_slug = (analysis.get("slug") or "").strip() or f"demo-{secrets.token_hex(3)}"

        # Slug uniq
        slug = suggested_slug.lower()
        slug = re.sub(r"[^a-z0-9_-]", "-", slug).strip("-") or f"demo-{secrets.token_hex(3)}"
        existing_slug = await self.db.execute(select(Tenant).where(Tenant.slug == slug))
        if existing_slug.scalar_one_or_none():
            slug = f"{slug}-{secrets.token_hex(2)}"

        user_result = await self.db.execute(select(User).where(User.email == email.lower()))
        user = user_result.scalar_one_or_none()

        if user:
            user.name = full_name
            user.password_hash = pw_hash
            user.role = "admin"
            user.is_active = True
            t_res = await self.db.execute(select(Tenant).where(Tenant.id == user.tenant_id))
            tenant = t_res.scalar_one_or_none()
            if tenant:
                tenant.status = "trial"
                tenant.website_url = website
                try:
                    data = json.loads(tenant.settings or "{}") if isinstance(tenant.settings, str) else (tenant.settings or {})
                except Exception:
                    data = {}
                data["demo_source"] = source
                data["demo_trial_expires_at"] = trial_expires_at.isoformat()
                data["demo_trial_days"] = self.DEMO_TRIAL_DAYS
                tenant.settings = json.dumps(data, ensure_ascii=False)
        else:
            tenant = Tenant(
                name=base_name,
                slug=slug,
                website_url=website,
                sector=sector,
                products_path=f"data/tenants/{slug}/products.json",
                status="trial",
                settings=json.dumps(
                    {
                        "name": base_name,
                        "demo_source": source,
                        "demo_trial_expires_at": trial_expires_at.isoformat(),
                        "demo_trial_days": self.DEMO_TRIAL_DAYS,
                    },
                    ensure_ascii=False,
                ),
            )
            self.db.add(tenant)
            await self.db.flush()

            user = User(
                tenant_id=tenant.id,
                name=full_name,
                email=email.lower(),
                password_hash=pw_hash,
                role="admin",
                is_active=True,
            )
            self.db.add(user)

        # Website icerigini tenant urun/hizmet baglamina yaz
        t_res = await self.db.execute(select(Tenant).where(Tenant.id == user.tenant_id))
        current_tenant = t_res.scalar_one_or_none()
        try:
            products_dir = Path(__file__).resolve().parent.parent / "data" / "tenants" / current_tenant.slug
            products_dir.mkdir(parents=True, exist_ok=True)
            with open(products_dir / "products.json", "w", encoding="utf-8") as f:
                json.dump(products, f, ensure_ascii=False, indent=2)
            current_tenant.products_path = f"data/tenants/{current_tenant.slug}/products.json"
        except Exception:
            pass

        return {
            "email": email.lower(),
            "password": password_plain,
            "website": website,
            "trial_expires_at": trial_expires_txt,
        }

    def _is_confirmation_text(self, text: str) -> bool:
        t = self._to_ascii_lower(text)
        confirmations = {"tamam", "olur", "uygun", "onay", "ok", "tamamdir", "anlastik"}
        return t in confirmations or any(t.startswith(f"{c} ") for c in confirmations)

    def _is_strong_confirmation_text(self, text: str) -> bool:
        t = self._to_ascii_lower(text)
        if not t:
            return False
        confirmations = {"evet", "e", "onay", "onayliyorum", "kesin", "dogruluyorum", "ok"}
        if t in confirmations or any(t.startswith(f"{c} ") for c in confirmations):
            return True
        # Noktalama/ek metinli formlari da yakala: "evet.", "onay, tamam", "evet lutfen" vb.
        if re.search(r"\b(evet|onay|onayliyorum|kesin|dogruluyorum|ok)\b", t):
            return True
        # "evet lutfen", "evet onay" gibi bilesik onaylar
        if t.startswith("evet ") and len(t.split()) <= 3:
            return True
        return False

    def _is_negative_confirmation_text(self, text: str) -> bool:
        t = self._to_ascii_lower(text)
        negatives = {"hayir", "h", "degil", "iptal", "vazgectim", "olmaz"}
        return t in negatives or any(t.startswith(f"{c} ") for c in negatives)

    def _extract_time_from_text(self, text: str) -> tuple[int, int] | None:
        if not text:
            return None
        # Sadece 15:30 gibi net saat formatini kabul et.
        # 14.02.2026 gibi tarihleri yanlislikla saat algilamamak icin ":" zorunlu.
        m = re.search(r"\b([01]?\d|2[0-3]):([0-5]\d)\b", text)
        if not m:
            return None
        return int(m.group(1)), int(m.group(2))

    def _extract_phone_from_history(self, history: list[dict]) -> str | None:
        for item in reversed(history):
            if item.get("role") != "user":
                continue
            txt = item.get("content") or ""
            digits = "".join(ch for ch in txt if ch.isdigit())
            if len(digits) >= 10:
                return digits[-11:] if len(digits) >= 11 else digits
        return None

    def _extract_name_from_history(self, history: list[dict]) -> str | None:
        stopwords = {
            "satis", "hizmet", "demo", "hesap", "yazilim", "urun", "urunleri",
            "beyaz", "esya", "otomotiv", "oto", "randevu", "toplanti", "gorusme",
            "hangi", "sektor", "sektorde", "sektoru", "nasil", "nedir", "ne", "evet", "hayir",
        }
        banned_fragments = (
            "hangi sektor",
            "hangi sektorde",
            "sektorunuz",
            "sektorunde",
            "kisa bir gorusme",
            "demo planlamak",
        )

        # 1) "Ad Soyad email telefon" tek satirinda adi ayikla
        for item in reversed(history):
            if item.get("role") != "user":
                continue
            txt = (item.get("content") or "").strip()
            txt_ascii = self._to_ascii_lower(txt)
            if "?" in txt or any(b in txt_ascii for b in banned_fragments):
                continue
            if "@" not in txt:
                continue
            # email ve telefonu ayikla
            cleaned = re.sub(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", " ", txt)
            cleaned = re.sub(r"\+?\d[\d\s-]{8,}\d", " ", cleaned)
            words = [w for w in re.split(r"\s+", cleaned) if w]
            if len(words) >= 2:
                ascii_words = [self._to_ascii_lower(w) for w in words]
                if not any(w in stopwords for w in ascii_words):
                    return " ".join(words[:3])[:120]

        # 2) Son kullanici mesajlarinda aday ad soyad ara
        for item in reversed(history):
            if item.get("role") != "user":
                continue
            txt = (item.get("content") or "").strip()
            txt_ascii = self._to_ascii_lower(txt)
            if "?" in txt or any(b in txt_ascii for b in banned_fragments):
                continue
            if "@" in txt:
                continue
            words = [w for w in re.split(r"\s+", txt) if w]
            if len(words) < 2:
                continue
            # Basit filtre: rakam icermesin
            if any(any(ch.isdigit() for ch in w) for w in words):
                continue
            ascii_words = [self._to_ascii_lower(w) for w in words]
            if any(w in stopwords for w in ascii_words):
                continue
            return " ".join(words[:3])[:120]
        return None

    def _latest_assistant_with_time(self, history: list[dict]) -> str | None:
        for item in reversed(history):
            if item.get("role") != "assistant":
                continue
            txt = item.get("content") or ""
            t_ascii = self._to_ascii_lower(txt)
            if self._extract_time_from_text(txt) and any(k in t_ascii for k in ("randevu", "gorusme", "demo")):
                return txt
        return None

    def _get_appointment_confirm_state(self, conv: Conversation) -> dict | None:
        data = self._read_order_draft_dict(conv)
        state = data.get("__appointment_confirm")
        return state if isinstance(state, dict) else None

    def _set_appointment_confirm_state(self, conv: Conversation, state: dict | None) -> None:
        data = self._read_order_draft_dict(conv)
        if state is None:
            data.pop("__appointment_confirm", None)
        else:
            data["__appointment_confirm"] = state
        conv.order_draft = json.dumps(data, ensure_ascii=False)

    async def _maybe_create_meeting_appointment(
        self,
        conv: Conversation,
        tenant_id: int,
        history: list[dict],
        message_text: str,
    ) -> str | None:
        msg = (message_text or "").strip()

        # 1) Bekleyen dogrulama varsa ikinci adimda net onay bekle
        pending = self._get_appointment_confirm_state(conv)
        if pending:
            if self._is_negative_confirmation_text(msg):
                self._set_appointment_confirm_state(conv, None)
                await self.db.commit()
                return "Tamam, randevu olusturma islemini iptal ettim."
            # Bekleyen onay adiminda "evet/onay" disinda "tamam/olur" gibi net onaylari da kabul et.
            if not (self._is_strong_confirmation_text(msg) or self._is_confirmation_text(msg)):
                return (
                    "Randevuyu olusturmam icin net onay gerekiyor. "
                    "Onayliyorsaniz 'evet' (veya 'onay') yazin; "
                    "iptal icin 'hayir' yazin, degistirmek isterseniz yeni saat paylasin."
                )

            try:
                scheduled_at = datetime.fromisoformat(pending.get("scheduled_at"))
            except Exception:
                self._set_appointment_confirm_state(conv, None)
                await self.db.commit()
                return None
            customer_name = (pending.get("customer_name") or "").strip()
            customer_phone = (pending.get("customer_phone") or "").strip()
            if not (customer_name and customer_phone):
                self._set_appointment_confirm_state(conv, None)
                await self.db.commit()
                return None

            dup = await self.db.execute(
                select(Appointment).where(
                    Appointment.conversation_id == conv.id,
                    Appointment.scheduled_at == scheduled_at,
                )
            )
            if dup.scalar_one_or_none():
                self._set_appointment_confirm_state(conv, None)
                await self.db.commit()
                return "Bu randevu zaten olusturulmus gorunuyor. Panelden kontrol edebilirsiniz."

            await create_appointment_svc(
                self.db,
                tenant_id=tenant_id,
                scheduled_at=scheduled_at,
                customer_name=customer_name,
                customer_phone=customer_phone,
                conversation_id=conv.id,
            )
            self._set_appointment_confirm_state(conv, None)
            await self.db.commit()

            day_names = ["Pazartesi", "Sali", "Carsamba", "Persembe", "Cuma", "Cumartesi", "Pazar"]
            day_name = day_names[scheduled_at.weekday()]
            return (
                "Randevunuzu olusturdum.\n"
                f"- Tarih: {day_name} {scheduled_at.strftime('%d.%m.%Y')}\n"
                f"- Saat: {scheduled_at.strftime('%H:%M')}\n"
                f"- Ad Soyad: {customer_name}\n"
                f"- Telefon: {customer_phone}"
            )

        # 2) Kullanici dogrudan gun+saat paylastiysa (ornek: "carsamba 15") da onaya gec.
        scheduled_at_direct = self._extract_datetime_from_user_text(msg)
        if scheduled_at_direct:
            customer_name = self._extract_name_from_history(history)
            customer_phone = self._extract_phone_from_history(history)
            if customer_name and customer_phone:
                self._set_appointment_confirm_state(
                    conv,
                    {
                        "scheduled_at": scheduled_at_direct.isoformat(),
                        "customer_name": customer_name,
                        "customer_phone": customer_phone,
                    },
                )
                await self.db.commit()
                day_names = ["Pazartesi", "Sali", "Carsamba", "Persembe", "Cuma", "Cumartesi", "Pazar"]
                day_name = day_names[scheduled_at_direct.weekday()]
                return (
                    "Paylastiginiz saate gore randevuyu hazirladim, son bir onay alayim.\n"
                    f"- Tarih: {day_name} {scheduled_at_direct.strftime('%d.%m.%Y')}\n"
                    f"- Saat: {scheduled_at_direct.strftime('%H:%M')}\n"
                    f"- Ad Soyad: {customer_name}\n"
                    f"- Telefon: {customer_phone}\n"
                    "Onay icin: 'evet' / 'onay' | Iptal icin: 'hayir'"
                )

        # 3) Yeni onay denemesi: onceki asistan saat onerisine "tamam/olur" vb. cevap verildiyse taslak olustur.
        if not self._is_confirmation_text(msg):
            return None

        assistant_line = self._latest_assistant_with_time(history)
        if not assistant_line:
            return None

        tm = self._extract_time_from_text(assistant_line)
        if not tm:
            return None
        hour, minute = tm

        customer_name = self._extract_name_from_history(history)
        customer_phone = self._extract_phone_from_history(history)
        if not (customer_name and customer_phone):
            return None

        now = now_turkey()
        scheduled_at = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if scheduled_at <= now:
            scheduled_at = scheduled_at + timedelta(days=1)

        self._set_appointment_confirm_state(
            conv,
            {
                "scheduled_at": scheduled_at.isoformat(),
                "customer_name": customer_name,
                "customer_phone": customer_phone,
            },
        )
        await self.db.commit()

        day_names = ["Pazartesi", "Sali", "Carsamba", "Persembe", "Cuma", "Cumartesi", "Pazar"]
        day_name = day_names[scheduled_at.weekday()]
        return (
            "Randevu olusturmadan once son bir dogrulama yapalim.\n"
            f"- Tarih: {day_name} {scheduled_at.strftime('%d.%m.%Y')}\n"
            f"- Saat: {scheduled_at.strftime('%H:%M')}\n"
            f"- Ad Soyad: {customer_name}\n"
            f"- Telefon: {customer_phone}\n"
            "Onay icin: 'evet' / 'onay' | Iptal icin: 'hayir'"
        )

    def _extract_datetime_from_user_text(self, text: str) -> datetime | None:
        raw = (text or "").strip()
        if not raw:
            return None

        tm = self._extract_time_from_text(raw)
        if tm:
            now = now_turkey()
            hour, minute = tm
            candidate = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
            if candidate <= now:
                candidate = candidate + timedelta(days=1)
            return candidate

        txt = self._to_ascii_lower(raw)
        day_map = {
            "pazartesi": 0,
            "sali": 1,
            "carsamba": 2,
            "persembe": 3,
            "cuma": 4,
            "cumartesi": 5,
            "pazar": 6,
        }
        weekday = None
        for key, idx in day_map.items():
            if key in txt:
                weekday = idx
                break
        if weekday is None:
            return None

        m = re.search(r"\b([01]?\d|2[0-3])(?::([0-5]\d))?\b", txt)
        if not m:
            return None
        hour = int(m.group(1))
        minute = int(m.group(2) or 0)

        now = now_turkey()
        delta_days = (weekday - now.weekday()) % 7
        candidate = (now + timedelta(days=delta_days)).replace(hour=hour, minute=minute, second=0, microsecond=0)
        if candidate <= now:
            candidate = candidate + timedelta(days=7)
        return candidate
