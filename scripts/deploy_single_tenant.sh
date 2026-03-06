#!/usr/bin/env bash
# Deploy a single-tenant instance on this server.
# Usage: ./scripts/deploy_single_tenant.sh <tenant_slug> [api_port] [bridge_port]
# Example: ./scripts/deploy_single_tenant.sh acme 8000 3100

set -euo pipefail

ROOT=$(cd "$(dirname "$0")/.." && pwd)
TENANT=${1:-}
API_PORT=${2:-8000}
BRIDGE_PORT=${3:-3100}

if [ -z "$TENANT" ]; then
  echo "Usage: $0 <tenant_slug> [api_port] [bridge_port]"
  exit 2
fi

DEPLOY_DIR="$ROOT/deploy/$TENANT"
mkdir -p "$DEPLOY_DIR"

ENV_FILE="$DEPLOY_DIR/.env"
cp "$ROOT/.env.example" "$ENV_FILE" 2>/dev/null || touch "$ENV_FILE"

# Append or overwrite tenant-specific envs
cat >> "$ENV_FILE" <<EOF
# Tenant-specific settings (generated)
TENANT_SLUG=$TENANT
DATABASE_URL=sqlite:///$ROOT/data/${TENANT}.db
ASISTAN_API_URL=http://localhost:${API_PORT}
QR_PORT=${BRIDGE_PORT}
LOCAL_LLM_ENABLED=false
EOF

echo "Wrote env -> $ENV_FILE"

# Start API using the venv python (uses uvicorn main:app)
API_LOG="$DEPLOY_DIR/api.log"
BRIDGE_LOG="$DEPLOY_DIR/bridge.log"

echo "Starting API on port $API_PORT (logs: $API_LOG)"
cd "$ROOT"
AS_ENV="$ENV_FILE" # used to pass to subprocess

nohup env $(cat "$ENV_FILE" | xargs) ./.venv/bin/python3 -m uvicorn main:app --host 0.0.0.0 --port ${API_PORT} > "$API_LOG" 2>&1 &
API_PID=$!
echo $API_PID > "$DEPLOY_DIR/api.pid"

echo "Starting WhatsApp Bridge on port $BRIDGE_PORT (logs: $BRIDGE_LOG)"
cd "$ROOT/whatsapp-bridge"
nohup env $(cat "$ENV_FILE" | xargs) npm run start:single > "$BRIDGE_LOG" 2>&1 &
BRIDGE_PID=$!
echo $BRIDGE_PID > "$DEPLOY_DIR/bridge.pid"

echo "Deployed tenant '$TENANT'"
echo "API: http://localhost:${API_PORT} (pid: $API_PID)"
echo "Bridge QR: http://localhost:${BRIDGE_PORT} (pid: $BRIDGE_PID)"
echo "Logs: $DEPLOY_DIR/*.log"

exit 0
