#!/usr/bin/env bash
# Remote deploy helper
# Usage:
# ./scripts/remote_deploy_tenant.sh \ 
#   --host partner.example.com \ 
#   --user deploy \ 
#   --key ~/.ssh/id_rsa_partner \ 
#   --tenant acme \ 
#   --api-port 8000 --bridge-port 3100 --ssh-port 2222

set -euo pipefail

usage(){
  echo "Usage: $0 --host HOST --user USER --key KEY_PATH --tenant TENANT [--api-port N] [--bridge-port N]"
  exit 2
}

HOST=""
USER=""
KEY=""
TENANT=""
API_PORT=8000
BRIDGE_PORT=3100
SSH_PORT=22

while [[ $# -gt 0 ]]; do
  case "$1" in
    --host) HOST="$2"; shift 2;;
    --user) USER="$2"; shift 2;;
    --key) KEY="$2"; shift 2;;
    --tenant) TENANT="$2"; shift 2;;
    --api-port) API_PORT="$2"; shift 2;;
    --bridge-port) BRIDGE_PORT="$2"; shift 2;;
  --ssh-port) SSH_PORT="$2"; shift 2;;
    -h|--help) usage;;
    *) echo "Unknown arg: $1"; usage;;
  esac
done

if [ -z "$HOST" ] || [ -z "$USER" ] || [ -z "$KEY" ] || [ -z "$TENANT" ]; then
  usage
fi

ROOT=$(cd "$(dirname "$0")/.." && pwd)
TMP_DIR="/tmp/asistan_deploy_${TENANT}_$$"

echo "== Remote deploy -> $USER@$HOST (tenant=$TENANT) =="

echo "Create temp dir $TMP_DIR"
mkdir -p "$TMP_DIR"

echo "Packing repo (excludes node_modules/.venv)"
rsync -av --exclude '.venv' --exclude 'node_modules' --exclude 'deploy' --exclude '.git' "$ROOT/" "$TMP_DIR/" >/dev/null

REMOTE_BASE="/home/$USER/asistan_deploys/$TENANT"

echo "Syncing to remote: $HOST:$REMOTE_BASE"
mkdir -p "$TMP_DIR/.rsync_excludes"
RSYNC_RSH="ssh -i $KEY -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -p 22"
RSYNC_RSH="ssh -i $KEY -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -p $SSH_PORT"
rsync -ave "$RSYNC_RSH" --delete "$TMP_DIR/" "$USER@$HOST:$REMOTE_BASE/"

echo "Write remote .env"
cat > "$TMP_DIR/.env.remote" <<EOF
TENANT_SLUG=$TENANT
DATABASE_URL=sqlite:///$REMOTE_BASE/data/${TENANT}.db
ASISTAN_API_URL=http://localhost:${API_PORT}
QR_PORT=${BRIDGE_PORT}
LOCAL_LLM_ENABLED=false
EOF
rsync -ave "$RSYNC_RSH" "$TMP_DIR/.env.remote" "$USER@$HOST:$REMOTE_BASE/.env"

echo "Run remote deploy script"
SSH_CMD="cd $REMOTE_BASE && chmod +x scripts/deploy_single_tenant.sh && ./scripts/deploy_single_tenant.sh $TENANT $API_PORT $BRIDGE_PORT"
ssh -i "$KEY" -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -p $SSH_PORT "$USER@$HOST" "$SSH_CMD"

echo "Cleaning temp"
rm -rf "$TMP_DIR"

echo "Remote deploy finished. Tenant $TENANT should be running on $HOST (api:$API_PORT, bridge:$BRIDGE_PORT)"

exit 0
