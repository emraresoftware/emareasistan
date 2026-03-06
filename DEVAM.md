# Devam Noktası

Cursor kapandığında bu dosyayı okuyarak nerede kaldığını ve ne yapılacağını öğren.

**Prensip:** Ne kadar çok esneklik, o kadar fazla potansiyel. Her yeni entegrasyon yeni pazar ve müşteri demek.

---

## Anlık İş Günlüğü (Cursor Kapansa da Kaybolmasın)

> **Kural:** Kod yazmadan ÖNCE ne yapılacağını buraya yaz. Her kod değişikliğinden SONRA bu bölümü güncelle ve dosyayı kaydet.

---

## 🔒 4 Mart 2026 — Gemini + Widget Düzeltmeleri (MÜHÜRLÜ)

> Aşağıdaki 4 sorun tamamen çözüldü. **Geri alma veya değiştirme.**

### 1. LOCAL_LLM kapatıldı
- **Dosya:** `/opt/asistan/.env`
- **Değişiklik:** `LOCAL_LLM_ENABLED=false` (eskiden `true` idi)
- **Sebep:** `true` olunca tüm mesajlar Gemini'ye hiç uğramadan local modele gidiyordu
- **Doğrulama:** `systemctl restart asistan-api` → yeni PID, Gemini yanıtları geldi

### 2. V4 Prompt doğru tabloya taşındı
- **Sorun:** 8671 karakterlik V4 prompt `tenant_settings` tablosuna kaydedilmişti ama kod `tenants.settings` JSON kolonunu okuyordu
- **Düzeltme:** `/tmp/fix_prompt.py` ile prompt `tenants` tablosunun `settings` JSON alanına kopyalandı (tenant_id=2)
- **Doğrulama:** `SELECT settings->>'ai_prompt_override' FROM tenants WHERE id=2` → 8671 karakter ✅

### 3. Hardcoded karşılama yanıtları kaldırıldı
- **Dosya:** `/opt/asistan/integrations/chat_handler.py`
- **Kaldırılan 1:** Satır 529-536 — `_enhance_first_reply_for_sales()` çağrı bloğu (tenant_id=1,2 için tüm ilk mesajları override ediyordu)
- **Kaldırılan 2:** Satır 892-898 — `_is_social_smalltalk()` kontrolü + hardcoded ASCII Türkçe yanıt
- **Sonuç:** Tüm yanıtlar artık saf Gemini'den geliyor; `_enhance_first_reply_for_sales` fonksiyonu dosyada duruyor ama HİÇ çağrılmıyor
- **Doğrulama:** `merhaba` → Gemini'den akıllı Türkçe yanıt ✅

### 4. Site widget Gemini'ye bağlandı (Finance-style)
- **Dosya:** `/Users/emre/Desktop/Emare/emareasistan/static/index.html`
- **Eski durum:** `chatReplies` dict + `fallbackReplies` array — tamamen hardcoded, API çağrısı yok
- **Yeni durum:** AlpineJS `eaChat()` reaktif widget
  - `fetch()` → `http://77.92.152.3:8000/api/chat/web` (POST JSON)
  - `tenant_slug: 'emare-asistan'`, `visitor_id` localStorage'da saklanır
  - 3 noktalı typing animasyonu (bounce)
  - `marked.js` + `DOMPurify` → Gemini markdown çıktısı render edilir
  - Quick reply butonları (karşılama mesajlarında)
  - Shift+Enter ile çok satır, Enter ile gönder
  - Mobil: tam ekran; Desktop: 3 sn sonra otomatik açılır
- **CDN'ler** (satır ~2058): `marked.min.js` + `dompurify@3.0.6`
- **Deploy:** `sshpass` ile `/opt/asistan/static/index.html`'e kopyalandı ✅

### Sunucu Erişim Bilgileri (Kopyala-Yapıştır)
```bash
# SSH
SSHPASS='Emre2025*' sshpass -e ssh -o StrictHostKeyChecking=no root@77.92.152.3

# Dosya deploy
SSHPASS='Emre2025*' sshpass -e scp -o StrictHostKeyChecking=no \
  /Users/emre/Desktop/Emare/emareasistan/static/index.html \
  root@77.92.152.3:/opt/asistan/static/index.html

# Servis yeniden başlat
systemctl restart asistan-api

# API test
curl -s -X POST http://77.92.152.3:8000/api/chat/web \
  -H "Content-Type: application/json" \
  -d '{"message":"merhaba","tenant_slug":"emare-asistan","visitor_id":"test"}'
```

### Kritik Dosya Konumları (Sunucu)
| Dosya | Konum |
|---|---|
| Ana uygulama | `/opt/asistan/` |
| Ortam değişkenleri | `/opt/asistan/.env` |
| Chat handler | `/opt/asistan/integrations/chat_handler.py` |
| Veritabanı | `/opt/asistan/asistan.db` |
| Site HTML | `/opt/asistan/static/index.html` |
| Servis logu | `journalctl -u asistan-api -n 50` |

---

### Şimdi Yapılacak
- Logging/monitoring altyapısı (structured logging, Prometheus metrics)
- Kıvılcım kalan docstring'leri (82 → hedef <30)
- CI/CD pipeline (GitHub Actions)

