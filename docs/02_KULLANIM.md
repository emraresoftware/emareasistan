# Emare Asistan — Kullanım Kılavuzu

---

## 1. Kullanıcı Rolleri ve Erişim

### Super Admin
- **Kim:** Platform sahibi, tüm sistemi yöneten üst düzey kullanıcı
- **Giriş:** `/admin` — E-posta boş + `ADMIN_PASSWORD` veya `SUPER_ADMIN_EMAIL` + `SUPER_ADMIN_PASSWORD`
- **Yetkiler:** Tüm firmalar, partnerlar, modül yönetimi, giriş logları, kullanıcı durumları, sohbet denetimi
- **Ana sayfa:** `/admin/super`

### Partner Admin
- **Kim:** Bayi/alt marka yöneticisi; kendi müşteri firmalarını yönetir
- **Giriş:** `/admin` veya `/admin/p/{partner_slug}` — E-posta + şifre
- **Yetkiler:** Kendi firmaları, modül yönetimi, marka & logo, kullanıcı listesi
- **Ana sayfa:** `/admin/partner`

### Firma Kullanıcısı (Tenant Admin / Agent)
- **Kim:** Bir firmaya bağlı panel kullanıcısı
- **Giriş:** `/admin/t/{firma-slug}` — E-posta + şifre
- **Yetkiler:** Firma modüllerine göre değişir

---

## 2. Giriş Yöntemleri

| Yol | Açıklama |
|-----|----------|
| `/admin` | Genel giriş (e-posta + şifre veya super admin) |
| `/admin/t/{tenant-slug}` | Firma bazlı giriş (örn: `/admin/t/meridyen-oto`) |
| `/admin/p/{partner-slug}` | Partner bazlı giriş |
| `/admin/super` | Super admin paneli |
| `/admin/partner` | Partner paneli |

---

## 3. Modüller ve Kullanım

### 3.1 Sohbet Platformları

**WhatsApp** — QR veya Meta Cloud API ile bağlantı. Sesli mesaj (STT+TTS), resim, Vision AI.
1. `/admin/whatsapp` → Yeni hesap ekle → QR tarayın
2. Bağlantı sonrası mesajlar otomatik işlenir

**Telegram** — Bot token ile bağlantı.
1. BotFather'dan token alın → Entegrasyonlar'a girin

**Instagram** — Meta Graph API ile DM yanıtı.
1. `/admin/instagram` → Webhook kurulumu

**Web Sohbet** — Web sitenize gömülebilen AI widget.
1. Entegrasyonlar > Sohbet > Web Sohbet → Embed kodu kopyalayın
2. HTML'e yapıştırın

**Kişiler** — Müşteri kartları (ad, telefon, e-posta). Sohbetten otomatik oluşur.

**Temsilci Paneli** — Canlı sohbet devralma.
1. `/admin/agent` → Sohbet seçin → "Devral"
2. Mesaj yazıp gönderin (AI yanıt vermez)
3. "AI'ya devret" ile otomatik yanıta geri dönün
4. CSAT: Devir sonrası müşteriye 1–5 memnuniyet anketi gider

### 3.2 Satış & Siparişler

**Siparişler** (`/admin/orders`) — AI ile alınan siparişler. Durum güncelleme, kargo no ekleme.
- Durumlar: Beklemede → Hazırlanıyor → Kargoya Verildi → Tamamlandı / İptal
- Kargo no ekleyince müşteriye otomatik bildirim gider

**Randevular** (`/admin/appointments`) — Müşteri uygun slot seçer, AI randevu kaydeder.

**İstatistikler** (`/admin/analytics`) — Sohbet ve sipariş grafikleri.

### 3.3 İçerik Yönetimi

**Ürünler** (`/admin/products`) — Katalog. AI mesaja göre ürün önerir, resim gönderir.

**Albümler** (`/admin/albums`) — Araç modeline göre resim albümleri. "Passat paspas" → Passat albümü.

**Videolar** (`/admin/videos`) — Montaj/kurulum videoları. "montaj videosu" yazıldığında gönderilir.

**Veri Aktarımı** (`/admin/export-templates`) — Webhook ile CRM/ERP'ye veri aktarma.

### 3.4 Ödeme & Kargo

**Iyzico / PlusPay** — Kredi kartı ödeme linki. Entegrasyonlar'dan API key girin.

