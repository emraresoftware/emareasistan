# Cursor Kapanma Sorununu Azaltma Rehberi

Bu proje büyük olduğunda Cursor IDE kapanma/reboot yapabilir. Aşağıdaki ayarlar yükü azaltır.

## 1. Proje Ayarları (.vscode/settings.json)

Zaten uygulandı:
- `editor.formatOnSave: false` — Her kayıtta format çalışmasın
- `files.watcherExclude` — node_modules, .venv, data vb. izlenmesin
- `search.exclude` — Ağır klasörler aramaya dahil olmasın

## 2. .cursorignore Güncellemesi (Manuel)

Proje kökündeki `.cursorignore` dosyasının **sonuna** şu satırları ekleyin (izin hatası alırsanız dosyayı manuel düzenleyin):

```
data/
uploads/
**/scripts/local_llm/
**/artifacts/
asistan.log
```

## 3. Cursor Uygulama Ayarları

**Settings > Cursor Settings > Beta:**
- **Agent Autocomplete** → KAPALI (yeşil toggle’ı kapatın)
- **Update Access** → Default (Early Access değil)

**Settings > General:**
- **Privacy Mode** → Açık (opsiyonel, veri azaltır)

## 4. Kullanım Alışkanlıkları

- **Az sekme tutun:** Sadece çalıştığınız 2-3 dosyayı açık bırakın
- **Sık kaydedin:** Değişiklik sonrası Cmd/Ctrl+S
- **Büyük dosyalardan kaçının:** `admin/routes.py` (5000+ satır) tek seferde açmayın, ilgili bölüme gidin
- **Sunucuyu reload olmadan çalıştırın:** `uvicorn --reload` yerine normal başlatın, değişiklik sonrası elle restart

## 5. Düzenli Bakım (Opsiyonel)

Chat geçmişi şişerse temizleyin (Mac/Linux):

```bash
# 7 günden eski chat geçmişini sil
find ~/.config/Cursor/User/History/ -type f -mtime +7 -delete
```

## 6. Proje Spesifik Kapanma (Sadece Bu Projede)

Bu proje **2.1 GB** (venv, local_llm, node_modules) – diğer projelerden çok daha ağır.

**Çözüm:** Hafif workspace ile açın:
- **File → Open Workspace from File**
- `asistan-hafif.code-workspace` dosyasını seçin
- Bu workspace venv, node_modules, data, scripts/local_llm’i Explorer’da gizler ve arama dışı bırakır

Normal proje klasörü yerine bu workspace ile açarsanız Cursor daha az yüklenir.

## 7. Sorun Devam Ederse

- **Safe mode:** `cursor --disable-extensions` ile başlatın
- **Cursor’u güncel tutun:** Help > Check for Updates
- **Projeyi hafif açın:** Sadece `admin/`, `integrations/`, `models/` gibi ana klasörleri açın, `whatsapp-bridge/node_modules` olmadan
