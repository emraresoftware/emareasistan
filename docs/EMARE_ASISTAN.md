# Emare Asistan — Tam Dokümantasyon

> Bu dosya tüm Emare Asistan dokümantasyonunu tek bir yerde toplar.  
> Son güncelleme: Şubat 2026

---

## İçindekiler

1. [Genel](#1-genel)
2. [Kullanım Kılavuzu](#2-kullanım-kılavuzu)
3. [Mimari](#3-mimari)
4. [Teknik Referans](#4-teknik-referans)
5. [Operasyon](#5-operasyon)

---
---

# 1. Genel

---

## Emare Asistan Nedir?

**Emare Asistan**, işletmelerin WhatsApp, Telegram, Instagram ve kendi web siteleri üzerinden müşterileriyle **7/24 otomatik iletişim** kurmasını sağlayan, **yapay zeka destekli** ve **çok kiracılı (multi-tenant)** bir sohbet ve satış asistanı platformudur.

Müşteri hizmetleri ve satış süreçlerini otomatikleştiren, kurumsal iletişim kanallarını tek bir yönetim panelinde birleştiren, modüler bir SaaS uygulamasıdır. Her firma (tenant) kendi ürün kataloğu, AI eğitimi, entegrasyonları ve marka kimliğiyle bağımsız çalışır; platform sahibi (super admin) ve partner (bayi/alt marka) katmanları ile ölçeklenebilir bir hiyerarşi sunar.

---

## Değer Önerisi

| Sorun | Çözüm |
|-------|-------|
| Müşteri mesajları geç yanıtlanıyor | AI 7/24 anında yanıt verir |
| WhatsApp, Telegram, Instagram ayrı yönetiliyor | Tüm kanallar tek panelde toplanır |
| Fiyat/ürün/kargo bilgisi tekrar tekrar soruluyor | AI eğitimi ve kurallar ile tutarlı cevap |
| Sipariş süreci manuel | AI ad, telefon, adres toplar; sipariş otomatik oluşur |
| Kargo takibi müşteriye elle bildiriliyor | Kargo no yazıldığında AI durumu söyler |
| Randevu alma kağıt/kalem | Slot seçimi ve randevu kaydı sohbet içinde tamamlanır |

---

## Kim İçin?

- **Perakende ve e-ticaret** — Ürün sorusu, sipariş, kargo takibi
- **Otomotiv ve aksesuar** — Araç modeli eşleştirme, albüm, montaj videosu
- **Hizmet sektörü** — Randevu yönetimi, konum paylaşımı
- **Bayi / distribütör (partner)** — Kendi müşteri firmalarını yöneten alt markalar
- **Platform sahibi (super admin)** — Birden fazla firmayı tek yerden yöneten işletmeler

---

## Nasıl Çalışır?

```
Müşteri mesajı (WhatsApp / Telegram / Instagram / Web)
        ↓
    ChatHandler
        ↓
┌──────────────────────────────────────────────────────┐
│  Kurallar (anahtar kelime, araç modeli) → Ürün/resim  │
│  AI eğitim örnekleri → Benzer soru-cevap             │
│  AI yanıt (Gemini / OpenAI) → Doğal dil yanıtı      │
│  Özel handler'lar → Sipariş, randevu, kargo          │
└──────────────────────────────────────────────────────┘
        ↓
Yanıt + Resim / Video / Konum / Ses → Müşteriye
```

---

## Desteklenen Platformlar

| Platform | Durum |
|----------|-------|
| WhatsApp (QR — whatsapp-web.js) | ✅ Aktif |
| WhatsApp Business Cloud API (Meta) | ✅ Aktif |
| Telegram Bot API | ✅ Aktif |
| Instagram DM (Meta Graph API) | ✅ Aktif |
| Web Sohbet Widget | ✅ Aktif |
| Panel Yardım Sohbeti (AI) | ✅ Aktif |

---

## Temel Özellikler

### Müşteri İletişimi
- WhatsApp — QR veya Meta Cloud API ile bağlantı
- Telegram — Bot üzerinden mesaj
- Instagram — Direct Message (Meta Graph API)
- Web Sohbet — Sitelere gömülebilen iframe widget

### AI Yetenekleri
- Doğal dil anlama ve yanıt (Gemini / OpenAI)
- Firma bazlı AI eğitimi (soru-cevap örnekleri)
- Kurallar (anahtar kelime, araç modeli → ürün/resim)
- Vision AI (müşteri resmi → ürün eşleştirme)
- Sesli mesaj (STT ile dinleme, TTS ile sesli yanıt)
- RAG (Retrieval Augmented Generation)

### Satış & Operasyon
- Sipariş alma (ad, telefon, adres, ödeme)
- Ödeme linki (Iyzico, PlusPay)
- Kargo takibi (Yurtiçi, Aras, MNG, PTT, Surat, UPS vb.)
- Randevu yönetimi (müsait slot, takvim)
- Temsilci devralma (insan + AI hibrit)
- CSAT anketi ve sohbet denetimi
- Enterprise WhatsApp Bridge (mesaj kuyruğu, retry, heartbeat)

### Yönetim & Entegrasyon
- Modüler yapı — 56 modül, firma bazlı açılır/kapatılır
- Partner (bayi) yönetimi ve remote deploy
- ERP, CRM, kargo, ödeme API entegrasyonları
- Webhook ile sipariş, kişi, hatırlatıcı aktarımı
- E-posta (SMTP), SMS (Netgsm), Telegram bildirimleri
- White-label — Logo, renkler firma bazlı
- Rate limiting ve güvenlik header'ları
- Otomatik test paketi (pytest) ve kod tarayıcı (Kıvılcım)

---

## Mimari Özeti

| Katman | Açıklama |
|--------|----------|
| **Super Admin** | Platform sahibi; tüm firmalar, partnerlar, modüller |
| **Partner** | Bayi/alt marka; kendi tenant grubunu yönetir |
| **Tenant (Firma)** | Her işletme; kendi sohbet kanalları, ürünleri, AI eğitimi |
| **Modüller** | Siparişler, Ürünler, Kargo, Randevu, Web Sohbet vb. — firma bazlı |

---

## Teknoloji

| Katman | Teknoloji |
|--------|-----------|
| Backend | Python, FastAPI, SQLAlchemy (async), Pydantic |
| AI | Google Gemini, OpenAI; RAG (pgvector), Vision AI, STT/TTS |
| WhatsApp | Node.js bridge (whatsapp-web.js) veya Meta Cloud API |
| Veritabanı | SQLite (geliştirme), PostgreSQL + pgvector (üretim) |
| Panel | Jinja2 şablonları, HTML/CSS/JS |
| Güvenlik | Rate limiting, güvenlik header'ları, API key şifreleme |
| Test | pytest + pytest-asyncio, Kıvılcım otomatik tarayıcı |
| Deploy | Docker Compose, systemd, partner remote deploy (SSH) |

---

## Hızlı Başlangıç

- **Kurulum:** `README.md`
- **Deploy:** `DEPLOY.md`
- **Yönetim paneli:** `http://localhost:8000/admin`
- **API dokümantasyonu:** `http://localhost:8000/docs`
- **Testler:** `.venv/bin/python3 -m pytest tests/ -v`
- **Kod tarama:** `python scripts/kivilcim.py`

---
---

# 2. Kullanım Kılavuzu

---

## 2.1 Kullanıcı Rolleri ve Erişim

### Super Admin
- **Giriş:** `/admin` — E-posta boş + `ADMIN_PASSWORD` veya `SUPER_ADMIN_EMAIL` + `SUPER_ADMIN_PASSWORD`
- **Yetkiler:** Tüm firmalar, partnerlar, modül yönetimi, giriş logları, kullanıcı durumları, sohbet denetimi
- **Ana sayfa:** `/admin/super`

### Partner Admin
- **Giriş:** `/admin` veya `/admin/p/{partner_slug}`
- **Yetkiler:** Kendi firmaları, modül yönetimi, marka & logo
- **Ana sayfa:** `/admin/partner`

### Firma Kullanıcısı
- **Giriş:** `/admin/t/{firma-slug}`
- **Yetkiler:** Firma modüllerine göre değişir

---

## 2.2 Modüller ve Kullanım

### Sohbet Platformları

**WhatsApp** — `/admin/whatsapp` → QR tarayın. Sesli mesaj, resim, Vision AI.

**Telegram** — Entegrasyonlar'dan bot token girin.

**Instagram** — `/admin/instagram` → Meta Graph API webhook kurulumu.

**Web Sohbet** — Entegrasyonlar > Sohbet > embed kodu kopyalayın.

**Temsilci Paneli** — `/admin/agent` → Sohbet devralma. "AI'ya devret" ile geri bırakın. CSAT anketi otomatik gider.

### Satış & Siparişler

**Siparişler** (`/admin/orders`) — Durum güncelleme, kargo no ekleme. AI ile otomatik sipariş alma.

**Randevular** (`/admin/appointments`) — AI müşteriye uygun slot sunar.

**İstatistikler** (`/admin/analytics`) — Sohbet ve sipariş grafikleri.

### İçerik Yönetimi

**Ürünler** (`/admin/products`) — Katalog, AI ürün önerisi.

**Albümler** (`/admin/albums`) — Araç modeline göre resim albümleri.

**Videolar** (`/admin/videos`) — Montaj/kurulum videoları.

### AI & Otomasyon

**Kurallar** (`/admin/rules`) — Anahtar kelime → ürün/resim/mesaj. Öncelik sırası.

**İş Akışları** (`/admin/workflows`) — Trigger → Action → Condition builder.

**AI Eğitim** (`/admin/training`) — Soru-cevap örnekleri, embedding, karşılama senaryoları.

**Sohbet Denetimi** (`/admin/chat-audits`) — AI yanıt kalite kontrolü.

### Genel Ayarlar

| Sayfa | URL | İçerik |
|-------|-----|--------|
| Hesap Sahibi | `/admin/settings/account` | Ad, e-posta, bildirim tercihleri |
| Görünüm & Marka | `/admin/settings/branding` | Logo, renk teması |
| Yapay Zeka | `/admin/settings/ai` | API key, model seçimi |
| Entegrasyonlar | `/admin/settings/api` | Tüm API entegrasyonları |
| Web Sohbet | `/admin/settings/web-chat` | Embed kodu |

---

## 2.3 Adım Adım Nasıl Yapılır

### WhatsApp Bağlama
1. `/admin/whatsapp` → Yeni hesap ekle → QR tarayın → Bağlantı kurulur

### Web Sohbet Siteye Ekleme
1. Entegrasyonlar > Sohbet > embed kodu kopyalayın → HTML'e yapıştırın

### Sipariş Durumu Güncelleme
1. `/admin/orders` → Siparişe tıklayın → Durum değiştirin, kargo no ekleyin

### Kural Oluşturma
1. `/admin/rules` → Tetikleyici + sonuç + öncelik → Kaydet

### AI Eğitim Örneği
1. `/admin/training` → Soru + cevap + anahtar kelimeler → Embedding oluşturun

### E-posta (SMTP)
1. Entegrasyonlar > E-posta → SMTP bilgileri girin

### İzin Talebi
1. AI & Otomasyon > İzin Talepleri → Yeni talep → HR + yönetici onay akışı

---

## 2.4 Kurallar Sorun Giderme

**Kural çalışmıyorsa:**
1. **Tenant eşleşmesi** — Cloud API mesajlar tenant_id=1'e gider; Bridge (QR) doğru tenant'a bağlı olmalı
2. **Kural ne yapar** — Sadece ürün resimleri/URL ekler. Metin yanıtı için AI yanıt kuralları veya İş Akışları kullanın
3. **Tetikleyici** — Virgülle ayrılmış kelimeler mesajda geçmeli
4. **Ürün/resim gerekli** — product_ids veya image_urls tanımlı olmalı
5. **Aktiflik** — is_active=True olmalı

---

## 2.5 Panel Yardım Sohbeti

Sağ altta **💬 Yardım** butonu. AI destekli, tenant_id=1 ayarlarını kullanır.

---

## 2.6 Menü Yapısı

| Menü | İçerik |
|------|--------|
| Dashboard | Özet bilgiler |
| Sohbet Platformları | WhatsApp, Telegram, Instagram, Kişiler, Temsilci Paneli |
| Satış & Siparişler | Siparişler, Randevular, İstatistikler |
| İçerik Yönetimi | Ürünler, Galerisi, Albümler, Videolar |
| Kargo & Lojistik | Kargo Takibi |
| AI & Otomasyon | Kurallar, İş Akışları, AI Eğitim, Sohbet Denetimi, İzin/Fatura/Satın Alma |
| Genel Ayarlar | Hesap, Marka, AI, Entegrasyonlar, Hatırlatıcılar |

---

## 2.7 Sık Sorulanlar

| Soru | Cevap |
|------|-------|
| Embed kodu nerede? | Entegrasyonlar > Sohbet |
| WhatsApp bağlanmıyor? | QR yenileyin, API ayarlarını kontrol edin |
| AI yanlış cevap? | AI Eğitim'e örnek ekleyin |
| Sipariş bildirimi gelmiyor? | Hesap Sahibi e-posta + SMTP ayarlı mı? |
| Modül görünmüyor? | Super Admin/Partner modülü açmamış |
| CSAT nerede? | Dashboard "CSAT (7 gün)" kartı |

---
---

# 3. Mimari

---

## 3.1 Modül Sistemi

56 modül, firma bazlı açılır/kapatılır. Dosya: `services/modules.py`

### Temel Modüller

| Modül ID | Ad | Kategori |
|----------|-----|----------|
| whatsapp | WhatsApp | Sohbet |
| web_chat | Web Sohbet | Sohbet |
| telegram | Telegram | Sohbet |
| instagram | Instagram DM | Sosyal Medya |
| products | Ürünler | Pazaryerleri |
| albums | Albümler | Pazaryerleri |
| videos | Videolar | Pazaryerleri |
| orders | Siparişler | Ödemeler |
| payment | Ödeme (Iyzico) | Ödemeler |
| cargo | Kargo Takibi | Kargo |
| rules | Kurallar | AI & Otomasyon |
| workflows | İş Akışları | AI & Otomasyon |
| training | AI Eğitim | AI & Otomasyon |
| contacts | Kişiler | Sohbet |
| reminders | Hatırlatıcılar | AI & Otomasyon |
| analytics | İstatistikler | AI & Otomasyon |
| quick_replies | Hızlı Yanıtlar | Sohbet |
| agent | Temsilci Paneli | Sohbet |
| conversations | Sohbetler | Sohbet |
| appointments | Randevular | Sohbet |
| admin_staff | İdari İşler | Pazaryerleri |
| export_templates | Veri Aktarımı | AI & Otomasyon |

### Modül Mantığı
- Boş/NULL → tüm modüller etkin (geriye uyumluluk)
- Devre dışı modüller menüde gizlenir, URL erişimi engellenir

---

## 3.2 Admin Panel

### Giriş Türleri

| Tip | Giriş | Erişim |
|-----|-------|--------|
| Super Admin | E-posta boş + `ADMIN_PASSWORD` veya `SUPER_ADMIN_*` | Tüm firmalar |
| Partner Admin | E-posta + şifre | Kendi firmaları |
| Firma Admin | E-posta + şifre | Kendi firması |
| Agent | E-posta + şifre | Temsilci paneli |

### Super Admin (`/admin/super`)
Dashboard, Firmalar, Partnerlar, Modül Yönetimi, Kullanıcı Durumları, Giriş Logları

### Sayfa Listesi (30+)

Dashboard, Siparişler, Kargo, İstatistikler, Ürünler, Galerisi, Albümler, Videolar, WhatsApp, Telegram, Instagram, Kişiler, Kurallar, İş Akışları, AI Eğitim, Sohbetler, Hatırlatıcılar, Temsilci Paneli, Hızlı Yanıtlar, Randevular, İzin/Fatura/Satın Alma, Veri Aktarımı, Marka, Sohbet Denetimi, Süreç Konfigürasyonu, AI Ayarları, Entegrasyonlar, Web Sohbet, Hesap Ayarları

### Teknik Detaylar

| Öğe | Açıklama |
|-----|----------|
| Layout | `base.html`, `partner_base.html`, `super_admin.html` |
| Route Dosyaları | `routes.py`, `routes_auth.py`, `routes_dashboard.py`, `routes_orders.py`, `routes_agent.py`, `routes_settings.py`, `routes_rules_workflows.py`, `routes_partner_super.py`, `partner.py` |
| Session | admin, tenant_id, super_admin, partner_admin, partner_id |
| Middleware | `admin_context.py` — her request'te bağlam yüklenir |

---

## 3.3 Partner Sistemi

### Hiyerarşi

```
Emare (platform sahibi)
├── Partner A → Tenant 1, 2, ...
├── Partner B → Tenant 3, 4, ...
└── Doğrudan tenant'lar (partner_id = NULL)
```

### Roller

| Rol | Yetki |
|-----|-------|
| Super Admin | Tüm partner ve tenant'ları yönetir |
| Partner Admin | Kendi tenant'larını yönetir |
| Tenant Admin / Agent | Kendi tenant'ını yönetir |

### Veri Modeli
- **Partner:** id, name, slug, settings (JSON), is_active
- **Tenant:** partner_id (FK, NULL = doğrudan)
- **User:** partner_id, is_partner_admin, tenant_id (partner admin için NULL)

### Partner Sayfaları
Firmalarım, Panelim, Modülleri Yönet, Marka & Logo, Kullanıcılar, Remote Deploy, Sunucular

---

## 3.4 Sohbet Çalışma Mantığı

### Kanal Soyutlaması

```
BaseChannel (soyut)
├── WhatsAppCloudChannel
├── TelegramChannel
├── InstagramChannel
└── (Yeni kanal → BaseChannel'dan türet)
```

### MessagePipeline

```
Gelen Mesaj → Sanitizer → Intent Detector → Router → Handler → Yanıt
```

### Alt Handler'lar

| Handler | Görev |
|---------|-------|
| OrderHandler | Sipariş alma |
| ProductHandler | Ürün araması |
| CargoHandler | Kargo takip |
| AppointmentHandler | Randevu |
| HumanHandler | Temsilci devralma |

### Süreç Adımları
1. Sohbet getir/oluştur → 2. Mesaj kaydet → 3. Pipeline → 4. Temsilci kontrolü → 5. Handler → 6. Kural motoru → 7. AI yanıt → 8. Sohbet denetimi

### AI Eğitim
- **Benzerlik Tabanlı** (pgvector + OpenAI) — en yakın 5 örnek
- **Öncelik Tabanlı** (Fallback) — ilk 15 örnek

### AI Servisleri
STT (`stt.py`), TTS (`tts.py`), Vision (`vision.py`), RAG (`rag.py`), Embeddings (`embeddings.py`)

---
---

# 4. Teknik Referans

---

## 4.1 Proje Yapısı

```
asistan/
├── admin/          # Yönetim paneli (9 route dosyası, ~40 şablon)
├── config/         # Pydantic Settings (.env)
├── data/           # Statik veri (vehicle_models.json vb.)
├── integrations/   # Kanallar, handler'lar, webhook'lar
│   ├── channels/   # BaseChannel, WhatsApp, Telegram, Instagram
│   └── handlers/   # Order, Product, Cargo, Appointment, Human
├── middleware/      # rate_limit, security_headers, admin_context
├── models/         # SQLAlchemy ORM (25+ dosya)
├── services/       # ai/, core/, order/, product/, workflow/, whatsapp/
├── scripts/        # kivilcim.py, deploy scriptleri
├── tests/          # pytest (27 test)
├── whatsapp-bridge/# Node.js Bridge
├── main.py         # FastAPI app, middleware, /health
└── run.py          # API + Bridge başlatma
```

---

## 4.2 Ana Dosyalar

| Dosya | Görev |
|-------|-------|
| `main.py` | FastAPI app, middleware stack, /health |
| `integrations/chat_handler.py` | Platform bağımsız sohbet |
| `integrations/channels/base.py` | BaseChannel, InboundMessage, ChatResponse |
| `services/ai/assistant.py` | AI Asistan (Gemini/OpenAI) |
| `services/ai/stt.py`, `tts.py`, `vision.py` | Ses/görüntü AI |
| `services/core/modules.py` | 56 modül tanımı |
| `services/core/crypto.py` | API key şifreleme |
| `services/workflow/rules.py` | Kural motoru |
| `middleware/rate_limit.py` | Rate limiting |
| `middleware/security_headers.py` | Güvenlik header'ları |
| `admin/partner.py` | Partner remote deploy (SSH) |
| `whatsapp-bridge/index.js` | Bridge: kuyruğu, retry, heartbeat |

---

## 4.3 Veritabanı Modelleri

**Tenant:** id, name, slug, sector, enabled_modules (JSON), settings (JSON)

**Partner:** id, name, slug, settings (JSON)

**User:** id, tenant_id, email, password_hash, role, partner_id, is_partner_admin

**Conversation + Message:** tenant_id, platform, platform_user_id, agent_took_over, csat_rating

**Order:** tenant_id, order_number, items (JSON), cargo_tracking_no, status

**Product, ImageAlbum, Video:** tenant_id, name, price, image_urls, vehicle_models

**ResponseRule:** trigger_keyword, response_text, product_ids, image_urls

**AITrainingExample:** question, expected_answer, embedding (vector)

**Appointment, AuditLog, ChatAudit, MessageFeedback, LeaveRequest, Invoice, PurchaseOrder, ExportTemplate, TenantWorkflow, WhatsAppConnection**

Detay: `models/` klasörü (25+ dosya)

---

## 4.4 Entegrasyon Mimarisi

```
Gelen Mesaj → Webhook → InboundMessage → ChatHandler → AI/Kurallar → ChatResponse → BaseChannel → Platform API
```

### Mevcut Kanallar (Tümü ✅)
WhatsApp QR, WhatsApp Cloud, Telegram, Instagram DM, Web Sohbet, Panel Yardım

### Yeni Kanal Ekleme
1. `BaseChannel`'dan türetme (`platform_id`, `send_text()`, `send_image()`)
2. Webhook endpoint oluşturma
3. `services/modules.py`'ye modül ekleme
4. `main.py`'ye router dahil etme
5. Menüye ekleme

---

## 4.5 Güvenlik

### Middleware Stack
```
İstek → SecurityHeaders → RateLimit → admin_context → Session → Route
```

### Rate Limiting
| Endpoint | Limit |
|----------|-------|
| `/admin/login` (POST) | 10/dk |
| `/webhook/*` | 300/dk |
| `/process` | 30/dk |
| Genel | 120/dk |

### Header'lar
X-Frame-Options, X-Content-Type-Options, X-XSS-Protection, Referrer-Policy, Permissions-Policy, HSTS

### Auth
Session tabanlı (itsdangerous), bcrypt parola hash, rol hiyerarşisi

### Sunucu Güvenliği
- `.env` deploy etmemek, `chmod 600 .env`
- Ayrı kullanıcı ile çalıştırma
- PyArmor / JS obfuscator (opsiyonel)

---

## 4.6 Migration & Docker

```bash
alembic upgrade head                    # Yeni kurulum
docker compose up -d                    # Docker
docker compose exec api python -m alembic upgrade head
```

---

## 4.7 Test

```bash
.venv/bin/python3 -m pytest tests/ -v
```

| Dosya | Test Sayısı |
|-------|-------------|
| `test_smoke.py` | 13 (import, health, security) |
| `test_modules.py` | 6 (modül yapısı) |
| `test_channels.py` | 8 (dataclass'lar) |

---

## 4.8 Kıvılcım (Kod Tarayıcı)

```bash
python scripts/kivilcim.py                    # Tam tarama
python scripts/kivilcim.py --task docstrings  # Belirli görev
```

Görevler: TODO, secret, endpoint, env, docstring, auth

---
---

# 5. Operasyon

---

## 5.1 Deploy

### Lokal
```bash
python run.py                           # API + Bridge
uvicorn main:app --port 8000 --reload   # Sadece API
```

### Docker
```bash
cp .env.example .env && docker compose up -d
```

### Sunucu (systemd)
```bash
sudo systemctl enable asistan-api asistan-whatsapp
sudo systemctl start asistan-api asistan-whatsapp
```

### Partner Remote Deploy
`/admin/partner/deploy` → 3 SSH yöntemi (şifre/dosya/yapıştır) → Otomatik kurulum

---

## 5.2 Tenant Onboarding

1. Tenant oluştur (Super Admin veya Partner)
2. Admin kullanıcı oluştur
3. AI API key, WhatsApp bağlantısı, marka ayarları
4. AI eğitim verileri + kurallar
5. Kontrol listesi ile doğrulama

---

## 5.3 WhatsApp Sorun Giderme

```
Müşteri → Bridge (3100) → API (8000) → AI → Yanıt → Bridge → Müşteri
```

| Sorun | Çözüm |
|-------|-------|
| ECONNREFUSED | API çalışıyor mu? |
| Yanlış API adresi | `ASISTAN_API_URL` kontrol |
| AI anahtarı yok | `.env` kontrol |
| Temsilci devraldı | Devralmayı kaldırın |
| CONNECTION_LOST | Ağ/telefon kontrol, 15 sn otomatik yeniden deneme |
| LOGOUT | Yeni QR tarayın |

---

## 5.4 WhatsApp Bridge Mimarisi

- **Mesaj Kuyruğu:** Max 1000, 10 dk TTL, 5 sn drain
- **Retry:** 3 deneme, exponential backoff (2→4→8s)
- **Catch-up:** Son 5 dk okunmamış mesajlar
- **Heartbeat:** 30 sn kontrol, 3 başarısız → yeniden başlatma
- **Dayanıklılık:** 2 sn reconnect, graceful shutdown, exception handling

---

## 5.5 Rakip Analizi

### Önerilen Özellikler

| Öncelik | Özellik | Durum |
|---------|---------|-------|
| P0 | CSAT anketi | ✅ Uygulandı |
| P0 | Agent Assist (AI öneri) | Planlandı |
| P0 | Sohbet özeti | Planlandı |
| P1 | Proaktif Web Sohbet | — |
| P1 | Sentiment analizi | — |
| P2 | Voice AI | — |
| P2 | Çok dilli destek | — |
| P2 | KB araması (RAG) | — |

---

## 5.6 Sistem Yetenekleri

- ✅ Pipeline, Handler ayırımı, Kanal soyutlaması
- ✅ AI eğitim, Kurallar, İş Akışları
- ✅ Sipariş, Randevu, Kargo, Vision, RAG
- ✅ STT + TTS, Sesli mesaj
- ✅ Super admin, Partner, Modül yönetimi
- ✅ Rate limiting, Güvenlik header'ları, API key encryption
- ✅ Enterprise WhatsApp Bridge
- ✅ Partner remote deploy (SSH)
- ✅ 27 test (pytest), Kıvılcım tarayıcı
- ✅ Web sohbet, Panel yardım sohbeti
- ✅ CSAT, Sohbet denetimi

---

*Son güncelleme: Şubat 2026*
