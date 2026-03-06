#!/usr/bin/env python3
"""
Emare Asistan (tenant_id=6) - AI hizmetlerini pazarlama için eğitim örnekleri.
Mevcut varsayılan örnekleri siler, Emare Asistan pazarlama örneklerini ekler.
"""
import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from models.database import AsyncSessionLocal
from models import AITrainingExample
from sqlalchemy import delete
from services.ai.vector_store import SOURCE_AI_TRAINING, delete_embeddings_by_source

# Emare Asistan AI hizmetleri pazarlama - tenant_id=6
EMARE_ASISTAN_EXAMPLES = [
    {"question": "Emare Asistan nedir?", "expected_answer": "Emare Asistan, işletmelerin WhatsApp ve Telegram üzerinden müşterileriyle otomatik iletişim kurmasını sağlayan yapay zeka destekli sohbet asistanıdır. 7/24 müşteri sorularına anında yanıt verir, ürün önerir, sipariş alır ve kargo takibi yapar. Daha fazla bilgi verebilirim.", "category": "tanitim", "trigger_keywords": "emare asistan, nedir, ne ise yarar", "priority": 10},
    {"question": "Nasıl çalışıyor?", "expected_answer": "WhatsApp veya Telegram hesabınıza bağlanırsınız. Müşteriler mesaj attığında Emare Asistan yapay zeka ile anında yanıt verir. Ürün kataloğunuzu yüklersiniz, kurallar tanımlarsınız. İsterseniz temsilcileriniz belirli sohbetlere devralabilir. Detaylı bilgi için emareasistan.com üzerinden demo talep edebilirsiniz.", "category": "nasil", "trigger_keywords": "nasıl çalışır, nasil, kurulum", "priority": 10},
    {"question": "WhatsApp entegrasyonu var mı?", "expected_answer": "Evet, WhatsApp entegrasyonumuz mevcuttur. QR kod ile telefonunuzdaki WhatsApp Business hesabınıza bağlanabilir veya Meta Cloud API kullanabilirsiniz. Müşteri mesajları otomatik yanıtlanır, temsilciler panelden devralabilir.", "category": "entegrasyon", "trigger_keywords": "whatsapp, entegrasyon, bağlantı", "priority": 10},
    {"question": "Telegram destekliyor musunuz?", "expected_answer": "Evet, Telegram Bot entegrasyonumuz da mevcuttur. BotFather'dan aldığınız token ile botunuzu bağlayabilirsiniz. WhatsApp ile aynı panelden yönetilir.", "category": "entegrasyon", "trigger_keywords": "telegram, bot", "priority": 9},
    {"question": "Fiyatlandırma nasıl?", "expected_answer": "Fiyatlandırma işletme büyüklüğüne ve kullanım hacmine göre değişir. Demo talep ederek size özel teklif alabilirsiniz. emareasistan.com veya iletişim formu üzerinden bize ulaşın.", "category": "fiyat", "trigger_keywords": "fiyat, ücret, ne kadar, paket", "priority": 10},
    {"question": "Demo alabilir miyim?", "expected_answer": "Tabii. emareasistan.com üzerinden demo talep edebilir veya bize doğrudan yazabilirsiniz. Size canlı bir demo ayarlayıp özellikleri gösterebiliriz.", "category": "demo", "trigger_keywords": "demo, deneme, test", "priority": 10},
    {"question": "Hangi sektörlere uygun?", "expected_answer": "Emare Asistan e-ticaret, otomotiv, sağlık, eğitim, turizm, perakende ve hizmet sektörlerine uygundur. Ürün satışı, randevu alma, müşteri hizmetleri veya lead toplama için kullanılabilir. Hangi sektördesiniz, size özel nasıl kullanabileceğinizi anlatabilirim.", "category": "sektor", "trigger_keywords": "sektör, hangi iş, uygun mu", "priority": 9},
    {"question": "Ürün önerisi yapabiliyor mu?", "expected_answer": "Evet. Ürün kataloğunuzu yüklediğinizde asistan müşteri mesajına göre otomatik ürün önerir, fiyat söyler ve resim paylaşabilir. Araç modeli, bütçe veya anahtar kelimeye göre eşleştirme yapar.", "category": "ozellik", "trigger_keywords": "ürün önerisi, öneri, ürün", "priority": 9},
    {"question": "Sipariş alabiliyor mu?", "expected_answer": "Evet. Müşteriden ad, adres, telefon ve ödeme seçeneği toplayarak sipariş oluşturur. Panelden siparişleri görüntüleyebilir, kargo takibi yapabilirsiniz.", "category": "ozellik", "trigger_keywords": "sipariş, sipariş alma, satış", "priority": 9},
    {"question": "Temsilci devralabiliyor mu?", "expected_answer": "Evet. Temsilcileriniz panelden sohbetlere devralabilir. Müşteriye 'Mesajınız temsilcimize iletildi' bilgisi gider. İş bitince AI'a bırakabilirsiniz. Böylece karma mod (AI + insan) çalışır.", "category": "ozellik", "trigger_keywords": "temsilci, devral, insan, canlı", "priority": 9},
    {"question": "İletişime geçmek istiyorum", "expected_answer": "emareasistan.com üzerinden iletişim formunu doldurabilir veya e-posta ile yazabilirsiniz. Demo ve fiyat teklifi için en kısa sürede dönüş yapacağız.", "category": "iletisim", "trigger_keywords": "iletişim, görüşmek, aramak, ulaşmak", "priority": 10},
    {"question": "Merhaba", "expected_answer": "Merhaba, Emare Asistan'a hoş geldiniz. İşletmeniz için WhatsApp ve Telegram üzerinden yapay zeka destekli müşteri hizmetleri sunuyoruz. Size nasıl yardımcı olabilirim? Demo veya özellikler hakkında bilgi verebilirim.", "category": "selamlama", "trigger_keywords": "merhaba, selam, günaydın", "priority": 8},
    {"question": "Ne tür özellikler var?", "expected_answer": "Soru-cevap, ürün önerisi, sipariş alma, kargo takibi, randevu yönetimi, kurallarla otomatik mesaj/resim gönderme, temsilci devralma, çok kiracılı panel. Her firma kendi WhatsApp bağlantısı ve AI ayarlarıyla çalışır.", "category": "ozellik", "trigger_keywords": "özellik, ne yapıyor, fonksiyon", "priority": 9},
    {"question": "Birden fazla firma yönetebilir miyim?", "expected_answer": "Evet. Emare Asistan çok kiracılı (multi-tenant) SaaS'tır. Bir panelden birden fazla firma hesabı yönetebilirsiniz. Her firmanın kendi WhatsApp bağlantısı, ürün kataloğu ve AI ayarları vardır.", "category": "ozellik", "trigger_keywords": "çok firma, birden fazla, multi", "priority": 8},
    {"question": "Kurulum zor mu?", "expected_answer": "Hayır. WhatsApp için QR kod taramanız yeterli. Ürün listesini yüklersiniz, birkaç kural tanımlarsınız. Teknik destek ile kurulum sürecinde yanınızdayız.", "category": "kurulum", "trigger_keywords": "kurulum, zor mu, ne kadar sürer", "priority": 8},
    {"question": "Yapay zeka hangi modeli kullanıyor?", "expected_answer": "Google Gemini veya OpenAI API kullanıyoruz. Firma bazlı API anahtarı tanımlayabilir veya bizim sağladığımız altyapıyı kullanabilirsiniz. İsteğe bağlı lokal model fallback de mevcuttur.", "category": "teknik", "trigger_keywords": "yapay zeka, model, gemini, openai", "priority": 7},
    {"question": "Randevu modülü var mı?", "expected_answer": "Evet, randevu yönetimi modülümüz mevcuttur. Çalışma saatleri ve slotları tanımlarsınız, müşteri uygun slot seçer ve randevu oluşturulur.", "category": "ozellik", "trigger_keywords": "randevu, appointment", "priority": 8},
    {"question": "Üye olmak istiyorum", "expected_answer": "emareasistan.com/admin/register adresinden üye olabilirsiniz. Web sitenizi girin, sektör seçin, e-posta ve şifre ile hesap oluşturun. Kayıt sonrası demo erişimi sağlanır.", "category": "kayit", "trigger_keywords": "üye ol, kayıt, hesap aç", "priority": 9},
    # Ek özellikler
    {"question": "Hatırlatıcı özelliği var mı?", "expected_answer": "Evet. Müşteri takibi için hatırlatıcı modülümüz var. Belirli tarih/saatte geri dönüş yapmanız gereken müşterileri kaydedebilir, panelden takip edebilirsiniz. Lead skoruna göre otomatik hatırlatıcı önerisi de sunulur.", "category": "ozellik", "trigger_keywords": "hatırlatıcı, takip, geri dönüş", "priority": 8},
    {"question": "Raporlama ve istatistik var mı?", "expected_answer": "Evet. İstatistikler modülünde sohbet sayıları, sipariş özetleri, platform bazlı dağılım (WhatsApp/Telegram) ve lead metrikleri görüntülenir. VIP ve sıcak lead sayıları, performans grafikleri mevcuttur.", "category": "ozellik", "trigger_keywords": "rapor, istatistik, analitik, analytics", "priority": 8},
    {"question": "Lead skorlama nedir?", "expected_answer": "Lead skoru, sohbet içeriğine göre müşteri potansiyelini puanlar. Telefon, e-posta paylaşan veya sipariş niyeti gösteren müşteriler yüksek skor alır. VIP ve sıcak lead'lere otomatik hatırlatıcı önerilir. Böylece en değerli müşterilere öncelik verirsiniz.", "category": "ozellik", "trigger_keywords": "lead, skor, potansiyel müşteri", "priority": 7},
    {"question": "Otomatik kurallar nasıl çalışır?", "expected_answer": "Kurallar modülünde anahtar kelime veya araç modeline göre otomatik ürün/resim gönderme tanımlarsınız. Örn: 'Passat' yazan müşteriye belirli ürün görselleri otomatik gider. Tetikleyici türü, öncelik ve mesaj metni özelleştirilebilir.", "category": "ozellik", "trigger_keywords": "kural, otomatik, tetikleyici", "priority": 8},
    {"question": "Hızlı yanıt şablonları var mı?", "expected_answer": "Evet. Hazır yanıt şablonları (quick replies) ile temsilciler sık kullanılan cevapları tek tıkla gönderebilir. AI ile birlikte veya devraldığınız sohbetlerde kullanılır.", "category": "ozellik", "trigger_keywords": "hızlı yanıt, şablon, template", "priority": 7},
    {"question": "Kişi kartları / CRM var mı?", "expected_answer": "Kişiler modülünde müşteri kartları oluşturulur. Sohbet geçmişi, siparişler ve iletişim bilgileri tek yerde toplanır. Lead skoru ve hatırlatıcılarla entegre çalışır.", "category": "ozellik", "trigger_keywords": "kişi, CRM, müşteri kartı, contact", "priority": 7},
    {"question": "Ürün albümleri nedir?", "expected_answer": "Albümler modülünde araç modeline göre resim albümleri tanımlarsınız. Müşteri 'Golf için ne var?' dediğinde ilgili ürün görselleri otomatik gönderilir. Kurallarla birlikte kullanılabilir.", "category": "ozellik", "trigger_keywords": "albüm, araç modeli, resim", "priority": 7},
    {"question": "Video paylaşımı yapabiliyor mu?", "expected_answer": "Evet. Videolar modülünde montaj, kurulum veya tanıtım videolarınızı yüklersiniz. AI müşteri sorusuna göre ilgili video linkini paylaşabilir. Örn: 'Montaj nasıl yapılır?' sorusunda kurulum videosu gönderilir.", "category": "ozellik", "trigger_keywords": "video, montaj videosu, kurulum", "priority": 7},
    {"question": "ERP veya API entegrasyonu var mı?", "expected_answer": "Entegrasyonlar sayfasından ERP, CRM, kargo ve ürün API ayarları yapılabilir. Firma bazlı API anahtarları tanımlanır. Webhook ve özel entegrasyonlar için teknik ekiple görüşebilirsiniz.", "category": "teknik", "trigger_keywords": "ERP, API, entegrasyon, webhook", "priority": 7},
    {"question": "Instagram destekliyor mu?", "expected_answer": "Instagram DM entegrasyonu yol haritamızda. Şu an WhatsApp ve Telegram tam destekleniyor. Instagram eklendiğinde aynı panelden yönetilecek. Güncellemeler için emareasistan.com'u takip edebilirsiniz.", "category": "entegrasyon", "trigger_keywords": "instagram, insta", "priority": 7},
    {"question": "Verilerim güvende mi?", "expected_answer": "Evet. Her firma verisi izole tutulur (multi-tenant). API anahtarları şifrelenir, sohbet geçmişi sadece sizin panelinizde görünür. KVKK uyumlu veri işleme politikamız mevcuttur.", "category": "guvenlik", "trigger_keywords": "güvenlik, veri, KVKK, gizlilik", "priority": 8},
    {"question": "Teknik destek nasıl alırım?", "expected_answer": "emareasistan.com üzerinden iletişim formu veya e-posta ile ulaşabilirsiniz. Kurulum sürecinde teknik destek sağlanır. Acil durumlar için öncelikli destek paketleri mevcuttur.", "category": "destek", "trigger_keywords": "destek, yardım, sorun", "priority": 8},
    {"question": "7/24 çalışıyor mu?", "expected_answer": "Evet. Emare Asistan 7/24 aktif kalır. Müşteriler gece veya hafta sonu mesaj attığında AI anında yanıt verir. Temsilciler müsait olduğunda devralabilir; yoksa AI otomatik hizmet sunar.", "category": "ozellik", "trigger_keywords": "7/24, gece, hafta sonu, sürekli", "priority": 8},
]


async def seed_emare_asistan():
    tenant_id = 6
    async with AsyncSessionLocal() as db:
        # Eski embedding'leri temizle (pgvector varsa)
        n = await delete_embeddings_by_source(db, SOURCE_AI_TRAINING, tenant_id=tenant_id)
        if n:
            print(f"✓ {n} eski embedding silindi")
        # Mevcut tenant_id=6 örneklerini sil
        await db.execute(delete(AITrainingExample).where(AITrainingExample.tenant_id == tenant_id))
        await db.commit()
        print(f"✓ tenant_id=6 eski örnekler silindi")

        # Yeni Emare Asistan örneklerini ekle
        for ex_data in EMARE_ASISTAN_EXAMPLES:
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
        await db.commit()
        print(f"✓ {len(EMARE_ASISTAN_EXAMPLES)} Emare Asistan pazarlama örneği eklendi (tenant_id=6)")


if __name__ == "__main__":
    asyncio.run(seed_emare_asistan())