### Az Önce Yapıldı
- ✅ Test altyapısı: pytest 9.0.2, pytest-asyncio, pytest.ini, conftest.py (fixture'lar), 27 test (hepsi geçiyor)
  - tests/test_smoke.py: Import, health, redirect, güvenlik header testleri
  - tests/test_modules.py: Modül sistemi testleri (yapı, benzersizlik, temel modüller)
  - tests/test_channels.py: InboundMessage ve ChatResponse dataclass testleri
- ✅ Dokümantasyon: docs/07_TENANT_ONBOARDING.md (tenant oluşturma rehberi), docs/08_ENTEGRASYON_EKLEME.md (yeni kanal ekleme rehberi), docs/00_INDEX.md güncellendi
- 🔥 Kıvılcım AI Asistanı: KIVILCIM.md (16 görev), scripts/kivilcim.py (otomatik tarayıcı), KIVILCIM_RAPOR.md
- Kıvılcım Tarama Sonuçları: Hardcoded secret düzeltildi (0'a indi), 102 docstring otomatik eklendi (183→82), tüm endpoint'ler auth korumalı
- scripts/add_docstrings.py: Otomatik docstring ekleyici (route fonksiyonlarına Türkçe docstring)
- Production güvenlik: Rate limit middleware aktifleştirildi (main.py), güvenlik header'ları middleware eklendi (middleware/security_headers.py), /health detaylı (DB + bridge + uptime)
- WhatsApp Bridge kesintisiz: 2sn reconnect, heartbeat 30sn, mesaj kuyruğu (1000 mesaj, 5 retry, exponential backoff), catch-up (okunmamış mesajlar), API retry, graceful shutdown
- Partner Remote Deploy: 3 yöntemli SSH (şifre/dosya/yapıştır), otomatik key üretim+yükleme, sunucu listesi sayfası
- scripts/create_piramit_vpn_workflow.py: Piramit (veya --tenant-id) için VPN sorunu iş akışı ekler; tetikleyici "vpn sorunu/vpn sorun/vpn yaşıyorum/vpn problemi", yanıt "Bilgisayarınızı yeniden başlatın ve internet bağlantınızı kontrol edin."; whatsapp + web platformları; --list-tenants ile tenant listesi
- admin/templates/base.html: Sol menü sadeleştirildi (platform alt başlıkları, Asistana sor, Entegrasyonlar birleşik, Kargo tek link, notlar kaldırıldı)
- admin/templates/base.html: Menüler sol sidebar’a alındı (sabit sol panel, içerik sağda); gruplar açılır/kapanır; 900px altında hamburger + overlay
- Workspace hafifletme: venv klasörü silindi (~380 MB); start.sh ve update.sh .venv öncelikli kullanacak şekilde güncellendi; asistan.log boşaltıldı; WORKSPACE_HAFIFLATMA.md güncellendi (.cursorignore satırları isteğe bağlı not olarak eklendi)
- routes.py + routes_rules_workflows.py + şablonlar: Albümler, kullanıcılar, kurallar, chat-audits, training (eğitim örnekleri) listelerine sayfalama (PAGE_SIZE=20) ve pagination linkleri; PERFORMANCE.md güncellendi
- routes.py + şablonlar: Videolar, kişiler, faturalar, izin talepleri, satın alma siparişleri listelerine sayfalama (PAGE_SIZE=20) ve pagination linkleri; PERFORMANCE.md güncellendi
- admin/routes_dashboard.py: Dashboard sorguları 4 paralel grupta asyncio.gather ile çalışacak şekilde refactor edildi (_dashboard_counts, _dashboard_revenue, _dashboard_recent, _dashboard_csat); PERFORMANCE.md ve DEVAM güncellendi
- Performans: admin/PERFORMANCE.md eklendi (yavaş/ağır sayfalar listesi, öneriler); sohbet detayda mesajlar son 500 ile sınırlandı; hatırlatıcılar listesine sayfalama (PAGE_SIZE=20) ve şablon pagination linkleri eklendi
- Sunucuya yükleme: ./remote-update.sh çalıştırıldı; dosyalar kopyalandı, migration OK, asistan-api yeniden başlatıldı (active/running), WhatsApp Bridge korundu
- Lokal test: uvicorn 8002'de çalıştırıldı; /health 200, /admin 307, /admin/agent, /admin/quick-replies, /admin/settings, /admin/rules, /admin/orders hepsi 302 (girişe yönlendirme) — refactor route'ları çalışıyor
- admin/REFACTOR_CHECKLIST.md: Tüm modüller "Tamamlandı" işaretlendi; isteğe bağlı madde tamamlandı olarak güncellendi
- Lokal import testi: uv run python -c "from admin.routes import router" başarılı
- admin/routes_agent.py: agent, quick-replies, api/agent/*, api/quick-replies, api/debug-session, api/whatsapp-status taşındı; routes.py'den ilgili blok ve _load_quick_replies_for_tenant kaldırıldı
- admin/routes_rules_workflows.py: rules, workflows, process-config, training, chat-audits taşındı; routes.py'den ilgili blok kaldırıldı
- admin/routes_partner_super.py: partner + super route'ları taşındı; routes.py'den ilgili blok kaldırıldı
- admin/routes_settings.py: settings + api/ai-status route'ları taşındı; routes.py'den settings bloğu kaldırıldı
- admin/routes.py: Siparişler ve kargo bloğu kaldırıldı (route'lar routes_orders.py'de)
- admin/refactor: admin/helpers.py (ortak yardımcılar), admin/routes_dashboard.py (dashboard + analytics route'ları taşındı), admin/routes_settings.py, routes_rules_workflows.py, routes_orders.py, routes_agent.py, routes_partner_super.py (stub + include); routes.py tüm modülleri include ediyor
- Lokal test: bağımlılıklar kuruldu, uvicorn 8001'de çalıştı, health OK
- admin/refactor: admin/common.py (templates + helpers), admin/routes_auth.py (auth route'ları), admin/routes.py auth kaldırıldı, auth_router include edildi
- docs/IYILESTIRME_RAKIP_ANALIZI.md: Rakip analizi ve yol haritası (CSAT, Agent Assist, sohbet özeti, proaktif web, sentiment)
- CSAT: Conversation csat_sent_at/csat_rating/csat_comment, migration 022; AI'ya devret sonrası WhatsApp'ta anket mesajı; 1-5 yanıtı ChatHandler'da kayıt; Dashboard'da CSAT (7 gün) kartı

### Az Önce Yapıldı
- admin/templates/base.html: Checkbox tik işareti daha belirgin (stroke 3.5, background-size 16px; hem input hem label::before hem dark theme)
- admin/templates/base.html: Checkbox tik sorunu — label içindeki kutular için görünüm label::before ile, input saydam ve üstte (opacity:0, position:absolute) bırakıldı; tıklama her zaman input'a gidiyor; koyu tema ::before stilleri eklendi
- admin/templates/base.html: Checkbox tik işareti / tıklanabilirlik düzeltildi (box-sizing, position relative, z-index 1, pointer-events auto, label user-select none)
- integrations/support_chat_api.py: Yardım sohbeti artık kural **yazabiliyor** — "bu kuralı oluştur" denince AI create_rule JSON döndürüyor, backend parse edip oturum açık kullanıcının tenant'ına ResponseRule kaydediyor; Request ile session/tenant_id alınıyor

### Az Önce Yapıldı
- admin/templates/base.html: AI & Otomasyon menüsüne "Asistana sor" butonları eklendi (Kurallar, İş Akışları, Süreç Konfig, AI Eğitim, Sohbet Denetimi, İzin/Faturalar/Satın Alma); tıklanınca yardım sohbeti açılıp ilgili soru otomatik gönderiliyor

### Az Önce Yapıldı
- admin/templates/base.html: yardım sohbeti geçmişi localStorage ile korunacak şekilde güncellendi
- admin/templates/super_admin.html: yardım sohbeti geçmişi localStorage ile korunacak şekilde güncellendi
- admin/templates/partner_base.html: yardım sohbeti geçmişi localStorage ile korunacak şekilde güncellendi
- admin/templates/super_admin.html: yardım sohbeti fetch çağrısında credentials include kaldırıldı
- admin/templates/partner_base.html: yardım sohbeti fetch çağrısında credentials include kaldırıldı
- admin/templates/base.html: yardım sohbeti fetch çağrısında credentials include kaldırıldı
- support_chat_api: Tenant 1 model önceliği, anahtar yoksa net hata mesajı; middleware api_base; base/partner_base/super_admin supportApiUrl
- base.html, super_admin.html, partner_base.html: Yardım sohbeti alanı büyütüldü (560px/70vh), mesaj satır kaydırma (pre-wrap, word-break)
- docs/YARDIM_SOHBETI_EGITIM.md: İzin Talepleri, Faturalar, Satın Alma modülleri, nasıl yapılır ve SSS eklendi
- integrations/support_chat_api.py: YARDIM_SOHBETI_EGITIM.md yüklenip prompt'a eklendi (_load_help_context güncellendi)
- docs/KULLANIM_KILAVUZU.md: Panel Yardım Sohbeti (Gemini API teknik notu), Yapay Zeka (yardım sohbeti GEMINI_API_KEY) güncellendi

### Az Önce Yapıldı
- support_chat_api.py: Sağ alttaki yardım sohbeti mevcut Gemini API ile çalışacak (GEMINI_API_KEY varsa api_overrides ile zorunlu kullanım)

### Az Önce Yapıldı
- Panel yardım sohbeti: sağ altta AI destekli "Yardım" widget (partner, tenant, super admin)
- POST /api/chat/support, support_chat_api.py, Conversation platform=support
- base.html, partner_base.html, super_admin.html'e widget eklendi

### Az Önce Yapıldı
- integrations/web_chat_api.py: POST /api/chat/web, GET /chat/{slug}
- Admin: Web Sohbet embed kodu sayfası (/admin/settings/web-chat)
- web_chat modülü (modules.py), CORS, ChatHandler platform=web
- docs/KULLANIM_KILAVUZU.md: Web Sohbet bölümü

### Az Önce Yapıldı
- docs/KULLANIM_KILAVUZU.md: Tam kullanım kılavuzu (modül modül, roller, nasıl kullanılır)
- base.html: Mükerrer Entegrasyon Ayarları kaldırıldı - Sosyal Medya menüsü silindi, Pazaryeri/Ödeme/Kargo/Sohbet altındaki tekrarlar kaldırıldı (tek giriş: Genel Ayarlar > Entegrasyonlar)
- Online/offline: User.last_seen, migration 020, middleware'de 60sn throttle ile güncelleme
- partner_users.html: Çevrimiçi/Çevrimdışı badge (5 dk içinde = online)
- Super admin: /admin/super/user-status sayfası, Kullanıcı Durumları linki
- Partner: Kendi kullanıcılarını görme - GET /admin/partner/users, partner_users.html (Firma | Ad | E-posta | Rol | Son giriş), header'a Kullanıcılar linki
- Super admin: Giriş Logu sayfası (/admin/super/login-logs) - AuditLog action=login listesi (e-posta, rol, IP, tarih)
- User.last_login: Migration 019, login başarısında güncelleme (partner_admin, user, login_complete_partner)
- Super admin partner bölümünde admin son giriş zamanı gösterimi
- Partner: Kendi eklediği firmaları silebilme - POST /admin/partner/tenants/{tid}/delete (soft delete), partner_admin.html ve partner_panel.html'de Sil butonu
- V2.md: Asistan yanıt kalitesi bölümü (genel vs firma bazlı eğitim, partner katmanı, sektör şablonları, teknik yaklaşım)
- V2.md: Mevcut yazılım için önerilen eklemeler (güvenlik, veri, test, panel, altyapı) + öncelik sıralaması
- Super admin: Partner admin şifre güncelleme (mevcut e-posta girilirse şifre değişir)
- Super admin: Firma silme (soft delete, status=deleted) - Firmalar kartında Sil butonu
- admin/routes.py: Super admin POST route'larında 401 yerine login'e redirect; _is_super_admin() ile session kontrolü (string "true" uyumluluğu)
- super_admin.html: Partnerlar bölümü düzenlendi - Yeni partner ve Mevcut partnerlar ayrı kartlar
- admin/routes.py: Partner admin eklerken e-posta hata mesajları iyileştirildi (aynı partner / farklı hesap)
- base.html: Super admin tenant seçtiğinde "← Firmalar" linki (aynı stil, yönetime dönüş)
- main.py: SessionMiddleware admin_context'ten ÖNCE çalışacak şekilde sıra değiştirildi - partner_admin session okunabilsin, Partner Yönetimi linki görünsün
- base.html: Partner admin tenant panelindeyken navbar'da "← Partner Yönetimi" linki - Panelim/Panele gir sonrası yönetime dönüş
- middleware/admin_context.py: Tenant panele girildiğinde (tid set) partner_name ve partner_logo_url yükle - Firma Paneli'nde partner ismi görünsün
- admin/routes.py: Super admin partner oluştururken otomatik varsayılan tenant (partner-slug-panel), partner.settings.default_tenant_id
- admin/routes.py: GET /admin/partner/panel - partner'ın varsayılan firmasına gir, /admin/dashboard'a yönlendir (eski partnerlar için lazy oluştur)
- admin/templates/partner_admin.html: Header'a "Panelim" linki eklendi
- Partner paneli: base.html yerine kendi minimal layout'u (Emare/Meridyen menüleri yok) - Defence 360 kendi paneline giriyor
- partner_admin.html, partner_base.html - sadece Firmalarım, Kurumsal Logo, Çıkış
- Partner logo: Partner kendi kurumsal logosunu ekleyebilir (/admin/partner/settings/branding)
- Tenant logo: Her tenant kendi logosunu ekleyebilir - partner "Marka & Logo" ile ayarlayabilir, tenant kullanıcıları Ayarlar > Görünüm & Marka
- partner_branding.html, partner_tenant_branding.html
- base.html: partner_logo_url navbar'da gösterilir
- Partner modül yönetimi: Partner alt tenant'ların hangi modülleri kullanacağını seçebilir (/admin/partner/modules/{tid})
- partner_modules.html, partner_panel.html'de "Modülleri Yönet" butonu
- Partner paneli: Yeni partner oluşturulunca otomatik tam panel (base.html) - Defence 360 Asistan markası, sidebar, Firmalarım
- partner_panel.html: base.html extend, partner'ın kendi paneli
- middleware: partner_admin tid=None iken partner_name yükle (navbar markası)
- remote-update: Sunucu güncellendi; sunucuda test1-test → Defence 360 atandı
- scripts/sync_db_from_server.sh: Lokal DB'yi sunucudan çekme
- scripts/list_tenants_partners.py, setup_defence360.py eklendi
- admin/routes.py: POST /admin/partner/tenants - partner admin kendi müşterisini ekleyebilir
- partner_admin.html: Yeni müşteri ekleme formu, boş durum mesajı güncellendi
- admin/routes.py: Login - partner admin tanıma, session partner_id yazma
- middleware: partner_admin scope, get_tenant_id partner/super fallback düzeltmesi
- admin/partner sayfası + partner/enter/{id} route
- base.html: partner_admin için Firmalarım/Dashboard linkleri
- super_admin: Partnerlar bölümü, partner ekleme, firmayı partner'a atama, partner admin kullanıcı oluşturma
- models/partner.py: Partner modeli oluştur
- models/tenant.py: partner_id FK ekle
- models/user.py: partner_id, is_partner_admin ekle
- alembic/versions/018_partners.py: migration
- middleware/admin_context.py: loginli normal kullanıcıda tenant sadece User.tenant_id (DB) kaynağından çözülüyor; session fallback kaldırıldı
- middleware/admin_context.py: tenant çözülemeyen loginli kullanıcı oturumu temizlenip /admin'e yönlendiriliyor
- services/workflow/proactive.py: conv.tenant_id boşsa tenant 1 fallback kaldırıldı (tenant'siz kayıtlar atlanıyor)
- admin/routes.py: tenant products_path fallback düzeltildi (products_path yoksa Meridyen dosyasına düşmüyor, tenant özel yola gidiyor)
- admin/routes.py: /admin/products DB sayımında tenant filtresi sıkılaştırıldı (non-tenant global ürün sızıntısı kesildi)
- admin/templates/base.html: dropdown hover geri açıldı (mouse ile üzerine gelince açılır)
- admin/templates/base.html: dropdown'lar sadece click ile açılacak şekilde güncellendi; aynı anda tek menü açık kalıyor
- admin/templates/base.html: navbar tenant badge (Meridyen Group #1) kaldırıldı
- admin/routes.py: /admin/t/{slug} tenant mismatch artık session.clear() yapmıyor; dashboard'a uyarı ile yönlendiriyor (401 döngüsü kesildi)
- admin/routes.py: get_tenant_id artık request.state.tenant_id öncelikli (session drift önlendi)
- admin/routes.py: super admin + tenant login başarılarında session.clear() eklendi (eski tenant kalıntısı temizleniyor)
- middleware: tenant_from_url varsa session tenant_id öncelikli (User.tenant_id override edilmez)
- admin/routes.py: Login — tenant_from_url session'a yazılır (URL'den tenant ile girişte)
- admin/routes.py: /admin/api/debug-session teşhis endpoint'i
- scripts/fix_tenant_check.py: User tenant_id kontrol ve düzeltme script'i
- middleware/admin_context.py: Tenant kullanıcı için User.tenant_id birincil kaynak (session yerine DB'den)
- admin/routes.py: admin_login_tenant — session tenant_id ≠ istenen tenant ise session temizle, login form göster (Cihan girişinde Meridyen görünme hatası düzeltildi)
- admin/routes.py: login — expected_tid varsa session tenant_id için onu kullan
- .vscode/settings.json: files.autoSave off, search/watcher exclude genişletildi (data, artifacts)
- .vscode/settings.json: files.autoSave off, search/watcher exclude genişletildi (data, artifacts)
- register.html: ?tenant= ile mevcut firmaya katılma formu (email+şifre)
- DEVAM.md: Tamamlanan maddeler güncellendi (Bridge systemd ✓, badge ID ✓)
- login.html: Üye Ol linki tenant_slug ile /admin/register?tenant=slug
- admin/routes.py: register_page join flow, register_submit join_tenant_slug

---

## Esneklik Hedefi – Entegrasyon Kapsamı

Aşağıdaki kategorilerde mümkün olduğunca çok seçenek sunulmalı. Her biri modül/ayar ile açılıp kapatılabilir.

### Sohbet / Mesajlaşma Araçları
| Platform | Durum | Not |
|----------|--------|-----|
| WhatsApp (QR) | Var | whatsapp-web.js bridge |
| WhatsApp Cloud API | Var | Meta Business |
| Telegram | Var | Bot API |
| Instagram DM | Var | Meta Graph API |
| Facebook Messenger | Plan | Meta Platform |
| Viber | Plan | Rakuten Viber Business |
| LINE | Plan | LINE Messaging API |
| WeChat | Plan | WeChat Official Account (Çin) |
| Signal | Plan | Sınırlı API |
| Discord | Plan | Bot API |
| Slack | Plan | Incoming webhook, Bot |
| Microsoft Teams | Plan | Bot Framework |
| Google Chat | Plan | Chat API |
| Zalo | Plan | Vietnam |
| KakaoTalk | Plan | Güney Kore |

### Sosyal Medya (İçerik / Yayın)
| Platform | Durum | Not |
|----------|--------|-----|
| Facebook Page | Plan | Post, yorum, mesaj |
| Instagram Feed | Plan | Post, story, yorum |
| Twitter/X | Plan | Tweet, DM |
| TikTok | Plan | İş hesabı |
| LinkedIn | Plan | Company page, mesaj |
| YouTube | Plan | Yorum, topluluk |
| Pinterest | Plan | Pin, mesaj |
| Snapchat | Plan | Business |
| Reddit | Plan | Subreddit, mesaj |
| Threads | Plan | Meta |

### Pazaryerleri
| Platform | Durum | Bölge |
|----------|--------|-------|
| Trendyol | Plan | TR |
| Hepsiburada | Plan | TR |
| N11 | Plan | TR |
| Amazon | Plan | Global, TR, EU, US |
| eBay | Plan | Global |
| Etsy | Plan | El yapımı |
| AliExpress | Plan | B2B/B2C |
| Walmart | Plan | US |
| Mercado Libre | Plan | LATAM |
| Shopee | Plan | SEA |
| Lazada | Plan | SEA |
| Cdiscount | Plan | FR |
| Rakuten | Plan | JP, FR |
| Zalando | Plan | EU |
| Otto | Plan | DE/EU |

### Ödeme Kuruluşları
| Sağlayıcı | Durum | Bölge |
|-----------|--------|-------|
| Iyzico | Var | TR |
| PayTR | Plan | TR |
| Param | Plan | TR |
| Stripe | Plan | Global |
| PayPal | Plan | Global |
| Square | Plan | US, JP |
| Adyen | Plan | Global |
| Mollie | Plan | EU |
| Klarna | Plan | EU, US |
| Apple Pay / Google Pay | Plan | Passthrough |
| Papara | Plan | TR |
| Payoneer | Plan | Global |

### Kargo / Lojistik
| Firma | Durum | Bölge |
|-------|--------|-------|
| Yurtiçi Kargo | Var | TR |
| Aras Kargo | Var | TR |
| MNG Kargo | Var | TR |
| PTT Kargo | Plan | TR |
| Sendeo | Plan | TR |
| HepsiJet | Plan | TR |
| Kolay Gelsin | Plan | TR |
| Surat Kargo | Plan | TR |
| UPS | Plan | Global |
| DHL | Plan | Global |
| FedEx | Plan | Global |
| TNT | Plan | EU |
| GLS | Plan | EU |
| DPD | Plan | EU |
| J&T Express | Plan | SEA |
| Cainiao | Plan | Çin/Alibaba |

### CRM / ERP / Diğer
| Tip | Örnekler |
|-----|----------|
| CRM | Salesforce, HubSpot, Zoho, Pipedrive, Monday |
| ERP | SAP, Odoo, Netsuite, Microsoft Dynamics |
| E-ticaret | WooCommerce, Shopify, Magento, PrestaShop |
| Muhasebe | Paraşüt, Logo, Luca, QuickBooks |
| Webhook | Genel (zaten var) |

---

## Son Tamamlananlar (Şubat 2026)

- [x] Soru seçenekleri: Panelden (AI Eğitim) tanımlı; müşteri numara (1,2,3) ile seçim; tenant bazlı quick_reply_options
- [x] Sesli mesaj (STT+TTS): Sesli mesaj → metin (Gemini/Whisper) → AI → sesli yanıt (OpenAI TTS)
- [x] Görünüm & Marka: Ana renk, vurgu rengi, logo (Ayarlar → Görünüm & Marka)
- [x] Chromium çökme önleme: Puppeteer args (--disable-dev-shm-usage, --disable-gpu vb.)
- [x] stop-bridge.sh: Port 3100 ve Chromium süreçlerini durdurma script'i
- [x] index.js sesli mesaj + resim desteği (tek hesap bridge)
- [x] Tenant 6 kuralları ve soru seçenekleri script'leri (load_tenant6_rules.py, load_tenant6_quick_replies.py)
- [x] MD dokümantasyon güncellemesi (README, docs/*, DEPLOY) – programı yansıtır
- [x] WhatsApp "bağlı ama cevap vermiyor" düzeltmeleri: fix_whatsapp.py, run.py env geçişi, bridge log, diagnose endpoint
- [x] Kurum Bazlı Entegrasyon Mimarisi: İş Akışları, Süreç Konfigürasyonu, Entegrasyon Ayarları'na hızlı erişim kartı
- [x] Docs 5 dosyaya sadeleştirildi (01_GENEL_BAKIS, 02_MODUL_VE_ADMIN, 03_SOHBET_VE_AI, 04_TEKNIK_REFERANS, 05_OPERASYON)
- [x] Kargo menüsü firma bazlı alt menüler (Yurtiçi, Aras, MNG, PTT, Surat, UPS, DHL)
- [x] Entegrasyon Ayarları eksik modüller: Stripe, PayPal, Trendyol, Hepsiburada, Amazon, Facebook, Twitter, TikTok, LinkedIn eklendi (module_api_config.py)
- [x] Sosyal Medya sekmesi eklendi (settings_api.html)
- [x] Modül Detayları ilgili gruplar altına taşındı (her sekmede kart içinde details)
- [x] 404 düzeltmesi: Tüm menü linkleri çalışır hale getirildi
- [x] base.html: WhatsApp, Telegram, Instagram, Iyzico, Sosyal Medya, Pazaryerleri, Kargo linkleri mevcut route'lara yönlendirildi
- [x] admin/routes.py: Eski path'ler için redirect route'ları eklendi (whatsapp/connection, telegram, instagram/settings, payment, facebook, twitter, trendyol, yurtici, stripe, paypal vb.)
- [x] Menü yeniden yapılandırması (Sohbet, Sosyal Medya, Satış, İçerik, Pazaryerleri, Ödemeler, Kargo)
- [x] modules.py → modüllere `category` alanı eklendi
- [x] Instagram kanalı (webhook, channel, admin panel)
- [x] base.html tenant branding (data attribute + JS)

---

## Mevcut Menü Yapısı (Güncel)

**Platform bazlı menü** – Tüm linkler çalışır, 404 yok.

```
Dashboard | Firmalar (super admin)

Sohbet Platformları ▾
├── Tüm Sohbetler                    → /admin/conversations ✓
├── WhatsApp ▾
│   ├── Mesajlar & Bağlantı          → /admin/whatsapp ✓
│   └── Ayarlar                      → /admin/settings/api ✓
├── Telegram ▾
│   ├── Mesajlar                     → /admin/conversations?platform=telegram ✓
│   └── Bot & Ayarlar                → /admin/settings/api ✓
├── Instagram ▾
│   ├── Mesajlar                     → /admin/instagram ✓
│   ├── Webhook Kurulum              → /admin/instagram/setup ✓
│   ├── Sohbetler                    → /admin/conversations?platform=instagram ✓
│   └── Ayarlar                      → /admin/settings/api ✓
├── Kişiler                          → /admin/contacts ✓
└── Temsilci Paneli                  → /admin/agent ✓

Sosyal Medya ▾
└── Entegrasyon Ayarları             → /admin/settings/api ✓
   (Facebook, Twitter, TikTok, LinkedIn → yakında)

Satış & Siparişler ▾
├── Siparişler                       → /admin/orders ✓
├── Randevular                       → /admin/appointments ✓
└── İstatistikler                    → /admin/analytics ✓

İçerik Yönetimi ▾
├── Ürünler                          → /admin/products ✓
├── Ürün Galerisi                    → /admin/products/gallery ✓
├── Albümler                         → /admin/albums ✓
└── Videolar                         → /admin/videos ✓

Pazaryerleri ▾
├── Veri Aktarımı                    → /admin/export-templates ✓
└── Entegrasyon Ayarları             → /admin/settings/api ✓
   (Trendyol, Hepsiburada, Amazon → yakında)

Ödeme Sistemleri ▾
├── Iyzico ▾
│   ├── Siparişler & Ödemeler        → /admin/orders ✓
│   └── Ödeme Ayarları               → /admin/settings/api ✓
└── (Stripe, PayPal → yakında)

Kargo & Lojistik ▾
├── Kargo Takibi (Tümü)              → /admin/cargo ✓
├── Firmaya Göre ▾
│   ├── Yurtiçi Kargo                → /admin/cargo/yurtici ✓
│   ├── Aras Kargo                   → /admin/cargo/aras ✓
│   ├── MNG Kargo                    → /admin/cargo/mng ✓
│   ├── PTT Kargo                    → /admin/cargo/ptt ✓
│   ├── Surat Kargo                  → /admin/cargo/surat ✓
│   ├── UPS                          → /admin/cargo/ups ✓
│   └── DHL                          → /admin/cargo/dhl ✓
└── Entegrasyon Ayarları             → /admin/settings/api#module-cargo ✓

Kullanıcı Yönetimi ▾
├── Kullanıcılar                     → /admin/users ✓
├── Temsilci Paneli                  → /admin/agent ✓
└── Hızlı Yanıtlar                   → /admin/quick-replies ✓

AI & Otomasyon ▾
├── Kurallar                         → /admin/rules ✓
├── İş Akışları                      → /admin/workflows ✓
├── Süreç Konfigürasyonu             → /admin/process-config ✓
├── AI Eğitim                        → /admin/training ✓
├── Sohbet Denetimi                  → /admin/chat-audits ✓
├── İzin Talepleri                   → /admin/admin-staff/leaves ✓
├── Faturalar                        → /admin/admin-staff/invoices ✓
└── Satın Alma                       → /admin/admin-staff/purchase-orders ✓

Genel Ayarlar ▾
├── Tüm Ayarlar                      → /admin/settings ✓
├── Hesap Sahibi                     → /admin/settings/account ✓
├── Görünüm & Marka                  → /admin/settings/branding ✓
├── Yapay Zeka                       → /admin/settings/ai ✓
├── Entegrasyonlar                   → /admin/settings/api ✓
├── Veri Aktarımı                    → /admin/export-templates ✓
└── Hatırlatıcılar                   → /admin/reminders ✓
```

**Eski path'ler** (bookmark vb.): whatsapp/connection, telegram, instagram/settings, payment, facebook, twitter, trendyol, yurtici vb. → redirect route ile /admin/settings/api veya ilgili sayfaya yönlendirilir.

---

## Sıradaki Yapılacaklar

### 0. [x] Menü Yeniden Yapılandırması – TAMAMLANDI

**Yapılanlar:**
- [x] Platform bazlı menü (WhatsApp, Telegram, Instagram alt menüleri)
- [x] Sosyal Medya, Pazaryerleri, Ödemeler, Kargo platform grupları
- [x] modules.py category alanları

---

### 0b. [x] 404 Düzeltmesi – Menü Linkleri – TAMAMLANDI

**Yapılanlar:**
- [x] base.html: WhatsApp → Mesajlar & Bağlantı (/admin/whatsapp), Ayarlar (/admin/settings/api)
- [x] base.html: Telegram → Mesajlar (conversations?platform=telegram), Bot & Ayarlar (/admin/settings/api)
- [x] base.html: Instagram → Ayarlar (/admin/settings/api)
- [x] base.html: Iyzico → Siparişler & Ödemeler (/admin/orders), Ödeme Ayarları (/admin/settings/api)
- [x] base.html: Sosyal Medya, Pazaryerleri, Kargo → sadece mevcut linkler, "yakında" notu
- [x] admin/routes.py: Eski path'ler için redirect route'ları (whatsapp/connection, telegram, instagram/settings, payment, facebook, twitter, trendyol, yurtici, stripe, paypal vb.)

---

### 1. [ ] Entegrasyon Altyapısı (Esneklik İçin)

- [ ] **Connector pattern:** Her yeni platform için `integrations/connectors/{platform}.py` benzeri yapı
- [ ] **Tenant API config:** Firma bazlı API key/token saklama (şifreli), `module_api_config` tablosu
- [ ] **Dinamik modül listesi:** `AVAILABLE_MODULES` genişletilebilir, yeni platform eklenince otomatik menü
- [ ] **Webhook/router:** Platform bazlı webhook yönlendirme (`/webhook/{platform}`)

### 1b. [x] Kurum Bazlı Entegrasyon Mimarisi – KISMEN TAMAMLANDI

- [x] **TenantWorkflow, WorkflowStep, ProcessConfig** veri modelleri (`models/tenant_workflow.py`, migration 014)
- [x] **İş Akışı Builder:** Form bazlı Trigger → Action → Condition (`/admin/workflows`)
- [x] **Süreç Konfigürasyonu:** SLA, escalation (`/admin/process-config`)
- [x] **Entegrasyon Ayarları:** İş Akışları & Süreçler hızlı erişim kartı
- [x] **Workflow Engine:** ChatHandler'da workflow çalıştırma (`services/workflow_engine.py`, `chat_handler.py` L151)
- [x] **Drag & Drop UI:** Görsel akış builder (`/admin/workflows/{id}/builder`, Drawflow)

---

### 2. [x] Sohbet Denetimi Panel Butonu – TAMAMLANDI
- [x] `/admin/chat-audits` sayfasında açık/kapalı toggle butonu (super_admin)
- [x] `.env` yerine panelden `CHAT_AUDIT_ENABLED` değiştirme (`data/app_settings.json`)

### 3. [ ] Dokümantasyon
- API dokümantasyonu (Swagger/OpenAPI)
- Tenant onboarding rehberi
- Entegrasyon ekleme rehberi (geliştirici için)

---

### 4. [ ] Test & Kalite
- Kritik flow'lar için test
- Entegrasyon mock/test modu


---

### Yeni: Partner Remote Deploy (Şubat 2026)

- `admin/partner.py`: Küçük admin sub-router eklendi. GET/POST `/admin/partner/deploy` formu ve submit. Başlatılan deploy için PID ve log dosyası kaydedilir.
- `admin/templates/partner_deploy.html`: Panelde form ve başlatma sonrası linkler.
- `admin/partner.py`: `/admin/partner/deploy/log/{tenant_slug}` ve `/admin/partner/deploy/status/{tenant_slug}` JSON endpointleri eklendi (log tail, süreç durumu).

Not: Private key'ler geçici olarak repo içi `deploy_keys/` altına 600 izinle yazılıyor; prod için secrets manager veya transient key akışı önerilir.


---

### 5. [x] Production Hazırlık — TAMAMLANDI
- [x] .env.example güncel (tüm config/settings alanları + opsiyonel Redis, ENCRYPTION_KEY, CRON_SECRET_KEY, SESSION_SECRET_KEY, Netgsm; super admin placeholder)
- [x] Rate limit middleware aktif (IP bazlı, login 10/dk, API 200/dk, webhook 300/dk, genel 120/dk)
- [x] Güvenlik header'ları middleware aktif (X-Frame-Options, XSS, nosniff, Referrer-Policy, Permissions-Policy, HSTS)
- [x] `/health` detaylı (DB, bridge durumu, uptime)
- [ ] Logging ve monitoring (Prometheus/Grafana — isteğe bağlı)

### 6. [x] WhatsApp Bridge Kesintisiz Bağlantı — TAMAMLANDI (Şubat 2026)
- [x] 2sn reconnect (disconnected event)
- [x] Heartbeat 30sn (getState kontrolü, 3 fail → yeniden başlat)
- [x] Mesaj kuyruğu (max 1000, 10dk TTL, 5 retry, exponential backoff)
- [x] Catch-up: bağlantı geldiğinde okunmamış mesajları tara (son 5dk)
- [x] API retry: 3 deneme, exponential backoff (2s→4s→8s)
- [x] Kuyruk drain: her 5sn otomatik kontrol
- [x] Graceful shutdown (SIGTERM/SIGINT)
- [x] Process crash guard (uncaughtException, unhandledRejection)
- [x] Systemd service güçlendirildi (StartLimitBurst, MemoryMax, network-online)

---

## Proje Yapısı (Hızlı Referans)

| Bölüm | Konum |
|-------|-------|
| Admin routes | `admin/routes.py` |
| Ana menü | `admin/templates/base.html` |
| Modül listesi | `services/modules.py` |
| Modül koruması | `main.py` → `_PATH_MODULES` |
| Kanallar (sohbet) | `integrations/channels/` |
| Webhook'lar | `integrations/*_webhook.py` |
| Ayarlar | `config/settings.py` |
| Kargo servisi | `services/cargo_service.py` |

---

## Notlar: API Entegrasyonları Sayfası

- [x] `admin/templates/settings_api.html` sadeleştirildi: sekmeli, kart bazlı ve gereksiz sync/push/test butonları kaldırıldı. (15 Şubat 2026)


## Kullanım

1. Cursor açıldığında bu dosyayı oku
2. "Esneklik Hedefi" bölümünden hedef platformları incele
3. "Sıradaki Yapılacaklar"dan bir madde seç, uygula
4. Tamamladıkça `[x]` işaretle
