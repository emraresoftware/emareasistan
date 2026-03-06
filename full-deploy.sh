#!/bin/bash
# Tam otomatik deploy - sshpass ile
# Kullanım: ./full-deploy.sh  (şifre sorar)
# Port 22 denemek için: SSH_PORT=22 ./full-deploy.sh

set -e

REMOTE="root@77.92.152.3"
SSH_PORT="${SSH_PORT:-22}"
REMOTE_DIR="/opt/asistan"

if [ -z "$SSHPASS" ]; then
  echo "Şifre girin (gösterilmeyecek):"
  read -s SSHPASS
  export SSHPASS
fi

echo "=== Emare Asistan - Tam Deploy ==="
echo "Hedef: $REMOTE (port $SSH_PORT)"
echo ""

# Bağlantı testi
echo "Bağlantı kontrol ediliyor..."
if ! sshpass -e ssh -p $SSH_PORT -o StrictHostKeyChecking=no -o ConnectTimeout=15 $REMOTE 'exit' 2>/dev/null; then
  echo ""
  echo "HATA: Sunucuya bağlanılamıyor (port $SSH_PORT)."
  echo ""
  echo "Kontrol edin:"
  echo "  1. Sunucu açık mı?"
  echo "  2. Hosting panelindeki firewall (güvenlik duvarı) - port $SSH_PORT açık olmalı"
  echo "  3. Varsayılan SSH portu deneyin: SSH_PORT=22 ./full-deploy.sh"
  echo "  4. Manuel test: ssh -p $SSH_PORT root@77.92.152.3"
  echo ""
  exit 1
fi
echo "Bağlantı OK"
echo ""

# 1. Dosyaları kopyala
echo "[1/5] Dosyalar kopyalanıyor..."
sshpass -e rsync -avz -e "ssh -p $SSH_PORT -o StrictHostKeyChecking=no" \
  --exclude 'venv/' --exclude '.env' --exclude '__pycache__/' \
  --exclude '*.pyc' --exclude '.wwebjs_auth/' --exclude '.wwebjs_auth_conn*/' --exclude '.wwebjs_cache/' --exclude '*.db' \
  --exclude 'uploads/' --exclude '.git/' \
  ./ "$REMOTE:$REMOTE_DIR/"

# 2. Dosya izinleri (güvenlik)
echo "[2/6] Dosya izinleri ayarlanıyor..."
sshpass -e ssh -p $SSH_PORT -o StrictHostKeyChecking=no -o ConnectTimeout=10 $REMOTE "chmod -R 750 $REMOTE_DIR 2>/dev/null; test -f $REMOTE_DIR/.env && chmod 600 $REMOTE_DIR/.env; echo 'İzinler OK'"

# 3. Firewall - ÖNCE SSH portunu aç (ufw enable'dan önce!)
echo "[3/6] Firewall ayarlanıyor..."
sshpass -e ssh -p $SSH_PORT -o StrictHostKeyChecking=no -o ConnectTimeout=15 $REMOTE 'ufw allow 22/tcp; ufw allow 8000/tcp; ufw allow 3100/tcp; ufw --force enable 2>/dev/null; ufw reload 2>/dev/null; echo "Firewall OK"'

# 4. Bağımlılıklar
echo "[4/6] Bağımlılıklar yükleniyor..."
sshpass -e ssh -p $SSH_PORT -o StrictHostKeyChecking=no -o ConnectTimeout=30 $REMOTE 'bash -s' << 'DEPS'
set -e
cd /opt/asistan
apt-get install -y -qq python3.12-venv 2>/dev/null || true
[ ! -d venv ] && python3 -m venv venv
source venv/bin/activate
pip install -q --upgrade pip
pip install -q -r requirements.txt
cd whatsapp-bridge && npm install -q && cd ..
echo "Bağımlılıklar OK"
DEPS

# 5. .env ve APP_BASE_URL
echo "[5/6] .env ayarlanıyor..."
sshpass -e ssh -p $SSH_PORT -o StrictHostKeyChecking=no -o ConnectTimeout=15 $REMOTE "cd $REMOTE_DIR && test -f .env || cp .env.example .env; sed -i 's|APP_BASE_URL=.*|APP_BASE_URL=http://77.92.152.3:8000|' .env 2>/dev/null || true"

# 6. Chrome (Puppeteer) kurulumu ve servisler
echo "[6/6] Chrome ve servisler kuruluyor..."
sshpass -e ssh -p $SSH_PORT -o StrictHostKeyChecking=no -o ConnectTimeout=60 $REMOTE 'bash -s' << 'SERVICES'
set -e
cd /opt/asistan

# Systemd servisleri
cat > /etc/systemd/system/asistan-api.service << 'EOF'
[Unit]
Description=Emare Asistan API
After=network.target
[Service]
Type=simple
User=root
WorkingDirectory=/opt/asistan
ExecStart=/opt/asistan/venv/bin/uvicorn main:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=5
Environment=PATH=/opt/asistan/venv/bin:/usr/bin
[Install]
WantedBy=multi-user.target
EOF

cat > /etc/systemd/system/asistan-whatsapp.service << 'EOF'
[Unit]
Description=Emare Asistan WhatsApp Bridge
After=network.target
[Service]
Type=simple
User=root
WorkingDirectory=/opt/asistan/whatsapp-bridge
ExecStart=/usr/bin/npm start
Restart=always
RestartSec=5
[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable asistan-api asistan-whatsapp
systemctl restart asistan-api asistan-whatsapp

# Chrome (Puppeteer) - arka planda
cd whatsapp-bridge
npx puppeteer browsers install chrome 2>/dev/null &
cd ..

sleep 3
systemctl status asistan-api asistan-whatsapp --no-pager | head -20
echo "Servisler OK"
SERVICES

echo ""
echo "=== Deploy tamamlandı ==="
echo ""
echo "Admin: http://77.92.152.3:8000/admin"
echo "WhatsApp QR: http://77.92.152.3:3100"
echo ""
echo ".env dosyasında GEMINI_API_KEY ve TELEGRAM_BOT_TOKEN girin, sonra:"
echo "  systemctl restart asistan-api asistan-whatsapp"
echo ""
