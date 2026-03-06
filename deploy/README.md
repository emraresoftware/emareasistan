# Emare Asistan - Deploy Araçları

## Systemd Servisleri

WhatsApp Bridge **ayrı servis** olarak çalışır – `remote-update.sh` sadece API'yi yeniden başlatır, bridge dokunulmaz. Böylece güncellemede WhatsApp kopmaz.

| Servis | Açıklama |
|--------|----------|
| `asistan-api` | FastAPI (port 8000) |
| `asistan-whatsapp` | WhatsApp Bridge (port 3100) |

Servis dosyaları: `deploy/systemd/`

## Güncelleme Stratejisi

| Script | Ne yapar |
|--------|----------|
| `./remote-update.sh` | Kod + API yeniden başlat. **Bridge dokunulmaz.** |
| `./deploy/update-bridge.sh` | Sadece bridge günceller ve yeniden başlatır. WhatsApp kısa süre kopar. |

Bridge kodunda değişiklik yapmadıysanız `remote-update.sh` yeterli. Bridge güncellemesi gerekiyorsa `update-bridge.sh` kullanın.
