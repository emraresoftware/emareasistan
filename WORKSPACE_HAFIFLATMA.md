# Workspace Hafifletme (Cursor Şişmesi)

Proje ~2.5 GB. Cursor’ın kapanmasını azaltmak için aşağıdakileri uygulayabilirsin.

## Tespit edilen büyük alanlar

| Konum | Boyut | Not |
|-------|--------|-----|
| `~/local_llm/` (eski `scripts/local_llm/`) | **~1.2 GB** | Lokal LLM artık repo dışına taşındı; workspace hafif. |
| `whatsapp-bridge/` | **~1.2 GB** | `node_modules` ağırlıklı. `.wwebjs_auth*` oturum klasörleri temizlendi (QR yeniden taranmalı). |
| `.venv` (kök) | **~388 MB** | Ana proje sanal ortamı. |
| `venv` (kök) | **~380 MB** | **Gereksiz kopya** – tek bir venv yeter. |
| `asistan.log` | ~0 B | Boşaltıldı. |

## Yapılacaklar (öneri sırasıyla)

### 1. Tek venv kullan (hemen ~380 MB kazanç)
Kök dizinde hem `venv` hem `.venv` var. Birini kullanıyorsan diğerini silebilirsin:

```bash
# Hangi venv kullanıldığını kontrol et (örn. run.py, start.sh)
# Sonra kullanılmayanı sil:
rm -rf venv
# veya
rm -rf .venv
```
**Not:** Projede genelde `.venv` kullanılıyorsa `venv` klasörünü silmek güvenli.

### 2. local_llm’i proje dışına taşımak (yapıldı, ~1.2 GB)
Lokal LLM klasörü artık repo dışında:

```bash
mv scripts/local_llm ~/local_llm   # yapıldı
# İhtiyaç olursa .env ile LOCAL_LLM_* yollarını yeni konuma göre güncelleyebilirsin
```
Böylece Cursor workspace’i 1.2 GB hafifledi (zaten index’e alınmıyor olsa da disk ve backup rahatladı).

### 3. Log dosyasını küçültmek
```bash
> asistan.log   # içini boşalt (dosyayı silmeden)
# veya
truncate -s 0 asistan.log
```

### 4. Cursor / workspace ayarları
- `asistan-hafif.code-workspace` içinde `venv`, `.venv`, `node_modules`, `scripts/local_llm`, `data`, `uploads`, `*.log`, `.wwebjs_auth*` zaten **files.exclude** ve **search.exclude** ile kapalı. Bu ayarlar kalmalı.
- `.cursorignore` güncel; Cursor index’e büyük klasörleri almıyor.

## Özet
- **Yapıldı:** Gereksiz `venv` silindi (~380 MB). `start.sh` / `update.sh` artık önce `.venv` kullanıyor. `asistan.log` boşaltıldı.
- **Yapıldı:** `scripts/local_llm` → `~/local_llm` taşındı; workspace küçüldü.
- **Yapıldı:** `whatsapp-bridge/.wwebjs_auth*` klasörleri temizlendi (WhatsApp oturumları sıfırlandı; QR yeniden taranmalı).
- Workspace ve .cursorignore ağır dizinleri hariç tutuyor; Cursor yine de kapanıyorsa tek venv, local_llm taşıma ve auth klasörlerini temizleme ilk denenecek adımlar.
