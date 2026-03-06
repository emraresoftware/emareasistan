# Emare Asistan

İşletmelerin WhatsApp, Telegram ve Instagram üzerinden müşterileriyle otomatik iletişim kurmasını sağlayan **yapay zeka destekli sohbet asistanı**. Çok kiracılı (multi-tenant) SaaS mimarisinde çalışır; her firma kendi hesabı, WhatsApp bağlantısı ve AI ayarlarıyla izole çalışır.

## Özellikler

- **Soru-Cevap**: Müşteri sorularına anında yanıt (ürün, fiyat, garanti, iade vb.)
- **Ürün Önerisi**: Araç modeli, bütçe veya ihtiyaca göre ürün önerisi
- **Ürün Resimleri**: İlgili ürünlerin görsellerini otomatik gönderme
- **Sipariş Alma**: Ad, adres, telefon toplama ve sipariş oluşturma
- **Kargo Takibi**: Takip numarası ile kargo durumu sorgulama ve link paylaşma
- **Soru Seçenekleri**: Panelden tanımlanan tıklanabilir seçenekler; müşteri numara yazarak (1, 2, 3) seçim yapar
- **Sesli Mesaj**: Müşteri sesli mesaj gönderir → STT ile metne çevrilir → AI yanıt verir → TTS ile sesli yanıt (OpenAI TTS)

## Desteklenen Platformlar

| Platform | Durum |
|----------|--------|
| WhatsApp (QR ile giriş) | ✅ Telefonla QR tarayın |
| WhatsApp Business Cloud API | ✅ Webhook hazır |
| Telegram Bot | ✅ Hazır |
| Instagram DM | ✅ Meta Graph API webhook hazır |

## Kurulum

### 1. Bağımlılıkları yükle

```bash
cd asistan
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Ortam değişkenleri

`.env` dosyası oluştur (`.env.example` şablonundan):

```bash
cp .env.example .env
```

Düzenlenmesi gerekenler:

- `GEMINI_API_KEY` veya `OPENAI_API_KEY` - Biri yeterli (Gemini: https://aistudio.google.com/apikey)
- `OPENAI_API_KEY` - Sesli yanıt (TTS) ve Whisper STT için; sesli mesajla gelen müşteriye sesli yanıt döner
- `TELEGRAM_BOT_TOKEN` - Telegram Bot için (BotFather'dan alınır)
- `ADMIN_PASSWORD` - Yönetim paneli şifresi (varsayılan: emare123)
- `WHATSAPP_*` - Sadece Cloud API kullanıyorsanız (QR yöntemi için gerekmez)
- `INSTAGRAM_*` - Instagram DM için (Meta Developer Console, Facebook Page + Instagram Business)

### 3. Çalıştırma

**Tek komutla tüm sistem (önerilen):**

```bash
# Önce WhatsApp bridge bağımlılıklarını yükleyin (bir kez)
cd whatsapp-bridge && npm install && cd ..

# Sonra tek komutla başlat (venv kullanır)
./start.sh
# veya: source venv/bin/activate && python run.py
```

API (8000) ve WhatsApp Bridge (3100) birlikte çalışır. Durdurmak için Ctrl+C.

**Ayrı ayrı çalıştırma:**

```bash
# 1. Python API
python main.py

# 2. Ayrı terminalde WhatsApp bridge
cd whatsapp-bridge
npm install
npm start

