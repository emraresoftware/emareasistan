"""
Kozmopol — Yapilandirma ve Sabitler
====================================
Tum konfigürasyon, kategoriler, tema, varsayilan ayarlar burada tanimlanir.
"""

import os
import logging
from dotenv import load_dotenv
from requests.auth import HTTPBasicAuth

# ════════════════════════════════════════════════════════
# ORTAM DEGISKENLERI
# ════════════════════════════════════════════════════════
load_dotenv()

SUPPLIER_ID = os.getenv('SUPPLIER_ID')
API_KEY = os.getenv('API_KEY')
API_SECRET_KEY = os.getenv('API_SECRET_KEY')
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')

MISSING_CREDS = not (SUPPLIER_ID and API_KEY and API_SECRET_KEY)
MISSING_GEMINI = not GEMINI_API_KEY

# Gemini opsiyonel
try:
    import google.generativeai as genai  # noqa: F401
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False
    print("[BILGI] google-generativeai kurulu degil. "
          "Kurmak icin: pip install google-generativeai")

if MISSING_GEMINI or not GEMINI_AVAILABLE:
    MISSING_GEMINI = True

if MISSING_CREDS:
    print("[UYARI] .env -> SUPPLIER_ID / API_KEY / API_SECRET_KEY eksik. "
          "UI calisir; API devre disi.")
if MISSING_GEMINI:
    print("[UYARI] Gemini AI kullanilamiyor "
          "(GEMINI_API_KEY eksik veya paket kurulu degil).")

# ════════════════════════════════════════════════════════
# API URL'LERI
# ════════════════════════════════════════════════════════
QNA_BASE = (
    f"https://apigw.trendyol.com/integration/qna/sellers/{SUPPLIER_ID}"
    if SUPPLIER_ID else "")

ORDER_BASE = (
    f"https://apigw.trendyol.com/integration/order/sellers/{SUPPLIER_ID}"
    if SUPPLIER_ID else "")

HEADERS = {
    "User-Agent": f"{SUPPLIER_ID or 'N/A'} - SelfIntegration",
    "Content-Type": "application/json",
}

AUTH = HTTPBasicAuth(API_KEY, API_SECRET_KEY) if not MISSING_CREDS else None

# ════════════════════════════════════════════════════════
# DOSYA YOLLARI
# ════════════════════════════════════════════════════════
RESPONSES_FILE = 'automated_responses.json'
LOG_FILE = 'question_log.json'
PENDING_FILE = 'pending_questions.json'
GEMINI_CONFIG_FILE = 'gemini_config.json'
REVIEWS_FILE = 'product_reviews.json'
TEMPLATES_FILE = 'response_templates.json'
BLACKLIST_FILE = 'word_blacklist.json'
SETTINGS_FILE = 'app_settings.json'

# ════════════════════════════════════════════════════════
# LOGLAMA
# ════════════════════════════════════════════════════════
logging.basicConfig(
    filename='kozmopol.log',
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
)
logger = logging.getLogger('kozmopol')

# ════════════════════════════════════════════════════════
# SORU KATEGORILERI
# ════════════════════════════════════════════════════════
# ════════════════════════════════════════════════════════
# MARKA RENK PALETI (Emare Finance Design Guide)
# ════════════════════════════════════════════════════════
BRAND = {
    50:  '#eef2ff',
    100: '#e0e7ff',
    200: '#c7d2fe',
    300: '#a5b4fc',
    400: '#818cf8',
    500: '#6366f1',   # Ana marka rengi (Primary)
    600: '#4f46e5',   # Hover/active primary
    700: '#4338ca',
    800: '#3730a3',
    900: '#312e81',
    950: '#1e1b4b',   # En koyu bg
}

