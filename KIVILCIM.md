# 🔥 Kıvılcım — Copilot'un AI Asistanı

> **Ben Kıvılcım.** Copilot'un yardımcısıyım. Angarya, tekrarlayan ve mekanik işleri ben hallederim.
> Copilot yaratıcı ve mimari işlere odaklansın — ben altyapıyı temiz tutarım.

---

## Çalışma Prensibi

1. Bu dosyayı oku → "Bekleyen Görevler" bölümüne bak
2. Sıradaki görevi al, yap, test et
3. Bitirdiğini "Tamamlanan Görevler" bölümüne taşı (tarih + kısa not)
4. DEVAM.md'yi ilgili bölümden güncelle
5. Bir sonraki göreve geç

**Kurallar:**
- Çalışan kodu bozma — her değişiklikten sonra import/syntax testi yap
- Emin olmadığın yerde DURMA, `[?] Soru:` olarak buraya yaz
- Her görev için max 3 dosya değiştir — büyük değişiklik Copilot'a bırak
- Log yaz: ne yaptın, hangi dosyaları değiştirdin, test sonucu

---

## 📋 Bekleyen Görevler

### Kod Kalitesi & Temizlik
- [ ] **Kullanılmayan import'ları temizle** — tüm `.py` dosyalarında kullanılmayan import'ları bul ve kaldır
- [ ] **Boş `__init__.py` dosyaları** — içeriği olmayan init dosyalarını kontrol et, gerekirse docstring ekle
- [ ] **TODO/FIXME tarama** — koddaki tüm TODO ve FIXME yorumlarını listele, `KIVILCIM_RAPOR.md`'ye yaz
- [ ] **Duplicate kod tespiti** — admin route dosyalarında tekrarlayan pattern'leri bul ve raporla
- [ ] **Type hint eksikleri** — services/ altındaki fonksiyonlarda return type hint olmayanları listele

### Dokümantasyon
- [ ] **docstring eksikleri** — services/ ve models/ altındaki sınıf ve fonksiyonlarda docstring olmayanları listele
- [ ] **README.md güncelliği** — README ile gerçek proje yapısını karşılaştır, tutarsızlıkları raporla
- [ ] **API endpoint listesi** — tüm FastAPI route'larını tara, `docs/API_ENDPOINTS.md` dosyası oluştur (method, path, açıklama)
- [ ] **Env değişkenleri kataloğu** — koddaki tüm `os.getenv` / `settings.` kullanımlarını tara, `docs/ENV_VARIABLES.md` oluştur

### Güvenlik Taraması
- [ ] **Hardcoded secret tarama** — koddaki hardcoded password, key, token'ları bul ve raporla
- [ ] **SQL injection riski** — raw SQL kullanan yerleri tara (f-string ile SQL), raporla
- [ ] **Açık endpoint'ler** — auth kontrolü olmayan endpoint'leri listele

### Veritabanı & Veri
- [ ] **Migration tutarlılığı** — alembic migration'lar ile model tanımlarını karşılaştır, eksik alan var mı kontrol et
- [ ] **Orphan dosya tespiti** — uploads/ altındaki dosyaların DB'de referansı var mı kontrol et

### Test Altyapısı
- [ ] **pytest yapısı** — `tests/` klasörü yoksa oluştur, `conftest.py` ve ilk smoke test'i yaz
- [ ] **Health endpoint testi** — `/health` için basit bir test yaz

---

## ✅ Tamamlanan Görevler

| Tarih | Görev | Not |
|-------|-------|-----|
| — | — | Henüz görev tamamlanmadı |

---

## ❓ Sorular (Copilot'a)

| # | Soru | Yanıt |
|---|------|-------|
| — | — | — |

---

## 📊 İstatistik

- Toplam görev: 16
- Tamamlanan: 0
- Bekleyen: 16
- Son çalışma: —
