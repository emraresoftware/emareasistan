#!/bin/bash
# Sunucudan verileri lokale çek (DB + data/tenants + uploads) — lokalle sunucu aynı olsun
# Kullanım: ./scripts/sync_db_from_server.sh
# Sadece DB: ./scripts/sync_db_from_server.sh db

set -e
REMOTE="${REMOTE:-root@77.92.152.3}"
REMOTE_DIR="${REMOTE_DIR:-/opt/asistan}"
SCRIPT_DIR="$(dirname "$0")"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
LOCAL_DB="$PROJECT_DIR/asistan.db"
REMOTE_DB="$REMOTE_DIR/asistan.db"

if [ -f "$HOME/.ssh/asistan_key" ]; then
  SSH_OPTS="-o StrictHostKeyChecking=no -i $HOME/.ssh/asistan_key"
else
  SSH_OPTS="-o StrictHostKeyChecking=no"
fi

echo "[1/3] Sunucudan DB çekiliyor..."
if ssh $SSH_OPTS "$REMOTE" "test -f $REMOTE_DB" 2>/dev/null; then
  scp $SSH_OPTS "$REMOTE:$REMOTE_DB" "$LOCAL_DB"
else
  echo "  UYARI: Sunucuda $REMOTE_DB bulunamadı."
  exit 1
fi
echo "  OK: $LOCAL_DB"

if [ "${1:-}" = "db" ]; then
  echo "Sadece DB çekildi (uploads/data atlandı)."
  exit 0
fi

echo "[2/3] data/tenants çekiliyor..."
mkdir -p "$PROJECT_DIR/data"
rsync -avz -e "ssh $SSH_OPTS" "$REMOTE:$REMOTE_DIR/data/" "$PROJECT_DIR/data/" --delete
echo "  OK: data/"

echo "[3/3] uploads çekiliyor..."
mkdir -p "$PROJECT_DIR/uploads"
rsync -avz -e "ssh $SSH_OPTS" "$REMOTE:$REMOTE_DIR/uploads/" "$PROJECT_DIR/uploads/" --delete
echo "  OK: uploads/"

echo "Bitti. Lokal ile sunucu verileri aynı."
