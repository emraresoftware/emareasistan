#!/bin/bash
# Emare Asistan - Tek komutla başlat
# Kullanım: ./start.sh  veya  bash start.sh
cd "$(dirname "$0")"

# .venv veya venv varsa kullan
if [ -f ".venv/bin/python" ]; then
  PYTHON=".venv/bin/python"
elif [ -f "venv/bin/python" ]; then
  PYTHON="venv/bin/python"
else
  PYTHON="python3"
fi

echo "=============================================="
echo "Emare Asistan"
echo "=============================================="
$PYTHON run.py
