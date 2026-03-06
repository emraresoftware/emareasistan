# Emare Asistan — Operasyon

---

## 1. Deploy

### Tek Komut (Lokal)

```bash
python run.py                           # API + Bridge birlikte
uvicorn main:app --port 8000 --reload   # Sadece API
```

### Docker Compose

```bash
cp .env.example .env
docker compose up -d
docker compose exec api python -m alembic upgrade head
```

### Sunucu (systemd)

```bash
sudo systemctl enable asistan-api asistan-whatsapp
sudo systemctl start asistan-api asistan-whatsapp
# Servis dosyaları: deploy/systemd/
```

### Partner Remote Deploy

Admin panelden (`/admin/partner/deploy`) uzak sunucuya otomatik tenant kurulumu:
- 3 SSH kimlik doğrulama yöntemi (şifre/dosya/yapıştır)
- Otomatik RSA key üretimi ve yükleme
- Deploy scriptleri: `scripts/deploy_single_tenant.sh`, `scripts/remote_deploy_tenant.sh`

### Nginx + SSL

Reverse proxy, Let's Encrypt ile HTTPS. Detay: `DEPLOY.md`

---

## 2. Tenant Onboarding

### Tenant Oluşturma

**Super Admin:** `/admin/super` → Yeni Firma → Ad + Slug → Kaydet

**Partner:** `/admin/partner` → Yeni Müşteri Ekle → Ad + Slug → Modülleri Yönet

**Remote Deploy:** `/admin/partner/deploy` → Sunucu bilgileri + SSH yöntemi → Deploy Başlat

### Admin Kullanıcı Oluşturma

1. Firma paneline giriş (Super Admin veya Partner → Panele Gir)
2. `/admin/users` → Yeni Kullanıcı (ad, e-posta, şifre, rol)

### Temel Yapılandırma

1. **AI API anahtarı:** `/admin/settings/ai` → Gemini veya OpenAI key
2. **WhatsApp bağlantısı:** `/admin/whatsapp` → QR tarayın
3. **Marka:** `/admin/settings/branding` → Logo, renkler
4. **AI Eğitim:** `/admin/training` → Soru-cevap çiftleri + embedding sync
5. **Kurallar:** `/admin/rules` → Tetikleyici kelime → ürün/resim

### Doğrulama Kontrol Listesi

- [ ] Admin panele giriş yapılabiliyor
- [ ] WhatsApp bağlantısı kuruldu
- [ ] AI API key girildi ve test edildi
- [ ] Hoş geldin mesajı ayarlandı
- [ ] En az 5 eğitim verisi eklendi
- [ ] Web sohbet widget test edildi
- [ ] Logo ve marka ayarları yapıldı
- [ ] Kullanıcı rolleri doğru atandı

---

## 3. WhatsApp Sorun Giderme

### Akış

```
Müşteri → WhatsApp Bridge (3100) → Python API (8000) → AI → Yanıt → Bridge → Müşteri
```

### Hızlı Teşhis

```bash
python scripts/check_whatsapp.py
curl http://localhost:8000/api/whatsapp/diagnose
```

### Olası Nedenler ve Çözümler

| Sorun | Kontrol | Çözüm |
|-------|---------|-------|
| API'ye ulaşamıyor | Bridge'de `ECONNREFUSED` | Python API çalışıyor mu? |
| Yanlış API adresi | `ASISTAN_API_URL` | `.env` kontrol edin |
| AI anahtarı yok | `.env` dosyası | `GEMINI_API_KEY` veya `OPENAI_API_KEY` |
| Temsilci devraldı | Admin panel → Sohbetler | Devralmayı kaldırın |
| Günlük limit doldu | Tenant ayarları | AI mesaj limiti aşılmış |
| Boş yanıt | API 200, text boş | Bridge fallback mesaj gönderir |

### Kontrol Listesi

1. Bridge: `curl http://localhost:3100/api/status` → `{"connected":true}`
2. API: `curl http://localhost:8000/api/whatsapp/test` → `{"status":"ok"}`
3. Mesaj testi: `curl -X POST http://localhost:8000/api/whatsapp/process -H "Content-Type: application/json" -d '{"from":"905321234567","text":"Merhaba"}'`
4. `ASISTAN_API_URL` doğru mu?
5. AI anahtarları `.env`'de var mı?
6. QR ile taranan numaraya mı mesaj atılıyor?
7. Bridge terminalinde `[1] Mesaj alındı` görünüyor mu?

### Arada Kopup Bağlanma

