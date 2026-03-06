#!/bin/bash
# WhatsApp Bridge'i güncelle ve yeniden başlat
# NOT: Bu script bridge'i yeniden başlatır - WhatsApp birkaç saniye kopar.
# Sadece bridge kodunda değişiklik olduğunda çalıştırın.
# normal remote-update.sh bridge'i yeniden başlatmaz (kopma olmasın diye).

set -e

REMOTE="${REMOTE:-root@77.92.152.3}"
SSH_PORT="${SSH_PORT:-22}"
REMOTE_DIR="/opt/asistan"

if [ -f "$HOME/.ssh/asistan_key" ]; then
  SSH_OPTS="-p $SSH_PORT -o StrictHostKeyChecking=no -i $HOME/.ssh/asistan_key"
  SSH_CMD="ssh $SSH_OPTS $REMOTE"
else
  if [ -z "$SSHPASS" ]; then
    echo "SSH şifresi girin (gösterilmeyecek):"
    read -s SSHPASS
    export SSHPASS
  fi
  SSH_CMD="sshpass -e ssh -p $SSH_PORT -o StrictHostKeyChecking=no $REMOTE"
fi

echo "=============================================="
echo "WhatsApp Bridge Güncelleme"
echo "UYARI: Bridge yeniden başlayacak, WhatsApp birkaç sn kopabilir."
echo "=============================================="

$SSH_CMD "cd $REMOTE_DIR/whatsapp-bridge && npm install -q 2>/dev/null; systemctl restart asistan-whatsapp"
sleep 2
$SSH_CMD "systemctl status asistan-whatsapp --no-pager | head -10"

echo ""
echo "✓ Bridge güncellendi ve yeniden başlatıldı."
