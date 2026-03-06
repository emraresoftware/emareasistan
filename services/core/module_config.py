"""
Modul bazli API ayarlari.
Firma admin panelinden her modul icin API URL, anahtar ve baglanti
parametreleri girilebilir.
"""


def _cargo_fields() -> list[dict]:
    """
    Turkiye'de yaygin kargo firmalari icin standart alan seti uret.
    type: text|url|password|textarea|checkbox
    """
    companies = [
        ("yurtici", "Yurtiçi Kargo"),
        ("aras", "Aras Kargo"),
        ("mng", "MNG Kargo"),
        ("ptt", "PTT Kargo"),
        ("surat", "Surat Kargo"),
        ("ups", "UPS Türkiye"),
        ("hepsijet", "HepsiJet"),
        ("sendeo", "Sendeo"),
        ("kolaygelsin", "Kolay Gelsin"),
        ("kargoist", "Kargoist"),
        ("trendyolexpress", "Trendyol Express"),
    ]

    fields: list[dict] = [
        {
            "key": "auto_detect_enabled",
            "label": "Takip no ile otomatik firma tespiti",
            "type": "checkbox",
            "group": "Genel Kargo Ayarlari",
            "placeholder": "",
        },
        {
            "key": "default_company",
            "label": "Varsayilan kargo firmasi (id)",
            "type": "text",
            "group": "Genel Kargo Ayarlari",
            "placeholder": "yurtici",
        },
        {
            "key": "fallback_order",
            "label": "Sorgu sirasi (virgulle)",
            "type": "text",
            "group": "Genel Kargo Ayarlari",
            "placeholder": "yurtici,aras,mng,ptt,surat,ups",
        },
    ]

    for company_id, company_name in companies:
        group = f"{company_name} Ayarlari"
        fields.extend(
            [
                {
                    "key": f"{company_id}_enabled",
                    "label": f"{company_name} aktif",
                    "type": "checkbox",
                    "group": group,
                    "placeholder": "",
                },
                {
                    "key": f"{company_id}_api_url",
                    "label": "API URL",
                    "type": "url",
                    "group": group,
                    "placeholder": "https://api.firma.com",
                },
                {
                    "key": f"{company_id}_api_key",
                    "label": "API Key",
                    "type": "password",
                    "group": group,
                    "placeholder": "",
                },
                {
                    "key": f"{company_id}_secret_key",
                    "label": "Secret Key / Token",
                    "type": "password",
                    "group": group,
                    "placeholder": "",
                },
                {
                    "key": f"{company_id}_customer_code",
                    "label": "Musteri / Cari Kodu",
                    "type": "text",
                    "group": group,
                    "placeholder": "",
                },
                {
                    "key": f"{company_id}_tracking_url",
                    "label": "Takip Link Sablonu",
                    "type": "url",
                    "group": group,
                    "placeholder": "https://.../{tracking_no}",
                },
            ]
        )

    return fields


