# Admin Panel – Performans Analizi ve Öneriler

Bu dosya, admin sayfalarında tespit edilen yavaş / ağır noktaları ve yapılan/önerilen iyileştirmeleri listeler.

---

## 1. Öncelikli (Yavaş veya Riskli) Sayfalar

### 1.1 Dashboard (`/admin/dashboard`)
- **Durum:** ~~Çok sayıda ayrı sorgu (≈15+ round-trip).~~ **İyileştirildi.**
- **Yapılan:** Sorgular 4 paralel gruba bölündü (`_dashboard_counts`, `_dashboard_revenue`, `_dashboard_recent`, `_dashboard_csat`); her grup kendi `AsyncSessionLocal()` oturumu ile `asyncio.gather()` içinde çalışıyor. Toplam süre artık ≈ en yavaş grubun süresi (önceki: tüm sorguların toplamı).
- **İsteğe bağlı:** Kısa TTL ile Redis cache (örn. 60 sn) eklenebilir.

### 1.2 Sohbet detay (`/admin/conversations/{id}`)
- **Durum:** Tek sohbetteki **tüm mesajlar** limit olmadan çekiliyor; çok uzun sohbetlerde bellek ve yanıt süresi artar.
- **Yapılan:** Son **500 mesaj** ile sınırlandırıldı (en son mesajlar; `order_by(created_at).limit(500)`). Daha eski mesajlar için ileride “daha eski mesajları yükle” eklenebilir.

### 1.3 Hatırlatıcılar listesi (`/admin/reminders`)
- **Durum:** Tüm reminder kayıtları limit olmadan çekiliyordu; binlerce kayıtta sayfa ağırlaşır.
- **Yapılan:** Sayfalama eklendi (`PAGE_SIZE = 20`); `offset/limit` ve `total_pages` hesaplanıyor.

### 1.4 Sohbet listesi (`/admin/conversations`)
- **Durum:** Zaten sayfalanıyor (PAGE_SIZE); son mesaj önizlemesi ve sipariş bilgisi 2 ek toplu sorgu ile alınıyor. Makul.
- **Öneri:** Gerekirse `last_message_at` / `last_message_preview` gibi alanları Conversation tarafında denormalize edip tek sorguda getirmek (bakım maliyeti artar).

### 1.5 Sohbet silme (`_delete_conversations_by_ids`)
- **Durum:** Cascade benzeri silme birkaç sorguda yapılıyor (MessageFeedback, Message, Reminder, Appointment, Order güncelleme, Conversation). Büyük toplu silmede yavaş olabilir.
- **Öneri:** Mümkünse DB tarafında FK `ON DELETE CASCADE` kullanmak; değilse toplu DELETE (örn. `delete(Message).where(Message.conversation_id.in_(ids))`) ile tek sorguda silmek.

---

## 2. Orta Öncelik

### 2.1 Videolar listesi (`/admin/videos`)
- **Durum:** ~~Tüm videolar limit olmadan çekiliyor.~~ **İyileştirildi.**
- **Yapılan:** Sayfalama eklendi (PAGE_SIZE=20).

### 2.2 Albümler listesi (`/admin/albums`)
- **Durum:** ~~Tüm albümler çekiliyor.~~ **İyileştirildi.**
- **Yapılan:** Sayfalama eklendi (PAGE_SIZE=20).

### 2.3 Kişiler listesi (`/admin/contacts`)
- **Durum:** ~~Tüm contact'lar limit yok.~~ **İyileştirildi.**
- **Yapılan:** Sayfalama eklendi (PAGE_SIZE=20).

### 2.4 Kullanıcılar listesi (`/admin/users`)
- **Durum:** ~~Tüm kullanıcılar çekiliyor.~~ **İyileştirildi.**
- **Yapılan:** Sayfalama eklendi (PAGE_SIZE=20).

### 2.5 Faturalar / Satın alma siparişleri (`/admin/admin-staff/invoices`, `/admin/admin-staff/purchase-orders`)
- **Durum:** ~~Liste sayfasında tüm kayıtlar çekiliyor.~~ **İyileştirildi.**
- **Yapılan:** Sayfalama eklendi (PAGE_SIZE=20); durum filtresi sayfa değişince korunuyor.

### 2.6 İzin talepleri (`/admin/admin-staff/leaves`)
- **Durum:** ~~Tüm talepler çekiliyor.~~ **İyileştirildi.**
- **Yapılan:** Sayfalama eklendi (PAGE_SIZE=20); durum filtresi korunuyor.

### 2.7 Kurallar listesi (`/admin/rules`)
- **Durum:** ~~Tüm kurallar çekiliyor.~~ **İyileştirildi.**
- **Yapılan:** Sayfalama eklendi (PAGE_SIZE=20).

### 2.8 AI eğitim örnekleri (`/admin/training`)
- **Durum:** ~~limit(100) ile sınırlı.~~ **İyileştirildi.**
- **Yapılan:** Sayfalama eklendi (PAGE_SIZE=20). Eski öneri: “daha fazla yükle”.

### 2.9 Sohbet denetimi / audit (`/admin/chat-audits`)
- **Durum:** ~~limit(100) vardı.~~ **İyileştirildi.**
- **Yapılan:** Sayfalama eklendi (PAGE_SIZE=20).

---

## 3. Diğer Notlar

- **Ürünler:** Ürün listesi JSON dosyasından yükleniyor (`_load_products`); büyük JSON’da I/O maliyeti olabilir. DB’ye geçildiğinde sayfalama düşünülmeli.
- **Agent sayfaları:** Sohbet listesi `limit(50)` kullanıyor; makul.
- **Export (conversations/export):** Seçilen sohbetlerin tüm mesajları çekiliyor; büyük seçimlerde bellek kullanımı artar. İleride stream/parça parça export düşünülebilir.

---

## 4. Yapılan İyileştirmeler (Özet)

| Sayfa / Bölüm | İyileştirme |
|---------------|-------------|
| `/admin/dashboard` | Sorgular 4 paralel grupta `asyncio.gather()` ile çalıştırılıyor |
| `/admin/conversations/{id}` | Mesajlar son 500 ile sınırlandı |
| `/admin/reminders` | Sayfalama (PAGE_SIZE=20) |
| `/admin/videos` | Sayfalama (PAGE_SIZE=20) |
| `/admin/contacts` | Sayfalama (PAGE_SIZE=20) |
| `/admin/admin-staff/invoices` | Sayfalama (PAGE_SIZE=20) |
| `/admin/admin-staff/leaves` | Sayfalama (PAGE_SIZE=20) |
| `/admin/admin-staff/purchase-orders` | Sayfalama (PAGE_SIZE=20) |
| `/admin/albums` | Sayfalama (PAGE_SIZE=20) |
| `/admin/users` | Sayfalama (PAGE_SIZE=20) |
| `/admin/rules` | Sayfalama (PAGE_SIZE=20) |
| `/admin/chat-audits` | Sayfalama (PAGE_SIZE=20) |
| `/admin/training` | Eğitim örnekleri listesi sayfalama (PAGE_SIZE=20) |

İleride dashboard için kısa TTL cache eklenebilir.
