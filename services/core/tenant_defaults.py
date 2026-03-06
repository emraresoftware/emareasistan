"""
Yeni tenant oluşturulduğunda otomatik örnek veri oluşturma.

Kurallar, iş akışları ve süreç konfigürasyonları dahildir.
Kullanıcılar paneli açtığında boş görmez, sistemin nasıl çalıştığını hemen anlar.
"""
import json
import logging

from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────────────────────
# ÖRNEK KURALLAR (ResponseRule)
# ──────────────────────────────────────────────────────────────────────────────

def _default_rules(tenant_id: int) -> list[dict]:
    return [
        {
            "tenant_id": tenant_id,
            "name": "💰 Fiyat Sorusu",
            "trigger_type": "keyword",
            "trigger_value": "fiyat,ücret,kaç para,ne kadar,fiyatı nedir",
            "product_ids": json.dumps([]),
            "image_urls": json.dumps([]),
            "custom_message": (
                "Fiyat bilgisi için lütfen ürün adını veya model numarasını paylaşır mısınız? "
                "Size en güncel fiyatı hemen ileteyim. 🏷️"
            ),
            "is_active": True,
            "priority": 10,
        },
        {
            "tenant_id": tenant_id,
            "name": "🚚 Kargo Takip",
            "trigger_type": "keyword",
            "trigger_value": "kargo,takip,ne zaman gelir,kargom,siparişim",
            "product_ids": json.dumps([]),
            "image_urls": json.dumps([]),
            "custom_message": (
                "Kargo takibi için sipariş numaranızı veya telefon numaranızı paylaşırsanız "
                "durumu anında kontrol edip bildiriyorum. 📦"
            ),
            "is_active": True,
            "priority": 9,
        },
        {
            "tenant_id": tenant_id,
            "name": "📅 Randevu Talebi",
            "trigger_type": "keyword",
            "trigger_value": "randevu,appointment,saat,müsait misin,ne zaman açık",
            "product_ids": json.dumps([]),
            "image_urls": json.dumps([]),
            "custom_message": (
                "Randevu almak için uygun olduğunuz tarih ve saati belirtir misiniz? "
                "Hemen uygun bir slot ayarlıyorum! 📅"
            ),
            "is_active": True,
            "priority": 8,
        },
        {
            "tenant_id": tenant_id,
            "name": "🔄 İade & Değişim",
            "trigger_type": "keyword",
            "trigger_value": "iade,değişim,ürünü iade,geri iade,iptal",
            "product_ids": json.dumps([]),
            "image_urls": json.dumps([]),
            "custom_message": (
                "İade veya değişim talebiniz için sipariş numaranızı paylaşır mısınız? "
                "Süreci hızlıca başlatıyorum. 🔄"
            ),
            "is_active": True,
            "priority": 7,
        },
        {
            "tenant_id": tenant_id,
            "name": "⭐ Memnuniyet Testi (Pasif Örnek)",
            "trigger_type": "keyword",
            "trigger_value": "memnun kaldım,teşekkürler,harika,çok güzel",
            "product_ids": json.dumps([]),
            "image_urls": json.dumps([]),
            "custom_message": (
                "Geri bildiriminiz için teşekkür ederiz! Sizi mutlu edebilmek bizim için en büyük motivasyon. "
                "Başka bir konuda yardımcı olabilir miyim? 😊"
            ),
            "is_active": False,   # Kapalı — örnek olarak bırakıldı
            "priority": 1,
        },
    ]


# ──────────────────────────────────────────────────────────────────────────────
# ÖRNEK İŞ AKIŞLARI (TenantWorkflow + WorkflowStep)
# ──────────────────────────────────────────────────────────────────────────────

