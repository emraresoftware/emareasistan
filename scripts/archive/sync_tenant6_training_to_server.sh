#!/bin/bash
# Tenant 6 AI Eğitim verilerini lokaldeki DB'den sunucuya aktar
# Kullanım: ./scripts/sync_tenant6_training_to_server.sh

set -e

REMOTE="root@77.92.152.3"
SSH_PORT="${SSH_PORT:-22}"
REMOTE_DIR="/opt/asistan"
EXPORT_FILE="data/tenant6_training.json"

cd "$(dirname "$0")/.."
ROOT="$(pwd)"

echo "=============================================="
echo "Tenant 6 AI Eğitim → Sunucuya Aktarım"
echo "=============================================="
echo ""

# 1. Lokal export
echo "[1/4] Lokal veritabanından export..."
source venv/bin/activate 2>/dev/null || true
python scripts/export_tenant6_training.py --output "$EXPORT_FILE"
if [ ! -f "$EXPORT_FILE" ]; then
  echo "HATA: Export dosyası oluşturulamadı."
  exit 1
fi
echo "  OK: $(wc -l < "$EXPORT_FILE") satır"
echo ""

# 2. SSH ayarı (scp -P port, ssh -p port)
if [ -f "$HOME/.ssh/asistan_key" ]; then
  SSH_OPTS="-p $SSH_PORT -o StrictHostKeyChecking=no -i $HOME/.ssh/asistan_key"
  SCP_OPTS="-P $SSH_PORT -o StrictHostKeyChecking=no -i $HOME/.ssh/asistan_key"
  SSH_CMD="ssh $SSH_OPTS $REMOTE"
  do_scp() { scp $SCP_OPTS "$1" "$2"; }
else
  if [ -z "$SSHPASS" ]; then
    echo "SSH şifresi girin (gösterilmeyecek):"
    read -s SSHPASS
    export SSHPASS
  fi
  SSH_CMD="sshpass -e ssh -p $SSH_PORT -o StrictHostKeyChecking=no $REMOTE"
  do_scp() { sshpass -e scp -P $SSH_PORT -o StrictHostKeyChecking=no "$1" "$2"; }
fi

# 3. Dosyaları sunucuya kopyala (export + import script)
echo "[2/4] Dosyalar sunucuya kopyalanıyor..."
$SSH_CMD "mkdir -p $REMOTE_DIR/scripts $REMOTE_DIR/data"
do_scp "$EXPORT_FILE" "$REMOTE:$REMOTE_DIR/$EXPORT_FILE"
do_scp "scripts/import_tenant6_training.py" "$REMOTE:$REMOTE_DIR/scripts/import_tenant6_training.py"
echo "  OK"
echo ""

# 4. Sunucuda import
echo "[3/4] Sunucuda import çalıştırılıyor..."
$SSH_CMD "cd $REMOTE_DIR && source venv/bin/activate && python scripts/import_tenant6_training.py $EXPORT_FILE"
echo ""

# 5. Embedding sync (opsiyonel - vector store varsa)
echo "[4/4] Embedding senkronizasyonu (panelden yapılabilir)..."
echo "  Sunucuda /admin/training → 'Embeddingleri Senkronize Et' butonuna tıklayın."
echo ""

echo "=============================================="
echo "✓ Tenant 6 AI Eğitim sunucuya aktarıldı"
echo ""
echo "Admin: http://77.92.152.3:8000/admin"
echo "Tenant 6 ile giriş yapıp AI Eğitim sayfasını kontrol edin."
echo "=============================================="