# Modul ID -> { name, desc, category, fields[] }
# category: Sohbet | Sosyal Medya | Ödemeler | Kargo | Pazaryerleri | Diğer
MODULE_API_FIELDS = {
    "products": {
        "name": "Ürünler",
        "category": "Pazaryerleri",
        "desc": "Dış ürün kataloğu veya stok API'si – kendi yazılımınızdan ürün çekmek için",
        "fields": [
            {"key": "api_url", "label": "API URL", "type": "url", "placeholder": "https://stok.firma.com/api/urunler"},
            {"key": "api_key", "label": "API Anahtarı", "type": "password", "placeholder": ""},
            {"key": "auth_header", "label": "Auth Header adı (opsiyonel)", "type": "text", "placeholder": "Authorization"},
            {"key": "list_path", "label": "JSON liste yolu (opsiyonel)", "type": "text", "placeholder": "data.items"},
            {"key": "sync_direction", "label": "Sync yönü (pull|push|bidirectional)", "type": "text", "placeholder": "pull"},
            {"key": "push_api_url", "label": "Push API URL (opsiyonel)", "type": "url", "placeholder": "https://stok.firma.com/api/urunler/upsert"},
            {"key": "push_method", "label": "Push method (POST|PUT|PATCH)", "type": "text", "placeholder": "POST"},
            {"key": "push_id_field", "label": "Remote id alanı", "type": "text", "placeholder": "slug"},
            {"key": "field_mapping_json", "label": "Field mapping (JSON, local->remote)", "type": "textarea", "placeholder": "{\"name\": \"title\", \"price\": \"amount\"}"},
            {"key": "conflict_strategy", "label": "Conflict stratejisi (last_write_wins|manual)", "type": "text", "placeholder": "last_write_wins"},
        ],
    },
    "contacts": {
        "name": "Kişiler",
        "category": "Sohbet",
        "desc": "CRM veya başka bir kaynaktan kişi rehberini çekmek/güncellemek için",
        "fields": [
            {"key": "api_url", "label": "Kişiler API URL", "type": "url", "placeholder": "https://crm.firma.com/api/contacts"},
            {"key": "api_key", "label": "API Anahtarı", "type": "password"},
            {"key": "auth_header", "label": "Auth Header adı", "type": "text", "placeholder": "Authorization"},
            {"key": "list_path", "label": "JSON liste yolu (opsiyonel)", "type": "text", "placeholder": "data.contacts"},
            {"key": "sync_direction", "label": "Sync yönü (pull|push|bidirectional)", "type": "text", "placeholder": "pull"},
            {"key": "push_api_url", "label": "Push API URL (opsiyonel)", "type": "url", "placeholder": "https://crm.firma.com/api/contacts/upsert"},
            {"key": "push_method", "label": "Push method (POST|PUT|PATCH)", "type": "text", "placeholder": "POST"},
            {"key": "push_id_field", "label": "Remote id alanı", "type": "text", "placeholder": "phone"},
            {"key": "field_mapping_json", "label": "Field mapping (JSON, local->remote)", "type": "textarea", "placeholder": "{\"name\": \"full_name\", \"phone\": \"mobile\"}"},
            {"key": "conflict_strategy", "label": "Conflict stratejisi (last_write_wins|manual)", "type": "text", "placeholder": "last_write_wins"},
        ],
    },
    "cargo": {
        "name": "Kargo Takibi",
        "category": "Kargo",
        "desc": "Tum yaygin TR kargo firmalari icin API ve takip ayarlari.",
        "fields": _cargo_fields(),
    },
    "orders": {
        "name": "Siparişler",
        "category": "Ödemeler",
        "desc": "ERP veya stok sistemi – sipariş oluşturulunca kendi sisteminize iletilir",
        "fields": [
            {"key": "erp_api_url", "label": "ERP / Stok API URL", "type": "url", "placeholder": "https://erp.firma.com/api/siparis"},
            {"key": "erp_api_key", "label": "API Anahtarı", "type": "password"},
            {"key": "webhook_url", "label": "Webhook URL (sipariş bildirimi)", "type": "url", "placeholder": "https://..."},
            {"key": "list_path", "label": "JSON liste yolu (opsiyonel)", "type": "text", "placeholder": "data.orders"},
            {"key": "sync_direction", "label": "Sync yönü (pull|push|bidirectional)", "type": "text", "placeholder": "pull"},
            {"key": "push_api_url", "label": "Push API URL (opsiyonel)", "type": "url", "placeholder": "https://erp.firma.com/api/orders/upsert"},
            {"key": "push_method", "label": "Push method (POST|PUT|PATCH)", "type": "text", "placeholder": "POST"},
            {"key": "push_id_field", "label": "Remote id alanı", "type": "text", "placeholder": "order_number"},
            {"key": "field_mapping_json", "label": "Field mapping (JSON, local->remote)", "type": "textarea", "placeholder": "{\"order_number\": \"code\", \"total_amount\": \"total\"}"},
            {"key": "conflict_strategy", "label": "Conflict stratejisi (last_write_wins|manual)", "type": "text", "placeholder": "last_write_wins"},
        ],
    },
    "appointments": {
        "name": "Randevular",
        "category": "Sohbet",
        "desc": "Dış sistemdeki randevu kayıtlarıyla senkronizasyon",
        "fields": [
            {"key": "api_url", "label": "Randevu API URL", "type": "url", "placeholder": "https://erp.firma.com/api/appointments"},
            {"key": "api_key", "label": "API Anahtarı", "type": "password"},
            {"key": "auth_header", "label": "Auth Header adı", "type": "text", "placeholder": "Authorization"},
            {"key": "list_path", "label": "JSON liste yolu (opsiyonel)", "type": "text", "placeholder": "data.appointments"},
            {"key": "google_calendar_webhook_url", "label": "Google Calendar Webhook URL (opsiyonel)", "type": "url", "placeholder": "https://script.google.com/macros/s/.../exec"},
            {"key": "calendar_sync_enabled", "label": "Randevulari Google Calendar'a yaz", "type": "checkbox", "placeholder": ""},
        ],
    },
    "reminders": {
        "name": "Hatırlatıcılar",
        "category": "Diğer",
        "desc": "Dış CRM görev/hatırlatıcı kayıtlarıyla senkronizasyon",
        "fields": [
            {"key": "api_url", "label": "Hatırlatıcı API URL", "type": "url", "placeholder": "https://crm.firma.com/api/reminders"},
            {"key": "api_key", "label": "API Anahtarı", "type": "password"},
            {"key": "auth_header", "label": "Auth Header adı", "type": "text", "placeholder": "Authorization"},
            {"key": "list_path", "label": "JSON liste yolu (opsiyonel)", "type": "text", "placeholder": "data.reminders"},
        ],
    },
    "admin_staff": {
        "name": "İdari İşler",
        "category": "Diğer",
        "desc": "İzin, fatura ve satın alma kayıtlarının dış sistemle senkronizasyonu",
        "fields": [
            {"key": "api_url", "label": "Genel API URL", "type": "url", "placeholder": "https://erp.firma.com/api/admin-staff"},
            {"key": "api_key", "label": "API Anahtarı", "type": "password"},
            {"key": "auth_header", "label": "Auth Header adı", "type": "text", "placeholder": "Authorization"},
            {"key": "leave_requests_path", "label": "İzin listesi yolu", "type": "text", "placeholder": "data.leave_requests"},
            {"key": "invoices_path", "label": "Fatura listesi yolu", "type": "text", "placeholder": "data.invoices"},
            {"key": "purchase_orders_path", "label": "Satın alma listesi yolu", "type": "text", "placeholder": "data.purchase_orders"},
        ],
    },
    "payment": {
        "name": "Ödeme (Iyzico)",
        "category": "Ödemeler",
        "desc": "Kredi kartı ile sipariş verildiğinde ödeme linki oluşturulur ve WhatsApp'tan gönderilir.",
        "fields": [
            {"key": "iyzico_api_key", "label": "Iyzico API Key", "type": "password", "placeholder": "sandbox-xxx veya canlı key"},
            {"key": "iyzico_secret_key", "label": "Iyzico Secret Key", "type": "password", "placeholder": ""},
            {"key": "iyzico_sandbox", "label": "Sandbox (Test)", "type": "text", "placeholder": "1 = test, boş = canlı"},
        ],
    },
    "crm": {
        "name": "CRM / Müşteri Yönetimi",
        "category": "Sohbet",
        "desc": "Müşteri verilerini kendi CRM sisteminizle senkronize etmek için",
        "fields": [
            {"key": "crm_api_url", "label": "CRM API URL", "type": "url"},
            {"key": "crm_api_key", "label": "API Anahtarı", "type": "password"},
        ],
    },
    "email": {
        "name": "E-posta (SMTP)",
        "category": "E-posta",
        "desc": "Firma e-posta servisi – sipariş bildirimleri, kayıt onayı vb. için. Boşsa sistem .env SMTP kullanır.",
        "fields": [
            {"key": "smtp_host", "label": "SMTP Sunucusu", "type": "text", "placeholder": "smtp.gmail.com"},
            {"key": "smtp_port", "label": "Port", "type": "text", "placeholder": "587"},
            {"key": "smtp_user", "label": "Kullanıcı / E-posta", "type": "text", "placeholder": "info@firma.com"},
            {"key": "smtp_password", "label": "Şifre / App Password", "type": "password", "placeholder": ""},
            {"key": "smtp_from", "label": "Gönderen Adresi (From)", "type": "text", "placeholder": "info@firma.com"},
            {"key": "smtp_from_name", "label": "Gönderen Adı", "type": "text", "placeholder": "Firma Adı"},
        ],
    },
    "custom": {
        "name": "Özel Entegrasyonlar",
        "category": "Diğer",
        "desc": "JSON formatında ek API ayarları – kendi yazılımınıza özel alanlar ekleyebilirsiniz",
        "fields": [
            {"key": "custom_json", "label": "Özel ayarlar (JSON)", "type": "textarea", "placeholder": '{"my_api": "https://...", "token": "xxx"}'},
        ],
    },
    # Ödeme sağlayıcıları
    "stripe": {
        "name": "Stripe",
        "category": "Ödemeler",
        "desc": "Stripe ile kredi kartı ve alternatif ödeme yöntemleri",
        "fields": [
            {"key": "stripe_api_key", "label": "Secret Key", "type": "password", "placeholder": "sk_live_xxx veya sk_test_xxx"},
            {"key": "stripe_publishable_key", "label": "Publishable Key", "type": "text", "placeholder": "pk_live_xxx"},
            {"key": "stripe_webhook_secret", "label": "Webhook Secret", "type": "password", "placeholder": "whsec_xxx"},
        ],
    },
    "paypal": {
        "name": "PayPal",
        "category": "Ödemeler",
        "desc": "PayPal ile ödeme alma ve iade işlemleri",
        "fields": [
            {"key": "paypal_client_id", "label": "Client ID", "type": "text", "placeholder": ""},
            {"key": "paypal_client_secret", "label": "Client Secret", "type": "password", "placeholder": ""},
            {"key": "paypal_sandbox", "label": "Sandbox (Test)", "type": "checkbox", "placeholder": ""},
        ],
    },
    "pluspay": {
        "name": "PlusPay",
        "category": "Ödemeler",
        "desc": "PlusPay ile kredi kartı ve sanal pos ödemeleri (Türkiye)",
        "fields": [
            {"key": "pluspay_merchant_id", "label": "Merchant ID", "type": "text", "placeholder": ""},
            {"key": "pluspay_api_key", "label": "API Key", "type": "password", "placeholder": ""},
            {"key": "pluspay_secret_key", "label": "Secret Key", "type": "password", "placeholder": ""},
            {"key": "pluspay_sandbox", "label": "Sandbox (Test)", "type": "checkbox", "placeholder": ""},
        ],
    },
    # Pazaryerleri
    "trendyol": {
        "name": "Trendyol",
        "category": "Pazaryerleri",
        "desc": "Trendyol satıcı paneli API – ürün, sipariş ve stok senkronizasyonu",
        "fields": [
            {"key": "trendyol_seller_id", "label": "Satıcı ID", "type": "text", "placeholder": ""},
            {"key": "trendyol_api_key", "label": "API Key", "type": "password", "placeholder": ""},
            {"key": "trendyol_api_secret", "label": "API Secret", "type": "password", "placeholder": ""},
            {"key": "trendyol_supplier_id", "label": "Tedarikçi ID (opsiyonel)", "type": "text", "placeholder": ""},
        ],
    },
    "hepsiburada": {
        "name": "Hepsiburada",
        "category": "Pazaryerleri",
        "desc": "Hepsiburada satıcı API – ürün ve sipariş entegrasyonu",
        "fields": [
            {"key": "hepsiburada_merchant_id", "label": "Merchant ID", "type": "text", "placeholder": ""},
            {"key": "hepsiburada_username", "label": "API Kullanıcı Adı", "type": "text", "placeholder": ""},
            {"key": "hepsiburada_password", "label": "API Şifresi", "type": "password", "placeholder": ""},
        ],
    },
    "amazon": {
        "name": "Amazon",
        "category": "Pazaryerleri",
        "desc": "Amazon Seller Central API – SP-API ile ürün ve sipariş yönetimi",
        "fields": [
            {"key": "amazon_seller_id", "label": "Seller ID", "type": "text", "placeholder": ""},
            {"key": "amazon_mws_access_key", "label": "MWS Access Key / LWA Client ID", "type": "text", "placeholder": ""},
            {"key": "amazon_mws_secret_key", "label": "MWS Secret Key / LWA Client Secret", "type": "password", "placeholder": ""},
            {"key": "amazon_region", "label": "Bölge (TR, EU, NA)", "type": "text", "placeholder": "TR"},
        ],
    },
    # Sosyal Medya
    "facebook": {
        "name": "Facebook",
        "category": "Sosyal Medya",
        "desc": "Facebook Page ve Messenger API – sayfa yönetimi, mesajlar",
        "fields": [
            {"key": "facebook_page_id", "label": "Page ID", "type": "text", "placeholder": ""},
            {"key": "facebook_access_token", "label": "Page Access Token", "type": "password", "placeholder": ""},
            {"key": "facebook_app_id", "label": "App ID (opsiyonel)", "type": "text", "placeholder": ""},
            {"key": "facebook_app_secret", "label": "App Secret (opsiyonel)", "type": "password", "placeholder": ""},
        ],
    },
    "twitter": {
        "name": "Twitter/X",
        "category": "Sosyal Medya",
        "desc": "Twitter/X API – tweet, DM ve analitik",
        "fields": [
            {"key": "twitter_api_key", "label": "API Key", "type": "text", "placeholder": ""},
            {"key": "twitter_api_secret", "label": "API Secret", "type": "password", "placeholder": ""},
            {"key": "twitter_access_token", "label": "Access Token", "type": "password", "placeholder": ""},
            {"key": "twitter_access_token_secret", "label": "Access Token Secret", "type": "password", "placeholder": ""},
        ],
    },
    "tiktok": {
        "name": "TikTok",
        "category": "Sosyal Medya",
        "desc": "TikTok for Business API – içerik ve mesaj yönetimi",
        "fields": [
            {"key": "tiktok_app_id", "label": "App ID", "type": "text", "placeholder": ""},
            {"key": "tiktok_app_secret", "label": "App Secret", "type": "password", "placeholder": ""},
            {"key": "tiktok_access_token", "label": "Access Token", "type": "password", "placeholder": ""},
        ],
    },
    "linkedin": {
        "name": "LinkedIn",
        "category": "Sosyal Medya",
        "desc": "LinkedIn Marketing API – sayfa ve mesaj yönetimi",
        "fields": [
            {"key": "linkedin_client_id", "label": "Client ID", "type": "text", "placeholder": ""},
            {"key": "linkedin_client_secret", "label": "Client Secret", "type": "password", "placeholder": ""},
            {"key": "linkedin_access_token", "label": "Access Token", "type": "password", "placeholder": ""},
        ],
    },
}


def get_modules_with_api_config() -> list[dict]:
    """API ayari yapilabilen modulleri dondur."""
    return [
        {
            "id": mid,
            "name": cfg["name"],
            "desc": cfg["desc"],
            "category": cfg.get("category", "Diğer"),
            "fields": cfg["fields"],
        }
        for mid, cfg in MODULE_API_FIELDS.items()
    ]


def get_module_fields(module_id: str) -> list[dict]:
    """Modulun API alan tanimlarini dondur."""
    cfg = MODULE_API_FIELDS.get(module_id)
    return cfg["fields"] if cfg else []