COLORS = {
    'purple': '#9333ea',
    'green':  '#22c55e',
    'green_light': '#4ade80',
    'amber':  '#f59e0b',
    'red':    '#ef4444',
    'pink':   '#ec4899',
    'violet': '#8b5cf6',
    'cyan':   '#06b6d4',
    'white':  '#ffffff',
    'gray_50':  '#f9fafb',
    'gray_100': '#f3f4f6',
    'gray_200': '#e5e7eb',
    'gray_300': '#d1d5db',
    'gray_400': '#9ca3af',
    'gray_500': '#6b7280',
    'gray_600': '#4b5563',
    'gray_700': '#374151',
    'gray_800': '#1f2937',
    'gray_900': '#111827',
    'gray_950': '#030712',
}

FONT_FAMILY = 'Inter'
FONT_FALLBACK = ('Inter', 'SF Pro Display', 'Helvetica Neue', 'Segoe UI', 'sans-serif')

QUESTION_CATEGORIES = {
    'kargo': {
        'label': 'Kargo / Teslimat',
        'keywords': ['kargo', 'teslimat', 'gelir', 'gelmedi', 'ulasma', 'nerede',
                     'gonderi', 'takip', 'suresi', 'teslim', 'ptt', 'express',
                     'kolay gelsin', 'siparis', 'ulasti'],
        'color': BRAND[500],
        'icon': '📦',
    },
    'iade': {
        'label': 'Iade / Para Iade',
        'keywords': ['iade', 'para iade', 'geri gonder', 'degisim', 'iptal',
                     'ucret iade', 'geri al', 'geri iade', 'degistir'],
        'color': COLORS['red'],
        'icon': '↩️',
    },
    'urun': {
        'label': 'Urun Bilgisi',
        'keywords': ['orijinal', 'sahte', 'icindekiler', 'icerik', 'kullanimdir',
                     'nasil kullanilir', 'etki', 'sonuc', 'fark', 'tur', 'cesit',
                     'renk', 'boyut', 'ml', 'gram', 'islak gorunum'],
        'color': COLORS['green'],
        'icon': '🧴',
    },
    'skt': {
        'label': 'Son Kullanma Tarihi',
        'keywords': ['skt', 'son kullanma', 'tarih', 'miat', 'bozulma',
                     'taze', 'yeni uretim'],
        'color': COLORS['amber'],
        'icon': '📅',
    },
    'sac_boyasi': {
        'label': 'Sac Boyasi',
        'keywords': ['boya', 'sac boyasi', 'acici', 'renk', 'tutar',
                     'yikamada', 'ton', 'acmadan', 'aciksiz'],
        'color': COLORS['purple'],
        'icon': '💇',
    },
    'hamile': {
        'label': 'Hamile / Emziren',
        'keywords': ['hamile', 'emziren', 'bebek', 'gebelik', 'anne'],
        'color': COLORS['pink'],
        'icon': '🤰',
    },
    'paketleme': {
        'label': 'Paketleme / Ozen',
        'keywords': ['paket', 'paketleme', 'ozen', 'kirik', 'hasar',
                     'zarar', 'kirilmis', 'akmis', 'patlak'],
        'color': COLORS['violet'],
        'icon': '📋',
    },
    'hediye': {
        'label': 'Hediye / Ozel Istek',
        'keywords': ['hediye', 'not', 'mesaj', 'surpriz', 'paketlenir'],
        'color': BRAND[600],
        'icon': '🎁',
    },
    'diger': {
        'label': 'Diger',
        'keywords': [],
        'color': COLORS['gray_500'],
        'icon': '❓',
    },
}

# ════════════════════════════════════════════════════════
# VARSAYILAN AYARLAR
# ════════════════════════════════════════════════════════
DEFAULT_SETTINGS = {
    'work_hours_start': '10:00',
    'work_hours_end': '18:00',
    'work_days': [0, 1, 2, 3, 4],  # Pazartesi-Cuma
    'poll_interval': 300,  # saniye
    'notifications_enabled': True,
    'notification_sound': True,
    'dark_mode': False,
    'auto_categorize': True,
    'max_response_length': 500,
    'backup_interval_hours': 24,
    'language': 'tr',
}

