# Emare Asistan — Yazılım Hafıza Belgesi

> **Son Güncelleme:** 3 Mart 2026  
> **Amaç:** Bu belge, Emare Asistan projesinin tüm teknik detaylarını, mimarisini, mevcut durumunu ve nerede kaldığımızı kayıt altına alır. Yeni bir oturumda devam ederken bu dosyayı referans alın.

---

## 1. PROJE NEDİR?

**Emare Asistan**, çok kiracılı (multi-tenant) bir SaaS AI müşteri hizmetleri platformudur. Firmalar bu platform üzerinden WhatsApp, Telegram, Instagram ve web sohbet kanallarından gelen müşteri mesajlarını yapay zeka ile otomatik yanıtlar. Sipariş alma, kargo takibi, ürün önerisi, randevu, temsilci devralma gibi iş süreçlerini yönetir.

**Kurucu / Geliştirici:** Emre  
**Firma:** Emare (emareas.com / emareasistan.com)

---

## 2. SUNUCU & DEPLOY BİLGİLERİ

| Bilgi | Değer |
|-------|-------|
| **Sunucu IP** | `77.92.152.3` |
| **SSH Kullanıcı** | `root` |
| **SSH Şifre** | `Emre2025*` |
| **İşletim Sistemi** | Ubuntu 24.04 |
| **Proje Dizini (sunucu)** | `/opt/asistan/` |
| **Python venv (sunucu)** | `/opt/asistan/venv/` (`.venv` DEĞİL!) |
| **Lokal Geliştirme** | `/Users/emre/Desktop/asistan` (macOS) |
| **Lokal Python** | 3.11.14, `.venv/` |
| **Domain** | `emareasistan.com` |
| **API URL (sunucu)** | `http://77.92.152.3:8000` |
| **Admin Panel** | `http://77.92.152.3:8000/admin` |
| **Super Admin E-posta** | `emre@emareas.com` |
| **Super Admin Şifre** | `3673` |

### 2.1 Servisler (Sunucu)

| Servis | Teknoloji | Port | Yönetim |
|--------|-----------|------|---------|
| **Python API** | FastAPI + Uvicorn | 8000 | `systemctl restart asistan-api` |
| **WhatsApp Bridge** | Node.js (systemd) | 3100 | `systemctl restart asistan-whatsapp` |

- **Güncel kalıcı çalışma modu:** `asistan-whatsapp` systemd servisi
- Docker bridge dosyaları yedek/alternatif olarak repo içinde tutuluyor

### 2.2 Deploy Akışı

```bash
# SSHPASS ayarla
export SSHPASS='Emre2025*'

# --- Python API deploy ---
sshpass -e scp -o StrictHostKeyChecking=no dosya.py root@77.92.152.3:/opt/asistan/dosya.py
sshpass -e ssh -o StrictHostKeyChecking=no root@77.92.152.3 "systemctl restart asistan-api"

# --- WhatsApp Bridge deploy ---
# JS bind-mount edildiği için sadece dosya yükle + restart (rebuild gereksiz)
sshpass -e scp -o StrictHostKeyChecking=no whatsapp-bridge/index-multi.js root@77.92.152.3:/opt/asistan/whatsapp-bridge/index-multi.js
sshpass -e ssh -o StrictHostKeyChecking=no root@77.92.152.3 "cd /opt/asistan && docker compose -f docker-compose.bridge.yml restart"

# --- Dockerfile/package.json değişikliği varsa rebuild ---
sshpass -e ssh -o StrictHostKeyChecking=no root@77.92.152.3 "cd /opt/asistan && docker compose -f docker-compose.bridge.yml up -d --build"
```

### 2.3 WhatsApp Stabilizasyon (9 Mart 2026)

- Kök neden: aynı anda hem manuel `node index-multi.js` hem de `asistan-whatsapp` servisi çalışınca `3100` port çakışması (`EADDRINUSE`) oluştu.
- Yeni operasyon kuralı: WhatsApp Bridge **tek sahipli** çalıştırılır (tercih: systemd servisi).
- Kalıcı koruma (servis şablonuna eklendi):
  - `ExecStartPre`: eski `index-multi.js` süreçlerini temizler
  - `ExecStartPre`: `fuser -k 3100/tcp` ile portu serbestler
  - `Restart=always`, `RestartSec=5`
- Ek kök neden/fix (9 Mart 2026): `pkill -f` deseninin kontrol sürecini öldürmesiyle systemd `signal/TERM` hatasına düşüldü. Çözüm olarak shell tabanlı pre-start yerine güvenli systemd komutları (`-/usr/bin/pkill -f [n]ode.*index-multi.js`) kullanıldı.
- Manuel `npm start` sadece arıza anında kısa teşhis için; kalıcı çalışma modu değildir.

---

## 3. TEKNOLOJİ STACK'İ

### 3.1 Backend (Python)

