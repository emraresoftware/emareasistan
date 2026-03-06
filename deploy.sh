#!/bin/bash
# Emare Asistan - SSH ile uzak sunucuya deploy
# Kullanım: ./deploy.sh

set -e

REMOTE="root@77.92.152.3"
SSH_PORT="22"
REMOTE_DIR="/opt/asistan"
SSH_OPTS="-p $SSH_PORT -o StrictHostKeyChecking=no -i ~/.ssh/asistan_key"

echo "=== Emare Asistan Deploy ==="
echo "Hedef: $REMOTE (port $SSH_PORT)"
echo ""

# 1. Dosyaları kopyala (venv, .env, __pycache__ hariç)
echo "[1/4] Dosyalar kopyalanıyor..."
rsync -avz --progress -e "ssh $SSH_OPTS" \
  --exclude 'venv/' \
  --exclude '.venv/' \
  --exclude '.env' \
  --exclude '__pycache__/' \
  --exclude '*.pyc' \
  --exclude '.wwebjs_auth/' \
  --exclude '.wwebjs_auth_conn*/' \
  --exclude '.wwebjs_cache/' \
  --exclude '*.db' \
  --exclude 'uploads/' \
  --exclude '.git/' \
  --exclude '.pytest_cache/' \
  --exclude 'node_modules/' \
  ./ "$REMOTE:$REMOTE_DIR/"

# 2. Sunucuda dosya izinleri (güvenlik: kod ve .env sadece yetkili okusun)
echo ""
echo "[2/5] Sunucuda dosya izinleri ayarlanıyor..."
ssh $SSH_OPTS "$REMOTE" "chmod -R 750 $REMOTE_DIR 2>/dev/null; test -f $REMOTE_DIR/.env && chmod 600 $REMOTE_DIR/.env; echo 'İzinler OK'"

# 3. Sunucuda kurulum ve başlatma
echo ""
echo "[3/5] Sunucuda kurulum yapılıyor..."
ssh $SSH_OPTS "$REMOTE" bash -s << 'REMOTE_SCRIPT'
set -e
cd /opt/asistan

# Python ve Node kurulu mu kontrol et
if ! command -v python3 &> /dev/null; then
  echo "Python3 kurulu değil. Yükleniyor..."
  apt-get update && apt-get install -y python3 python3-pip python3-venv
fi
# Ubuntu 24.04: python3.12-venv gerekli (ensurepip)
apt-get install -y -qq python3.12-venv 2>/dev/null || apt-get install -y -qq python3-venv 2>/dev/null || true

if ! command -v node &> /dev/null; then
  echo "Node.js kurulu değil. Yükleniyor..."
  curl -fsSL https://deb.nodesource.com/setup_20.x | bash -
  apt-get install -y nodejs
fi

# Python venv kurulumu
if [ ! -d "venv" ]; then
  python3 -m venv venv
fi
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

# WhatsApp bridge
cd whatsapp-bridge
npm install
cd ..

# Alembic migration (audit_logs vb.)
cd /opt/asistan && source venv/bin/activate
if ! alembic upgrade head 2>/dev/null; then
  alembic stamp 001 2>/dev/null || true
  alembic upgrade head 2>/dev/null || true
fi

# Sadece API yeniden başlat (Bridge kopmasın - ayrı servis)
systemctl restart asistan-api 2>/dev/null || true
# systemctl restart asistan-whatsapp  # Bridge sadece update-bridge.sh ile güncellenir

echo "Kurulum tamamlandı."
REMOTE_SCRIPT

# 3. .env dosyası kontrolü
echo ""
echo "[4/5] .env kontrolü..."
ssh $SSH_OPTS "$REMOTE" "test -f $REMOTE_DIR/.env || echo 'UYARI: .env dosyası yok! Sunucuda .env oluşturun.'"

# 4. Systemd servisleri oluştur (ayrı - güncellemede WhatsApp kopmaz)
echo ""
echo "[5/5] Servis kurulumu (API + Bridge ayrı)..."
ssh $SSH_OPTS "$REMOTE" "cd /opt/asistan && bash deploy/install-services.sh 2>/dev/null || bash -s" << 'SERVICES'
cd /opt/asistan
INSTALL_DIR=/opt/asistan
# API servisi
cat > /etc/systemd/system/asistan-api.service << EOF
[Unit]
Description=Emare Asistan API
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=$INSTALL_DIR
ExecStart=$INSTALL_DIR/venv/bin/uvicorn main:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=5
Environment=PATH=$INSTALL_DIR/venv/bin:/usr/bin

[Install]
WantedBy=multi-user.target
EOF
# WhatsApp Bridge servisi (AYRI - güncellemede kopmaz)
cat > /etc/systemd/system/asistan-whatsapp.service << EOF
[Unit]
Description=Emare Asistan WhatsApp Bridge (ayrı servis)
After=network.target asistan-api.service

[Service]
Type=simple
User=root
WorkingDirectory=$INSTALL_DIR/whatsapp-bridge
Environment=ASISTAN_API_URL=http://127.0.0.1:8000
ExecStart=/usr/bin/npm start
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF
systemctl daemon-reload
systemctl enable asistan-api asistan-whatsapp
echo "Servisler oluşturuldu. Başlatmak için:"
echo "  systemctl start asistan-api asistan-whatsapp"
echo "  systemctl status asistan-api asistan-whatsapp"
SERVICES

echo ""
echo "=== Deploy tamamlandı ==="
echo ""
echo "Sunucuda yapmanız gerekenler:"
echo "  1. ssh root@77.92.152.3"
echo "  2. cd /opt/asistan && cp .env.example .env"
echo "  3. nano .env  # API anahtarlarını, TELEGRAM_BOT_TOKEN vb. girin"
echo "  4. systemctl start asistan-api asistan-whatsapp"
echo "  5. systemctl enable asistan-api asistan-whatsapp  # Otomatik başlatma"
echo ""
echo "WhatsApp QR: http://77.92.152.3:3100"
echo "Admin panel: http://77.92.152.3:8000/admin"
echo ""