DEFAULT_GEMINI_CONFIG = {
    'enabled': True,
    'model': 'gemini-2.0-flash',
    'temperature': 0.3,
    'max_tokens': 500,
    'system_prompt': (
        "Sen Kozmopol magazasinin musteri hizmetleri asistanisin. "
        "Trendyol uzerinde kozmetik ve kisisel bakim urunleri satan bir magazanin "
        "musteri sorularini yanitliyorsun.\n\n"
        "Kurallar:\n"
        "1. Her zaman nazik ve profesyonel ol\n"
        "2. \"Merhaba\" ile basla, \"Saygilar\" veya \"Saygilarimizla Kozmopol\" ile bitir\n"
        "3. Emin olmadigin tibbi/saglik bilgilerini VERME, uretici firmaya yonlendir\n"
        "4. Kargo sorularinda: Trendyol Express ve Kolay Gelsin Kargo kullanildigini belirt\n"
        "5. Iade/para iade sorularinda Trendyol musteri hizmetlerine yonlendir\n"
        "6. Urun orijinalligi soruldugunda tum urunlerin orijinal oldugunu belirt\n"
        "7. Hamile/emziren kadinlarla ilgili sorularda dikkatli ol, genel tavsiye verme\n"
        "8. Kisa ve oz yanitlar ver, maksimum 3-4 cumle\n"
        "9. Yanitindan emin degilsen [MANUAL_REVIEW] etiketi ekle\n"
        "10. Eger sana musteri yorumlari verildiyse, yanitinda bu yorumlardan YARARLAN.\n"
        "    Ornek: 'Degerli musterimizin yorumunda belirttigi gibi...' veya\n"
        "    'Urunumuzu kullanan musterilerimizin geri bildirimlerine gore...' seklinde\n"
        "    gercek yorumlara atifta bulun. Bu guvenirligi arttirir.\n"
        "11. Yorumlardaki olumlu geri bildirimleri one cikar, olumsuzlari kabul edip cozum oner"
    ),
    'confidence_threshold': 0.7,
    'auto_send': False,
    'fuzzy_threshold': 0.65,
}

DEFAULT_TEMPLATES = [
    {
        'name': 'Kargo Bilgisi',
        'text': ('Merhaba, gonderilerimizi Trendyol Express ve Kolay Gelsin '
                 'Kargo ile saglamaktayiz. {{ek_bilgi}} Saygilar, Kozmopol'),
        'variables': ['ek_bilgi'],
        'category': 'kargo',
    },
    {
        'name': 'Urun Orijinallik',
        'text': ('Merhaba, tum urunlerimiz orijinaldir. {{urun_adi}} markanin '
                 'kendisi veya ana dagiticisindan temin edilmektedir. '
                 'Saygilar, Kozmopol'),
        'variables': ['urun_adi'],
        'category': 'urun',
    },
    {
        'name': 'Iade Yonlendirme',
        'text': ('Merhaba, {{sorun_detay}} konusunda Trendyol musteri '
                 'hizmetleri ile iletisime gecmenizi rica ederiz. '
                 'Saygilarimizla Kozmopol'),
        'variables': ['sorun_detay'],
        'category': 'iade',
    },
    {
        'name': 'SKT Bilgisi',
        'text': ('Merhaba, tum urunlerimizde son kullanma tarihi en az 12 aydir. '
                 '{{urun_adi}} urunumuzun SKT bilgisi icin mesai saatlerinde '
                 'iletisime gecebilirsiniz. Saygilar'),
        'variables': ['urun_adi'],
        'category': 'skt',
    },
    {
        'name': 'Hamile/Emziren Uyarisi',
        'text': ('Merhaba, hamile ve emziren bayanlara ozel urun degilse veya '
                 'acikca belirtilmiyorsa urun onerememekteyiz. {{ek_not}} '
                 'Uretici firmanin resmi sayfasina danismanizi oneriyoruz. Saygilar'),
        'variables': ['ek_not'],
        'category': 'hamile',
    },
    {
        'name': 'Genel Bilgi Yonlendirme',
        'text': ('Merhaba, {{konu}} hakkinda en dogru bilgiyi uretici firmanin '
                 'resmi internet sayfasi veya musteri hizmetlerine ulasarak '
                 'alabilirsiniz. Saygilar, Kozmopol'),
        'variables': ['konu'],
        'category': 'diger',
    },
]

