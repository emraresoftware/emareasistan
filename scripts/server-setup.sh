#!/bin/bash
# Sunucuda çalıştırılacak kurulum scripti
# ssh root@77.92.152.3 'bash -s' < scripts/server-setup.sh

set -e
cd /opt/asistan

echo "=== APP_BASE_URL güncelleniyor ==="
sed -i 's|APP_BASE_URL=.*|APP_BASE_URL=http://77.92.152.3:8000|' .env 2>/dev/null || echo "APP_BASE_URL=http://77.92.152.3:8000" >> .env

echo "=== Chrome (Puppeteer) kurulumu ==="
cd whatsapp-bridge
npx puppeteer browsers install chrome 2>/dev/null || true
cd ..

echo "=== Servisler yeniden başlatılıyor ==="
systemctl restart asistan-api asistan-whatsapp
sleep 2
systemctl status asistan-api asistan-whatsapp --no-pager

echo ""
echo "=== Tamamlandı ==="
echo "Admin: http://77.92.152.3:8000/admin"
echo "WhatsApp QR: http://77.92.152.3:3100"