**Kargo Takibi** (`/admin/cargo`) — Yurtiçi, Aras, MNG, PTT, Surat, UPS, DHL sorgulama. Müşteri takip no yazınca AI durumu söyler.

### 3.5 AI & Otomasyon

**Kurallar** (`/admin/rules`) — Anahtar kelime / araç modeli → ürün/resim/mesaj.
- Tetikleyici: virgülle ayrılmış anahtar kelimeler
- Sonuç: Ürün ID'leri, resim URL'leri veya özel mesaj
- Öncelik sırası ile eşleştirme

**İş Akışları** (`/admin/workflows`) — Trigger → Action → Condition builder.

**Süreç Konfigürasyonu** (`/admin/process-config`) — SLA, escalation, otomatik yanıt ayarları.

**AI Eğitim** (`/admin/training`) — Soru-cevap örnekleri.
1. Soru + beklenen cevap + anahtar kelimeler + öncelik
2. Embedding ile benzerlik araması (pgvector + OpenAI)
3. AI yanıt kuralları, karşılama senaryoları, soru seçenekleri

**Sohbet Denetimi** (`/admin/chat-audits`) — AI yanıtlarını denetleme. Örnekleme oranı ile maliyet kontrolü.

**İdari İşler** — İzin talepleri, faturalar, satın alma (admin_staff modülü).

### 3.6 Genel Ayarlar

| Sayfa | URL | İçerik |
|-------|-----|--------|
| Hesap Sahibi | `/admin/settings/account` | Ad, e-posta, bildirim tercihleri |
| Görünüm & Marka | `/admin/settings/branding` | Logo, ana renk, vurgu rengi |
| Yapay Zeka | `/admin/settings/ai` | Gemini/OpenAI API key, model seçimi |
| Entegrasyonlar | `/admin/settings/api` | WhatsApp, Telegram, Instagram, E-posta, Kargo, Ödeme API'leri |
| Web Sohbet | `/admin/settings/web-chat` | Embed kodu |
| Hatırlatıcılar | `/admin/reminders` | Zamanlı müşteri bildirimleri |

---

## 4. Adım Adım Nasıl Yapılır

### WhatsApp Bağlama
1. `/admin/whatsapp` → Yeni hesap ekle
2. QR kodu telefondan tarayın → Bağlantı kurulur
3. Mesajlar otomatik işlenir

### Web Sohbet Siteye Ekleme
1. Entegrasyonlar > Sohbet > Web Sohbet kartı
2. `/admin/settings/web-chat` → iframe kodu kopyalayın
3. Sitenin HTML'ine `</body>` öncesine yapıştırın

### Sipariş Durumu Güncelleme
1. `/admin/orders` → Siparişe tıklayın
2. Durum değiştirin, kargo takip no ekleyin
3. Müşteriye otomatik bildirim gider

### Kural Oluşturma
1. `/admin/rules` → Yeni kural
2. Tetikleyici: araç modeli veya anahtar kelime
3. Sonuç: ürün ID'leri / resim URL'leri / özel mesaj
4. Öncelik belirleyin → Kaydet

### AI Eğitim Örneği Ekleme
1. `/admin/training` → Yeni eğitim verisi
2. Soru + beklenen cevap + anahtar kelimeler
3. Embedding oluşturun (benzerlik araması için)

### E-posta (SMTP) Ayarlama
1. Entegrasyonlar > E-posta sekmesi
2. SMTP sunucusu, port, kullanıcı, şifre, gönderen adresi
3. Sipariş bildirimleri bu ayarlarla gider

### Yapay Zeka Ayarlama
1. `/admin/settings/ai` → API anahtarı girin (Gemini veya OpenAI)
2. Model seçin, günlük mesaj limiti belirleyin

### İzin Talebi Oluşturma
1. AI & Otomasyon > İzin Talepleri
2. Çalışan adı, izin tipi, tarih aralığı girin
3. Onay akışı: HR Onayı → Yönetici Onayı → Onaylandı

### Logo ve Renk Özelleştirme
1. `/admin/settings/branding` → Logo URL, renk kodları girin
2. Navbar ve butonlara yansır

### Partner'dan Firma Modülü Açma
1. Firmalarım → Firma seç → Modülleri Yönet
2. Checkbox ile modül aç/kapat → Kaydet

### Randevu Slotları Tanımlama
1. `/admin/process-config` → Çalışma saatleri, slot süresi
2. Müşteri "randevu" dediğinde AI uygun slotları sunar