| Bileşen | Teknoloji |
|---------|-----------|
| **Framework** | FastAPI |
| **ASGI Server** | Uvicorn |
| **ORM** | SQLAlchemy 2.0 (async) |
| **Veritabanı** | SQLite (varsayılan) / PostgreSQL + pgvector (opsiyonel) |
| **Migration** | Alembic (22 migration dosyası mevcut) |
| **Template Engine** | Jinja2 |
| **Frontend (Admin)** | Alpine.js + TailwindCSS (CDN) |
| **Session** | Starlette SessionMiddleware |
| **Arka Plan İşleri** | Celery + Redis (opsiyonel) |
| **AI** | Google Gemini (birincil), OpenAI (yedek) |
| **AI Modeli** | `gemini-2.5-flash-lite` |
| **Gemini API Key** | `AIzaSyCfrVLGK3LE4F7rMA-7Q27HLH5pNZL53i8` |
| **Lokal LLM** | Qwen2.5-0.5B-Instruct + LoRA (fallback) |
| **Cache** | Redis (opsiyonel, yoksa in-memory) |

### 3.2 WhatsApp Bridge (Node.js)

| Bileşen | Teknoloji |
|---------|-----------|
| **Runtime** | Node.js 18 (Docker container içinde) |
| **Kütüphane** | whatsapp-web.js v1.25 |
| **Browser** | Chromium (Docker gömülü, `/usr/bin/chromium`) |
| **PID Manager** | dumb-init (zombie process önleme) |
| **Container** | `emare-whatsapp-bridge` |
| **Ana Dosya** | `whatsapp-bridge/index-multi.js` (~818 satır) |

### 3.3 Docker Ayarları (Bridge)

```yaml
# docker-compose.bridge.yml
network_mode: host              # localhost:8000'e doğrudan erişim
shm_size: 256m                  # Chrome shared memory
memory limit: 1536M             # RAM limiti
cpu limit: 2 core               # CPU limiti
LAZY_LOADING: true              # Sadece auth dosyası olan bağlantılar Chrome başlatır
MAX_CONCURRENT_CHROME: 3        # Aynı anda max 3 Chrome instance
AUTH_BASE_DIR: /app/auth_data   # Auth dizini (host: ./whatsapp-bridge)
```

---

## 4. MİMARİ YAPI

### 4.1 Dizin Yapısı

