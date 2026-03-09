#!/bin/bash
# Systemd servislerini kur - API ve WhatsApp Bridge AYRI çalışır
# Güncellemede sadece API yeniden başlar, WhatsApp kopmaz.
# Kullanım: Bu script sunucuda /opt/asistan içinde çalıştırılmalı.
# Örn: ssh root@SUNUCU "cd /opt/asistan && bash -s" < deploy/install-services.sh

set -e

INSTALL_DIR="${INSTALL_DIR:-/opt/asistan}"

echo "=============================================="
echo "Emare Asistan - Systemd Servis Kurulumu"
echo "Kurulum: $INSTALL_DIR"
echo "=============================================="

# API servisi
cat > /etc/systemd/system/asistan-api.service << EOF
[Unit]
Description=Emare Asistan API
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=$INSTALL_DIR
ExecStart=$INSTALL_DIR/venv/bin/uvicorn main:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=5
Environment=PATH=$INSTALL_DIR/venv/bin:/usr/bin

[Install]
WantedBy=multi-user.target
EOF

# WhatsApp Bridge servisi - AYRI (güncellemede kopmaz)
# node index-multi.js: npm path sorunlarını önler, direkt Node kullanır
cat > /etc/systemd/system/asistan-whatsapp.service << EOF
[Unit]
Description=Emare Asistan WhatsApp Bridge (ayrı servis - güncellemede kopmaz)
After=network.target asistan-api.service

[Service]
Type=simple
User=root
WorkingDirectory=$INSTALL_DIR/whatsapp-bridge
Environment=ASISTAN_API_URL=http://127.0.0.1:8000
Environment=QR_HOST=0.0.0.0
Environment=PATH=/usr/local/bin:/usr/bin
ExecStartPre=-/usr/bin/pkill -f [n]ode.*index-multi.js
ExecStartPre=-/usr/bin/fuser -k 3100/tcp
ExecStart=/usr/bin/env node index-multi.js
ExecStopPost=-/usr/bin/pkill -f chrome.*whatsapp
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable asistan-api asistan-whatsapp

echo ""
echo "✓ Servisler kuruldu ve enable edildi."
echo ""
echo "Başlatmak için:"
echo "  systemctl start asistan-api asistan-whatsapp"
echo ""
echo "Güncellemede: remote-update.sh sadece API'yi restart eder."
echo "WhatsApp Bridge ayrı çalıştığı için güncellemede KOPMAZ."
echo ""