# Tarayıcıda http://localhost:3100 açın, QR kodu telefonla tarayın
# WhatsApp > Ayarlar > Bağlı Cihazlar > Cihaz Bağla
```

**Web sunucusu (Cloud API webhook için):**

```bash
python main.py
# veya
uvicorn main:app --reload --port 8000
```

**Telegram bot (ayrı terminal):**

```bash
python main.py telegram
```

## Temsilci Paneli

Müşteri temsilcisi müsait olduğunda sohbetlere dahil olabilir:

1. **Admin giriş** → Menüden **Temsilci** sayfasına gidin
2. **Profil** → Adınızı ve durumunuzu (Müsait / Meşgul / Çevrimdışı) kaydedin
3. **Devral** → Sohbet listesinden bir sohbeti seçip "Devral" ile müşteriyle doğrudan iletişime geçin
4. **Mesaj gönder** → Devraldığınız sohbette mesaj kutusundan yanıt yazın
5. **AI'a bırak** → İşiniz bitince "AI'a Bırak" ile sohbeti yapay zekaya devredin

Devralınan sohbetlerde AI yanıt vermez; müşteriye "Mesajınız temsilcimize iletildi" bilgisi gider. Mesajlar WhatsApp Bridge veya Cloud API üzerinden iletilir.

## Yönetim Paneli

Admin paneli: **http://localhost:8000/admin** (veya sunucu adresiniz)

### Giriş Türleri

| Tür | Nasıl |
|-----|-------|
| **Super Admin** | E-posta boş + `.env` `ADMIN_PASSWORD` veya `SUPER_ADMIN_EMAIL` + `SUPER_ADMIN_PASSWORD` |
| **Firma Admin** | Kendi e-posta + şifre (firma yöneticisi) |

### Üye Ol

Yeni firmalar **Üye Ol** (`/admin/register`) ile kayıt olur: web sitesi URL girin, sistem otomatik analiz eder, sektör seçin (30+ seçenek), e-posta/şifre ile hesap oluşturun.

### Özellikler

- **Kurallar**: Araç modeli veya anahtar kelimeye göre otomatik ürün/resim gönderme
  - Örnek: "Passat" yazan müşteriye belirli ürün resimlerini gönder
  - Tetikleyici türü: `vehicle_model` veya `keyword`
  - Ürün ID'leri (JSON: `[1, 2, 3]`) veya doğrudan resim URL'leri
  - Özel mesaj, öncelik ve aktif/pasif durumu
- **AI Eğitim**: Soru-cevap örnekleri, AI yanıt kuralları, **Soru Seçenekleri** (panelden tanımlı; müşteri 1, 2, 3 yazarak seçim), karşılama senaryoları
- **Görünüm & Marka**: Ana renk, vurgu rengi, logo URL (Ayarlar → Görünüm & Marka)
- **Sohbet Denetimi**: AI yanıt kalite kontrolü (`.env`: `CHAT_AUDIT_ENABLED=true`)
- **Sohbetler**: Müşteri bazlı tüm sohbet geçmişi
  - Platform (WhatsApp/Telegram), müşteri adı/telefon
  - Mesaj detayları (kullanıcı + asistan)
- **Dashboard**: Sohbet sayısı, sipariş sayısı, kural sayısı özeti

## API Dokümantasyonu

Sunucu çalışırken: http://localhost:8000/docs

## WhatsApp Entegrasyonu

### Yöntem 1: QR ile giriş (kolay, Meta hesabı gerekmez)

1. `python main.py` ile API'yi başlatın
2. `cd whatsapp-bridge && npm install && npm start` ile bridge'i çalıştırın
3. Terminalde çıkan QR kodu telefonunuzla tarayın (WhatsApp > Ayarlar > Bağlı Cihazlar)
4. "WhatsApp'a bağlandı!" mesajını görünce hazırsınız

**Bağlı ama cevap vermiyorsa:**
```bash
python scripts/fix_whatsapp.py   # Temsilci devralmasını sıfırlar, teşhis yapar
./whatsapp-bridge/stop-bridge.sh # Port 3100 ve Chromium süreçlerini durdurur
python run.py                    # Yeniden başlat
```

### Yöntem 2: Cloud API (kurumsal, Meta Developer hesabı gerekir)

1. [Meta for Developers](https://developers.facebook.com) üzerinden uygulama oluştur
2. WhatsApp Business API ürününü ekle
3. Webhook URL: `https://SIZIN_DOMAIN/webhook/whatsapp`
4. Verify Token: `.env` içindeki `WHATSAPP_VERIFY_TOKEN`
5. `hub.verify_token` doğrulamasından sonra "messages" alanını subscribe edin

## Detaylı Dokümantasyon

Teknik detaylar, modül sistemi, sohbet mantığı için:

📁 **[docs/](docs/00_INDEX.md)** – Tüm doküman listesi (5 dosya)

- [Genel Bakış](docs/01_GENEL_BAKIS.md) – Emare Asistan nedir, özellikler, hedef kitle
- [Modül ve Admin](docs/02_MODUL_VE_ADMIN.md) – Modül sistemi, Super Admin, Admin Panel
- [Sohbet ve AI](docs/03_SOHBET_VE_AI.md) – ChatHandler akışı, AI eğitim
- [Teknik Referans](docs/04_TEKNIK_REFERANS.md) – Proje yapısı, veritabanı, migration, Docker
- [Operasyon](docs/05_OPERASYON.md) – WhatsApp sorun giderme, deploy

## Proje Yapısı

```
asistan/
├── config/          # Ayarlar
├── docs/            # Detaylı dokümantasyon (modüller, super admin, akış)
├── models/          # Veritabanı modelleri (Product, Order, Conversation)
├── services/        # AI asistan, ürün, sipariş, kargo, speech_to_text, text_to_speech, chat_audit
├── integrations/    # WhatsApp webhook, Telegram bot, QR bridge
├── whatsapp-bridge/ # QR ile WhatsApp bağlantısı (Node.js), stop-bridge.sh
├── scripts/         # load_tenant6_rules.py, load_tenant6_quick_replies.py vb.
├── data/            # Örnek / scraped ürün verileri
├── main.py          # FastAPI uygulaması
└── requirements.txt
```

## Yardımcı Script'ler

| Script | Açıklama |
|--------|----------|
| `scripts/load_tenant6_rules.py` | Tenant 6 (Emare Asistan) için AI yanıt kurallarını yükler |
| `scripts/load_tenant6_quick_replies.py` | Tenant 6 için Soru Seçenekleri yükler |
| `scripts/migrate_uploads_to_tenant_folders.py` | Eski albüm/video dosyalarını tenant klasörlerine taşır |
| `whatsapp-bridge/stop-bridge.sh` | Port 3100 ve Chromium süreçlerini durdurur (EADDRINUSE çözümü) |

## Ürün Verisi

Tenant ürün verisini firmanın web sitesinden çekmek için:

```bash
python scripts/scrape_products.py
```

Çıktı `data/products_scraped.json` dosyasına yazılır. AI asistan bu dosyayı otomatik kullanır.

**Detaylı scraping** (ürün sayfalarından resim ve açıklama, ilk 20 ürün):

```bash
python scripts/scrape_products.py --details
```

Yoksa `data/products_sample.json` örnek veri kullanılır.

## Kargo Takibi

Şu an Yurtiçi, Aras, MNG için takip linki oluşturuluyor. Kargo firmalarının resmi API’leri eklenerek detaylı takip eklenebilir.

## Lisans

Emare Asistan - Tüm hakları saklıdır.