```
asistan/
├── main.py                      # FastAPI app oluşturma, router'lar, middleware
├── run.py                       # Tek komutla API + Bridge başlatma (lokal geliştirme)
├── config/settings.py           # Pydantic Settings (.env okuma)
├── celery_app.py                # Celery yapılandırması
├── tasks.py                     # Celery görevleri (abandoned cart, proactive msg)
│
├── models/                      # SQLAlchemy modelleri
│   ├── database.py              # Engine, session, init_db, migration
│   ├── tenant.py                # Tenant (firma) - multi-tenant çekirdek
│   ├── partner.py               # Partner (alt marka, ör. Piramit Bilgisayar)
│   ├── user.py                  # Panel kullanıcıları (admin, agent)
│   ├── conversation.py          # Sohbet + ChatMessage
│   ├── order.py                 # Sipariş (state machine ile)
│   ├── product.py               # Ürün + Kategori
│   ├── whatsapp_connection.py   # WhatsApp hesap bağlantıları (QR)
│   ├── response_rule.py         # Kural motoru kuralları
│   ├── ai_training.py           # AI eğitim örnekleri (soru-cevap)
│   ├── tenant_workflow.py       # İş akışları (Trigger→Condition→Action)
│   ├── contact.py               # Müşteri kişi kartları
│   ├── reminder.py              # Hatırlatıcılar
│   ├── appointment.py           # Randevular
│   ├── image_album.py           # Resim albümleri
│   ├── video.py                 # Video yönetimi
│   ├── embedding.py             # Vector store (pgvector)
│   ├── audit_log.py             # Denetim günlüğü
│   ├── chat_audit.py            # Sohbet kalite denetimi
│   ├── message_feedback.py      # Mesaj geri bildirimi
│   ├── invoice.py               # Fatura
│   ├── leave_request.py         # İzin talepleri
│   ├── purchase_order.py        # Satın alma siparişleri
│   ├── export_template.py       # Veri aktarım şablonları
│   ├── quick_reply.py           # Hızlı yanıt şablonları
│   ├── tenant_setting.py        # Tenant ayarları
│   └── pending_registration.py  # Bekleyen kayıtlar
│
├── services/                    # İş mantığı servisleri
│   ├── ai/
│   │   ├── assistant.py         # Ana AI asistanı (Gemini/OpenAI, sistem prompt)
│   │   ├── embeddings.py        # Metin vektörleştirme (OpenAI, 1536 dim)
│   │   ├── vector_store.py      # pgvector ile semantik arama
│   │   ├── rag.py               # Dokuman tabanlı RAG (docs/*.md)
│   │   ├── stt.py               # Speech-to-Text (sesli mesaj→metin, Gemini)
│   │   ├── tts.py               # Text-to-Speech (metin→ses, OpenAI)
│   │   ├── vision.py            # Resim→ürün eşleştirme (Gemini Vision)
│   │   ├── ocr.py               # Plaka/ruhsat/VIN OCR (Gemini Vision)
│   │   ├── indexer.py           # Embedding indeksleme
│   │   └── website_analyzer.py  # Web sitesi analizi
│   ├── core/
│   │   ├── state_machine.py     # OrderStateMachine (INIT→...→CONFIRMED)
│   │   ├── tenant.py            # Tenant ayar okuma
│   │   ├── tenant_settings.py   # Tenant ayar yönetimi
│   │   ├── modules.py           # Modül sistemi
│   │   ├── module_config.py     # Modül yapılandırması
│   │   ├── settings.py          # Genel ayar servisi
│   │   ├── audit.py             # Denetim log servisi
│   │   ├── cache.py             # Cache yönetimi (Redis/memory)
│   │   ├── crypto.py            # Şifreleme (API anahtarları)
│   │   ├── tracing.py           # İstek izleme
│   │   └── time_utils.py        # Türkiye saati yardımcıları
│   ├── order/
│   │   ├── service.py           # OrderService (CRUD)
│   │   ├── cargo.py             # CargoService (kargo takibi)
│   │   ├── payment.py           # Ödeme (Iyzico)
│   │   └── abandoned_cart.py    # Terk edilen sepet hatırlatması
│   ├── product/
│   │   ├── service.py           # ProductService (CRUD)
│   │   ├── importer.py          # Ürün import
│   │   └── vehicles.py          # Araç modeli → ürün eşleştirme
│   ├── workflow/
│   │   ├── engine.py            # Workflow Engine (Trigger→Condition→Action)
│   │   ├── rules.py             # RuleEngine (anahtar kelime→ürün)
│   │   ├── service.py           # Workflow CRUD
│   │   ├── proactive.py         # Proaktif mesajlaşma
│   │   ├── metrics.py           # Chat response metrikleri
│   │   ├── export.py            # Veri aktarım
│   │   └── export_trigger.py    # Aktarım tetikleyici
│   ├── trendyol/
│   │   ├── api.py               # Trendyol Seller API istemcisi
│   │   ├── questions.py         # Trendyol soru işleme (kategorize, AI yanıt)
│   │   └── sync.py              # Trendyol senkronizasyon (soru çek/yanıtla)
│   ├── whatsapp/
│   │   ├── agent.py             # Temsilci mesaj gönderimi (Bridge/Cloud API)
│   │   ├── audit.py             # Sohbet kalite denetimi
│   │   ├── escalation.py        # Eskalasyon yönetimi
│   │   └── health.py            # Bridge sağlık kontrolü
│   ├── appointment/service.py   # Randevu servisi
│   ├── integration/
│   │   ├── email.py             # E-posta gönderimi
│   │   └── sync.py              # Genel senkronizasyon
│   ├── notifications/
│   │   └── user_notifier.py     # Kullanıcı bildirimleri
│   └── modules.py               # AVAILABLE_MODULES listesi (56 modül)
│
├── integrations/                # Platform entegrasyonları (Webhook + Handler)
│   ├── chat_handler.py          # Ana sohbet işleyici (~1928 satır, platform bağımsız)
│   ├── whatsapp_qr.py           # WhatsApp QR Bridge → /api/whatsapp/process
│   ├── whatsapp_webhook.py      # WhatsApp Cloud API webhook
│   ├── telegram_bot.py          # Telegram bot handler
│   ├── instagram_webhook.py     # Instagram DM webhook (Meta Graph API)
│   ├── web_chat_api.py          # Web sohbet API (/api/chat/web)
│   ├── support_chat_api.py      # Panel yardım sohbeti (/api/chat/support)
│   ├── bridge_api.py            # Bridge internal API (/api/bridge/connections)
│   ├── cron_api.py              # Cron endpoint'leri
│   ├── channels/                # Kanal abstraction layer
│   │   ├── base.py              # Temel kanal sınıfı
│   │   ├── manager.py           # Kanal yöneticisi
│   │   ├── whatsapp_cloud.py    # WhatsApp Cloud implementasyonu
│   │   ├── telegram_channel.py  # Telegram implementasyonu
│   │   └── instagram_channel.py # Instagram implementasyonu
│   └── handlers/                # İş mantığı handler'ları
│       ├── human_handler.py     # İnsan temsilciye devretme
│       ├── order_handler.py     # Sipariş akışı
│       ├── product_handler.py   # Ürün önerisi
│       ├── cargo_handler.py     # Kargo takibi
│       └── appointment_handler.py # Randevu
│
├── admin/                       # Yönetim paneli
│   ├── routes.py                # Ana admin router (~2313 satır)
│   ├── routes_auth.py           # Kimlik doğrulama (login, register, partner login)
│   ├── routes_dashboard.py      # Dashboard & analitik
│   ├── routes_settings.py       # Ayarlar sayfaları
│   ├── routes_rules_workflows.py# Kurallar & iş akışları
│   ├── routes_orders.py         # Sipariş yönetimi
│   ├── routes_agent.py          # Temsilci paneli (canlı devralma)
│   ├── routes_partner_super.py  # Partner & super admin paneli
│   ├── routes_trendyol.py       # Trendyol yönetim sayfaları
│   ├── common.py                # Ortak yardımcılar
│   ├── helpers.py               # Admin yardımcı fonksiyonları
│   ├── partner.py               # Partner router
│   └── templates/               # 65+ Jinja2 HTML template
│
├── middleware/
│   ├── admin_context.py         # Tenant çözümleme (session→DB, izolasyon)
│   ├── rate_limit.py            # IP bazlı rate limiting
│   └── security_headers.py      # Güvenlik header'ları
│
├── whatsapp-bridge/             # Node.js WhatsApp Bridge
│   ├── Dockerfile               # Docker image (Chromium gömülü)
│   ├── index-multi.js           # Ana bridge kodu (~818 satır)
│   ├── index.js                 # Tek bağlantı versiyonu (yedek)
│   ├── package.json             # Node.js bağımlılıkları
│   └── .wwebjs_auth_*/          # WhatsApp auth dosyaları (35 dizin, ~3.5GB)
│
├── docker-compose.bridge.yml   # Bridge-only Docker Compose (KULLANILAN)
├── docker-compose.yml          # Full-stack Docker Compose (production hazırlığı)
├── Dockerfile                  # Python API Docker image
├── alembic.ini                 # Alembic yapılandırması
├── alembic/versions/           # 22 migration dosyası
├── data/                       # JSON veri dosyaları
│   ├── app_settings.json
│   ├── products_sample.json
│   ├── vehicle_models.json
│   ├── quick_replies.json
│   └── tenants/                # Tenant bazlı veri dosyaları
├── static/
│   ├── index.html              # Landing page (emareasistan.com)
│   └── scenarios/              # Senaryo kartı görselleri (6 PNG)
├── uploads/                    # Yüklenen dosyalar
├── scripts/                    # Yardımcı scriptler (29 dosya)
│   ├── generate_scenario_images.py  # Senaryo kartı oluşturucu (Pillow)
│   ├── local_llm/              # Lokal LLM eğitim/çalıştırma
│   └── ...
├── docs/                       # Dokümantasyon (RAG kaynağı olarak da kullanılır)
│   ├── 00_INDEX.md ... 05_OPERASYON.md
│   └── KULLANIM_KILAVUZU.md, EMARE_ASISTAN_YETENEKLERI.md vb.
└── tests/                      # Pytest testleri
```