def _default_workflows(tenant_id: int) -> list[dict]:
    """Her akış: workflow_data + steps listesi döndürür."""
    return [
        {
            "workflow": {
                "tenant_id": tenant_id,
                "platform": "whatsapp",
                "workflow_name": "🙋 Yeni Müşteri Karşılama",
                "description": (
                    "İlk kez yazan kullanıcıyı otomatik karşılar, hizmetleri tanıtır "
                    "ve sıkça sorulan sorulara yönlendirir."
                ),
                "is_active": True,
                "graph_layout": json.dumps({
                    "nodes": [
                        {"id": "n1", "step_order": 0, "x": 80,  "y": 200},
                        {"id": "n2", "step_order": 1, "x": 280, "y": 200},
                        {"id": "n3", "step_order": 2, "x": 480, "y": 200},
                    ],
                    "edges": [
                        {"source": "n1", "target": "n2"},
                        {"source": "n2", "target": "n3"},
                    ],
                }),
            },
            "steps": [
                {
                    "step_name": "🔔 Tetikleyici: İlk Mesaj",
                    "step_type": "trigger",
                    "config": json.dumps({
                        "event": "first_message",
                        "description": "Kullanıcının ilk mesajı bu akışı başlatır.",
                        "conditions": {"is_new_contact": True},
                    }),
                    "order_index": 0,
                },
                {
                    "step_name": "✉️ Karşılama Mesajı Gönder",
                    "step_type": "action",
                    "config": json.dumps({
                        "action": "send_message",
                        "message": (
                            "Merhaba! 👋 Hoş geldiniz.\n\n"
                            "Size nasıl yardımcı olabilirim?\n\n"
                            "1️⃣ Ürünler & Fiyatlar\n"
                            "2️⃣ Sipariş Takibi\n"
                            "3️⃣ Randevu Al\n"
                            "4️⃣ Diğer"
                        ),
                        "description": "Kullanıcıya menü seçenekleriyle karşılama mesajı gönderilir.",
                    }),
                    "order_index": 1,
                },
                {
                    "step_name": "⏳ Bekle & Yanıt Al",
                    "step_type": "condition",
                    "config": json.dumps({
                        "condition": "wait_for_reply",
                        "timeout_seconds": 300,
                        "fallback": "ai_response",
                        "description": "Kullanıcı yanıt vermezse AI normal akışa döner.",
                    }),
                    "order_index": 2,
                },
            ],
        },
        {
            "workflow": {
                "tenant_id": tenant_id,
                "platform": "whatsapp",
                "workflow_name": "📦 Sipariş Durum Sorgulama",
                "description": (
                    "Kargo veya sipariş durumu soran kullanıcıdan sipariş no alır, "
                    "otomatik sorgular ve bildirir."
                ),
                "is_active": True,
                "graph_layout": json.dumps({
                    "nodes": [
                        {"id": "n1", "step_order": 0, "x": 80,  "y": 200},
                        {"id": "n2", "step_order": 1, "x": 280, "y": 200},
                        {"id": "n3", "step_order": 2, "x": 480, "y": 200},
                        {"id": "n4", "step_order": 3, "x": 680, "y": 200},
                    ],
                    "edges": [
                        {"source": "n1", "target": "n2"},
                        {"source": "n2", "target": "n3"},
                        {"source": "n3", "target": "n4"},
                    ],
                }),
            },
            "steps": [
                {
                    "step_name": "🔔 Tetikleyici: Kargo Anahtar Kelime",
                    "step_type": "trigger",
                    "config": json.dumps({
                        "event": "keyword_match",
                        "keywords": ["kargo", "takip", "ne zaman gelir", "siparişim"],
                        "description": "Kullanıcı kargo veya sipariş sorduğunda tetiklenir.",
                    }),
                    "order_index": 0,
                },
                {
                    "step_name": "💬 Sipariş Numarası İste",
                    "step_type": "action",
                    "config": json.dumps({
                        "action": "send_message",
                        "message": (
                            "Sipariş durumunuzu kontrol edebilmem için sipariş numaranızı "
                            "veya kayıtlı telefon numaranızı paylaşır mısınız? 📦"
                        ),
                        "description": "Kullanıcıdan sipariş numarası istenir.",
                    }),
                    "order_index": 1,
                },
                {
                    "step_name": "🔍 Sipariş No Doğrula",
                    "step_type": "condition",
                    "config": json.dumps({
                        "condition": "input_matches",
                        "pattern": r"^\d{5,20}$",
                        "on_match": "query_order",
                        "on_fail": "ask_again",
                        "max_retries": 2,
                        "description": "Girilen değer sipariş numarası formatına uyuyorsa sorgular.",
                    }),
                    "order_index": 2,
                },
                {
                    "step_name": "📋 Kargo Durumu Bildir",
                    "step_type": "action",
                    "config": json.dumps({
                        "action": "query_and_respond",
                        "source": "order_system",
                        "message_template": (
                            "Siparişiniz bulundu! 🎉\n"
                            "Durum: {order_status}\n"
                            "Kargo No: {cargo_tracking}\n"
                            "Tahmini Teslimat: {estimated_date}"
                        ),
                        "description": "Sipariş sorgusunun sonucu kullanıcıya iletilir.",
                    }),
                    "order_index": 3,
                },
            ],
        },
        {
            "workflow": {
                "tenant_id": tenant_id,
                "platform": "whatsapp",
                "workflow_name": "🔔 Çalışma Saati Dışı Bildirim (Pasif Örnek)",
                "description": (
                    "Mesai saatleri dışında gelen mesajları yakalar ve "
                    "çalışma saatlerini bildirir."
                ),
                "is_active": False,   # Kapalı — örnek olarak bırakıldı
                "graph_layout": json.dumps({
                    "nodes": [
                        {"id": "n1", "step_order": 0, "x": 80,  "y": 200},
                        {"id": "n2", "step_order": 1, "x": 280, "y": 200},
                    ],
                    "edges": [{"source": "n1", "target": "n2"}],
                }),
            },
            "steps": [
                {
                    "step_name": "🕐 Mesai Dışı Tetikleyici",
                    "step_type": "trigger",
                    "config": json.dumps({
                        "event": "message_received",
                        "schedule": {
                            "outside_hours": {"start": "09:00", "end": "18:00"},
                            "timezone": "Europe/Istanbul",
                            "days": ["monday", "tuesday", "wednesday", "thursday", "friday"],
                        },
                        "description": "Hafta içi 09:00-18:00 dışında gelen mesajlarda tetiklenir.",
                    }),
                    "order_index": 0,
                },
                {
                    "step_name": "💤 Mesai Dışı Otomatik Yanıt",
                    "step_type": "action",
                    "config": json.dumps({
                        "action": "send_message",
                        "message": (
                            "Merhaba! Şu an çalışma saatlerimiz dışındasınız. 🌙\n\n"
                            "Çalışma saatlerimiz: Hafta içi 09:00 – 18:00\n\n"
                            "Mesajınız kaydedildi, en kısa sürede dönüş yapacağız. "
                            "Acil durumlar için: 0850 XXX XX XX"
                        ),
                        "description": "Kullanıcıya çalışma saati bilgisi ve acil iletişim gönderilir.",
                    }),
                    "order_index": 1,
                },
            ],
        },
    ]


