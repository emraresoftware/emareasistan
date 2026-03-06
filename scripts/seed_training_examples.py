#!/usr/bin/env python3
"""
AI eğitim örneklerini veritabanına ekle (AITrainingExample).
Panel: /admin/training
"""
import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from models.database import AsyncSessionLocal
from models import AITrainingExample
from sqlalchemy import select

# Zengin eğitim örnekleri - Örnek tenant verisi (oto koltuk kılıfı)
EXAMPLES = [
    {"question": "Montaj fiyatı ne kadar?", "expected_answer": "Montaj işlemleri mağazamızda yapılıyor. Montaj süresi yaklaşık 2-2.5 saat sürebiliyor. Detaylı bilgi için 0532 294 38 11 numaralı hattımızı arayabilirsiniz.", "category": "montaj", "trigger_keywords": "montaj, fiyat, ücret, takma", "priority": 10},
    {"question": "Montaj videosu var mı?", "expected_answer": "Montaj videomuz burada: https://www.youtube.com/watch?v=ghKZxRCtwK4", "category": "montaj", "trigger_keywords": "montaj videosu, video, kurulum videosu, nasıl takılır", "priority": 10},
    {"question": "Kargo var mı?", "expected_answer": "Evet, Türkiye'nin her yerine kargo hizmetimiz bulunmaktadır. Kargo süreci ve takip numarası hakkında bilgi almak için siparişinizle ilgili detayları bizimle paylaşın.", "category": "kargo", "trigger_keywords": "kargo, gönderim, teslimat", "priority": 9},
    {"question": "İade yapıyor musunuz?", "expected_answer": "Ürünlerimizde iade ve değişim süreçleri, garanti koşullarımıza tabidir. İade veya değişim talepleriniz için lütfen ürününüzün faturasıyla birlikte bizimle iletişime geçin. Detaylı bilgi için 0532 294 38 11 numaralı hattımızı arayabilirsiniz.", "category": "iade", "trigger_keywords": "iade, değişim, iptal", "priority": 9},
    {"question": "Elit koltuk kılıfı fiyatı ne kadar?", "expected_answer": "Elit serisi koltuk kılıflarımız 5999 TL'dir. Farklı renk ve model seçeneklerimiz mevcut. İsterseniz ürünlerin görsellerini paylaşabilirim.", "category": "fiyat", "trigger_keywords": "elit, fiyat, ne kadar, ücret", "priority": 8},
    {"question": "Peugeot Rifter var mı?", "expected_answer": "Peugeot Rifter modeliniz için özel olarak uyumlu ürünlerimiz bulunmaktadır. Aracınızın modeli ve yılını belirtirseniz size en uygun ürünleri önerebiliriz. İsterseniz ürünlerin resimlerini paylaşabilirim.", "category": "ürün", "trigger_keywords": "rifter, rifter, peugeot, araç modeli", "priority": 8},
    {"question": "Adresiniz nerede?", "expected_answer": "Lokasyonumuz Meridyen Oto, Mermerli Mahallesi, Kemerburgaz Caddesi, No: 32, 34400 Eyüpsultan/İstanbul'dur. Dilerseniz size konum bilgisi gönderebilirim.", "category": "konum", "trigger_keywords": "adres, konum, nerede, lokasyon", "priority": 8},
    {"question": "Temsilciyle görüşmek istiyorum", "expected_answer": "Detaylı bilgi için 0532 294 38 11 numaralı hattımızdan bizi arayabilirsiniz. Temsilcilerimiz size yardımcı olacaktır.", "category": "iletişim", "trigger_keywords": "temsilci, canlı, insan, yetkili, aramak", "priority": 9},
    {"question": "Garanti var mı?", "expected_answer": "Ürünlerimiz garanti kapsamındadır. Garanti koşulları ürün türüne göre değişiklik gösterebilir. Detaylı bilgi için 0532 294 38 11 numaralı hattımızı arayabilirsiniz.", "category": "garanti", "trigger_keywords": "garanti, garanti süresi", "priority": 7},
    {"question": "Ödeme seçenekleri neler?", "expected_answer": "Havale/EFT, kredi kartı ve kapıda ödeme seçeneklerimiz mevcuttur. Siparişinizi tamamlarken tercihinizi belirtebilirsiniz.", "category": "ödeme", "trigger_keywords": "ödeme, havale, kredi kartı, kapıda", "priority": 7},
    {"question": "Paspas satıyor musunuz?", "expected_answer": "Maalesef, şu anda paspas satışı yapmamaktayız. Sadece oto koltuk kılıfı, 7D zemin döşeme, bagaj paspası, yastık kolçak ve organizer ürünlerimiz mevcuttur.", "category": "ürün", "trigger_keywords": "paspas, paspas", "priority": 6},
    {"question": "BMW 5 serisi için ürün var mı?", "expected_answer": "BMW 5 Serisi için özel olarak tasarlanmış ürünümüz bulunmamaktadır. Ancak genel olarak birçok araç modeliyle uyumlu koltuk kılıflarımız mevcuttur.", "category": "ürün", "trigger_keywords": "bmw, 5 serisi", "priority": 6},
    {"question": "Resim gönderir misiniz?", "expected_answer": "İşte ürünlerimiz:", "category": "ürün", "trigger_keywords": "resim, görsel, fotoğraf, yolla, gönder", "priority": 8},
    {"question": "Bu olsun", "expected_answer": "Seçiminiz onaylandı. Siparişinizi tamamlamak için adınızı, telefon numaranızı ve teslimat adresinizi paylaşır mısınız?", "category": "sipariş", "trigger_keywords": "bu olsun, bunu alayım, seçtim, onay", "priority": 9},
    {"question": "Evet onaylıyorum", "expected_answer": "Teşekkürler. Siparişiniz alındı. En kısa sürede sizinle iletişime geçerek kargo bilgisini paylaşacağız.", "category": "sipariş", "trigger_keywords": "evet, onay, tamam", "priority": 9},
    {"question": "Merhaba nasılsınız?", "expected_answer": "Teşekkürler, iyiyiz. Siz nasılsınız? Hangi sektördesiniz, kısaca anlatır mısınız? Size nasıl yardımcı olabilirim?", "category": "selamlama", "trigger_keywords": "merhaba, nasılsın, günaydın", "priority": 5},
    {"question": "Montajı kendim yapabilir miyim?", "expected_answer": "Montaj işlemleri mağazamızda yapılıyor. Montaj süresi yaklaşık 2-2.5 saat sürebiliyor. Kurulum videomuz da mevcut: https://www.youtube.com/watch?v=ghKZxRCtwK4", "category": "montaj", "trigger_keywords": "kendim, evde, montaj", "priority": 7},
    {"question": "Kargo ne kadar sürer?", "expected_answer": "Kargo süresi bölgenize göre 1-3 iş günü arasında değişebilir. Siparişiniz kargoya verildiğinde takip numarası ile bilgilendirilirsiniz.", "category": "kargo", "trigger_keywords": "kargo süresi, ne zaman gelir", "priority": 7},
    {"question": "Kapıda ödeme yapabilir miyim?", "expected_answer": "Evet, kapıda ödeme seçeneğimiz mevcuttur. Siparişinizi tamamlarken bu seçeneği belirtebilirsiniz.", "category": "ödeme", "trigger_keywords": "kapıda, kapıda ödeme", "priority": 7},
    {"question": "Havale ile ödeyebilir miyim?", "expected_answer": "Evet, havale/EFT ile ödeme yapabilirsiniz. Siparişinizi tamamladıktan sonra size hesap bilgilerimizi ileteceğiz.", "category": "ödeme", "trigger_keywords": "havale, eft", "priority": 7},
]


async def seed(tenant_id: int = 1, skip_existing: bool = True):
    async with AsyncSessionLocal() as db:
        existing = set()
        if skip_existing:
            r = await db.execute(
                select(AITrainingExample.question).where(AITrainingExample.tenant_id == tenant_id)
            )
            existing = {row[0].strip().lower() for row in r.fetchall() if row[0]}

        added = 0
        for ex_data in EXAMPLES:
            q_lower = ex_data["question"].strip().lower()
            if q_lower in existing:
                continue
            ex = AITrainingExample(
                tenant_id=tenant_id,
                question=ex_data["question"],
                expected_answer=ex_data["expected_answer"],
                category=ex_data.get("category"),
                trigger_keywords=ex_data.get("trigger_keywords"),
                is_active=True,
                priority=ex_data.get("priority", 0),
            )
            db.add(ex)
            added += 1
            existing.add(q_lower)

        await db.commit()
        print(f"✓ {added} eğitim örneği eklendi (tenant_id={tenant_id})")
        if added < len(EXAMPLES):
            print(f"  ({len(EXAMPLES) - added} örnek zaten mevcuttu)")


if __name__ == "__main__":
    tid = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    asyncio.run(seed(tenant_id=tid))