### 4.2 Mesaj Akışı (WhatsApp QR Bridge)

```
Müşteri WhatsApp Mesajı
    ↓
[WhatsApp Sunucuları]
    ↓
[whatsapp-bridge/index-multi.js] (Docker container, port 3100)
  - whatsapp-web.js ile mesaj alır
  - Grup mesajı: @emareasistan mention kontrolü
  - POST /api/whatsapp/process'a gönderir
    ↓
[integrations/whatsapp_qr.py] → ProcessRequest
  - connection_id → tenant_id eşleşmesi
  - Sesli mesaj → STT (Gemini)
  - Resim → Vision AI
    ↓
[integrations/chat_handler.py] → ChatHandler.process_message()
  - Workflow Engine çalıştır
  - Rule Engine: anahtar kelime → ürün eşleştirme
  - AI Assistant: Gemini ile yanıt üret
  - Sipariş akışı (OrderStateMachine)
  - Kargo takibi
  - Randevu
    ↓
JSON yanıt → Bridge'e döner
    ↓
[Bridge] → Müşteriye WhatsApp mesajı/resim gönderir
```

### 4.3 Multi-Tenant & Partner Mimarisi

```
Platform (Emare Asistan)
  └── Partner (ör. Defence 360, Piramit Bilgisayar)
       └── Tenant (ör. Meridyen Oto, Kozmo Mağaza)
            ├── Users (admin, agent)
            ├── WhatsApp Connections
            ├── Products, Orders, Conversations
            ├── Rules, Workflows
            └── Settings (AI prompt, API keys, modules)
```

- **Super Admin**: Platform sahibi (emre@emareas.com), tüm tenant/partner erişimi
- **Partner Admin**: Kendi tenant'larını yönetir (giriş: `/admin/p/{partner-slug}`)
- **Tenant Admin/Agent**: Bir firmaya bağlı kullanıcı (giriş: `/admin/t/{firma-slug}` veya `/admin`)

### 4.4 Modül Sistemi

56 modül tanımlı, tenant bazlı açılıp kapanabilir. Temel modüller:

| Kategori | Modüller |
|----------|---------|
| **Sohbet** | whatsapp, web_chat, telegram, quick_replies, agent, conversations, contacts, appointments |
| **AI & Otomasyon** | rules, workflows, training, reminders, analytics, crm, reports |
| **Pazaryerleri** | products, albums, videos, trendyol, hepsiburada, amazon, shopify, export_templates |
| **Sosyal Medya** | instagram, facebook, twitter, tiktok, linkedin |
| **Ödemeler** | orders, payment (Iyzico), stripe, paypal, billing, subscriptions |
| **Kargo** | cargo, yurtici, aras, mng, ups, dhl, ptt |

