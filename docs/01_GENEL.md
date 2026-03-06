# Emare Asistan — Genel

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

Veri izolasyonu: Her firma kendi konuşmaları, siparişleri ve ayarlarıyla çalışır.

---

## Teknoloji

| Katman | Teknoloji |
|--------|-----------|
| Backend | Python, FastAPI, SQLAlchemy (async), Pydantic |
| AI | Google Gemini, OpenAI; RAG (pgvector), Vision AI, STT/TTS |
| WhatsApp | Node.js bridge (whatsapp-web.js) veya Meta Cloud API; mesaj kuyruğu, retry, heartbeat |
| Veritabanı | SQLite (geliştirme), PostgreSQL + pgvector (üretim) |
| Panel | Jinja2 şablonları, HTML/CSS/JS |
| Güvenlik | Rate limiting, güvenlik header'ları (XSS, HSTS), API key şifreleme |
| Test | pytest + pytest-asyncio, Kıvılcım otomatik tarayıcı |
| Deploy | Docker Compose, systemd, partner remote deploy (SSH) |

---

## Hızlı Başlangıç

- **Kurulum:** Proje kökündeki `README.md`
- **Deploy:** Proje kökündeki `DEPLOY.md`
- **Yönetim paneli:** `http://localhost:8000/admin`
- **API dokümantasyonu:** `http://localhost:8000/docs`
- **Testler:** `.venv/bin/python3 -m pytest tests/ -v`
- **Kod tarama:** `python scripts/kivilcim.py`

### Nasıl Başlanır?

1. Hedef sektör seçimi ve modül onayı (Super admin tarafından)
2. Sohbet kanalı bağlama: WhatsApp (QR veya Cloud API), Telegram veya Instagram
3. Ürün/servis veri yükleme (CSV/JSON, ürün galerisi)
4. AI eğitim örnekleri ve kurallar tanımlama
5. Pilot: Vision AI (otomotiv), Abandoned Cart (e-ticaret) veya randevu akışı (hizmet sektörü)

---

> **Emare Asistan**, işletmelerin müşterileriyle WhatsApp, Telegram, Instagram ve web üzerinden yapay zeka destekli, 7/24 otomatik ve satış odaklı iletişim kurmasını sağlayan, çok kiracılı ve modüler bir SaaS platformudur.

*Son güncelleme: Şubat 2026*
