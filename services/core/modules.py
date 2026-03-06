"""
Modül sistemi - Firmalar için etkinleştirilebilir özellikler.
Super admin firma seçer, hangi modüllerin aktif olacağını belirler.
Bağımlılık: payment → orders (ödeme siparişe bağlı).
"""
from typing import Optional

from models.database import AsyncSessionLocal
from models import Tenant
from sqlalchemy import select

# Modül bağımlılıkları: modül_id -> [bağımlı olduğu modül_id'ler]
MODULE_DEPENDENCIES: dict[str, list[str]] = {
    "payment": ["orders"],  # Ödeme modülü sipariş modülüne bağlı
}

# Tüm mevcut modüller - geniş kitle için
AVAILABLE_MODULES = [
    {"id": "whatsapp", "name": "WhatsApp", "desc": "WhatsApp mesajlaşma entegrasyonu", "category": "Sohbet"},
    {"id": "web_chat", "name": "Web Sohbet", "desc": "Web sitesine gömülebilen AI destekli sohbet widget'ı", "category": "Sohbet"},
    {"id": "telegram", "name": "Telegram", "desc": "Telegram bot entegrasyonu", "category": "Sohbet"},
    {"id": "instagram", "name": "Instagram DM", "desc": "Instagram Direct Message entegrasyonu (Meta API)", "category": "Sosyal Medya"},
    {"id": "products", "name": "Ürünler", "desc": "Ürün kataloğu ve galeri", "category": "Pazaryerleri"},
    {"id": "albums", "name": "Albümler", "desc": "Araç modeline göre resim albümleri", "category": "Pazaryerleri"},
    {"id": "videos", "name": "Videolar", "desc": "Montaj/kurulum videoları", "category": "Pazaryerleri"},
    {"id": "orders", "name": "Siparişler", "desc": "Online sipariş alma", "category": "Ödemeler"},
    {"id": "appointments", "name": "Randevular", "desc": "Randevu planlama ve takip", "category": "Sohbet"},
    {"id": "admin_staff", "name": "İdari İşler", "desc": "İzin, fatura ve satın alma otomasyonu", "category": "Pazaryerleri"},
    {"id": "payment", "name": "Ödeme (Iyzico)", "desc": "Kredi kartı ödeme linki (Sipariş modülüne bağlı)", "category": "Ödemeler"},
    {"id": "cargo", "name": "Kargo Takibi", "desc": "Yurtiçi, Aras, MNG kargo sorgulama", "category": "Kargo"},
    {"id": "rules", "name": "Kurallar", "desc": "Yönetim kuralları (anahtar kelime → ürün/resim)", "category": "AI & Otomasyon"},
    {"id": "workflows", "name": "İş Akışları", "desc": "Kurum bazlı iş akışı builder (Trigger → Action → Condition)", "category": "AI & Otomasyon"},
    {"id": "training", "name": "AI Eğitim", "desc": "Soru-cevap örnekleri ile AI eğitimi", "category": "AI & Otomasyon"},
    {"id": "contacts", "name": "Kişiler", "desc": "Müşteri kişi kartları", "category": "Sohbet"},
    {"id": "reminders", "name": "Hatırlatıcılar", "desc": "Takip hatırlatıcıları", "category": "AI & Otomasyon"},
    {"id": "analytics", "name": "İstatistikler", "desc": "Sohbet ve sipariş istatistikleri", "category": "AI & Otomasyon"},
    {"id": "quick_replies", "name": "Hızlı Yanıtlar", "desc": "Hazır yanıt şablonları", "category": "Sohbet"},
    {"id": "agent", "name": "Temsilci Paneli", "desc": "Canlı sohbet devralma", "category": "Sohbet"},
    {"id": "conversations", "name": "Sohbetler", "desc": "Tüm sohbet geçmişi", "category": "Sohbet"},
    {"id": "export_templates", "name": "Veri Aktarımı", "desc": "Asistan verisini CRM/ERP'ye formatlı aktarma", "category": "Pazaryerleri"},
    {"id": "facebook", "name": "Facebook", "desc": "Facebook sayfa/mesaj yönetimi", "category": "Sosyal Medya"},
    {"id": "twitter", "name": "Twitter/X", "desc": "Tweet ve DM yönetimi", "category": "Sosyal Medya"},
    {"id": "tiktok", "name": "TikTok", "desc": "İçerik yönetimi ve analiz", "category": "Sosyal Medya"},
    {"id": "linkedin", "name": "LinkedIn", "desc": "Company page ve mesajlar", "category": "Sosyal Medya"},
    {"id": "trendyol", "name": "Trendyol", "desc": "Trendyol entegrasyonu ve ürün yönetimi", "category": "Pazaryerleri"},
    {"id": "hepsiburada", "name": "Hepsiburada", "desc": "Hepsiburada entegrasyonu ve siparişler", "category": "Pazaryerleri"},
    {"id": "amazon", "name": "Amazon", "desc": "Amazon entegrasyonu ve siparişler", "category": "Pazaryerleri"},
    {"id": "stripe", "name": "Stripe", "desc": "Stripe ödemeleri ve ayarlar", "category": "Ödemeler"},
    {"id": "paypal", "name": "PayPal", "desc": "PayPal ödemeleri ve ayarlar", "category": "Ödemeler"},
    {"id": "yurtici", "name": "Yurtiçi Kargo", "desc": "Yurtiçi gönderi sorgulama ve yönetim", "category": "Kargo"},
    {"id": "aras", "name": "Aras Kargo", "desc": "Aras gönderi sorgulama ve yönetim", "category": "Kargo"},
    {"id": "mng", "name": "MNG Kargo", "desc": "MNG gönderi sorgulama ve yönetim", "category": "Kargo"},
    {"id": "ups", "name": "UPS", "desc": "UPS entegrasyonu", "category": "Kargo"},
    {"id": "dhl", "name": "DHL", "desc": "DHL entegrasyonu", "category": "Kargo"},
    {"id": "ptt", "name": "PTT", "desc": "PTT entegrasyonu", "category": "Kargo"},
]