| Neden | Çözüm |
|-------|-------|
| CONNECTION_LOST | Bridge 15 sn sonra yeniden dener. Ağı kontrol edin |
| LOGOUT | Yeni QR tarayın; başka cihazda oturum açmayın |
| Telefon kapalı | Telefonun sürekli internette olduğundan emin olun |
| Çok hesap / bellek | Bridge'i bölün veya RAM artırın |
| Sunucu ağ kesintisi | Host sağlayıcıyla kontrol edin |

### Port 3100 Çakışması

```bash
cd whatsapp-bridge && ./stop-bridge.sh && node index-multi.js
```

---

## 4. WhatsApp Bridge Mimarisi

Bridge (`whatsapp-bridge/index.js`) enterprise-grade dayanıklılık sağlar:

### Mesaj Kuyruğu
- API'ye ulaşılamadığında `pendingMessages` kuyruğuna alınır
- Max 1000 mesaj, 10 dakika TTL
- `drainQueue()` her 5 saniyede kuyruğu boşaltır

### API Retry
- `sendToAPI()` — 3 deneme, exponential backoff (2s → 4s → 8s)
- Başarısız mesajlar kuyruğa geri eklenir

### Catch-up
- `ready` event'inde son 5 dakikanın okunmamış mesajları taranır

### Heartbeat
- Her 30 saniyede bağlantı kontrolü
- 3 ardışık başarısız → otomatik yeniden başlatma

### Dayanıklılık
- Bağlantı kopması → 2 saniyede yeniden bağlanma
- `isReconnecting` guard ile çoklu bağlantı engeli
- Graceful shutdown (SIGTERM, SIGINT)
- `uncaughtException` / `unhandledRejection` yakalama
- systemd: `Restart=always`, `MemoryMax=1G`, `StartLimitBurst=10`

---

## 5. İdari Personel Otomasyonu

- **İzin talepleri:** leave_requests, HR + yönetici onay akışı
- **Faturalar:** invoices, OCR destekli
- **Satın alma:** purchase_orders
- Admin panel: AI & Otomasyon menüsünden erişim

---

## 6. Rakip Analizi ve Yol Haritası

### Sektör Trendleri

- **Agentic AI** — Gözlemleyen, planlayan, aksiyon alan asistanlar
- **İnsan–AI orkestrasyonu** — Düşük risk AI, karmaşık işler insan
- **CSAT / NPS otomasyonu** — Otomatik memnuniyet anketi
- **Agent Assist** — Canlı sohbette anlık AI öneri
- **Proaktif mesajlaşma** — Olay tetikleyicili mesajlar
- **Sentiment analizi** — Sinirli müşteri tespiti

### Mevcut Güçlü Yönler

- Çok kanallı (WhatsApp, Telegram, Instagram, Web)
- Temsilci devralma + AI'ya devret
- Kurallar + iş akışları + randevu + kargo + sipariş
- Partner / çok tenant, modül yönetimi
- CSAT anketi ✅, Enterprise Bridge ✅, Rate limiting ✅

### Önerilen Özellikler

**P0 (Hemen):**
- ✅ CSAT anketi — Uygulandı
- Temsilciye AI öneri (Agent Assist) — Planlandı
- Sohbet özeti (ticket summary) — Planlandı

**P1 (Farklılaştırıcı):**
- Proaktif Web Sohbet tetikleyicileri
- Duygu / sentiment tespiti
- CSAT genişletme (e-posta, NPS)

**P2 (Uzun vadeli):**
- Sesli kanal (Voice AI)
- Çok dilli destek
- Help center / KB araması (RAG)
- Dashboard özelleştirme

---

## 7. Sistem Yetenekleri Özeti

- ✅ Pipeline (sanitizer → intent → router), Handler ayırımı
- ✅ Kanal soyutlaması (BaseChannel → WhatsApp, Telegram, Instagram, Web)
- ✅ Niyet tespiti, AI eğitim (benzerlik/pgvector, CSV import)
- ✅ Sipariş, randevu, kargo takip, Vision ürün eşleştirme, RAG
- ✅ Soru seçenekleri, AI yanıt kuralları, karşılama senaryoları
- ✅ Sesli mesaj: STT (Gemini/Whisper) + TTS (OpenAI)
- ✅ İdari personel (izin, fatura, satın alma)
- ✅ Super admin, partner yönetimi, modül yönetimi, API key encryption
- ✅ Rate limiting, güvenlik header'ları (XSS, HSTS, CSP)
- ✅ Enterprise WhatsApp Bridge (mesaj kuyruğu, retry, heartbeat, catch-up)
- ✅ Partner remote deploy (SSH key, uzak sunucu)
- ✅ 27 otomatik test (pytest), Kıvılcım kod tarayıcı
- ✅ Web sohbet widget, panel yardım sohbeti
- ✅ CSAT anketi, sohbet denetimi, mesaj geri bildirimi

---

*Son güncelleme: Şubat 2026*