DEFAULT_BLACKLIST = [
    'sahte', 'fake', 'zararlı', 'tehlikeli', 'kanser',
    'ölüm', 'zehir', 'dava', 'şikayet', 'dolandırıcı',
]

OUT_OF_SERVICE_MSG = (
    "Merhaba, su anda mesai saatleri disindayiz. "
    "Sorunuzun karsiligi urun sayfasinda bulunan Soru-Cevap veya Degerlendirmeler "
    "sayfasinda bulunuyor olabilir, incelemenizi tavsiye edebiliriz veya "
    "Pazartesi-Cuma 10:00-17:00 arasinda sorar iseniz yardimci olabiliriz. Saygilar"
)

# ════════════════════════════════════════════════════════
# TEMA SISTEMI (Emare Finance Design Guide)
# ════════════════════════════════════════════════════════
LIGHT_THEME = {
    'bg':           COLORS['white'],
    'fg':           COLORS['gray_800'],
    'card_bg':      BRAND[50],
    'card_border':  BRAND[100],
    'accent':       BRAND[500],
    'accent_hover': BRAND[600],
    'accent_light': BRAND[50],
    'success':      COLORS['green'],
    'warning':      COLORS['amber'],
    'danger':       COLORS['red'],
    'muted':        COLORS['gray_500'],
    'input_bg':     COLORS['white'],
    'input_border': COLORS['gray_200'],
    'header_fg':    COLORS['gray_900'],
    'topbar_bg':    COLORS['white'],
    'topbar_border': BRAND[100],
    'status_bg':    BRAND[950],
    'status_fg':    BRAND[200],
    'tab_selected': BRAND[500],
    'tab_fg':       COLORS['white'],
    'sidebar_bg':   BRAND[50],
    'highlight':    BRAND[100],
    'separator':    COLORS['gray_200'],
    'bar_bg':       BRAND[100],
    'bar_fill':     BRAND[500],
}

DARK_THEME = {
    'bg':           '#0f0a2e',
    'fg':           BRAND[100],
    'card_bg':      BRAND[900],
    'card_border':  BRAND[800],
    'accent':       BRAND[400],
    'accent_hover': BRAND[300],
    'accent_light': BRAND[950],
    'success':      COLORS['green_light'],
    'warning':      COLORS['amber'],
    'danger':       COLORS['red'],
    'muted':        BRAND[300],
    'input_bg':     BRAND[800],
    'input_border': BRAND[700],
    'header_fg':    BRAND[50],
    'topbar_bg':    BRAND[950],
    'topbar_border': BRAND[800],
    'status_bg':    '#060420',
    'status_fg':    BRAND[300],
    'tab_selected': BRAND[400],
    'tab_fg':       COLORS['white'],
    'sidebar_bg':   BRAND[950],
    'highlight':    BRAND[800],
    'separator':    BRAND[800],
    'bar_bg':       BRAND[800],
    'bar_fill':     BRAND[400],
}

# Yontem etiketleri (UI‟de kullanilir)
METHOD_LABELS = {
    'keyword': 'Anahtar Kelime',
    'fuzzy': 'Bulanik Eslestirme',
    'gemini': 'Gemini AI',
    'manual_approved': 'Manuel Onay',
    'manual_edited': 'Manuel Duzenleme',
    'template': 'Sablon',
    'out_of_service': 'Mesai Disi',
    'pending': 'Beklemede',
    'no_match': 'Eslesmedi',
}