async def get_enabled_modules(tenant_id: int) -> set[str]:
    """
    Tenant için etkin modülleri döndür.
    Boş/None ise tüm modüller etkin (geriye uyumluluk).
    """
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Tenant).where(Tenant.id == tenant_id))
        tenant = result.scalar_one_or_none()
    if not tenant:
        return set(m["id"] for m in AVAILABLE_MODULES)
    raw = tenant.enabled_modules
    if raw is None or (isinstance(raw, list) and len(raw) == 0):
        return set(m["id"] for m in AVAILABLE_MODULES)
    if isinstance(raw, str):
        import json
        try:
            raw = json.loads(raw)
        except Exception:
            return set(m["id"] for m in AVAILABLE_MODULES)
    return set(str(m) for m in raw if m)


def is_module_enabled(enabled_modules: set[str], module_id: str) -> bool:
    """Modül etkin mi? Boş set = hepsi etkin."""
    if not enabled_modules:
        return True
    return module_id in enabled_modules


def get_module_dependencies(module_id: str) -> list[str]:
    """Modülün bağımlı olduğu modülleri döndür."""
    return MODULE_DEPENDENCIES.get(module_id, [])


def check_module_dependencies(
    module_id: str,
    enabled_modules: set[str],
    *,
    enabling: bool = True,
) -> tuple[bool, list[str]]:
    """
    Modül etkinleştirme/devre dışı bırakma öncesi bağımlılık kontrolü.
    enabling=True: modül açılıyorsa, bağımlılıkların da açık olması gerekir.
    enabling=False: modül kapatılıyorsa, buna bağımlı modüller de kapatılmalı veya uyarı.
    Returns: (ok, [uyarı mesajları])
    """
    warnings = []
    if enabling:
        deps = get_module_dependencies(module_id)
        missing = [d for d in deps if d not in enabled_modules]
        if missing:
            mod_names = {m["id"]: m["name"] for m in AVAILABLE_MODULES}
            names = [mod_names.get(d, d) for d in missing]
            warnings.append(f"'{mod_names.get(module_id, module_id)}' modülü şunlara bağlıdır: {', '.join(names)}. Önce onları etkinleştirin.")
            return False, warnings
    else:
        # Bu modüle bağımlı olanlar var mı?
        dependents = [mid for mid, deps in MODULE_DEPENDENCIES.items() if module_id in deps and mid in enabled_modules]
        if dependents:
            mod_names = {m["id"]: m["name"] for m in AVAILABLE_MODULES}
            names = [mod_names.get(m, m) for m in dependents]
            warnings.append(f"Bu modül kapatılırsa şu modüller de devre dışı kalacak: {', '.join(names)}.")
    return True, warnings
