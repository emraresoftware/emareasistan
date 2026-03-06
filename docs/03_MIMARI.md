# Emare Asistan — Mimari

---

## 1. Modül Sistemi

Emare Asistan **modüler** bir yapıdadır. Her firma (tenant) için hangi özelliklerin etkin olacağı super admin veya partner tarafından belirlenir.

### Modüller Listesi

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

**Tam liste:** `services/modules.py` — 56 modül (ek: pazaryerleri, kargo firmaları, sosyal medya, ödeme yöntemleri vb.)

### Modül Mantığı

- **Boş/NULL:** `enabled_modules` boşsa tüm modüller etkin (geriye uyumluluk)
- **Seçili:** Sadece listedeki modüller görünür ve kullanılabilir
- **Navigasyon:** Devre dışı modüller menüde gizlenir
- **Erişim kontrolü:** Devre dışı modül URL'sine doğrudan erişim engellenir

---

## 2. Admin Panel

### Giriş Türleri

| Tip | Giriş | Erişim |
|-----|-------|--------|
| Super Admin | E-posta boş + `ADMIN_PASSWORD` veya `SUPER_ADMIN_EMAIL` + şifre | Tüm firmalar, partnerlar, modüller |
| Partner Admin | Partner admin e-posta + şifre | Kendi müşteri firmaları |
| Firma Admin | Firma e-posta + şifre | Sadece kendi firması |
| Agent | Agent e-posta + şifre | Temsilci paneli, canlı sohbet |

### Super Admin Sayfası (`/admin/super`)

- **Dashboard** – İstatistikler, firmalar listesi
- **Firmalar** – Tüm kayıtlı firmalar (ad, sektör, durum, silme)
- **Partnerlar** – Partner oluşturma, admin atama, firma bağlama
- **Modülleri Yönet** – Firma bazlı modül etkinleştirme
- **Kullanıcı Durumları** – Online/offline durumu
- **Giriş Logları** – Login denetim kayıtları (e-posta, IP, tarih)

### Sayfa Listesi

| Modül | Sayfa | URL |
|-------|-------|-----|
| — | Dashboard | `/admin/dashboard` |
| orders | Siparişler | `/admin/orders` |
| cargo | Kargo Takibi | `/admin/cargo` |
| analytics | İstatistikler | `/admin/analytics` |
| products | Ürünler | `/admin/products`, `/admin/products/gallery` |
| albums | Albümler | `/admin/albums` |
| videos | Videolar | `/admin/videos` |
| whatsapp | WhatsApp | `/admin/whatsapp` |
| telegram | Telegram | `/admin/conversations?platform=telegram` |
| instagram | Instagram | `/admin/instagram` |
| contacts | Kişiler | `/admin/contacts` |
| rules | Kurallar | `/admin/rules` |
| workflows | İş Akışları | `/admin/workflows` |
| training | AI Eğitim | `/admin/training` |
| conversations | Sohbetler | `/admin/conversations` |
| reminders | Hatırlatıcılar | `/admin/reminders` |
| agent | Temsilci Paneli | `/admin/agent` |
| quick_replies | Hızlı Yanıtlar | `/admin/quick-replies` |
| appointments | Randevular | `/admin/appointments` |
| admin_staff | İzin/Fatura/Satın Alma | `/admin/admin-staff/*` |
| export_templates | Veri Aktarımı | `/admin/export-templates` |
| — | Görünüm & Marka | `/admin/settings/branding` |
| — | Sohbet Denetimi | `/admin/chat-audits` |
| — | Süreç Konfigürasyonu | `/admin/process-config` |
| — | AI Ayarları | `/admin/settings/ai` |
| — | API Entegrasyonları | `/admin/settings/api` |
| — | Web Sohbet | `/admin/settings/web-chat` |
| — | Hesap Ayarları | `/admin/settings/account` |

### Teknik Detaylar

| Öğe | Açıklama |
|-----|----------|
| Layout | `base.html` (tenant), `partner_base.html` (partner), `super_admin.html` (super) |
| Route Dosyaları | `routes.py`, `routes_auth.py`, `routes_dashboard.py`, `routes_orders.py`, `routes_agent.py`, `routes_settings.py`, `routes_rules_workflows.py`, `routes_partner_super.py`, `partner.py` |
| Yardımcılar | `admin/common.py`, `admin/helpers.py` |
| Session | `request.session` — admin, tenant_id, super_admin, partner_admin, partner_id |
| Modül kontrolü | `main.py` `_PATH_MODULES` — enabled_modules ile koruması |
| Middleware | `middleware/admin_context.py` — her request'te bağlam yüklenir |

---

## 3. Partner (Bayi) Sistemi

### Hiyerarşi

```
Emare (platform sahibi)
├── Partner A (bayi)
│   ├── Tenant 1
│   ├── Tenant 2
│   └── ...
├── Partner B
└── Doğrudan tenant'lar (partner_id = NULL)
```

### Roller

| Rol | Yetki |
|-----|-------|
| Emare Super Admin | Tüm partner ve tenant'ları yönetir |
| Partner Admin | Sadece kendi tenant'larını yönetir |
| Tenant Admin / Agent | Sadece kendi tenant'ını yönetir |

### Veri Modeli

**Partner:** `id`, `name`, `slug`, `settings` (JSON — branding), `is_active`

