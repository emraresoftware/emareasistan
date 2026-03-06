#!/bin/bash
# Emare Asistan - Sunucu / Geliştirme Ortamı Güncelleme
# Kullanım: ./update.sh  veya  bash update.sh

set -e
cd "$(dirname "$0")"

echo "=============================================="
echo "Emare Asistan - Güncelleme"
echo "=============================================="

# Docker kullanılıyor mu?
if docker compose ps 2>/dev/null | grep -q "Up"; then
  echo ""
  echo "Docker Compose ile çalışıyor. Güncelleme..."
  docker compose exec api pip install -r requirements.txt -q 2>/dev/null || true
  docker compose exec api python -m alembic upgrade head 2>/dev/null || true
  echo "API yeniden başlatılıyor..."
  docker compose restart api
  docker compose restart whatsapp-bridge 2>/dev/null || true
  echo ""
  echo "✓ Güncelleme tamamlandı."
  exit 0
fi

# Yerel geliştirme (.venv veya venv)
if [ -f ".venv/bin/activate" ]; then
  echo ".venv aktifleştiriliyor..."
  source .venv/bin/activate
elif [ -f "venv/bin/activate" ]; then
  echo "venv aktifleştiriliyor..."
  source venv/bin/activate
fi

echo ""
echo "1. Python bağımlılıkları güncelleniyor..."
pip install -r requirements.txt -q

echo "2. Veritabanı migration..."
python -m alembic upgrade head 2>/dev/null || echo "   (migration atlandı veya zaten güncel)"

echo "3. WhatsApp Bridge bağımlılıkları..."
if [ -d "whatsapp-bridge" ] && [ -f "whatsapp-bridge/package.json" ]; then
  (cd whatsapp-bridge && npm install --silent 2>/dev/null) || true
fi

echo ""
echo "=============================================="
echo "✓ Güncelleme tamamlandı."
echo ""
echo "Sunucuyu yeniden başlatmak için:"
echo "  ./start.sh"
echo "  veya: python run.py"
echo "=============================================="