---

## 5. Kurallar (ResponseRule) Sorun Giderme

### Kuralım neden çalışmıyor?

**1. Tenant eşleşmesi:** Kurallar tenant bazlı çalışır. WhatsApp Cloud API tek webhook ile tüm mesajlar tenant_id=1'e gider. Bridge (QR) kullanıyorsanız doğru tenant'a bağlı bağlantı üzerinden mesaj gelmelidir.

**2. Kural ne yapar:** Tetikleyici kelime eşleşince tanımlı ürün resimleri/URL'leri yanıta eklenir. AI'ın genel cevap metnini değiştirmez. Metin yanıtı için AI yanıt kuralları veya İş Akışları kullanın.

**3. Tetikleyici eşleşmesi:** Virgülle ayrılmış kelimeler, mesajın içinde geçmelidir (büyük/küçük harf duyarsız). Boş tetikleyici atlanır.

**4. Ürün/resim gerekli:** product_ids veya image_urls tanımlı olmalı. İkisi de boşsa kural eşleşse bile yanıta bir şey eklenmez.

**5. Aktiflik:** Kural aktif (is_active=True) olmalı. Birden fazla eşleşmede öncelik yüksek olan kullanılır.

### Kontrol listesi
- [ ] WhatsApp Bridge (QR) kullanılıyor mu?
- [ ] Bağlantı doğru tenant'a mı ait?
- [ ] Tetikleyici kelime mesajda geçiyor mu?
- [ ] Kuralda ürün resmi veya URL tanımlı mı?
- [ ] Metin yanıtı mı istiyorsunuz? → AI yanıt kuralları veya İş Akışları kullanın

---

## 6. Panel Yardım Sohbeti

Sağ altta **💬 Yardım** butonu ile AI destekli yardım. Partner, tenant ve firma kullanıcıları soruları sorabilir (örn: "Bunu nasıl yaparım?", "Şu senaryoyu nasıl oluştururum?").

Yardım sohbeti **Emare Asistan tenant'ına** (tenant_id=1) bağlıdır. API anahtarları önce tenant 1 ayarlarından, yoksa `.env` kullanılır.

---

## 7. Menü Yapısı

| Menü | İçerik |
|------|--------|
| **Dashboard** | Ana sayfa, özet bilgiler |
| **Sohbet Platformları** | Tüm Sohbetler, WhatsApp, Telegram, Instagram, Kişiler, Temsilci Paneli |
| **Satış & Siparişler** | Siparişler, Randevular, İstatistikler |
| **İçerik Yönetimi** | Ürünler, Ürün Galerisi, Albümler, Videolar |
| **Pazaryerleri** | Veri Aktarımı |
| **Ödeme Sistemleri** | Siparişler & Ödemeler |
| **Kargo & Lojistik** | Kargo Takibi |
| **Kullanıcı Yönetimi** | Kullanıcılar, Temsilci Paneli, Hızlı Yanıtlar |
| **AI & Otomasyon** | Kurallar, İş Akışları, Süreç Konfigürasyonu, AI Eğitim, Sohbet Denetimi, İzin/Fatura/Satın Alma |
| **Genel Ayarlar** | Hesap, Marka, Yapay Zeka, Entegrasyonlar, Hatırlatıcılar |

---

## 8. Sık Sorulanlar

| Soru | Cevap |
|------|-------|
| Embed kodu nerede? | Entegrasyonlar > Sohbet sekmesi |
| WhatsApp bağlanmıyor? | QR süresi dolmuş olabilir. Yenileyin. API ayarlarını kontrol edin |
| AI yanlış cevap veriyor? | AI Eğitim'e doğru örnek ekleyin. Kurallar ile eşleştirme yapın |
| Sipariş bildirimi gelmiyor? | Hesap Sahibi'nde e-posta tanımlı mı? SMTP ayarlı mı? |
| Modül menüde görünmüyor? | Super Admin/Partner modülü açmamış olabilir |
| Temsilci devralınca ne olur? | AI yanıt vermez, insan mesaj yazar. "AI'ya devret" ile geri döner. CSAT anketi gider |
| CSAT nerede? | Dashboard'daki "CSAT (7 gün)" kartında ortalama ve yanıt sayısı |
| İzin Talepleri nerede? | AI & Otomasyon > İzin Talepleri (admin_staff modülü açık olmalı) |

---

*Son güncelleme: Şubat 2026*
