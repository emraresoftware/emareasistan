#!/usr/bin/env bash
set -euo pipefail

API_URL="http://127.0.0.1:8000/docs"
BRIDGE_URL="http://127.0.0.1:3100/"

ok_api=0
ok_bridge=0

if curl -fsS --max-time 8 "$API_URL" >/dev/null 2>&1; then
  ok_api=1
fi
if curl -fsS --max-time 8 "$BRIDGE_URL" >/dev/null 2>&1; then
  ok_bridge=1
fi

if [[ "$ok_api" -ne 1 ]]; then
  logger -t asistan-health-check "API unhealthy, restarting asistan-api"
  systemctl restart asistan-api || true
  sleep 2
fi
if [[ "$ok_bridge" -ne 1 ]]; then
  logger -t asistan-health-check "Bridge unhealthy, restarting asistan-whatsapp"
  systemctl restart asistan-whatsapp || true
  sleep 2
fi

# ikinci kontrol: hala kapaliysa loga not dus
if [[ "$ok_api" -ne 1 ]] && ! curl -fsS --max-time 8 "$API_URL" >/dev/null 2>&1; then
  logger -t asistan-health-check "API still unhealthy after restart attempt"
fi
if [[ "$ok_bridge" -ne 1 ]] && ! curl -fsS --max-time 8 "$BRIDGE_URL" >/dev/null 2>&1; then
  logger -t asistan-health-check "WhatsApp bridge still unhealthy after restart attempt"
fi