# ──────────────────────────────────────────────────────────────────────────────
# ÖRNEK SÜREÇ KONFİGÜRASYONLARI (ProcessConfig)
# ──────────────────────────────────────────────────────────────────────────────

def _default_process_configs(tenant_id: int) -> list[dict]:
    return [
        {
            "tenant_id": tenant_id,
            "process_type": "customer_service",
            "platform": "whatsapp",
            "auto_response": True,
            "escalation_rules": json.dumps({
                "after_seconds": 300,
                "assign_to": "agent",
                "notify_message": (
                    "Talebiniz bir temsilciye iletildi. En kısa sürede dönüş yapılacak. ⏳"
                ),
                "description": (
                    "5 dakika içinde çözülemeyen sorunlar temsilciye devredilir."
                ),
            }),
            "sla_settings": json.dumps({
                "first_response_seconds": 60,
                "resolution_hours": 24,
                "priority_levels": {
                    "high": {"response_seconds": 30, "resolution_hours": 4},
                    "normal": {"response_seconds": 60, "resolution_hours": 24},
                    "low": {"response_seconds": 300, "resolution_hours": 72},
                },
                "description": (
                    "Normal sorular için 1 dak içinde ilk yanıt, 24 saat içinde çözüm hedeflenir."
                ),
            }),
            "notification_rules": json.dumps([
                {
                    "event": "new_message",
                    "channels": ["whatsapp"],
                    "description": "Yeni müşteri mesajında panelde bildirim oluştur.",
                },
                {
                    "event": "unread_5min",
                    "channels": ["whatsapp", "email"],
                    "description": "5 dakika okunmayan mesajda e-posta bildirimi gönder.",
                },
            ]),
        },
        {
            "tenant_id": tenant_id,
            "process_type": "order_management",
            "platform": "whatsapp",
            "auto_response": True,
            "escalation_rules": json.dumps({
                "after_seconds": 600,
                "assign_to": "agent",
                "notify_message": (
                    "Sipariş talebiniz işleme alındı. Ekibimiz en kısa sürede iletişime geçecek. 📦"
                ),
                "description": (
                    "10 dakika içinde sistem otomatik yanıt veremezse temsilciye aktarılır."
                ),
            }),
            "sla_settings": json.dumps({
                "first_response_seconds": 30,
                "resolution_hours": 48,
                "order_confirmation_seconds": 120,
                "description": (
                    "Sipariş talebi 30 saniye içinde onaylanmalı, 48 saat içinde teslim planlanmalı."
                ),
            }),
            "notification_rules": json.dumps([
                {
                    "event": "new_order",
                    "channels": ["whatsapp"],
                    "description": "Yeni sipariş geldiğinde ilgili ekibe WhatsApp bildirimi.",
                },
                {
                    "event": "order_cancelled",
                    "channels": ["whatsapp", "email"],
                    "description": "Sipariş iptalinde hem müşteriye hem işletmeye bildirim.",
                },
                {
                    "event": "payment_failed",
                    "channels": ["whatsapp"],
                    "description": "Ödeme başarısız olduğunda müşteriye anında bilgi ver.",
                },
            ]),
        },
        {
            "tenant_id": tenant_id,
            "process_type": "marketing",
            "platform": "whatsapp",
            "auto_response": False,
            "escalation_rules": json.dumps({
                "after_seconds": 1800,
                "assign_to": "agent",
                "description": (
                    "Pazarlama mesajlarına 30 dakika yanıt yoksa manuel takip gerekir."
                ),
            }),
            "sla_settings": json.dumps({
                "campaign_send_limit_per_day": 200,
                "min_interval_seconds": 3,
                "opt_out_respect": True,
                "description": (
                    "Günlük maksimum 200 kampanya mesajı, mesajlar arası min 3 saniye beklenir. "
                    "Vazgeç listesi her zaman dikkate alınır."
                ),
            }),
            "notification_rules": json.dumps([
                {
                    "event": "campaign_completed",
                    "channels": ["email"],
                    "description": "Kampanya tamamlandığında özet rapor e-posta ile gönderilir.",
                },
                {
                    "event": "high_unsubscribe_rate",
                    "channels": ["whatsapp", "email"],
                    "description": "Abonelik iptali %5'i geçerse uyarı verilir.",
                },
            ]),
        },
    ]


