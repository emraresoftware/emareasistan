# Emare Asistan — Teknik Referans

---

## 1. Proje Yapısı

```
asistan/
├── admin/                        # Yönetim paneli
│   ├── common.py                 # Ortak yardımcılar
│   ├── helpers.py                # Admin yardımcı fonksiyonlar
│   ├── partner.py                # Partner deploy (SSH)
│   ├── routes.py                 # Ana admin route'ları
│   ├── routes_agent.py           # Temsilci paneli
│   ├── routes_auth.py            # Login, logout, register
│   ├── routes_dashboard.py       # Dashboard, analytics
│   ├── routes_orders.py          # Sipariş ve kargo
│   ├── routes_partner_super.py   # Partner ve Super Admin
│   ├── routes_rules_workflows.py # Kurallar, iş akışları, AI eğitim
│   ├── routes_settings.py        # Ayarlar
│   └── templates/                # Jinja2 HTML şablonları (~40 dosya)
├── config/
│   └── settings.py               # Pydantic Settings (.env)
├── data/                         # Statik veri (vehicle_models.json vb.)
├── integrations/
│   ├── channels/                 # Kanal soyutlaması
│   │   ├── base.py               # BaseChannel, InboundMessage, ChatResponse
│   │   ├── whatsapp_cloud.py     # WhatsApp Cloud API
│   │   ├── telegram_channel.py   # Telegram
│   │   ├── instagram_channel.py  # Instagram DM
│   │   └── manager.py            # Kanal yöneticisi
│   ├── handlers/                 # Alt handler'lar
│   │   ├── order_handler.py, product_handler.py, cargo_handler.py
│   │   ├── appointment_handler.py, human_handler.py
│   ├── chat_handler.py           # Ana sohbet işleyici
│   ├── cron_api.py               # Zamanlanmış görevler
│   ├── support_chat_api.py       # Panel yardım sohbeti
│   ├── telegram_bot.py           # Telegram webhook
│   ├── web_chat_api.py           # Web sohbet widget API
│   ├── whatsapp_qr.py            # WhatsApp QR Bridge API
│   └── whatsapp_webhook.py       # WhatsApp Cloud webhook
├── middleware/
│   ├── admin_context.py          # Tenant/partner context
│   ├── rate_limit.py             # IP tabanlı rate limiting
│   └── security_headers.py       # Güvenlik header'ları
├── models/                       # SQLAlchemy ORM (~25 dosya)
│   ├── database.py               # Engine, session, init_db
│   ├── tenant.py, user.py, partner.py
│   ├── conversation.py, order.py, product.py
│   └── ...                       # appointment, audit_log, chat_audit vb.
├── services/
│   ├── ai/                       # assistant, embeddings, rag, stt, tts, vision, website_analyzer
│   ├── core/                     # modules, tenant, crypto, state_machine, cache, audit, tracing
│   ├── integration/              # email, sync
│   ├── notifications/            # Bildirim servisi
│   ├── order/                    # service, cargo, payment, abandoned_cart
│   ├── pipeline/                 # Mesaj pipeline
│   ├── product/                  # Ürün servisleri
│   ├── whatsapp/                 # agent, audit, escalation, health
│   ├── workflow/                 # engine, rules, pipeline/, export, proactive
│   └── modules.py                # AVAILABLE_MODULES sarmalayıcı
├── scripts/                      # kivilcim.py, add_docstrings.py, deploy scriptleri
├── tests/                        # conftest.py, test_smoke.py, test_modules.py, test_channels.py
├── whatsapp-bridge/              # Node.js Bridge (index.js, index-multi.js)
├── main.py                       # FastAPI app, middleware, /health
├── run.py                        # API + Bridge başlatma
├── pytest.ini                    # Test yapılandırması
└── requirements.txt              # Python bağımlılıkları
```

---

## 2. Ana Dosyalar

