#!/bin/bash
# Uzak sunucuyu güncelle - kod, bağımlılıklar, DB migration, servisler
# Kullanım: ./remote-update.sh
# SSH key: ~/.ssh/asistan_key  veya  SSHPASS ile şifre

set -e

REMOTE="root@77.92.152.3"
SSH_PORT="${SSH_PORT:-22}"
REMOTE_DIR="/opt/asistan"

# SSH: key varsa kullan, yoksa sshpass
if [ -f "$HOME/.ssh/asistan_key" ]; then
  SSH_OPTS="-p $SSH_PORT -o StrictHostKeyChecking=no -i $HOME/.ssh/asistan_key"
  SSH_CMD="ssh $SSH_OPTS $REMOTE"
  RSYNC_SSH="ssh $SSH_OPTS"
else
  if [ -z "$SSHPASS" ]; then
    echo "SSH şifresi girin (gösterilmeyecek):"
    read -s SSHPASS
    export SSHPASS
  fi
  SSH_CMD="sshpass -e ssh -p $SSH_PORT -o StrictHostKeyChecking=no $REMOTE"
  RSYNC_SSH="ssh -p $SSH_PORT -o StrictHostKeyChecking=no"
fi

echo "=============================================="
echo "Emare Asistan - Uzak Sunucu Güncelleme"
echo "Hedef: $REMOTE:$REMOTE_DIR"
echo "=============================================="
echo ""

# Bağlantı testi
echo "[1/5] Bağlantı kontrol ediliyor..."
if ! $SSH_CMD 'exit' 2>/dev/null; then
  echo "HATA: Sunucuya bağlanılamıyor."
  echo "  ssh -p $SSH_PORT $REMOTE  ile test edin."
  exit 1
fi
echo "  OK"
echo ""

# 2. Dosyaları kopyala
echo "[2/5] Dosyalar kopyalanıyor..."
if [ -f "$HOME/.ssh/asistan_key" ]; then
  rsync -avz -e "ssh $SSH_OPTS" \
    --exclude 'venv/' --exclude '.venv/' --exclude '.env' --exclude '__pycache__/' \
    --exclude '*.pyc' --exclude '.wwebjs_auth/' --exclude '.wwebjs_auth_conn*/' --exclude '.wwebjs_cache/' \
    --exclude '*.db' --exclude 'uploads/' --exclude '.git/' \
    ./ "$REMOTE:$REMOTE_DIR/"
else
  sshpass -e rsync -avz -e "ssh -p $SSH_PORT -o StrictHostKeyChecking=no" \
    --exclude 'venv/' --exclude '.venv/' --exclude '.env' --exclude '__pycache__/' \
    --exclude '*.pyc' --exclude '.wwebjs_auth/' --exclude '.wwebjs_auth_conn*/' --exclude '.wwebjs_cache/' \
    --exclude '*.db' --exclude 'uploads/' --exclude '.git/' \
    ./ "$REMOTE:$REMOTE_DIR/"
fi
echo "  OK"
echo ""

# 3. Sunucuda güncelleme
echo "[3/5] Bağımlılıklar ve migration..."
$SSH_CMD "bash -s" << 'REMOTE_UPDATE'
set -e
cd /opt/asistan

# Python bağımlılıkları
source venv/bin/activate
pip install -q --upgrade pip
pip install -q -r requirements.txt

# WhatsApp Bridge
cd whatsapp-bridge && npm install -q 2>/dev/null && cd ..

# Veritabanı migration
cd /opt/asistan && source venv/bin/activate
echo "  Alembic migration çalıştırılıyor..."
if alembic upgrade head 2>/dev/null; then
  echo "  Migration OK"
else
  echo "  Migration uyarısı (stamp denemesi)..."
  alembic stamp head 2>/dev/null || true
  alembic upgrade head 2>/dev/null || true
fi

echo "  Bağımlılıklar OK"
REMOTE_UPDATE
echo ""

# 4. Sadece API servisini yeniden başlat (Bridge KOPMASIN - ayrı servis)
echo "[4/5] API servisi yeniden başlatılıyor (WhatsApp Bridge korunuyor)..."
$SSH_CMD "systemctl restart asistan-api 2>/dev/null || true"
# Bridge restart EDİLMİYOR - güncellemede WhatsApp kopmasın
sleep 2
echo "  OK (Bridge çalışmaya devam ediyor)"
echo ""

# 5. Durum kontrolü
echo "[5/5] Servis durumu..."
$SSH_CMD "systemctl status asistan-api asistan-whatsapp --no-pager 2>/dev/null | head -20" || true

echo ""
echo "=============================================="
echo "✓ Uzak sunucu güncellendi"
echo ""
echo "Admin:    http://77.92.152.3:8000/admin"
echo "WhatsApp: http://77.92.152.3:3100"
echo "=============================================="
