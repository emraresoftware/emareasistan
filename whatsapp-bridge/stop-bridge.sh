#!/bin/bash
# WhatsApp Bridge süreçlerini durdurur (port 3100 ve Chromium oturumları)
# Kullanım: ./stop-bridge.sh

echo "WhatsApp Bridge süreçleri durduruluyor..."

# Port 3100 kullanan süreci bul ve sonlandır
PID=$(lsof -t -i :3100 2>/dev/null)
if [ -n "$PID" ]; then
  echo "  Port 3100 kullanan süreç (PID $PID) sonlandırılıyor..."
  kill -9 $PID 2>/dev/null
fi

# wwebjs Chromium süreçlerini sonlandır
pkill -f "wwebjs_auth" 2>/dev/null && echo "  Chromium oturumları kapatıldı."

sleep 1
if lsof -i :3100 2>/dev/null | grep -q .; then
  echo "Uyarı: Port 3100 hâlâ kullanımda. Manuel kontrol: lsof -i :3100"
else
  echo "Tamamlandı. Port 3100 serbest."
fi