| Dosya | Görev |
|-------|-------|
| `main.py` | FastAPI app, middleware stack, /health |
| `integrations/chat_handler.py` | Platform bağımsız sohbet, AI çağrısı |
| `integrations/channels/base.py` | BaseChannel, InboundMessage, ChatResponse |
| `integrations/whatsapp_qr.py` | QR Bridge API, sesli mesaj, TTS |
| `integrations/web_chat_api.py` | Web sohbet widget API |
| `integrations/support_chat_api.py` | Panel yardım sohbeti |
| `services/ai/assistant.py` | AI Asistan (Gemini/OpenAI) |
| `services/ai/stt.py` | Sesli mesaj → metin |
| `services/ai/tts.py` | Metin → ses |
| `services/ai/vision.py` | Resimden ürün eşleştirme |
| `services/core/modules.py` | 56 modül tanımı |
| `services/core/crypto.py` | API key şifreleme/çözme |
| `services/order/cargo.py` | Kargo takip |
| `services/workflow/engine.py` | İş akışı çalıştırıcı |
| `services/workflow/rules.py` | Kural motoru (RuleEngine) |
| `middleware/rate_limit.py` | Rate limiting |
| `middleware/security_headers.py` | Güvenlik header'ları |
| `middleware/admin_context.py` | Tenant/partner bağlamı |
| `admin/partner.py` | Partner remote deploy (3 SSH yöntemi) |
| `whatsapp-bridge/index.js` | Node.js Bridge: kuyruğu, retry, heartbeat |

---

## 3. Veritabanı Modelleri

### Temel Modeller

**Tenant:** `id`, `name`, `slug`, `website_url`, `sector`, `status`, `enabled_modules` (JSON), `settings` (JSON — ai_response_rules, quick_reply_options, branding_*, welcome_scenarios)

**Partner:** `id`, `name`, `slug`, `admin_user_id`, `settings` (JSON — default_tenant_id, branding_logo_url)

**User:** `id`, `tenant_id`, `name`, `email`, `password_hash`, `role` (admin/user/agent), `partner_id`, `is_partner_admin`, `last_login`, `last_seen`

### Sohbet Modelleri

**Conversation:** `tenant_id`, `platform`, `platform_user_id`, `customer_name`, `agent_took_over`, `csat_rating`

**Message:** `role` (user/assistant), `content`, `extra_data`, `platform`

### İş Modelleri

**Order:** `tenant_id`, `order_number`, `customer_*`, `items` (JSON), `cargo_tracking_no`, `cargo_company`, `status`

**Product:** `tenant_id`, `name`, `price`, `image_urls`, `vehicle_models`, `trigger_keyword`

**ImageAlbum, Video:** Araç modeli eşleştirmeli resim/video

**ResponseRule:** `trigger_keyword`, `response_text`, `product_ids`, `image_urls`

**AITrainingExample:** `question`, `expected_answer`, `embedding` (vector)

**Appointment:** `tenant_id`, `customer_name`, `customer_phone`, `date`, `time_slot`, `status`

### Yardımcı Modeller

- **AuditLog, ChatAudit, MessageFeedback** — Denetim, kalite kontrolü, geri bildirim
- **LeaveRequest, Invoice, PurchaseOrder** — İdari işler
- **ExportTemplate, TenantWorkflow, WhatsAppConnection** — Veri aktarımı, iş akışları, bağlantılar

Detay: `models/` klasörü (25+ dosya)

---

## 4. Entegrasyon Mimarisi

### Katmanlı Mimari

```
Gelen Mesaj → Webhook → InboundMessage → ChatHandler → AI/Kurallar → ChatResponse → BaseChannel → Platform API
```

### Mevcut Kanallar

| Kanal | Dosya | Durum |
|-------|-------|-------|
| WhatsApp (QR) | `integrations/whatsapp_qr.py` | ✅ |
| WhatsApp Cloud | `integrations/channels/whatsapp_cloud.py` | ✅ |
| Telegram | `integrations/channels/telegram_channel.py` | ✅ |
| Instagram DM | `integrations/channels/instagram_channel.py` | ✅ |
| Web Sohbet | `integrations/web_chat_api.py` | ✅ |
| Panel Yardım | `integrations/support_chat_api.py` | ✅ |

### Yeni Kanal Ekleme (Özet)