# ──────────────────────────────────────────────────────────────────────────────
# ANA ENTRY POINT
# ──────────────────────────────────────────────────────────────────────────────

async def create_tenant_defaults(tenant_id: int, db: AsyncSession) -> None:
    """
    Yeni tenant için örnek kurallar, iş akışları ve süreç konfigürasyonları oluştur.
    routes_auth._create_tenant_and_user içinden db.flush() sonrasında çağrılır.
    """
    try:
        from models.response_rule import ResponseRule
        from models.tenant_workflow import TenantWorkflow, WorkflowStep, ProcessConfig

        # 1. Kurallar
        for rule_data in _default_rules(tenant_id):
            db.add(ResponseRule(**rule_data))

        # 2. İş akışları + adımlar
        for wf_def in _default_workflows(tenant_id):
            wf = TenantWorkflow(**wf_def["workflow"])
            db.add(wf)
            await db.flush()   # wf.id'yi almak için
            for step_data in wf_def["steps"]:
                db.add(WorkflowStep(workflow_id=wf.id, **step_data))

        # 3. Süreç konfigürasyonları
        for cfg_data in _default_process_configs(tenant_id):
            db.add(ProcessConfig(**cfg_data))

        logger.info("Tenant %s için örnek veriler oluşturuldu.", tenant_id)

    except Exception as e:
        logger.exception("Tenant %s örnek veri oluşturma hatası: %s", tenant_id, e)
        # Kritik değil — tenant yine de oluşsun, sadece log'a düş
