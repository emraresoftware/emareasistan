#!/bin/bash
# Sunucuda yazılım neden çalışmıyor? Bu script SSH ile bağlanıp kontrol eder.
# Kullanım: ./scripts/check-server.sh
# SSH: REMOTE ve SSH_OPTS remote-update.sh ile aynı (asistan_key veya SSHPASS)

set -e

REMOTE="${REMOTE:-root@77.92.152.3}"
SSH_PORT="${SSH_PORT:-22}"
REMOTE_DIR="${REMOTE_DIR:-/opt/asistan}"

if [ -f "$HOME/.ssh/asistan_key" ]; then
  SSH_OPTS="-p $SSH_PORT -o StrictHostKeyChecking=no -i $HOME/.ssh/asistan_key"
  SSH_CMD="ssh $SSH_OPTS $REMOTE"
else
  [ -n "$SSHPASS" ] || { echo "SSHPASS ayarlı değil veya: ssh -p $SSH_PORT $REMOTE"; exit 1; }
  SSH_CMD="sshpass -e ssh -p $SSH_PORT -o StrictHostKeyChecking=no $REMOTE"
fi

echo "=============================================="
echo "Sunucu sağlık kontrolü: $REMOTE"
echo "=============================================="
echo ""

echo "--- 1. Servis durumu ---"
$SSH_CMD "systemctl is-active asistan-api 2>/dev/null || echo 'asistan-api: yok/hatalı'; systemctl is-active asistan-whatsapp 2>/dev/null || echo 'asistan-whatsapp: yok/hatalı'"
echo ""

echo "--- 2. API son log (son 30 satır) ---"
$SSH_CMD "journalctl -u asistan-api -n 30 --no-pager 2>/dev/null || echo 'journalctl erişilemedi'"
echo ""

echo "--- 3. Health check (localhost:8000) ---"
$SSH_CMD "curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:8000/health 2>/dev/null || echo 'curl hatası'"
echo ""
echo ""

echo "--- 4. Migration durumu ---"
$SSH_CMD "cd $REMOTE_DIR && (test -f venv/bin/activate && source venv/bin/activate; alembic current 2>/dev/null) || echo 'alembic yok/hatalı'"
echo ""

echo "--- 5. Port 8000 dinleniyor mu? ---"
$SSH_CMD "ss -tlnp 2>/dev/null | grep 8000 || netstat -tlnp 2>/dev/null | grep 8000 || echo '8000 dinlenmiyor'"
echo ""

echo "=============================================="
echo "Öneriler:"
echo "  - API failed ise: ssh ... 'journalctl -u asistan-api -n 100' ile hatayı inceleyin."
echo "  - Migration eksikse: ./remote-update.sh ile güncelleyin (alembic upgrade head çalışır)."
echo "  - Servis yoksa: sunucuda 'bash deploy/install-services.sh' veya ./deploy.sh"
echo "=============================================="