1. `integrations/channels/` altında `BaseChannel`'dan türetme
2. `platform_id` property, `send_text()`, `send_image()` implementasyonu
3. Webhook endpoint oluşturma (`integrations/`)
4. `services/modules.py`'ye modül ekleme
5. `main.py`'ye router dahil etme
6. Admin panel menüsüne ekleme

**InboundMessage alanları:** `platform`, `user_id`, `message_text`, `customer_name`, `customer_phone`, `image_base64`, `image_mimetype`, `replied_to_caption`, `tenant_id`, `raw`

**ChatResponse alanları:** `text`, `image_url`, `image_caption`, `product_images`, `location`, `suggested_products`

---

## 5. Güvenlik

### Middleware Stack

```
İstek → SecurityHeadersMiddleware → RateLimitMiddleware → admin_context → SessionMiddleware → Route
```

### Rate Limiting

| Endpoint | Limit |
|----------|-------|
| `/admin/login` (POST) | 10/dakika |
| `/webhook/*` | 300/dakika |
| `/process` | 30/dakika |
| Genel | 120/dakika |

### Güvenlik Header'ları

- `X-Frame-Options: SAMEORIGIN`
- `X-Content-Type-Options: nosniff`
- `X-XSS-Protection: 1; mode=block`
- `Referrer-Policy: strict-origin-when-cross-origin`
- `Permissions-Policy: camera=(), microphone=(), geolocation=()`
- `Strict-Transport-Security` — HTTPS'de otomatik

### API Key Şifreleme

API anahtarları veritabanında AES ile şifreli saklanır (`services/core/crypto.py`, `SECRET_KEY` env).

### Auth

- Session tabanlı (itsdangerous), bcrypt parola hash
- Super Admin / Partner Admin / Tenant Admin rol hiyerarşisi
- Tüm admin endpoint'ler oturum kontrolü gerektirir

### Sunucu Güvenliği

| Önlem | Açıklama |
|-------|----------|
| `.env` deploy etmemek | Gizliler rsync'te yok, sunucuda elle oluşturulur |
| `chmod 600 .env`, `chmod 750` dizin | Sadece yetkili kullanıcı okur |
| Ayrı kullanıcı ile çalıştırma | `User=asistan` ile root izolasyonu |
| PyArmor (opsiyonel) | Python kaynak obfuscation |
| JS obfuscator (opsiyonel) | Bridge kaynak obfuscation |

---

## 6. Migration & Docker

### Alembic

```bash
alembic upgrade head        # Yeni kurulum
alembic stamp 001 && alembic upgrade head  # Mevcut SQLite
```

### PostgreSQL + pgvector

```bash
# Ubuntu: sudo apt install postgresql-16-pgvector
# macOS: brew install pgvector
```

### Docker

```bash
cp .env.example .env
docker compose up -d
docker compose exec api python -m alembic upgrade head
```

Servisler: api (8000), postgres (5432), redis (6379)

---

## 7. Test

```bash
.venv/bin/python3 -m pytest tests/ -v      # Tüm testler
.venv/bin/python3 -m pytest tests/test_smoke.py -v  # Smoke testler
```

| Dosya | İçerik | Test Sayısı |
|-------|--------|-------------|
| `tests/conftest.py` | Fixture'lar (db_session, test_client) | — |
| `tests/test_smoke.py` | Import, health, redirect, security headers | 13 |
| `tests/test_modules.py` | Modül yapısı, benzersizlik, temel modüller | 6 |
| `tests/test_channels.py` | InboundMessage, ChatResponse dataclass'ları | 8 |

---

## 8. Kıvılcım (Kod Tarayıcı)

```bash
python scripts/kivilcim.py                    # Tam tarama
python scripts/kivilcim.py --task docstrings  # Belirli görev
python scripts/kivilcim.py --task secrets
python scripts/kivilcim.py --task endpoints
```

Tarama sonuçları: `KIVILCIM_RAPOR.md`

Görevler: TODO/FIXME, hardcoded secret, endpoint listesi, env değişkenleri, docstring eksikleri, auth kontrolü

---

*Son güncelleme: Şubat 2026*