**Tenant:** `partner_id` (FK → partners.id, NULL = doğrudan Emare tenant'ı)

**User:** `partner_id`, `is_partner_admin` (Boolean), `tenant_id` (partner admin için NULL olabilir)

### Partner Sayfaları

| Sayfa | URL | Açıklama |
|-------|-----|----------|
| Firmalarım | `/admin/partner` | Müşteri listesi |
| Panelim | `/admin/partner/panel` | Varsayılan firmaya giriş |
| Modülleri Yönet | `/admin/partner/modules/{tid}` | Firma modülleri |
| Marka & Logo | `/admin/partner/settings/branding` | Partner logosu |
| Firma Markası | `/admin/partner/tenant/{tid}/branding` | Firma bazlı logo/renk |
| Kullanıcılar | `/admin/partner/users` | Kullanıcı durumları |
| Remote Deploy | `/admin/partner/deploy` | Uzak sunucuya kurulum (SSH) |
| Sunucular | `/admin/partner/servers` | Kayıtlı sunucular |

### Partner Akışları

1. **Partner oluşturma:** Super Admin → Partnerlar → Ad + Slug
2. **Firma atama:** Firmalar → Partner dropdown → Ata
3. **Admin oluşturma:** Partner listesinde e-posta + şifre → Partner Admin Ekle
4. **Giriş:** `/admin` veya `/admin/p/{slug}` → Firmalarım listesi
5. **Müşteri ekleme:** `/admin/partner` → Yeni müşteri ekle (ad, slug, sektör, ilk admin)

---

## 4. Sohbet Çalışma Mantığı

### Sohbet Akışı

```
Müşteri mesajı → Platform → ChatHandler → AI / Kurallar → Yanıt + Resim/Video/Konum/Ses
```

**Sesli mesaj:**
```
Sesli mesaj → Bridge indirir → API (audio_base64) → STT → metin → AI → TTS → sesli yanıt
```

### Kanal Soyutlaması

```
BaseChannel (soyut)
├── WhatsAppCloudChannel    # integrations/channels/whatsapp_cloud.py
├── TelegramChannel         # integrations/channels/telegram_channel.py
├── InstagramChannel        # integrations/channels/instagram_channel.py
└── (Yeni kanal → BaseChannel'dan türet)
```

**Ortak veri yapıları:**
- `InboundMessage` — Normalize edilmiş gelen mesaj
- `ChatResponse` — Tüm kanallara gönderilen yanıt

### MessagePipeline

```
Gelen Mesaj → Sanitizer → Intent Detector → Router → Handler → Yanıt
```

| Adım | Dosya | Açıklama |
|------|-------|----------|
| Sanitizer | `services/workflow/pipeline/sanitizer.py` | Mesaj temizleme, XSS engelleme |
| Intent Detector | `services/workflow/pipeline/intent_detector.py` | Niyet tespiti |
| Router | `services/workflow/pipeline/router.py` | Doğru handler'a yönlendirme |
| Formatter | `services/workflow/pipeline/formatter.py` | Yanıt biçimlendirme |

### Alt Handler'lar

| Handler | Dosya | Görev |
|---------|-------|-------|
| OrderHandler | `integrations/handlers/order_handler.py` | Sipariş alma |
| ProductHandler | `integrations/handlers/product_handler.py` | Ürün araması |
| CargoHandler | `integrations/handlers/cargo_handler.py` | Kargo takip |
| AppointmentHandler | `integrations/handlers/appointment_handler.py` | Randevu oluşturma |
| HumanHandler | `integrations/handlers/human_handler.py` | Temsilci devralma |

### Adım Adım Süreç

1. Sohbet getir/oluştur — platform + user_id ile Conversation kaydı
2. Mesajı kaydet
3. Pipeline — Sanitizer → Intent → Router
4. Temsilci kontrolü — Devredildiyse AI yanıt vermez
5. Handler delegasyonu — Sipariş, ürün, kargo, randevu
6. Kural motoru — RuleEngine ile anahtar kelime/araç modeli eşleştirme
7. AI yanıtı — `AIAssistant.chat()`
8. Sohbet denetimi — ChatAudit (opsiyonel)

### AI Eğitim

**İki Mod:**
1. **Benzerlik Tabanlı** (pgvector + OpenAI) — En yakın 5 örnek, token tasarrufu
2. **Öncelik Tabanlı** (Fallback) — pgvector yoksa ilk 15 örnek

**Özellikler:** Anahtar kelime tetikleyici, toplu import (CSV), sohbetten örnek üretme, mesaj geri bildirimi

### AI Servisleri

| Bileşen | Dosya | Açıklama |
|---------|-------|----------|
| STT | `services/ai/stt.py` | Sesli mesaj → metin (Gemini/Whisper) |
| TTS | `services/ai/tts.py` | Metin → ses (OpenAI TTS) |
| Vision | `services/ai/vision.py` | Resimden ürün eşleştirme |
| RAG | `services/ai/rag.py` | Retrieval Augmented Generation |
| Embeddings | `services/ai/embeddings.py` | Vektör embedding oluşturma |

### Firma API Entegrasyonları

| Modül | Amaç |
|-------|------|
| Ürünler | Dış ürün kataloğu veya stok API'si |
| Kargo Takibi | Kargo API anahtarları |
| Siparişler | ERP webhook |
| Ödeme (Iyzico) | Kredi kartı ödeme linki |
| CRM | Müşteri yönetimi API |

---

*Son güncelleme: Şubat 2026*
