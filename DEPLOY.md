# Emare Asistan - Sunucuya Deploy

**Sunucu güvenliği (kod izinleri, .env, isteğe bağlı obfuscation):** [docs/GUVENLIK_SUNUCU.md](docs/GUVENLIK_SUNUCU.md)

## WhatsApp Bridge – Güncellemede Kopmaması

**Önemli:** WhatsApp Bridge, ana API'den **ayrı bir systemd servisi** olarak çalışmalıdır. Böylece `remote-update.sh` sadece API'yi yeniden başlatır; Bridge çalışmaya devam eder, WhatsApp kopmaz.

- `asistan-api` → Port 8000 (API)
- `asistan-whatsapp` → Port 3100 (Bridge, ayrı süreç)

**Sunucuda `run.py` kullanmayın** – hem API hem Bridge aynı süreçte çalışır, güncellemede ikisi de durur.

---

## Gereksinimler

- Docker ve Docker Compose
- Sunucu (VPS): Ubuntu 22.04+ önerilir
- Domain (opsiyonel, SSL için)

## Hızlı Deploy (Docker Compose)

### 1. Projeyi sunucuya kopyala

```bash
# Git ile
git clone <repo-url> asistan
cd asistan

# veya rsync/scp ile mevcut projeyi kopyala
```

### 2. .env dosyasını oluştur

```bash
cp .env.example .env
nano .env  # veya vim
```

**Önemli değişkenler:**

| Değişken | Açıklama | Örnek |
|----------|----------|-------|
| `GEMINI_API_KEY` | Google AI Studio API anahtarı | `AIzaSy...` |
| `OPENAI_API_KEY` | TTS (sesli yanıt) ve Whisper STT için (opsiyonel) | `sk-...` |
| `APP_BASE_URL` | Uygulama public URL | `https://asistan.example.com` |
| `DATABASE_URL` | Docker Compose PostgreSQL kullanır, değiştirmeyin | - |
| `SUPER_ADMIN_EMAIL` | Super admin e-posta | `admin@firma.com` |
| `SUPER_ADMIN_PASSWORD` | Super admin şifre | Güçlü şifre |
| `TELEGRAM_BOT_TOKEN` | Telegram bot (opsiyonel) | - |
| `CHAT_AUDIT_ENABLED` | Sohbet denetimi (AI kalite kontrolü) | `true` / `false` |

### 3. Başlat

```bash
docker compose up -d
```

### 4. Veritabanı migrasyonu

İlk çalıştırmada tablolar otomatik oluşturulur. Gerekirse:

```bash
docker compose exec api python -c "
from models.database import init_db
import asyncio
asyncio.run(init_db())
print('DB hazır')
"
```

### 5. Erişim

- **Admin panel:** http://SUNUCU_IP:8000/admin
- **WhatsApp QR:** http://SUNUCU_IP:3100
- **API docs:** http://SUNUCU_IP:8000/docs

---

## Nginx + SSL (Önerilen)

Domain varsa HTTPS için Nginx reverse proxy:

```nginx
# /etc/nginx/sites-available/asistan
server {
    listen 80;
    server_name asistan.example.com;
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name asistan.example.com;

    ssl_certificate /etc/letsencrypt/live/asistan.example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/asistan.example.com/privkey.pem;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}

# WhatsApp Bridge - QR için ayrı port veya subdomain
server {
    listen 443 ssl http2;
    server_name qr.asistan.example.com;

    ssl_certificate /etc/letsencrypt/live/asistan.example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/asistan.example.com/privkey.pem;

    location / {
        proxy_pass http://127.0.0.1:3100;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
    }
}
```

`.env` güncelle:
```
APP_BASE_URL=https://asistan.example.com
WHATSAPP_BRIDGE_URL=https://qr.asistan.example.com
```

---

## Sadece API (WhatsApp Bridge olmadan)

WhatsApp QR kullanmayacaksan, sadece API + Postgres + Redis:

```bash
# docker-compose.yml'dan whatsapp-bridge servisini kaldır veya
docker compose up -d api postgres redis
```

Cloud API webhook kullanıyorsan bridge gerekmez.

---

## Güncelleme

### Hızlı güncelleme (update.sh)

```bash
# Kod çekildikten veya dosyalar yüklendikten sonra
./update.sh
```

Script otomatik olarak:
- Python bağımlılıklarını günceller
- `alembic upgrade head` çalıştırır
- Docker kullanıyorsa API ve Bridge'i yeniden başlatır
- Yerel çalışıyorsa WhatsApp Bridge npm install yapar

### Docker ile (manuel)

```bash
git pull
docker compose build --no-cache
docker compose up -d
# Migration:
docker compose exec api python -m alembic upgrade head
docker compose restart api whatsapp-bridge
```

### Uzak sunucu güncelleme (remote-update.sh)

Kod, bağımlılıklar, DB migration ve **sadece API** servisini günceller:

```bash
./remote-update.sh
```

**Önemli:** WhatsApp Bridge **yeniden başlatılmaz** – güncellemede WhatsApp kopmasın. Bridge ayrı systemd servisi olarak çalışır.

**Gereksinim:** SSH key (`~/.ssh/asistan_key`) veya `sshpass` ile şifre. Hedef: `root@77.92.152.3`, `/opt/asistan`.

### Systemd servis kurulumu (ilk kurulumda)

Bridge'in ayrı servis olarak çalışması için:

```bash
# Uzak sunucuda veya deploy sonrası
cd /opt/asistan
sudo bash deploy/install-services.sh
systemctl start asistan-api asistan-whatsapp
```

Veya `deploy.sh` ile otomatik kurulum yapılır.

### WhatsApp Bridge güncelleme (sadece bridge değiştiğinde)

Bridge kodunda değişiklik yaptıysanız ve güncellemek istiyorsanız (WhatsApp birkaç saniye kopar):

```bash
./deploy/update-bridge.sh
```

Bu script bridge'i yeniden başlatır. Normal `remote-update.sh` bridge'e dokunmaz.

### Dosya yüklemesi sonrası (rsync/scp ile)

Sunucuya dosyaları elle yüklediyseniz, veritabanı ve servisleri güncelleyin:

```bash
# Sunucuya bağlan
ssh root@SUNUCU_IP

cd /opt/asistan

# 1. Veritabanı migration (yeni tablolar / sütunlar)
source venv/bin/activate
alembic upgrade head

# 2. Sadece API yeniden başlat (Bridge kopmasın)
systemctl restart asistan-api
# Bridge: ./deploy/update-bridge.sh ile güncellenir
```

**Not:** `alembic upgrade head` hata verirse (örn. mevcut SQLite tabloları varsa):
```bash
alembic stamp 001
alembic upgrade head
```

**Docker kullanıyorsanız:**
```bash
docker compose exec api python -m alembic upgrade head
docker compose restart api
docker compose restart whatsapp-bridge  # varsa
```

---

## Sorun Giderme

**Port kullanımda / Chromium çökmesi:**
```bash
# WhatsApp Bridge: Port 3100 ve Chromium süreçlerini durdur
cd whatsapp-bridge && ./stop-bridge.sh
node index-multi.js  # veya node index.js
```

**Port 8000 kullanımda:**
```bash
lsof -i :8000
# Durdur veya docker-compose.yml'da port değiştir
```

**WhatsApp Bridge bağlanamıyor:**
- Chromium Docker'da bazen sorun çıkarır
- Alternatif: Bridge'i sunucuda ayrı çalıştır: `cd whatsapp-bridge && npm start`

**Veritabanı sıfırlama:**
```bash
docker compose down -v  # Tüm volume'ları siler!
docker compose up -d
```
