# Hata Ayıklama Günlüğü

---

## [2026-03-03] WhatsApp Bridge connection_id=34 → "Teknik Gecikme" Sorunu

### Belirti
WhatsApp'tan gelen mesajlara AI yanıt vermiyordu. Her mesaja **134 karakter** sabit bir yanıt geliyordu: _"Su anda teknik bir gecikme yasiyoruz..."_

Bridge loglarında:
```
[34] Mesaj alındı: merhaba
[34] Yanıt gönderildi (134 karakter)
```

---

### Kök Neden — 3 Katmanlı Sorun

#### 1. connection_id=34 DB'de Yoktu
Bridge, hafızasında `connection_id=34` (telefon: 908502653673) ile aktif bir WhatsApp oturumu tutuyordu. Ancak **`whatsapp_connections` tablosunda bu ID mevcut değildi** (max ID=30).

Akış:
```
Bridge → POST /api/whatsapp/process {connection_id: 34}
whatsapp_qr.py → DB'de id=34 yok → conn=None
tenant_id = 1 (varsayılan, Meridyen Group)
```

#### 2. Tenant 1'in DB Ayarlarında Gemini API Anahtarı Yoktu
Önceki oturumda tenant 1'in `settings` JSON'undaki `gemini_api_key` silinmişti. Fallback mekanizması da `tenant_id != 1` koşuluna takılıyordu:

```python
# ESKİ (HATALI)
if not api_overrides.get("gemini_api_key") and ... and tenant_id != 1:
    emare = await get_tenant_settings(1)  # tenant 1 = boş anahtar → döngü
```

#### 3. chat_handler.py'daki Fallback Yanlış Tenant'ı Gösteriyordu
Fallback `tenant_id=1`'e bakıyordu ama asıl anahtar `tenant_id=2` (Emare Asistan) DB'sindeydi.

---

### Yapılan Düzeltmeler

#### Düzeltme 1 — DB'ye connection 32 ve 34 Eklendi
```python
# /opt/asistan/asistan.db
INSERT INTO whatsapp_connections
  (id, tenant_id, name, phone_number, status, is_active, auth_path)
VALUES
  (34, 2, 'Emare Ana Hat', '908502653673', 'connected', 1, 'conn_9080efc1'),
  (32, 2, 'Emare Yedek Hat', NULL, 'idle', 1, 'conn_cfd6cef7');
```
auth_path tespiti: `/opt/asistan/whatsapp-bridge/` içinde en son değiştirilen `.wwebjs_auth_conn_9080efc1` (Mar 3 16:16) aktif oturuma aitti.

#### Düzeltme 2 — chat_handler.py Fallback Düzeltildi
`integrations/chat_handler.py` satır 382–384:

```python
# ESKİ
if not api_overrides.get("gemini_api_key") and not api_overrides.get("openai_api_key") and tenant_id != 1:
    emare = await get_tenant_settings(1)

# YENİ
if not api_overrides.get("gemini_api_key") and not api_overrides.get("openai_api_key"):
    emare = await get_tenant_settings(2)
```

Değişiklikler:
- `tenant_id != 1` koşulu kaldırıldı → tüm tenant'lar için fallback çalışır
- `get_tenant_settings(1)` → `get_tenant_settings(2)` → gerçek Gemini anahtarının bulunduğu tenant

#### Düzeltme 3 — asistan-api Yeniden Başlatıldı
```bash
systemctl restart asistan-api
```

---

### Doğrulama
```bash
curl -X POST http://127.0.0.1:8000/api/whatsapp/process \
  -H 'Content-Type: application/json' \
  -d '{"connection_id": 34, "from": "905551234567@c.us", "text": "merhaba test"}'
# Yanıt: Gerçek Gemini yanıtı (Emare Asistan tanıtımı) ✓
```

---

### Öğrenilenler

| Kontrol Noktası | Açıklama |
|---|---|
| Bridge bağlantı ID'leri | Bridge, container restart'ta API'den yüklediği ID'leri hafızada tutar. DB temizlenirse ID uyuşmazlığı oluşur. |
| Tenant ayarları önceliği | `tenant.settings.gemini_api_key` > systemd env > `.env` — DB'deki tenant ayarları her şeyi ezer. |
| auth_path tespiti | `ls -la /opt/asistan/whatsapp-bridge/` → en son değiştirilen `.wwebjs_auth_*` = aktif oturum |
| Fallback mantığı | Fallback `tenant_id != 1` gibi hard-coded ID kontrolü içermemeli; tüm tenant'lar kapsanmalı. |

---

## Önceki Sorunlar

### [2026-03-03] Gemini API Anahtarı Güncelleme Süreci

**Sorun:** Yeni Gemini anahtarı (`AIzaSyCfrVLGK3LE4F7rMA-7Q27HLH5pNZL53i8`) verildi, ancak AI hâlâ çalışmadı.

**Kök Nedenler:**
1. `.env` dosyasında anahtar güncellendi, ancak systemd servisi `.env` okumuyordu → `EnvironmentFile=` eklendi
2. `tenants.settings` JSON sütununda eski anahtar (`AIzaSyChQoHb8bH9AwdFU3qXPUcEQ8PYJz25pHU`) hardcoded saklanıyordu ve `.env`'i eziyordu
3. `gemini-2.0-flash` modeli ücretsiz katmanda kota=0 → `gemini-2.5-flash-lite` olarak değiştirildi

**Çözülen Dosyalar:**
- `/opt/asistan/.env` — yeni anahtar
- `/etc/systemd/system/asistan-api.service` — `Environment=` ve `EnvironmentFile=` satırları eklendi
- `services/ai/assistant.py`, `services/trendyol/questions.py`, `services/whatsapp/audit.py`, `integrations/support_chat_api.py`, `services/chat_audit_service.py` — model adı düzeltildi
- `asistan.db` → tenant 1 settings: anahtar silindi; tenant 2: yeni anahtar eklendi