---

## 5. AI SİSTEMİ

### 5.1 Ana AI Asistanı (`services/ai/assistant.py`)

- **Birincil:** Google Gemini (`gemini-2.5-flash-lite`) - httpx ile doğrudan REST API
- **Yedek:** OpenAI GPT - openai kütüphanesi
- **Lokal Fallback:** Qwen2.5-0.5B-Instruct + LoRA adapter (API çöktüğünde devreye girer)
- **Sistem Prompt:** Tenant adı ve telefonu ile dinamik olarak oluşturulur
- **JSON Çıktı:** AI yanıtı JSON formatında döner → `reply`, `send_image`, `image_url`, `suggested_products`, `create_order`, `create_appointment` vb.

### 5.2 Özel AI Yetenekleri

| Yetenek | Servis | Açıklama |
|---------|--------|----------|
| **Sesli Mesaj** | `ai/stt.py` | Gemini ile ses→metin (fallback: OpenAI Whisper) |
| **Sesli Yanıt** | `ai/tts.py` | OpenAI TTS ile metin→ses |
| **Resim Tanıma** | `ai/vision.py` | Gemini Vision ile ürün eşleştirme |
| **OCR** | `ai/ocr.py` | Plaka/ruhsat/VIN metin çıkarma |
| **RAG** | `ai/rag.py` | docs/*.md dosyalarından bilgi çekme |
| **Embedding** | `ai/embeddings.py` | OpenAI text-embedding-3-small (1536 dim) |
| **Vector Store** | `ai/vector_store.py` | pgvector ile semantik arama |

### 5.3 Kural Motoru (`services/workflow/rules.py`)

- ResponseRule tablosundan tenant bazlı kurallar
- Anahtar kelime eşleşmesi → ürün/resim listesi döndürme
- Öncelik sırasına göre ilk eşleşen kural
- Örnek: "paspas" → belirli ürünlerin resimleri gönderilir

### 5.4 Workflow Engine (`services/workflow/engine.py`)

- Trigger → Condition → Action yapısı
- Platform bazlı (WhatsApp, Telegram vb.)
- Admin panelinden görsel builder ile oluşturulabilir

---

## 6. WHATSAPP BRIDGE DETAYLARI

### 6.1 Genel

- **Dosya:** `whatsapp-bridge/index-multi.js` (~818 satır)
- Multi-account: 10 bağlantı kayıtlı, sadece auth dosyası olanlar Chrome başlatır
- `MAX_CONCURRENT_CHROME=3`: Aynı anda en fazla 3 Chrome instance
- Bağlantı [34] aktif ve çalışıyor ("Bağlandı")

### 6.2 Önemli Mekanizmalar

- **Lazy Loading:** `LAZY_LOADING=true` - Auth dosyası olmayan bağlantılar Chrome başlatmaz
- **Priority Sort:** `fallback_phone` alanı dolu olanlar önce başlar
- **Chrome Lock Temizliği:** `cleanChromeLocks()` - başlangıçta SingletonLock/Socket/Cookie dosyalarını temizler
- **Fire-and-forget init:** `client.initialize()` await edilmez, arka planda çalışır
- **3 saniyelik gecikme:** Chrome başlatımları arasında 3 saniye beklenir

### 6.3 Grup Mesajları

- **Tetikleme:** Sadece `@emareasistan` veya `@emare asistan` (@ prefix zorunlu)
- Bare text "emareasistan" trigger etmez (false positive düzeltildi)
- Grup debug logları: `📩 from=... remote=... author=... isGroup=...` ve `🔇 Grup mesajı ignore: "..." (mention yok)`
- Grup mesajında gönderen numarası `sender` alanında gelir
- Grup sohbet ID: `group_{jid}` formatında (tüm mesajlar aynı conversation'da)
- Grup AI yanıtı: kısa ve profesyonel ton

### 6.4 Bridge → API İletişimi

```
Bridge HTTP POST → http://127.0.0.1:8000/api/whatsapp/process
Body: { from, text, connection_id, is_group, group_name, sender, audio_base64, image_base64, ... }
Response: { reply, images, audio, ... }
```

### 6.5 Docker Komutları

```bash
# Loglar
docker compose -f docker-compose.bridge.yml logs -f

# Restart (kod güncellemesi sonrası)
docker compose -f docker-compose.bridge.yml restart

# Rebuild (Dockerfile değişikliği)
docker compose -f docker-compose.bridge.yml up -d --build

# Durdur
docker compose -f docker-compose.bridge.yml down

# Container durumu
docker ps --format "table {{.Names}}\t{{.Status}}"
docker stats emare-whatsapp-bridge --no-stream
```

---

## 7. VERİTABANI

### 7.1 Kullanılan DB

- **Geliştirme/Sunucu:** SQLite (`asistan.db`)
- **Production hazırlığı:** PostgreSQL + pgvector (docker-compose.yml'de tanımlı)

### 7.2 Tablolar (28 model)

| Tablo | Model | Açıklama |
|-------|-------|----------|
| `tenants` | Tenant | Firma/organizasyon |
| `partners` | Partner | Alt marka (Defence 360 vb.) |
| `users` | User | Panel kullanıcıları (admin, agent) |
| `conversations` | Conversation | Sohbet oturumları |
| `messages` | ChatMessage | Sohbet mesajları |
| `orders` | Order | Siparişler (state machine) |
| `products` | Product | Ürünler |
| `product_categories` | ProductCategory | Ürün kategorileri |
| `whatsapp_connections` | WhatsAppConnection | WhatsApp QR bağlantıları |
| `response_rules` | ResponseRule | Kural motoru kuralları |
| `ai_training_examples` | AITrainingExample | AI eğitim verileri |
| `tenant_workflows` | TenantWorkflow | İş akışları |
| `workflow_steps` | WorkflowStep | İş akışı adımları |
| `process_configs` | ProcessConfig | Süreç yapılandırmaları |
| `contacts` | Contact | Müşteri kişi kartları |
| `reminders` | Reminder | Hatırlatıcılar |
| `appointments` | Appointment | Randevular |
| `image_albums` | ImageAlbum | Resim albümleri |
| `videos` | Video | Videolar |
| `embeddings` | Embedding | Vector store (pgvector) |
| `audit_logs` | AuditLog | Denetim günlüğü |
| `chat_audits` | ChatAudit | Sohbet kalite denetimi |
| `message_feedbacks` | MessageFeedback | Mesaj geri bildirimi |
| `invoices` | Invoice | Faturalar |
| `leave_requests` | LeaveRequest | İzin talepleri |
| `purchase_orders` | PurchaseOrder | Satın alma siparişleri |
| `export_templates` | ExportTemplate | Veri aktarım şablonları |
| `quick_replies` | QuickReply | Hızlı yanıt şablonları |
| `tenant_settings` | TenantSetting | Tenant bazlı ayarlar |
| `pending_registrations` | PendingRegistration | Onay bekleyen kayıtlar |

### 7.3 Sipariş State Machine

```
INIT → PRODUCT_SELECTED → CUSTOMER_INFO → ADDRESS → PAYMENT → CONFIRMED
```

Conversation.order_draft alanında JSON olarak saklanır.

---

## 8. ADMIN PANELİ

### 8.1 Template'ler (65+)

Admin paneli Jinja2 + Alpine.js + TailwindCSS ile render edilir.

| Sayfa | URL | Template |
|-------|-----|----------|
| Dashboard | `/admin/dashboard` | `dashboard.html` |
| Sohbetler | `/admin/conversations` | `conversations.html` |
| Sohbet Detay | `/admin/conversations/{id}` | `conversation_detail.html` |
| Siparişler | `/admin/orders` | `orders.html` |
| Sipariş Detay | `/admin/orders/{id}` | `order_detail.html` |
| Ürünler | `/admin/products` | `products.html` |
| Ürün Galerisi | `/admin/products/gallery` | `products_gallery.html` |
| Kurallar | `/admin/rules` | `rules.html` |
| İş Akışları | `/admin/workflows` | `workflows_list.html` |
| AI Eğitim | `/admin/training` | `training_list.html` |
| WhatsApp | `/admin/whatsapp` | `whatsapp_list.html` |
| Temsilci Panel | `/admin/agent` | `agent_panel.html` / `agent_chat.html` |
| Kişiler | `/admin/contacts` | `contacts_list.html` |
| Hatırlatıcılar | `/admin/reminders` | `reminders_list.html` |
| Randevular | `/admin/appointments` | `appointments_list.html` |
| İstatistikler | `/admin/analytics` | `analytics.html` |
| Hızlı Yanıtlar | `/admin/quick-replies` | `quick_replies.html` |
| Ayarlar | `/admin/settings` | `settings_index.html` ve alt sayfalar |
| Trendyol | `/admin/trendyol` | `trendyol_dashboard.html` |
| Kargo | `/admin/cargo` | `cargo_list.html` |
| Albümler | `/admin/albums` | `albums.html` |
| Videolar | `/admin/videos` | `videos_list.html` |
| Kullanıcılar | `/admin/users` | `users_list.html` |
| Super Admin | `/admin/super` | `super_admin.html` |
| Partner Panel | `/admin/partner` | `partner_panel.html` |

### 8.2 Giriş Yöntemleri

- **Super Admin:** `/admin` → e-posta boş + şifre "3673"
- **Firma Admin:** `/admin/t/{firma-slug}` → e-posta + şifre  
- **Partner Admin:** `/admin/p/{partner-slug}` → e-posta + şifre

---

## 9. TRENDYOL ENTEGRASYONU

### 9.1 Genel

Trendyol Seller API entegrasyonu, tenant bazlı çalışır.

| Dosya | İşlev |
|-------|-------|
| `services/trendyol/api.py` | Trendyol Seller API istemcisi (GET/POST) |
| `services/trendyol/questions.py` | Soru işleme zinciri (kategorize, bulanık eşleştirme, Gemini AI) |
| `services/trendyol/sync.py` | Periyodik senkronizasyon (soru çek, yanıtla, sipariş çek) |
| `admin/routes_trendyol.py` | Admin panel Trendyol sayfaları |

### 9.2 Soru Kategorileri

- 📦 Kargo/Teslimat
- ↩️ İade/Para İade
- 🛍️ Ürün Bilgisi
- 📅 Son Kullanma Tarihi
- 💰 Fiyat/İndirim
- ❓ Diğer

### 9.3 API Yapılandırması

Tenant ayarlarında saklanır:
- `trendyol_seller_id`
- `trendyol_api_key`
- `trendyol_api_secret`
- `trendyol_supplier_id`

---

## 10. MIDDLEWARE & GÜVENLİK

| Middleware | Dosya | İşlev |
|-----------|-------|-------|
| **SessionMiddleware** | Starlette | Admin oturum yönetimi |
| **AdminContextMiddleware** | `middleware/admin_context.py` | Tenant çözümleme, izolasyon |
| **RateLimitMiddleware** | `middleware/rate_limit.py` | IP bazlı istek limiti |
| **SecurityHeadersMiddleware** | `middleware/security_headers.py` | Güvenlik header'ları |
| **CORSMiddleware** | FastAPI | Web sohbet için CORS (allow_origins=*) |

**Rate Limits:**
- `/webhook/whatsapp`: 120/dk
- `/admin/login`: 10/dk
- `/admin/register`: 5/dk
- `/api/whatsapp/process`: 30/dk
- Genel: 100/dk

---

## 11. ENTEGRASYONLAR

| Platform | Dosya | Endpoint | Durum |
|----------|-------|----------|-------|
| **WhatsApp QR Bridge** | `whatsapp_qr.py` | `POST /api/whatsapp/process` | ✅ Aktif (Docker) |
| **WhatsApp Cloud API** | `whatsapp_webhook.py` | `POST /webhook/whatsapp` | ⚙️ Yapılandırılabilir |
| **Telegram** | `telegram_bot.py` | python-telegram-bot | ⚙️ Yapılandırılabilir |
| **Instagram DM** | `instagram_webhook.py` | `POST /webhook/instagram` | ⚙️ Yapılandırılabilir |
| **Web Sohbet** | `web_chat_api.py` | `POST /api/chat/web` | ✅ Aktif |
| **Panel Yardım** | `support_chat_api.py` | `POST /api/chat/support` | ✅ Aktif |
| **Trendyol** | `services/trendyol/` | Seller API | ✅ Aktif |
| **Iyzico Ödeme** | `services/order/payment.py` | Iyzico API | ⚙️ Yapılandırılabilir |
| **Bridge Internal** | `bridge_api.py` | `GET /api/bridge/connections` | ✅ Aktif |
| **Cron** | `cron_api.py` | `POST /api/cron/*` | ✅ Aktif |

---

## 12. ARKA PLAN İŞLERİ

### 12.1 Celery (Opsiyonel)

- **Broker:** Redis
- **Beat Schedule:**
  - `abandoned_cart_reminder_task`: Her 10 dakika - terk edilen sepet hatırlatması
  - `proactive_message_task`: Her 30 dakika - pasif sohbetlere mesaj

### 12.2 Cron Endpoint'leri (`integrations/cron_api.py`)

- `POST /api/cron/abandoned-cart` - Sepet terk hatırlatması
- `POST /api/cron/trendyol-sync` - Trendyol soru senkronizasyonu

---

## 13. ÖNCEKİ ÇALIŞMALAR (Tamamlanan)

| Özellik | Durum | Açıklama |
|---------|-------|----------|
| Multi-tenant SaaS altyapısı | ✅ | Tenant, Partner, User, modül sistemi |
| AI Asistan (Gemini/OpenAI) | ✅ | Sohbet, ürün önerisi, sipariş, kargo |
| WhatsApp QR Bridge (multi-account) | ✅ | 10 bağlantı, Docker'da çalışıyor |
| WhatsApp grup @mention desteği | ✅ | @emareasistan ile tetikleme |
| WhatsApp grup false positive fix | ✅ | Bare text "emareasistan" artık trigger etmiyor |
| Docker migration (Bridge) | ✅ | Chromium gömülü, lazy loading, Chrome limiti |
| Trendyol entegrasyonu | ✅ | Soru işleme, AI yanıt, senkronizasyon |
| Landing page | ✅ | `static/index.html` (emareasistan.com) |
| Senaryo kartı görselleri | ✅ | Pillow ile 6 PNG oluşturuldu, `static/scenarios/` |
| Temsilci devralma + CSAT | ✅ | Canlı sohbet, memnuniyet anketi |
| Web Sohbet widget | ✅ | Embed kodu, `/chat/{slug}` |
| Panel Yardım Sohbeti | ✅ | Sağ alt AI destekli yardım |
| Sipariş state machine | ✅ | INIT→...→CONFIRMED akışı |
| Kargo takibi | ✅ | Yurtiçi, Aras, MNG |
| Randevu sistemi | ✅ | AI ile slot önerisi |
| Sesli mesaj (STT/TTS) | ✅ | Gemini→metin, OpenAI→ses |
| Görsel ürün eşleştirme | ✅ | Gemini Vision |
| OCR (plaka/ruhsat) | ✅ | Gemini Vision |
| Kurallar & İş Akışları | ✅ | Builder UI, otomatik tetikleme |
| Proaktif mesajlaşma | ✅ | Pasif sohbetlere otomatik mesaj |
| Terk edilen sepet | ✅ | 1 saat sonra hatırlatma |
| İzin yönetimi | ✅ | HR onay sistemi |
| Lokal LLM fallback | ✅ | Qwen2.5 + LoRA |

---

## 14. CONFIGURATION (.env)

```bash
# Sunucu .env (/opt/asistan/.env) ana ayarları:
GEMINI_API_KEY=AIzaSyCfrVLGK3LE4F7rMA-7Q27HLH5pNZL53i8
GEMINI_MODEL=gemini-2.5-flash-lite
DATABASE_URL=sqlite+aiosqlite:///./asistan.db
APP_BASE_URL=http://77.92.152.3:8000
WHATSAPP_BRIDGE_URL=http://localhost:3100
LOCAL_LLM_ENABLED=true
CHAT_AUDIT_ENABLED=true
CHAT_AUDIT_SAMPLE_RATE=20
SUPER_ADMIN_EMAIL=emre@emareas.com
SUPER_ADMIN_PASSWORD=3673
BASE_URL=https://meridyenoto.com
```

---

## 15. SON DURUM & NEREDE KALINDI (3 Mart 2026)

### 15.1 Aktif Durum

- **Python API:** Sunucuda çalışıyor (`systemctl status asistan-api`)
- **WhatsApp Bridge:** Docker container'da çalışıyor (`emare-whatsapp-bridge`)
- **Bağlantı [34]:** "Bağlandı" durumunda (aktif WhatsApp bağlantısı)
- **Bağlantı [13], [17]:** QR bekliyor (kimse taramıyor)
- **Diğer 7 bağlantı:** Idle (Chrome başlatılmadı, lazy loading)
- **Container kaynakları:** ~918 MB RAM, ~%2.5 CPU

### 15.2 Son Yapılan İşler

1. WhatsApp grup @mention false positive düzeltildi
2. WhatsApp Bridge Docker'a taşındı (systemd'den)
3. Lazy loading + Chrome limit (max 3) eklendi
4. Priority sort (fallback_phone) eklendi
5. Chrome lock temizliği otomasyonu eklendi
6. Eski `asistan-whatsapp` systemd servisi disable edildi

### 15.3 Potansiyel Sonraki Adımlar

- [ ] WebSocket stabilite testi (Docker uzun süreli)
- [ ] Kullanılmayan auth dizinlerinin temizliği (35 dizin, sadece 10 API'de kayıtlı)
- [ ] PostgreSQL migration (production için SQLite→PostgreSQL)
- [ ] Hepsiburada, Amazon entegrasyonları
- [ ] Facebook, Twitter, TikTok, LinkedIn entegrasyonları
- [ ] Stripe, PayPal ödeme entegrasyonları
- [ ] UPS, DHL, PTT kargo entegrasyonları
- [ ] SMS bildirimleri (Netgsm)
- [ ] Redis production kurulumu (Celery beat)

---

## 16. SÖZLÜK / KISA REFERANS

| Terim | Açıklama |
|-------|----------|
| **Tenant** | Firmaya/organizasyona karşılık gelir (multi-tenant) |
| **Partner** | Birden fazla tenant'ı yöneten üst kuruluş |
| **Bridge** | Node.js WhatsApp bağlantı köprüsü (whatsapp-web.js) |
| **Connection** | WhatsApp hesap bağlantısı (QR ile) |
| **Rule** | Anahtar kelime→ürün eşleştirme kuralı |
| **Workflow** | Trigger→Condition→Action iş akışı |
| **Agent/Temsilci** | Canlı sohbet devralan insan |
| **CSAT** | Customer Satisfaction - 1-5 memnuniyet puanı |
| **Lazy Loading** | Auth dosyası olmayan bağlantılarda Chrome başlatılmaz |
| **STT** | Speech-to-Text (ses→metin) |
| **TTS** | Text-to-Speech (metin→ses) |
| **OCR** | Optical Character Recognition (görsel→metin) |
| **RAG** | Retrieval-Augmented Generation (dokuman tabanlı AI) |
| **pgvector** | PostgreSQL vector extension (embedding arama) |

---

> **Bu belge, projeyi sıfırdan anlayabilmek için gereken tüm bilgileri içerir. Yeni bir oturumda bu dosyayı okuyarak kaldığınız yerden devam edebilirsiniz.**
