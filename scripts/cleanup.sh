#!/usr/bin/env bash
# ============================================================
# cleanup.sh — Emare Asistan otomatik temizlik scripti
# Kullanım:
#   ./scripts/cleanup.sh          # Standart temizlik
#   ./scripts/cleanup.sh --deep   # Derin temizlik (node cache dahil)
# ============================================================
set -uo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

DEEP=false
[[ "${1:-}" == "--deep" ]] && DEEP=true

echo "🧹 Emare Asistan — Temizlik Başlıyor"
echo "   Dizin: $ROOT"
echo ""

# 1. Python __pycache__
count=$(find . -name "__pycache__" -not -path "./.venv/*" 2>/dev/null | wc -l | tr -d ' ')
if [ "$count" -gt 0 ]; then
    find . -name "__pycache__" -not -path "./.venv/*" -exec rm -rf {} + 2>/dev/null || true
    echo "✅ $count __pycache__ klasörü silindi"
else
    echo "— __pycache__ temiz"
fi

# 2. .pyc / .pyo dosyaları (pycache dışında kalanlar)
pyc=$(find . -name "*.pyc" -o -name "*.pyo" | grep -v .venv | wc -l | tr -d ' ')
if [ "$pyc" -gt 0 ]; then
    find . \( -name "*.pyc" -o -name "*.pyo" \) -not -path "./.venv/*" -delete 2>/dev/null || true
    echo "✅ $pyc .pyc/.pyo dosyası silindi"
else
    echo "— .pyc/.pyo temiz"
fi

# 3. pytest cache
if [ -d ".pytest_cache" ]; then
    rm -rf .pytest_cache
    echo "✅ .pytest_cache silindi"
fi

# 4. Test DB artıkları
for f in test_asistan.db test.db; do
    if [ -f "$f" ]; then
        rm -f "$f"
        echo "✅ $f silindi"
    fi
done

# 5. WhatsApp Bridge cache
if [ -d "whatsapp-bridge/.wwebjs_cache" ]; then
    size=$(du -sh whatsapp-bridge/.wwebjs_cache 2>/dev/null | cut -f1)
    rm -rf whatsapp-bridge/.wwebjs_cache
    echo "✅ .wwebjs_cache silindi ($size)"
else
    echo "— .wwebjs_cache temiz"
fi

# 6. macOS DS_Store
ds=$(find . -name ".DS_Store" 2>/dev/null | wc -l | tr -d ' ')
if [ "$ds" -gt 0 ]; then
    find . -name ".DS_Store" -delete 2>/dev/null || true
    echo "✅ $ds .DS_Store silindi"
fi

# 7. Derin temizlik (opsiyonel)
if $DEEP; then
    echo ""
    echo "🔥 Derin temizlik..."

    # WhatsApp auth (yeniden QR gerekir!)
    if [ -d "whatsapp-bridge/.wwebjs_auth" ]; then
        size=$(du -sh whatsapp-bridge/.wwebjs_auth 2>/dev/null | cut -f1)
        rm -rf whatsapp-bridge/.wwebjs_auth
        echo "✅ .wwebjs_auth silindi ($size) — ⚠️ QR yeniden taranmalı"
    fi

    # Kıvılcım raporu
    if [ -f "KIVILCIM_RAPOR.md" ]; then
        rm -f KIVILCIM_RAPOR.md
        echo "✅ KIVILCIM_RAPOR.md silindi"
    fi
fi

echo ""
echo "🎉 Temizlik tamamlandı!"
echo ""

# Özet boyut
code_size=$(find . -not -path "./.venv/*" -not -path "*/node_modules/*" -not -path "*/__pycache__/*" -type f -exec du -ch {} + 2>/dev/null | tail -1 | cut -f1)
echo "📊 Proje boyutu (venv/node_modules hariç): $code_size"
