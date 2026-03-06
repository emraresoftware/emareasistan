"""
Kozmopol — Trendyol Akilli Musteri Hizmetleri Sistemi v3.0
============================================================
Yeni Ozellikler (v3.0):
  - Soru Kategorileri: Otomatik kategorizasyon (Kargo, Urun, Iade, SKT vb.)
  - Yanit Sablonlari: Degiskenli hizli sablon sistemi
  - Kelime Kara Listesi: Hassas/yasakli kelimeleri AI yanitlarinda tespit
  - Yapilandirilabilir Mesai Saatleri: UI uzerinden ayarlanabilir
  - Toplu Islemler: Bekleyen sorulari toplu onayla/reddet
  - CSV Import/Export: Otomatik yanitlari iceri/disari aktar
  - Gunluk Rapor: Aktif gunun ozeti
  - Masaustu Bildirimleri: macOS native bildirimler
  - Performans Metrikleri: Yanit suresi, cozum orani
  - Gelismis Istatistikler: Saatlik dagilim, trend grafikleri
  - Hizli Yanit Onerileri: Sik sorulan sorulardan oneriler
  - Karanlik Mod: Tema degistirme
  - Merkezi Ayarlar Sekmesi: Tum yapilandirma tek yerde
  - Gelismis Yorum Analizi: Duygu analizi, kelime bulutu

Mevcut Ozellikler (v2.0):
  - Anahtar kelime bazli otomatik yanit
  - Google Gemini AI ile akilli yanit uretimi
  - Bulanik (fuzzy) eslestirme
  - Kargo & Iade takibi (Trendyol API)
  - Soru gecmisi & istatistikler
  - Bekleyen sorular kuyrugu (AI onay mekanizmasi)
  - Musteri yorumlari entegrasyonu
  - CSV disa aktarim
  - Sekmeli modern arayuz
"""

import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext, filedialog, colorchooser
import requests
from requests.auth import HTTPBasicAuth
import time
import threading
import json
import os
import sys
import re
import csv
import logging
import subprocess
import platform
from dotenv import load_dotenv
from datetime import datetime, timedelta
from difflib import SequenceMatcher
from collections import Counter, defaultdict

# Gemini opsiyonel
try:
    import google.generativeai as genai
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False
    print("[BILGI] google-generativeai kurulu degil. Kurmak icin: pip install google-generativeai")

# ════════════════════════════════════════════════════════
# YAPILANDIRMA
# ════════════════════════════════════════════════════════
load_dotenv()
supplier_id = os.getenv('SUPPLIER_ID')
api_key = os.getenv('API_KEY')
api_secret_key = os.getenv('API_SECRET_KEY')
gemini_api_key = os.getenv('GEMINI_API_KEY')

MISSING_CREDS = not (supplier_id and api_key and api_secret_key)
MISSING_GEMINI = not gemini_api_key or not GEMINI_AVAILABLE

if MISSING_CREDS:
    print("[UYARI] .env -> SUPPLIER_ID / API_KEY / API_SECRET_KEY eksik. UI calisir; API devre disi.")
if MISSING_GEMINI:
    print("[UYARI] Gemini AI kullanilamiyor (GEMINI_API_KEY eksik veya paket kurulu degil).")

# API URL'leri
QNA_BASE = (f"https://apigw.trendyol.com/integration/qna/sellers/{supplier_id}"
            if supplier_id else "")
ORDER_BASE = (f"https://apigw.trendyol.com/integration/order/sellers/{supplier_id}"
              if supplier_id else "")
HEADERS = {
    "User-Agent": f"{supplier_id or 'N/A'} - SelfIntegration",
    "Content-Type": "application/json",
}
AUTH = HTTPBasicAuth(api_key, api_secret_key) if not MISSING_CREDS else None

# Dosya yollari
RESPONSES_FILE = 'automated_responses.json'
LOG_FILE = 'question_log.json'
PENDING_FILE = 'pending_questions.json'
GEMINI_CONFIG_FILE = 'gemini_config.json'
REVIEWS_FILE = 'product_reviews.json'
TEMPLATES_FILE = 'response_templates.json'
BLACKLIST_FILE = 'word_blacklist.json'
SETTINGS_FILE = 'app_settings.json'

# Thread kilidi
data_lock = threading.Lock()

# Loglama
logging.basicConfig(
    filename='kozmopol.log',
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
)
logger = logging.getLogger('kozmopol')

# ════════════════════════════════════════════════════════
# VERI DEPOLARI
# ════════════════════════════════════════════════════════
automated_responses: dict = {}  # {('anahtar','kelime'): 'cevap', ...}
question_log: list = []
pending_questions: list = []
product_reviews: dict = {}  # {product_name: [{'comment','rate','date','user'}, ...]}
response_templates: list = []  # [{'name','text','variables'}, ...]
word_blacklist: list = []  # ['yasakli_kelime', ...]

# ════════════════════════════════════════════════════════
# SORU KATEGORILERI
# ════════════════════════════════════════════════════════
QUESTION_CATEGORIES = {
    'kargo': {
        'label': 'Kargo / Teslimat',
        'keywords': ['kargo', 'teslimat', 'gelir', 'gelmedi', 'ulasma', 'nerede',
                     'gonderi', 'takip', 'suresi', 'teslim', 'ptt', 'express',
                     'kolay gelsin', 'siparis', 'ulasti'],
        'color': '#2196F3',
        'icon': '📦',
    },
    'iade': {
        'label': 'Iade / Para Iade',
        'keywords': ['iade', 'para iade', 'geri gonder', 'degisim', 'iptal',
                     'ucret iade', 'geri al', 'geri iade', 'degistir'],
        'color': '#f44336',
        'icon': '↩️',
    },
    'urun': {
        'label': 'Urun Bilgisi',
        'keywords': ['orijinal', 'sahte', 'icindekiler', 'icerik', 'kullanimdir',
                     'nasil kullanilir', 'etki', 'sonuc', 'fark', 'tur', 'cesit',
                     'renk', 'boyut', 'ml', 'gram', 'islak gorunum'],
        'color': '#4CAF50',
        'icon': '🧴',
    },
    'skt': {
        'label': 'Son Kullanma Tarihi',
        'keywords': ['skt', 'son kullanma', 'tarih', 'miat', 'bozulma',
                     'taze', 'yeni uretim'],
        'color': '#FF9800',
        'icon': '📅',
    },
    'sac_boyasi': {
        'label': 'Sac Boyasi',
        'keywords': ['boya', 'sac boyasi', 'acici', 'renk', 'tutar',
                     'yikamada', 'ton', 'acmadan', 'aciksiz'],
        'color': '#9C27B0',
        'icon': '💇',
    },
    'hamile': {
        'label': 'Hamile / Emziren',
        'keywords': ['hamile', 'emziren', 'bebek', 'gebelik', 'anne'],
        'color': '#E91E63',
        'icon': '🤰',
    },
    'paketleme': {
        'label': 'Paketleme / Ozen',
        'keywords': ['paket', 'paketleme', 'ozen', 'kirik', 'hasar',
                     'zarar', 'kirilmis', 'akmis', 'patlak'],
        'color': '#795548',
        'icon': '📋',
    },
    'hediye': {
        'label': 'Hediye / Ozel Istek',
        'keywords': ['hediye', 'not', 'mesaj', 'surpriz', 'paketlenir'],
        'color': '#607D8B',
        'icon': '🎁',
    },
    'diger': {
        'label': 'Diger',
        'keywords': [],
        'color': '#9E9E9E',
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
app_settings: dict = {}

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
gemini_config: dict = {}

OUT_OF_SERVICE_MSG = (
    "Merhaba, su anda mesai saatleri disindayiz. "
    "Sorunuzun karsiligi urun sayfasinda bulunan Soru-Cevap veya Degerlendirmeler "
    "sayfasinda bulunuyor olabilir, incelemenizi tavsiye edebiliriz veya "
    "Pazartesi-Cuma 10:00-17:00 arasinda sorar iseniz yardimci olabiliriz. Saygilar"
)


# ════════════════════════════════════════════════════════
# YARDIMCI FONKSIYONLAR
# ════════════════════════════════════════════════════════

def normalize_key_text(key_text: str):
    """Virgul ile ayrilmis metni normalize tuple'a donustur."""
    return tuple(w.strip().lower() for w in key_text.split(',') if w.strip())


def normalize_key_tuple(key_tuple):
    return tuple(w.strip().lower() for w in key_tuple if str(w).strip())


def normalize_dict(d: dict):
    norm = {}
    for k, v in d.items():
        nk = (normalize_key_tuple(k) if isinstance(k, (tuple, list))
              else normalize_key_text(str(k)))
        if nk:
            norm[nk] = v
    return norm


def categorize_question(question_text: str) -> str:
    """Soruyu otomatik kategorize et. Doner: kategori kodu."""
    qtext = question_text.lower()
    scores = {}
    for cat_code, cat_info in QUESTION_CATEGORIES.items():
        if cat_code == 'diger':
            continue
        score = 0
        for kw in cat_info['keywords']:
            if kw in qtext:
                score += 1
                # Cok kelimeli eslesmeler bonus verir
                if ' ' in kw:
                    score += 0.5
        scores[cat_code] = score
    if not scores or max(scores.values()) == 0:
        return 'diger'
    return max(scores, key=scores.get)


def check_blacklist(text: str) -> list:
    """Metinde kara listedeki kelimeleri kontrol et. Bulunanları doner."""
    if not word_blacklist:
        return []
    text_lower = text.lower()
    found = [w for w in word_blacklist if w.lower() in text_lower]
    return found


def send_notification(title: str, message: str):
    """Masaustu bildirimimi gonder (macOS)."""
    if not app_settings.get('notifications_enabled', True):
        return
    try:
        if platform.system() == 'Darwin':
            # macOS native notification
            subprocess.run([
                'osascript', '-e',
                f'display notification "{message}" with title "{title}"'
            ], capture_output=True, timeout=5)
        elif platform.system() == 'Linux':
            subprocess.run(
                ['notify-send', title, message],
                capture_output=True, timeout=5)
        elif platform.system() == 'Windows':
            # Windows Toast (basit fallback)
            from tkinter import messagebox as _mb
            # Notification sound
            pass
    except Exception as e:
        logger.debug(f"Bildirim gonderilemedi: {e}")


def fill_template(template_text: str, variables: dict) -> str:
    """Sablondaki degiskenleri doldur. {{degisken}} formatinda."""
    result = template_text
    for key, value in variables.items():
        result = result.replace(f'{{{{{key}}}}}', str(value))
    return result


# ════════════════════════════════════════════════════════
# VERI YUKLEME / KAYDETME
# ════════════════════════════════════════════════════════

def _safe_load_json(filepath, default):
    """JSON dosyasini guvenli yukle."""
    if os.path.exists(filepath) and os.path.getsize(filepath) > 0:
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            logger.error(f"{filepath} okuma hatasi: {e}")
    return default


def _safe_save_json(filepath, data):
    """JSON dosyasini guvenli kaydet."""
    try:
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except IOError as e:
        logger.error(f"{filepath} yazma hatasi: {e}")


def load_responses():
    with data_lock:
        raw = _safe_load_json(RESPONSES_FILE, {})
        loaded = {}
        for key_str, value in raw.items():
            nk = normalize_key_text(key_str)
            if nk:
                loaded[nk] = value
        automated_responses.clear()
        automated_responses.update(loaded)


def save_responses():
    with data_lock:
        data = {','.join(k): v for k, v in automated_responses.items()}
        _safe_save_json(RESPONSES_FILE, data)


def load_question_log():
    global question_log
    question_log = _safe_load_json(LOG_FILE, [])


def save_question_log():
    _safe_save_json(LOG_FILE, question_log)


def load_pending():
    global pending_questions
    pending_questions = _safe_load_json(PENDING_FILE, [])


def save_pending():
    _safe_save_json(PENDING_FILE, pending_questions)


def load_gemini_config():
    global gemini_config
    gemini_config = dict(DEFAULT_GEMINI_CONFIG)
    saved = _safe_load_json(GEMINI_CONFIG_FILE, {})
    gemini_config.update(saved)


def save_gemini_config():
    _safe_save_json(GEMINI_CONFIG_FILE, gemini_config)


def load_reviews():
    global product_reviews
    product_reviews = _safe_load_json(REVIEWS_FILE, {})


def save_reviews():
    _safe_save_json(REVIEWS_FILE, product_reviews)


def load_templates():
    global response_templates
    saved = _safe_load_json(TEMPLATES_FILE, None)
    if saved is not None:
        response_templates = saved
    else:
        response_templates = [
            {
                'name': 'Kargo Bilgisi',
                'text': 'Merhaba, gonderilerimizi Trendyol Express ve Kolay Gelsin Kargo ile saglamaktayiz. {{ek_bilgi}} Saygilar, Kozmopol',
                'variables': ['ek_bilgi'],
                'category': 'kargo',
            },
            {
                'name': 'Urun Orijinallik',
                'text': 'Merhaba, tum urunlerimiz orijinaldir. {{urun_adi}} markanin kendisi veya ana dagiticisindan temin edilmektedir. Saygilar, Kozmopol',
                'variables': ['urun_adi'],
                'category': 'urun',
            },
            {
                'name': 'Iade Yonlendirme',
                'text': 'Merhaba, {{sorun_detay}} konusunda Trendyol musteri hizmetleri ile iletisime gecmenizi rica ederiz. Saygilarimizla Kozmopol',
                'variables': ['sorun_detay'],
                'category': 'iade',
            },
            {
                'name': 'SKT Bilgisi',
                'text': 'Merhaba, tum urunlerimizde son kullanma tarihi en az 12 aydir. {{urun_adi}} urunumuzun SKT bilgisi icin mesai saatlerinde iletisime gecebilirsiniz. Saygilar',
                'variables': ['urun_adi'],
                'category': 'skt',
            },
            {
                'name': 'Hamile/Emziren Uyarisi',
                'text': 'Merhaba, hamile ve emziren bayanlara ozel urun degilse veya acikca belirtilmiyorsa urun onerememekteyiz. {{ek_not}} Uretici firmanin resmi sayfasina danismanizi oneriyoruz. Saygilar',
                'variables': ['ek_not'],
                'category': 'hamile',
            },
            {
                'name': 'Genel Bilgi Yonlendirme',
                'text': 'Merhaba, {{konu}} hakkinda en dogru bilgiyi uretici firmanin resmi internet sayfasi veya musteri hizmetlerine ulasarak alabilirsiniz. Saygilar, Kozmopol',
                'variables': ['konu'],
                'category': 'diger',
            },
        ]
        save_templates()


def save_templates():
    _safe_save_json(TEMPLATES_FILE, response_templates)


def load_blacklist():
    global word_blacklist
    saved = _safe_load_json(BLACKLIST_FILE, None)
    if saved is not None:
        word_blacklist = saved
    else:
        word_blacklist = [
            'sahte', 'fake', 'zararlı', 'tehlikeli', 'kanser',
            'ölüm', 'zehir', 'dava', 'şikayet', 'dolandırıcı',
        ]
        save_blacklist()


def save_blacklist():
    _safe_save_json(BLACKLIST_FILE, word_blacklist)


def load_settings():
    global app_settings
    app_settings = dict(DEFAULT_SETTINGS)
    saved = _safe_load_json(SETTINGS_FILE, {})
    app_settings.update(saved)


def save_settings():
    _safe_save_json(SETTINGS_FILE, app_settings)


def add_log_entry(question_id, question_text, answer_text, method,
                  product_info="", category=""):
    """Soru loguna kayit ekle."""
    if not category and app_settings.get('auto_categorize', True):
        category = categorize_question(question_text)
    entry = {
        'timestamp': datetime.now().isoformat(),
        'question_id': question_id,
        'question': question_text,
        'answer': answer_text,
        'method': method,
        'product_info': product_info,
        'category': category,
    }
    question_log.append(entry)
    save_question_log()
    logger.info(f"[{method}][{category}] Q:{question_text[:60]}... -> A:{answer_text[:60]}...")


# ════════════════════════════════════════════════════════
# ZAMANLAMA
# ════════════════════════════════════════════════════════

def is_out_of_service_hours():
    now = datetime.now()
    work_start = app_settings.get('work_hours_start', '10:00')
    work_end = app_settings.get('work_hours_end', '18:00')
    work_days = app_settings.get('work_days', [0, 1, 2, 3, 4])

    t = now.time()
    start_t = datetime.strptime(work_start, "%H:%M").time()
    end_t = datetime.strptime(work_end, "%H:%M").time()

    # Hafta sonu veya mesai disi
    if now.weekday() not in work_days:
        return True
    if t < start_t or t >= end_t:
        return True
    return False


# ════════════════════════════════════════════════════════
# ESLESTIRME MOTORU
# ════════════════════════════════════════════════════════

def exact_keyword_match(question_text: str):
    """AND mantigi: tuple'daki tum kelimeler soru metninde gecmeli."""
    qtext = question_text.lower()
    for search_words, response_text in list(automated_responses.items()):
        if all(word in qtext for word in search_words):
            return response_text
    return None


def fuzzy_keyword_match(question_text: str):
    """Bulanik eslestirme — benzer kelimeleri de yakalar."""
    threshold = gemini_config.get('fuzzy_threshold', 0.65)
    qtext = question_text.lower()
    question_words = set(re.findall(r'\w+', qtext))

    best_match = None
    best_score = 0.0

    for search_words, response_text in automated_responses.items():
        matched = 0
        for sw in search_words:
            if sw in qtext:
                matched += 1
                continue
            for qw in question_words:
                if SequenceMatcher(None, sw, qw).ratio() > 0.80:
                    matched += 1
                    break
        if len(search_words) > 0:
            score = matched / len(search_words)
            if score > best_score:
                best_score = score
                best_match = response_text

    if best_score >= threshold:
        return best_match, best_score
    return None, 0.0


def get_quick_suggestions(question_text: str, max_results: int = 3) -> list:
    """Soru metnine gore sik sorulan sorulardan hizli oneriler getir."""
    if not question_log:
        return []

    qtext = question_text.lower()
    q_words = set(re.findall(r'\w+', qtext))
    q_words = {w for w in q_words if len(w) > 2}

    scored = []
    seen_answers = set()

    for entry in question_log:
        answer = entry.get('answer', '')
        if not answer or answer.startswith('[') or answer in seen_answers:
            continue
        eq = entry.get('question', '').lower()
        e_words = set(re.findall(r'\w+', eq))
        overlap = len(q_words & e_words)
        if overlap > 0:
            scored.append((overlap, answer, entry.get('question', '')))
            seen_answers.add(answer)

    scored.sort(key=lambda x: -x[0])
    return [(s[2], s[1]) for s in scored[:max_results]]


# ════════════════════════════════════════════════════════
# GEMINI AI
# ════════════════════════════════════════════════════════

def generate_gemini_response(question_text: str, product_info: str = None):
    """Gemini API ile akilli yanit uret. -> (yanit, guven) veya (None, 0)."""
    if MISSING_GEMINI or not gemini_config.get('enabled', False):
        return None, 0.0

    try:
        genai.configure(api_key=gemini_api_key)
        model = genai.GenerativeModel(
            gemini_config.get('model', 'gemini-2.0-flash'))

        # Magaza tarzini ornek yanitlardan cikar
        examples = ""
        sample_items = list(automated_responses.items())[:5]
        if sample_items:
            examples = "\n\nOrnek Yanitlar (magazanin uslubu):\n"
            for keys, resp in sample_items:
                examples += f"- Anahtar: {', '.join(keys)} -> {resp[:120]}\n"

        # Ilgili musteri yorumlarini bul ve prompt'a ekle
        review_context = ''
        if product_reviews:
            relevant = find_relevant_reviews(
                question_text, product_info or '', max_reviews=5)
            review_context = format_reviews_for_prompt(relevant)

        prompt = (
            f"{gemini_config.get('system_prompt', '')}"
            f"{examples}"
            f"{review_context}"
            f"\n\nMusteri Sorusu: {question_text}"
        )
        if product_info:
            prompt += f"\nUrun Bilgisi: {product_info}"
        prompt += "\n\nYanitini ver:"

        response = model.generate_content(
            prompt,
            generation_config=genai.GenerationConfig(
                temperature=gemini_config.get('temperature', 0.3),
                max_output_tokens=gemini_config.get('max_tokens', 500),
            ),
        )

        answer = response.text.strip()
        needs_review = '[MANUAL_REVIEW]' in answer
        answer = answer.replace('[MANUAL_REVIEW]', '').strip()
        confidence = 0.50 if needs_review else 0.85

        # Kara liste kontrolu
        blacklisted = check_blacklist(answer)
        if blacklisted:
            logger.warning(
                f"Gemini yanitinda kara liste kelimeleri tespit edildi: {blacklisted}")
            answer = f"[KARA_LISTE_UYARI: {', '.join(blacklisted)}] {answer}"
            confidence = min(confidence, 0.40)
            needs_review = True

        logger.info(f"Gemini yanit (guven: {confidence:.0%}): {answer[:80]}...")
        return answer, confidence

    except Exception as e:
        logger.error(f"Gemini API hatasi: {e}")
        return None, 0.0


# ════════════════════════════════════════════════════════
# SORU ISLEME ZINCIRI
# ════════════════════════════════════════════════════════

def process_question(question_id, question_text, product_info=""):
    """
    Isleme sirasi:
      1) Tam anahtar kelime eslesmesi
      2) Bulanik eslestirme
      3) Gemini AI
      4) Bekleyen sorulara ekle
    Donus: (yanitlandi_mi: bool, yontem: str)
    """
    category = categorize_question(question_text)

    # 1. Exact keyword
    resp = exact_keyword_match(question_text)
    if resp:
        answer_question(question_id, resp)
        add_log_entry(question_id, question_text, resp, 'keyword',
                      product_info, category)
        return True, 'keyword'

    # 2. Fuzzy
    fuzzy_resp, fuzzy_score = fuzzy_keyword_match(question_text)
    if fuzzy_resp:
        answer_question(question_id, fuzzy_resp)
        add_log_entry(question_id, question_text, fuzzy_resp, 'fuzzy',
                      product_info, category)
        return True, 'fuzzy'

    # 3. Gemini AI
    if not MISSING_GEMINI and gemini_config.get('enabled', False):
        ai_response, confidence = generate_gemini_response(
            question_text, product_info)
        if ai_response:
            threshold = gemini_config.get('confidence_threshold', 0.7)
            if (confidence >= threshold
                    and gemini_config.get('auto_send', False)
                    and '[KARA_LISTE_UYARI' not in ai_response):
                answer_question(question_id, ai_response)
                add_log_entry(question_id, question_text, ai_response,
                              'gemini', product_info, category)
                return True, 'gemini'
            else:
                # Onay kuyruguna ekle
                pending_questions.append({
                    'question_id': question_id,
                    'question': question_text,
                    'suggested_answer': ai_response,
                    'confidence': confidence,
                    'product_info': product_info,
                    'timestamp': datetime.now().isoformat(),
                    'status': 'pending',
                    'category': category,
                })
                save_pending()
                add_log_entry(question_id, question_text,
                              f"[BEKLEMEDE] {ai_response}",
                              'pending', product_info, category)
                # Bildirim gonder
                send_notification(
                    "Kozmopol — Yeni Bekleyen Soru",
                    f"Kategori: {QUESTION_CATEGORIES.get(category, {}).get('label', category)} | {question_text[:60]}...")
                return False, 'pending'

    # 4. Hicbiri eslesmedi
    pending_questions.append({
        'question_id': question_id,
        'question': question_text,
        'suggested_answer': '',
        'confidence': 0.0,
        'product_info': product_info,
        'timestamp': datetime.now().isoformat(),
        'status': 'no_match',
        'category': category,
    })
    save_pending()
    add_log_entry(question_id, question_text, "[ESLESMEDI]",
                  'no_match', product_info, category)
    send_notification(
        "Kozmopol — Eslesmedi",
        f"Yanit bulunamadi: {question_text[:60]}...")
    return False, 'no_match'


# ════════════════════════════════════════════════════════
# TRENDYOL API
# ════════════════════════════════════════════════════════

def _api_get(url):
    """Ortak GET istegi."""
    try:
        r = requests.get(url, headers=HEADERS, auth=AUTH, timeout=30)
        if r.status_code == 200:
            return r.json()
        logger.warning(f"API GET {r.status_code}: {url}")
    except Exception as e:
        logger.error(f"API baglanti hatasi: {e}")
    return None


def get_customer_questions():
    if MISSING_CREDS:
        return None
    return _api_get(
        f"{QNA_BASE}/questions/filter?status=WAITING_FOR_ANSWER")


def answer_question(question_id, answer):
    if MISSING_CREDS:
        print(f"[Simulasyon] Yanit (ID={question_id}): {answer[:80]}...")
        logger.info(f"[Simulasyon] Yanit gonderildi: {question_id}")
        return True
    url = f"{QNA_BASE}/questions/{question_id}/answers"
    payload = {"text": answer}
    try:
        r = requests.post(url, headers=HEADERS, auth=AUTH,
                          json=payload, timeout=30)
        if r.status_code == 200:
            logger.info(f"Yanit gonderildi: Q#{question_id}")
            return True
        logger.error(f"Yanit gonderilemedi ({r.status_code}): {r.text}")
        return False
    except Exception as e:
        logger.error(f"Yanit gonderme hatasi: {e}")
        return False


def get_orders(days=7):
    """Son N gunun siparislerini cek."""
    if MISSING_CREDS:
        return []
    end_ts = int(datetime.now().timestamp() * 1000)
    start_ts = int((datetime.now() - timedelta(days=days)).timestamp() * 1000)
    data = _api_get(
        f"{ORDER_BASE}/orders?startDate={start_ts}&endDate={end_ts}")
    return data.get('content', []) if data else []


def get_claims(days=30):
    """Son N gunun iade/taleplerini cek."""
    if MISSING_CREDS:
        return []
    end_ts = int(datetime.now().timestamp() * 1000)
    start_ts = int((datetime.now() - timedelta(days=days)).timestamp() * 1000)
    data = _api_get(
        f"{ORDER_BASE}/claims?startDate={start_ts}&endDate={end_ts}")
    return data.get('content', []) if data else []


def fetch_product_reviews(page=0, size=100, approved=True):
    """Trendyol API'den urun yorumlarini cek."""
    if MISSING_CREDS:
        return []
    status = 'APPROVED' if approved else ''
    url = (f"https://apigw.trendyol.com/integration/"
           f"product/sellers/{supplier_id}/products/reviews"
           f"?page={page}&size={size}")
    if status:
        url += f"&status={status}"
    data = _api_get(url)
    return data.get('content', []) if data else []


def fetch_all_reviews(max_pages=10):
    """Tum sayfalardaki yorumlari cek ve cache'e kaydet."""
    all_reviews = []
    for page in range(max_pages):
        batch = fetch_product_reviews(page=page, size=100)
        if not batch:
            break
        all_reviews.extend(batch)
        logger.info(f"Yorum sayfasi {page}: {len(batch)} yorum cekildi")
        if len(batch) < 100:
            break
        time.sleep(0.5)  # rate limit

    # Urun bazinda gruplama
    grouped: dict = {}
    for r in all_reviews:
        product_name = (r.get('productName') or 'Bilinmeyen').strip()
        review_entry = {
            'comment': (r.get('comment') or '').strip(),
            'rate': r.get('rate', 0),
            'date': '',
            'user': (r.get('customerFirstName') or '') + ' '
                    + (r.get('customerLastName') or '').strip(),
            'product_id': r.get('productId', ''),
        }
        ts = r.get('lastModifiedDate') or r.get('createdDate')
        if ts:
            try:
                review_entry['date'] = datetime.fromtimestamp(
                    ts / 1000).strftime('%Y-%m-%d')
            except Exception:
                pass

        if review_entry['comment']:  # Bos yorumlari atla
            grouped.setdefault(product_name, []).append(review_entry)

    product_reviews.clear()
    product_reviews.update(grouped)
    save_reviews()
    total = sum(len(v) for v in grouped.values())
    logger.info(f"Toplam {total} yorum, {len(grouped)} urun icin kaydedildi")
    return total, len(grouped)


def find_relevant_reviews(question_text: str, product_name: str = '',
                          max_reviews: int = 5):
    """Soruyla en ilgili yorumlari bul."""
    qtext = question_text.lower()
    q_words = set(re.findall(r'\w+', qtext))
    q_words = {w for w in q_words if len(w) > 2}

    scored: list = []

    for prod_name, reviews in product_reviews.items():
        pname_lower = prod_name.lower()
        product_bonus = 0.0
        if product_name:
            pn = product_name.lower()
            if pn in pname_lower or pname_lower in pn:
                product_bonus = 2.0
            else:
                common = len(set(pn.split()) & set(pname_lower.split()))
                product_bonus = common * 0.3

        for rev in reviews:
            comment = (rev.get('comment') or '').lower()
            if not comment or len(comment) < 10:
                continue
            c_words = set(re.findall(r'\w+', comment))
            overlap = len(q_words & c_words)
            if overlap == 0 and product_bonus == 0:
                continue
            score = overlap * 1.0 + product_bonus
            rate = rev.get('rate', 0)
            if rate >= 4:
                score += 0.3
            elif rate <= 2:
                score -= 0.2
            scored.append((prod_name, rev, score))

    scored.sort(key=lambda x: -x[2])
    return scored[:max_reviews]


def format_reviews_for_prompt(relevant_reviews: list) -> str:
    """Gemini promptuna eklenecek yorum metni olustur."""
    if not relevant_reviews:
        return ''

    lines = ['\n\n=== MUSTERI YORUMLARI (gercek kullanici deneyimleri) ===']
    for i, (prod, rev, score) in enumerate(relevant_reviews, 1):
        user = rev.get('user', '').strip() or 'Anonim'
        rate = rev.get('rate', 0)
        comment = rev.get('comment', '')
        date = rev.get('date', '')
        stars = '*' * rate
        lines.append(
            f"Yorum {i} | Urun: {prod[:50]} | "
            f"Kullanici: {user} | Puan: {stars} ({rate}/5) | "
            f"Tarih: {date}\n"
            f"  \"{comment[:300]}\"")
    lines.append(
        '\nBu yorumlari yanitinda kullan. '
        'Ornegin: "Musterilerimizin geri bildirimlerine gore...", '
        '"Degerli musterimizin yorumunda belirttigi gibi...", '
        '"Urunumuzu kullanan musterilerimiz ... oldugunu belirtmistir." '
        'gibi ifadelerle gercek deneyimlere atifta bulun.')
    return '\n'.join(lines)


def get_review_sentiment_stats() -> dict:
    """Yorum duygu analizi istatistikleri."""
    if not product_reviews:
        return {}
    stats = {
        'total': 0,
        'positive': 0,  # 4-5 puan
        'neutral': 0,   # 3 puan
        'negative': 0,  # 1-2 puan
        'avg_rate': 0.0,
        'by_product': {},
    }
    total_rate = 0
    for prod_name, reviews in product_reviews.items():
        prod_stats = {'total': 0, 'avg': 0, 'positive': 0,
                      'negative': 0}
        prod_rate_sum = 0
        for rev in reviews:
            rate = rev.get('rate', 0)
            stats['total'] += 1
            total_rate += rate
            prod_stats['total'] += 1
            prod_rate_sum += rate
            if rate >= 4:
                stats['positive'] += 1
                prod_stats['positive'] += 1
            elif rate == 3:
                stats['neutral'] += 1
            else:
                stats['negative'] += 1
                prod_stats['negative'] += 1
        if prod_stats['total'] > 0:
            prod_stats['avg'] = prod_rate_sum / prod_stats['total']
        stats['by_product'][prod_name] = prod_stats
    if stats['total'] > 0:
        stats['avg_rate'] = total_rate / stats['total']
    return stats


# ════════════════════════════════════════════════════════
# PERFORMANS METRIKLERI
# ════════════════════════════════════════════════════════

def get_performance_metrics() -> dict:
    """Gunluk / haftalik performans metriklerini hesapla."""
    now = datetime.now()
    today_str = now.date().isoformat()
    week_start = (now - timedelta(days=now.weekday())).date().isoformat()

    metrics = {
        'total_questions': len(question_log),
        'today_questions': 0,
        'week_questions': 0,
        'auto_resolved': 0,
        'manual_resolved': 0,
        'unresolved': 0,
        'auto_rate': 0.0,
        'category_distribution': defaultdict(int),
        'hourly_distribution': defaultdict(int),
        'daily_distribution': defaultdict(int),
        'method_counts': Counter(),
        'avg_response_methods': {},
    }

    for entry in question_log:
        ts = entry.get('timestamp', '')
        method = entry.get('method', '')
        category = entry.get('category', 'diger')

        metrics['method_counts'][method] += 1
        metrics['category_distribution'][category] += 1

        if ts.startswith(today_str):
            metrics['today_questions'] += 1
        if ts >= week_start:
            metrics['week_questions'] += 1

        # Saatlik dagilim
        try:
            dt = datetime.fromisoformat(ts)
            metrics['hourly_distribution'][dt.hour] += 1
            metrics['daily_distribution'][dt.strftime('%A')] += 1
        except (ValueError, TypeError):
            pass

        if method in ('keyword', 'fuzzy', 'gemini'):
            metrics['auto_resolved'] += 1
        elif method in ('manual_approved', 'manual_edited'):
            metrics['manual_resolved'] += 1
        elif method in ('pending', 'no_match'):
            metrics['unresolved'] += 1

    total = metrics['auto_resolved'] + metrics['manual_resolved']
    if total > 0:
        metrics['auto_rate'] = metrics['auto_resolved'] / total

    return metrics


def generate_daily_report() -> str:
    """Gunluk rapor olustur."""
    now = datetime.now()
    today_str = now.date().isoformat()
    today_entries = [e for e in question_log
                     if e.get('timestamp', '').startswith(today_str)]
    total = len(today_entries)
    if total == 0:
        return f"=== Gunluk Rapor — {today_str} ===\n\nBugun soru islenmedi."

    methods = Counter(e.get('method', '') for e in today_entries)
    categories = Counter(e.get('category', 'diger') for e in today_entries)

    auto = methods.get('keyword', 0) + methods.get('fuzzy', 0) + methods.get('gemini', 0)
    manual = methods.get('manual_approved', 0) + methods.get('manual_edited', 0)

    report_lines = [
        f"=== Gunluk Rapor — {today_str} ===",
        f"",
        f"Toplam Soru: {total}",
        f"Otomatik Cozulunen: {auto} ({auto/total*100:.0f}%)" if total else "",
        f"Manuel Cozulunen: {manual}",
        f"Bekleyen: {methods.get('pending', 0) + methods.get('no_match', 0)}",
        f"",
        "--- Yontem Dagilimi ---",
    ]
    method_labels = {
        'keyword': 'Anahtar Kelime',
        'fuzzy': 'Bulanik Eslestirme',
        'gemini': 'Gemini AI',
        'manual_approved': 'Manuel Onay',
        'manual_edited': 'Manuel Duzenleme',
        'out_of_service': 'Mesai Disi',
        'pending': 'Beklemede',
        'no_match': 'Eslesmedi',
    }
    for m, c in methods.most_common():
        report_lines.append(f"  {method_labels.get(m, m)}: {c}")

    report_lines.append("")
    report_lines.append("--- Kategori Dagilimi ---")
    for cat, c in categories.most_common():
        cat_info = QUESTION_CATEGORIES.get(cat, {})
        label = cat_info.get('label', cat)
        report_lines.append(f"  {label}: {c}")

    # Aktif bekleyenler
    active_pending = [p for p in pending_questions
                      if p.get('status') in ('pending', 'no_match')]
    if active_pending:
        report_lines.append(f"\n--- Aktif Bekleyen Sorular: {len(active_pending)} ---")
        for p in active_pending[:5]:
            report_lines.append(
                f"  • {p.get('question', '')[:60]}... "
                f"[{QUESTION_CATEGORIES.get(p.get('category', 'diger'), {}).get('label', '?')}]")

    return '\n'.join(report_lines)


# ════════════════════════════════════════════════════════
# ARKA PLAN IS PARCACIGI
# ════════════════════════════════════════════════════════

def check_and_answer_questions():
    """Poll interval'da sorulari kontrol eden daemon thread."""
    answered_ids: set = set()
    while True:
        try:
            questions = get_customer_questions()
            if (questions
                    and 'content' in questions
                    and questions['content']):
                for q in questions['content']:
                    qid = q.get('id')
                    qtext = (q.get('text') or '').strip()
                    product_info = q.get('productName', '')

                    if not qid or qid in answered_ids:
                        continue

                    logger.info(f"Yeni soru: [{qid}] {qtext}")
                    print(f"Cekilen Soru: {qtext}")

                    answered, method = process_question(
                        qid, qtext, product_info)

                    if not answered and method == 'no_match':
                        app_ref = globals().get('app')
                        if (is_out_of_service_hours()
                                and app_ref
                                and getattr(app_ref, 'out_of_office_var', None)
                                and app_ref.out_of_office_var.get()):
                            answer_question(qid, OUT_OF_SERVICE_MSG)
                            add_log_entry(qid, qtext, OUT_OF_SERVICE_MSG,
                                          'out_of_service', product_info)

                    answered_ids.add(qid)

                    # UI guncelle
                    app_ref = globals().get('app')
                    if app_ref:
                        try:
                            app_ref.after(100, app_ref.refresh_all_tabs)
                        except Exception:
                            pass
            else:
                logger.debug("Bekleyen soru yok veya API yaniti bos")

            interval = app_settings.get('poll_interval', 300)
            time.sleep(interval)

        except Exception as e:
            logger.error(f"Thread hatasi: {e}")
            time.sleep(300)


# ════════════════════════════════════════════════════════
# TEMA SISTEMI
# ════════════════════════════════════════════════════════

LIGHT_THEME = {
    'bg': '#ffffff',
    'fg': '#000000',
    'card_bg': '#f8f8f8',
    'card_border': '#e0e0e0',
    'accent': '#2196F3',
    'success': '#4CAF50',
    'warning': '#FF9800',
    'danger': '#f44336',
    'muted': '#666666',
    'input_bg': '#ffffff',
    'header_fg': '#333333',
}

DARK_THEME = {
    'bg': '#1e1e1e',
    'fg': '#d4d4d4',
    'card_bg': '#2d2d2d',
    'card_border': '#404040',
    'accent': '#569cd6',
    'success': '#6a9955',
    'warning': '#ce9178',
    'danger': '#f44747',
    'muted': '#808080',
    'input_bg': '#3c3c3c',
    'header_fg': '#e0e0e0',
}


def get_theme() -> dict:
    """Aktif temayi doner."""
    if app_settings.get('dark_mode', False):
        return DARK_THEME
    return LIGHT_THEME


# ════════════════════════════════════════════════════════
# UI — ANA UYGULAMA
# ════════════════════════════════════════════════════════

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Kozmopol — Trendyol Akilli Musteri Hizmetleri v3.0")
        self.geometry("1300x850")
        self.minsize(1100, 650)

        self.out_of_office_var = tk.BooleanVar(value=True)
        self.status_var = tk.StringVar(value="Hazir")
        self.selected_key = None
        self.theme = get_theme()

        self._build_ui()

        # Ilk yukleme
        self.reload_responses_list()
        self.refresh_pending_list()
        self.refresh_log_list()
        self.refresh_stats()
        self.refresh_templates_list()
        self.refresh_blacklist_display()

    # ───────────────────────────────────────────
    # UI OLUSTURMA
    # ───────────────────────────────────────────
    def _build_ui(self):
        style = ttk.Style()
        try:
            style.theme_use('clam')
        except Exception:
            pass
        style.configure('TNotebook.Tab', padding=[12, 5],
                        font=('Helvetica', 10))
        style.configure('Header.TLabel',
                        font=('Helvetica', 13, 'bold'))
        style.configure('Success.TLabel', foreground='#4CAF50',
                        font=('Helvetica', 10, 'bold'))
        style.configure('Warning.TLabel', foreground='#FF9800',
                        font=('Helvetica', 10, 'bold'))
        style.configure('Danger.TLabel', foreground='#f44336',
                        font=('Helvetica', 10, 'bold'))
        style.configure('Category.TLabel',
                        font=('Helvetica', 9, 'italic'))
        style.configure('Small.TButton',
                        font=('Helvetica', 9))

        # Ust bar
        topbar = ttk.Frame(self)
        topbar.pack(fill='x', padx=10, pady=(8, 4))
        ttk.Label(
            topbar, text="Kozmopol Akilli Cevap Sistemi v3.0",
            style='Header.TLabel').pack(side='left')

        # Tema degistirme
        self.theme_btn = ttk.Button(
            topbar, text="🌙 Karanlik Mod",
            command=self.toggle_theme, style='Small.TButton')
        self.theme_btn.pack(side='right', padx=4)

        if MISSING_CREDS:
            ttk.Label(topbar, text="[!] API DEVRE DISI",
                      style='Danger.TLabel').pack(side='right', padx=10)
        if MISSING_GEMINI:
            ttk.Label(topbar, text="[!] Gemini AI Devre Disi",
                      style='Warning.TLabel').pack(side='right', padx=10)
        else:
            ttk.Label(topbar, text="[OK] Gemini AI Aktif",
                      style='Success.TLabel').pack(side='right', padx=10)

        # Mesai disi
        cb_frame = ttk.Frame(self)
        cb_frame.pack(fill='x', padx=10, pady=(0, 6))
        ttk.Checkbutton(
            cb_frame,
            text="Mesai disi otomatik cevabi aktif et",
            variable=self.out_of_office_var).pack(side='left')

        # Mesai durumu gostergesi
        self.work_status_var = tk.StringVar()
        self._update_work_status()
        ttk.Label(cb_frame, textvariable=self.work_status_var,
                  foreground='#666').pack(side='left', padx=(12, 0))

        # Sekmeler
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill='both', expand=True, padx=10, pady=(0, 4))

        self.tab_responses = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_responses, text='  Otomatik Yanitlar  ')
        self._build_responses_tab()

        self.tab_pending = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_pending, text='  Bekleyen Sorular  ')
        self._build_pending_tab()

        self.tab_templates = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_templates, text='  Sablonlar  ')
        self._build_templates_tab()

        self.tab_orders = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_orders, text='  Kargo & Iade  ')
        self._build_orders_tab()

        self.tab_log = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_log, text='  Soru Gecmisi  ')
        self._build_log_tab()

        self.tab_reviews = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_reviews, text='  Yorumlar  ')
        self._build_reviews_tab()

        self.tab_ai = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_ai, text='  AI Ayarlari  ')
        self._build_ai_tab()

        self.tab_stats = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_stats, text='  Istatistikler  ')
        self._build_stats_tab()

        self.tab_settings = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_settings, text='  Ayarlar  ')
        self._build_settings_tab()

        # Durum cubugu
        status_bar = ttk.Frame(self, relief='sunken')
        status_bar.pack(fill='x', side='bottom')
        ttk.Label(status_bar, textvariable=self.status_var).pack(
            fill='x', padx=8, pady=2)

    def _update_work_status(self):
        if is_out_of_service_hours():
            self.work_status_var.set(
                "⏸ Mesai disi  |  "
                f"Mesai: {app_settings.get('work_hours_start', '10:00')}"
                f"-{app_settings.get('work_hours_end', '18:00')}")
        else:
            self.work_status_var.set(
                "▶ Mesai icinde  |  "
                f"Mesai: {app_settings.get('work_hours_start', '10:00')}"
                f"-{app_settings.get('work_hours_end', '18:00')}")
        # Her 60 saniyede bir guncelle
        self.after(60000, self._update_work_status)

    def toggle_theme(self):
        app_settings['dark_mode'] = not app_settings.get('dark_mode', False)
        save_settings()
        self.theme = get_theme()
        dark = app_settings['dark_mode']
        self.theme_btn.configure(
            text="☀️ Acik Mod" if dark else "🌙 Karanlik Mod")
        if dark:
            self.configure(bg=self.theme['bg'])
        else:
            self.configure(bg='')
        self._set_status(
            "Tema degistirildi: " + ("Karanlik" if dark else "Acik"))

    # ───────────────────────────────────────────
    # Mousewheel yardimci (macOS + Windows + Linux)
    # ───────────────────────────────────────────
    def _bind_mousewheel(self, canvas):
        if sys.platform == 'darwin':
            canvas.bind_all(
                '<MouseWheel>',
                lambda e: canvas.yview_scroll(-e.delta, 'units'))
        else:
            canvas.bind_all(
                '<MouseWheel>',
                lambda e: canvas.yview_scroll(
                    -1 * (e.delta // 120), 'units'))
            canvas.bind_all(
                '<Button-4>',
                lambda e: canvas.yview_scroll(-1, 'units'))
            canvas.bind_all(
                '<Button-5>',
                lambda e: canvas.yview_scroll(1, 'units'))

    def _unbind_mousewheel(self, canvas):
        canvas.unbind_all('<MouseWheel>')
        if sys.platform != 'darwin':
            canvas.unbind_all('<Button-4>')
            canvas.unbind_all('<Button-5>')

    # ══════════════════════════════════════════
    # TAB 1 — Otomatik Yanitlar
    # ══════════════════════════════════════════
    def _build_responses_tab(self):
        top = ttk.Frame(self.tab_responses)
        top.pack(fill='x', padx=8, pady=6)

        ttk.Label(top, text="Ara:").pack(side='left')
        self.search_var = tk.StringVar()
        self.search_var.trace_add(
            'write', lambda *_: self.reload_responses_list())
        ttk.Entry(top, textvariable=self.search_var,
                  width=30).pack(side='left', padx=(4, 12))

        ttk.Button(top, text="Yeni Ekle",
                   command=self.add_new).pack(side='left')
        ttk.Button(top, text="Seciliyi Sil",
                   command=self.delete_selected).pack(
            side='left', padx=(6, 0))

        # Import/Export butonlari
        ttk.Button(top, text="CSV Aktar",
                   command=self.export_responses_csv).pack(
            side='right')
        ttk.Button(top, text="CSV Yukle",
                   command=self.import_responses_csv).pack(
            side='right', padx=(0, 6))
        ttk.Button(
            top, text="Yenile",
            command=lambda: [load_responses(),
                             self.reload_responses_list()]
        ).pack(side='right', padx=(0, 6))

        # Kaydirma alani
        container = ttk.Frame(self.tab_responses)
        container.pack(fill='both', expand=True, padx=8, pady=(0, 8))

        self.resp_canvas = tk.Canvas(
            container, borderwidth=0, highlightthickness=0)
        self.resp_scroll = ttk.Scrollbar(
            container, orient='vertical',
            command=self.resp_canvas.yview)
        self.resp_list_frame = ttk.Frame(self.resp_canvas)
        self.resp_list_frame.bind(
            '<Configure>',
            lambda e: self.resp_canvas.configure(
                scrollregion=self.resp_canvas.bbox('all')))
        self.resp_canvas.create_window(
            (0, 0), window=self.resp_list_frame, anchor='nw')
        self.resp_canvas.configure(
            yscrollcommand=self.resp_scroll.set)
        self.resp_canvas.pack(side='left', fill='both', expand=True)
        self.resp_scroll.pack(side='right', fill='y')

        self.resp_canvas.bind(
            '<Enter>',
            lambda e: self._bind_mousewheel(self.resp_canvas))
        self.resp_canvas.bind(
            '<Leave>',
            lambda e: self._unbind_mousewheel(self.resp_canvas))

    def reload_responses_list(self):
        for w in self.resp_list_frame.winfo_children():
            w.destroy()

        normalized = normalize_dict(automated_responses)
        automated_responses.clear()
        automated_responses.update(normalized)

        search_text = ''
        if hasattr(self, 'search_var'):
            search_text = self.search_var.get().lower().strip()

        items = sorted(automated_responses.items(),
                       key=lambda kv: ', '.join(kv[0]))
        if search_text:
            items = [
                (k, v) for k, v in items
                if search_text in ', '.join(k) or search_text in v.lower()
            ]

        if not items:
            ttk.Label(self.resp_list_frame, text="(Kayit yok)",
                      foreground='#888').pack(anchor='w', pady=6)
            self.selected_key = None
            return

        ttk.Label(self.resp_list_frame,
                  text=f"Toplam {len(items)} kayit",
                  foreground='#666').pack(anchor='w', pady=(0, 4))

        for key_tuple, resp in items:
            block = tk.Frame(self.resp_list_frame, bd=1,
                             relief='solid', bg='#f8f8f8')
            block.pack(fill='x', pady=4, padx=0)
            block.grid_columnconfigure(1, weight=1)

            soru_text = ', '.join(key_tuple)

            # Kategori gostergesi
            sample_text = ' '.join(key_tuple)
            cat = categorize_question(sample_text)
            cat_info = QUESTION_CATEGORIES.get(cat, {})
            cat_label = cat_info.get('icon', '') + ' ' + cat_info.get('label', cat)

            lbl_cat = tk.Label(block, text=cat_label,
                               font=('Helvetica', 8, 'italic'),
                               fg=cat_info.get('color', '#999'),
                               bg='#f8f8f8')
            lbl_cat.grid(row=0, column=0, columnspan=2,
                         sticky='w', padx=(8, 4), pady=(4, 0))

            lbl_sk = tk.Label(block, text="Soru :", fg='#b00000',
                              font=('Helvetica', 10, 'bold'),
                              bg='#f8f8f8')
            lbl_sv = tk.Label(block, text=soru_text, fg='#b00000',
                              font=('Helvetica', 11), bg='#f8f8f8')
            lbl_ck = tk.Label(block, text="Cevap :",
                              font=('Helvetica', 10, 'bold'),
                              bg='#f8f8f8')
            lbl_cv = tk.Label(block, text=resp, fg='#000',
                              font=('Helvetica', 11), justify='left',
                              wraplength=900, bg='#f8f8f8')

            lbl_sk.grid(row=1, column=0, sticky='nw',
                        padx=(8, 4), pady=(2, 2))
            lbl_sv.grid(row=1, column=1, sticky='nw',
                        padx=(0, 8), pady=(2, 2))
            lbl_ck.grid(row=2, column=0, sticky='nw',
                        padx=(8, 4), pady=(0, 6))
            lbl_cv.grid(row=2, column=1, sticky='w',
                        padx=(0, 8), pady=(0, 6))

            for lab, handler in (
                (lbl_sv, self.edit_question),
                (lbl_cv, self.edit_answer),
                (lbl_sk, self.edit_question),
                (lbl_ck, self.edit_answer),
            ):
                lab.configure(cursor='hand2')
                lab.bind('<Button-1>',
                         lambda e, k=key_tuple, h=handler: h(k))

            block.bind('<Button-1>',
                       lambda e, k=key_tuple: self._select_response(k))
            for lab in (lbl_cat, lbl_sk, lbl_sv, lbl_ck, lbl_cv):
                lab.bind(
                    '<Button-1>',
                    lambda e, k=key_tuple: self._select_response(k),
                    add='+')

    def _select_response(self, key_tuple):
        self.selected_key = key_tuple

    def export_responses_csv(self):
        """Otomatik yanitlari CSV olarak disa aktar."""
        filepath = filedialog.asksaveasfilename(
            defaultextension='.csv',
            filetypes=[('CSV', '*.csv')],
            initialfile=f'responses_{datetime.now().strftime("%Y%m%d")}.csv',
        )
        if not filepath:
            return
        try:
            with open(filepath, 'w', newline='', encoding='utf-8-sig') as f:
                writer = csv.writer(f)
                writer.writerow(['Anahtar Kelimeler', 'Yanit'])
                for key_tuple, resp in sorted(automated_responses.items()):
                    writer.writerow([','.join(key_tuple), resp])
            self._set_status(f"Yanitlar disa aktarildi: {filepath}")
        except Exception as e:
            messagebox.showerror("Hata", f"Disa aktarma hatasi: {e}")

    def import_responses_csv(self):
        """CSV'den otomatik yanitlari iceri aktar."""
        filepath = filedialog.askopenfilename(
            filetypes=[('CSV', '*.csv'), ('Tüm Dosyalar', '*.*')])
        if not filepath:
            return
        try:
            imported = 0
            with open(filepath, 'r', encoding='utf-8-sig') as f:
                reader = csv.reader(f)
                header = next(reader, None)  # baslik satirini atla
                for row in reader:
                    if len(row) >= 2:
                        key = normalize_key_text(row[0])
                        if key:
                            automated_responses[key] = row[1].strip()
                            imported += 1
            save_responses()
            self.reload_responses_list()
            self.refresh_stats()
            self._set_status(f"{imported} yanit kurali iceri aktarildi")
        except Exception as e:
            messagebox.showerror("Hata", f"Iceri aktarma hatasi: {e}")

    # ══════════════════════════════════════════
    # TAB 2 — Bekleyen Sorular
    # ══════════════════════════════════════════
    def _build_pending_tab(self):
        top = ttk.Frame(self.tab_pending)
        top.pack(fill='x', padx=8, pady=6)

        ttk.Label(
            top,
            text="AI tarafindan uretilen veya eslesme bulunamayan yanitlar",
            foreground='#666').pack(side='left')
        ttk.Button(top, text="Yenile",
                   command=self.refresh_pending_list).pack(side='right')
        ttk.Button(
            top, text="Tamamlananlari Temizle",
            command=self.clear_completed_pending
        ).pack(side='right', padx=(0, 6))

        # Kategori filtresi
        filter_frame = ttk.Frame(self.tab_pending)
        filter_frame.pack(fill='x', padx=8, pady=(0, 4))
        ttk.Label(filter_frame, text="Kategori:").pack(side='left')
        self.pending_cat_var = tk.StringVar(value='Tumu')
        cat_values = ['Tumu'] + [
            c['label'] for c in QUESTION_CATEGORIES.values()]
        ttk.Combobox(
            filter_frame, textvariable=self.pending_cat_var,
            values=cat_values, width=20, state='readonly'
        ).pack(side='left', padx=4)
        ttk.Button(filter_frame, text="Filtrele",
                   command=self.refresh_pending_list).pack(
            side='left', padx=4)

        # Alt butonlar
        btn_frame = ttk.Frame(self.tab_pending)
        btn_frame.pack(fill='x', padx=8, pady=(0, 8), side='bottom')
        ttk.Button(btn_frame, text="Onayla ve Gonder",
                   command=self.approve_pending).pack(side='left')
        ttk.Button(btn_frame, text="Duzenle ve Gonder",
                   command=self.edit_and_send_pending).pack(
            side='left', padx=(6, 0))
        ttk.Button(btn_frame, text="Reddet",
                   command=self.reject_pending).pack(
            side='left', padx=(6, 0))
        ttk.Button(btn_frame, text="Sablondan Yanit",
                   command=self.reply_from_template).pack(
            side='left', padx=(6, 0))

        # Toplu islem butonlari
        ttk.Separator(btn_frame, orient='vertical').pack(
            side='left', fill='y', padx=8)
        ttk.Button(btn_frame, text="Tumunu Onayla",
                   command=self.approve_all_pending).pack(side='left')
        ttk.Button(btn_frame, text="Tumunu Reddet",
                   command=self.reject_all_pending).pack(
            side='left', padx=(6, 0))

        ttk.Button(btn_frame, text="Yanit Olarak Kaydet",
                   command=self.save_pending_as_response).pack(side='right')

        # Treeview
        columns = ('kategori', 'zaman', 'soru', 'oneri', 'guven', 'durum')
        tree_frame = ttk.Frame(self.tab_pending)
        tree_frame.pack(fill='both', expand=True, padx=8, pady=(0, 4))

        self.pending_tree = ttk.Treeview(
            tree_frame, columns=columns, show='headings', height=20)
        self.pending_tree.heading('kategori', text='Kategori')
        self.pending_tree.heading('zaman', text='Zaman')
        self.pending_tree.heading('soru', text='Soru')
        self.pending_tree.heading('oneri', text='AI Onerisi')
        self.pending_tree.heading('guven', text='Guven')
        self.pending_tree.heading('durum', text='Durum')

        self.pending_tree.column('kategori', width=100, minwidth=80)
        self.pending_tree.column('zaman', width=120, minwidth=100)
        self.pending_tree.column('soru', width=280, minwidth=200)
        self.pending_tree.column('oneri', width=380, minwidth=200)
        self.pending_tree.column('guven', width=60, minwidth=50)
        self.pending_tree.column('durum', width=90, minwidth=70)

        p_scroll = ttk.Scrollbar(
            tree_frame, orient='vertical',
            command=self.pending_tree.yview)
        self.pending_tree.configure(yscrollcommand=p_scroll.set)
        self.pending_tree.pack(
            fill='both', expand=True, side='left')
        p_scroll.pack(side='right', fill='y')

    def refresh_pending_list(self):
        for item in self.pending_tree.get_children():
            self.pending_tree.delete(item)

        cat_filter = self.pending_cat_var.get() if hasattr(
            self, 'pending_cat_var') else 'Tumu'

        for i, p in enumerate(pending_questions):
            if p.get('status') in ('sent', 'rejected'):
                continue

            cat = p.get('category', 'diger')
            cat_info = QUESTION_CATEGORIES.get(cat, {})
            cat_label = cat_info.get('label', cat)

            if cat_filter != 'Tumu' and cat_label != cat_filter:
                continue

            ts = p.get('timestamp', '')[:16].replace('T', ' ')
            q = p.get('question', '')[:80]
            a = p.get('suggested_answer', '')[:80]
            c = f"{p.get('confidence', 0):.0%}"
            s = p.get('status', 'pending')
            status_map = {
                'pending': 'Bekliyor',
                'no_match': 'Eslesmedi',
            }
            self.pending_tree.insert(
                '', 'end', iid=str(i),
                values=(cat_label, ts, q, a, c, status_map.get(s, s)))

    def _get_selected_pending_idx(self):
        sel = self.pending_tree.selection()
        if not sel:
            messagebox.showwarning("Uyari", "Bir soru secin.")
            return None
        return int(sel[0])

    def approve_pending(self):
        idx = self._get_selected_pending_idx()
        if idx is None:
            return
        p = pending_questions[idx]
        if not p.get('suggested_answer'):
            messagebox.showerror("Hata", "Bu soru icin AI onerisi yok.")
            return
        answer_text = p['suggested_answer']
        # Kara liste uyarisini temizle
        if '[KARA_LISTE_UYARI' in answer_text:
            answer_text = re.sub(
                r'\[KARA_LISTE_UYARI:[^\]]*\]\s*', '', answer_text).strip()
        if answer_question(p['question_id'], answer_text):
            p['status'] = 'sent'
            save_pending()
            add_log_entry(p['question_id'], p['question'],
                          answer_text, 'manual_approved')
            self.refresh_pending_list()
            self.refresh_stats()
            self._set_status("Yanit onaylandi ve gonderildi")

    def edit_and_send_pending(self):
        idx = self._get_selected_pending_idx()
        if idx is None:
            return
        p = pending_questions[idx]

        def do_save(text, win):
            if not text.strip():
                messagebox.showerror(
                    "Hata", "Yanit bos olamaz.", parent=win)
                return
            if answer_question(p['question_id'], text.strip()):
                p['status'] = 'sent'
                p['suggested_answer'] = text.strip()
                save_pending()
                add_log_entry(p['question_id'], p['question'],
                              text.strip(), 'manual_edited')
                self.refresh_pending_list()
                self.refresh_stats()
                self._set_status("Duzenlenmis yanit gonderildi")
                win.destroy()

        # Kara liste uyarisini temizleyerek goster
        initial = p.get('suggested_answer', '')
        if '[KARA_LISTE_UYARI' in initial:
            initial = re.sub(
                r'\[KARA_LISTE_UYARI:[^\]]*\]\s*', '', initial).strip()

        self._open_edit_dialog(
            f"Yaniti Duzenle — {p['question'][:50]}...",
            initial,
            do_save, lambda w: w.destroy())

    def reject_pending(self):
        idx = self._get_selected_pending_idx()
        if idx is None:
            return
        pending_questions[idx]['status'] = 'rejected'
        save_pending()
        self.refresh_pending_list()
        self._set_status("Soru reddedildi")

    def approve_all_pending(self):
        """Tum bekleyen sorulari toplu onayla."""
        active = [
            (i, p) for i, p in enumerate(pending_questions)
            if p.get('status') in ('pending',)
            and p.get('suggested_answer')
            and '[KARA_LISTE_UYARI' not in p.get('suggested_answer', '')
        ]
        if not active:
            messagebox.showinfo("Bilgi", "Onaylanacak soru yok.")
            return
        if not messagebox.askyesno(
                "Toplu Onay",
                f"{len(active)} bekleyen soruyu onaylamak istediginize emin misiniz?"):
            return
        count = 0
        for i, p in active:
            if answer_question(p['question_id'], p['suggested_answer']):
                p['status'] = 'sent'
                add_log_entry(p['question_id'], p['question'],
                              p['suggested_answer'], 'manual_approved')
                count += 1
        save_pending()
        self.refresh_pending_list()
        self.refresh_stats()
        self._set_status(f"{count} soru toplu onaylandi")

    def reject_all_pending(self):
        """Tum bekleyen sorulari toplu reddet."""
        active = [
            (i, p) for i, p in enumerate(pending_questions)
            if p.get('status') in ('pending', 'no_match')
        ]
        if not active:
            messagebox.showinfo("Bilgi", "Reddedilecek soru yok.")
            return
        if not messagebox.askyesno(
                "Toplu Reddet",
                f"{len(active)} bekleyen soruyu reddetmek istediginize emin misiniz?"):
            return
        for i, p in active:
            p['status'] = 'rejected'
        save_pending()
        self.refresh_pending_list()
        self._set_status(f"{len(active)} soru toplu reddedildi")

    def reply_from_template(self):
        """Secili bekleyen soruya sablon ile yanit ver."""
        idx = self._get_selected_pending_idx()
        if idx is None:
            return
        if not response_templates:
            messagebox.showinfo("Bilgi", "Henuz sablon tanimlanmamis.")
            return

        p = pending_questions[idx]
        win = tk.Toplevel(self)
        win.title("Sablondan Yanit")
        win.geometry("650x500")
        win.transient(self)
        win.grab_set()

        ttk.Label(win, text=f"Soru: {p.get('question', '')[:80]}...",
                  wraplength=600).pack(anchor='w', padx=10, pady=(10, 6))

        ttk.Label(win, text="Sablon Secin:").pack(
            anchor='w', padx=10)
        template_names = [t['name'] for t in response_templates]
        self._tmpl_reply_var = tk.StringVar()
        tmpl_combo = ttk.Combobox(
            win, textvariable=self._tmpl_reply_var,
            values=template_names, width=40, state='readonly')
        tmpl_combo.pack(anchor='w', padx=10, pady=4)

        ttk.Label(win, text="Onizleme / Duzenle:").pack(
            anchor='w', padx=10, pady=(8, 0))
        preview_text = scrolledtext.ScrolledText(
            win, wrap='word', height=12, font=('Helvetica', 11))
        preview_text.pack(fill='both', expand=True, padx=10, pady=4)

        def on_template_select(*_):
            name = self._tmpl_reply_var.get()
            tmpl = next((t for t in response_templates
                         if t['name'] == name), None)
            if tmpl:
                preview_text.delete('1.0', 'end')
                preview_text.insert('1.0', tmpl['text'])

        tmpl_combo.bind('<<ComboboxSelected>>', on_template_select)

        def do_send():
            text = preview_text.get('1.0', 'end').strip()
            if not text:
                messagebox.showerror("Hata", "Yanit bos olamaz.", parent=win)
                return
            if answer_question(p['question_id'], text):
                p['status'] = 'sent'
                p['suggested_answer'] = text
                save_pending()
                add_log_entry(p['question_id'], p['question'],
                              text, 'template')
                self.refresh_pending_list()
                self.refresh_stats()
                self._set_status("Sablondan yanit gonderildi")
                win.destroy()

        btn_frame = ttk.Frame(win)
        btn_frame.pack(fill='x', padx=10, pady=(0, 10))
        ttk.Button(btn_frame, text="Gonder", command=do_send).pack(side='right')
        ttk.Button(btn_frame, text="Iptal",
                   command=win.destroy).pack(side='right', padx=(0, 6))

    def save_pending_as_response(self):
        """Bekleyen soruyu otomatik yanit kurali olarak kaydet."""
        idx = self._get_selected_pending_idx()
        if idx is None:
            return
        p = pending_questions[idx]

        def do_save_key(key_text, win):
            key = normalize_key_text(key_text)
            if not key:
                messagebox.showerror(
                    "Hata", "En az bir anahtar kelime girin.",
                    parent=win)
                return
            win.destroy()

            def do_save_answer(answer_text, w2):
                if not answer_text.strip():
                    messagebox.showerror(
                        "Hata", "Cevap bos olamaz.", parent=w2)
                    return
                automated_responses[key] = answer_text.strip()
                save_responses()
                self.reload_responses_list()
                answer_question(p['question_id'], answer_text.strip())
                p['status'] = 'sent'
                save_pending()
                self.refresh_pending_list()
                self.refresh_stats()
                self._set_status(
                    "Yeni yanit kurali kaydedildi ve gonderildi")
                w2.destroy()

            self._open_edit_dialog(
                "Cevap", p.get('suggested_answer', ''),
                do_save_answer, lambda w: w.destroy())

        words = re.findall(r'\w+', p.get('question', '').lower())
        suggested = ','.join(w for w in words if len(w) > 2)[:100]
        self._open_edit_dialog(
            "Anahtar Kelimeler (virgul ile)", suggested,
            do_save_key, lambda w: w.destroy())

    def clear_completed_pending(self):
        global pending_questions
        pending_questions = [
            p for p in pending_questions
            if p.get('status') not in ('sent', 'rejected')
        ]
        save_pending()
        self.refresh_pending_list()
        self._set_status("Tamamlananlar temizlendi")

    # ══════════════════════════════════════════
    # TAB 3 — Sablonlar
    # ══════════════════════════════════════════
    def _build_templates_tab(self):
        top = ttk.Frame(self.tab_templates)
        top.pack(fill='x', padx=8, pady=6)

        ttk.Label(top, text="Hizli yanit sablonlari — "
                  "{{degisken}} ifadeleri degistirilebilir",
                  foreground='#666').pack(side='left')
        ttk.Button(top, text="Yeni Sablon",
                   command=self.add_template).pack(side='right')

        # Sol panel: sablon listesi
        paned = ttk.PanedWindow(self.tab_templates, orient='horizontal')
        paned.pack(fill='both', expand=True, padx=8, pady=(0, 8))

        left_frame = ttk.LabelFrame(paned, text="Sablonlar", padding=4)
        paned.add(left_frame, weight=1)

        self.template_listbox = tk.Listbox(
            left_frame, font=('Helvetica', 11), selectmode='browse')
        self.template_listbox.pack(fill='both', expand=True)
        self.template_listbox.bind(
            '<<ListboxSelect>>', self._on_template_select)

        btn_frame = ttk.Frame(left_frame)
        btn_frame.pack(fill='x', pady=(4, 0))
        ttk.Button(btn_frame, text="Duzenle",
                   command=self.edit_template).pack(side='left')
        ttk.Button(btn_frame, text="Sil",
                   command=self.delete_template).pack(
            side='left', padx=(4, 0))

        # Sag panel: onizleme
        right_frame = ttk.LabelFrame(
            paned, text="Sablon Onizleme", padding=8)
        paned.add(right_frame, weight=2)

        self.template_preview = scrolledtext.ScrolledText(
            right_frame, wrap='word', font=('Helvetica', 11),
            state='disabled')
        self.template_preview.pack(fill='both', expand=True)

        info_frame = ttk.Frame(right_frame)
        info_frame.pack(fill='x', pady=(4, 0))
        self.template_info_var = tk.StringVar()
        ttk.Label(info_frame, textvariable=self.template_info_var,
                  foreground='#666').pack(side='left')

    def refresh_templates_list(self):
        if not hasattr(self, 'template_listbox'):
            return
        self.template_listbox.delete(0, 'end')
        for t in response_templates:
            cat = t.get('category', '')
            cat_info = QUESTION_CATEGORIES.get(cat, {})
            icon = cat_info.get('icon', '')
            self.template_listbox.insert(
                'end', f"{icon} {t['name']}")

    def _on_template_select(self, event=None):
        sel = self.template_listbox.curselection()
        if not sel:
            return
        idx = sel[0]
        if idx < len(response_templates):
            t = response_templates[idx]
            self.template_preview.configure(state='normal')
            self.template_preview.delete('1.0', 'end')
            self.template_preview.insert('1.0', t['text'])
            self.template_preview.configure(state='disabled')
            vars_str = ', '.join(
                f'{{{{{v}}}}}' for v in t.get('variables', []))
            cat_info = QUESTION_CATEGORIES.get(
                t.get('category', ''), {})
            self.template_info_var.set(
                f"Kategori: {cat_info.get('label', t.get('category', 'Genel'))} | "
                f"Degiskenler: {vars_str or 'Yok'}")

    def add_template(self):
        win = tk.Toplevel(self)
        win.title("Yeni Sablon")
        win.geometry("600x450")
        win.transient(self)
        win.grab_set()

        ttk.Label(win, text="Sablon Adi:").pack(
            anchor='w', padx=10, pady=(10, 2))
        name_var = tk.StringVar()
        ttk.Entry(win, textvariable=name_var, width=40).pack(
            anchor='w', padx=10)

        ttk.Label(win, text="Kategori:").pack(
            anchor='w', padx=10, pady=(8, 2))
        cat_var = tk.StringVar(value='diger')
        cat_values = list(QUESTION_CATEGORIES.keys())
        ttk.Combobox(win, textvariable=cat_var,
                     values=cat_values, width=20,
                     state='readonly').pack(anchor='w', padx=10)

        ttk.Label(win, text="Sablon Metni ({{degisken}} kullanin):").pack(
            anchor='w', padx=10, pady=(8, 2))
        text_widget = scrolledtext.ScrolledText(
            win, wrap='word', height=10, font=('Helvetica', 11))
        text_widget.pack(fill='both', expand=True, padx=10)

        ttk.Label(win, text="Degiskenler (virgul ile, orn: urun_adi, ek_bilgi):").pack(
            anchor='w', padx=10, pady=(8, 2))
        vars_var = tk.StringVar()
        ttk.Entry(win, textvariable=vars_var, width=40).pack(
            anchor='w', padx=10)

        def save():
            name = name_var.get().strip()
            text = text_widget.get('1.0', 'end').strip()
            if not name or not text:
                messagebox.showerror(
                    "Hata", "Ad ve metin zorunludur.", parent=win)
                return
            variables = [v.strip() for v in vars_var.get().split(',')
                         if v.strip()]
            response_templates.append({
                'name': name,
                'text': text,
                'variables': variables,
                'category': cat_var.get(),
            })
            save_templates()
            self.refresh_templates_list()
            self._set_status(f"Sablon eklendi: {name}")
            win.destroy()

        btn_frame = ttk.Frame(win)
        btn_frame.pack(fill='x', padx=10, pady=10)
        ttk.Button(btn_frame, text="Kaydet", command=save).pack(side='right')
        ttk.Button(btn_frame, text="Iptal",
                   command=win.destroy).pack(side='right', padx=(0, 6))

    def edit_template(self):
        sel = self.template_listbox.curselection()
        if not sel:
            messagebox.showwarning("Uyari", "Bir sablon secin.")
            return
        idx = sel[0]
        t = response_templates[idx]

        win = tk.Toplevel(self)
        win.title(f"Sablon Duzenle — {t['name']}")
        win.geometry("600x450")
        win.transient(self)
        win.grab_set()

        ttk.Label(win, text="Sablon Adi:").pack(
            anchor='w', padx=10, pady=(10, 2))
        name_var = tk.StringVar(value=t['name'])
        ttk.Entry(win, textvariable=name_var, width=40).pack(
            anchor='w', padx=10)

        ttk.Label(win, text="Kategori:").pack(
            anchor='w', padx=10, pady=(8, 2))
        cat_var = tk.StringVar(value=t.get('category', 'diger'))
        ttk.Combobox(win, textvariable=cat_var,
                     values=list(QUESTION_CATEGORIES.keys()),
                     width=20, state='readonly').pack(anchor='w', padx=10)

        ttk.Label(win, text="Sablon Metni:").pack(
            anchor='w', padx=10, pady=(8, 2))
        text_widget = scrolledtext.ScrolledText(
            win, wrap='word', height=10, font=('Helvetica', 11))
        text_widget.pack(fill='both', expand=True, padx=10)
        text_widget.insert('1.0', t['text'])

        ttk.Label(win, text="Degiskenler:").pack(
            anchor='w', padx=10, pady=(8, 2))
        vars_var = tk.StringVar(
            value=', '.join(t.get('variables', [])))
        ttk.Entry(win, textvariable=vars_var, width=40).pack(
            anchor='w', padx=10)

        def save():
            name = name_var.get().strip()
            text = text_widget.get('1.0', 'end').strip()
            if not name or not text:
                messagebox.showerror(
                    "Hata", "Ad ve metin zorunludur.", parent=win)
                return
            variables = [v.strip() for v in vars_var.get().split(',')
                         if v.strip()]
            response_templates[idx] = {
                'name': name,
                'text': text,
                'variables': variables,
                'category': cat_var.get(),
            }
            save_templates()
            self.refresh_templates_list()
            self._set_status(f"Sablon guncellendi: {name}")
            win.destroy()

        btn_frame = ttk.Frame(win)
        btn_frame.pack(fill='x', padx=10, pady=10)
        ttk.Button(btn_frame, text="Kaydet", command=save).pack(side='right')
        ttk.Button(btn_frame, text="Iptal",
                   command=win.destroy).pack(side='right', padx=(0, 6))

    def delete_template(self):
        sel = self.template_listbox.curselection()
        if not sel:
            messagebox.showwarning("Uyari", "Bir sablon secin.")
            return
        idx = sel[0]
        name = response_templates[idx]['name']
        if messagebox.askyesno("Sil", f"'{name}' sablonunu silmek istiyor musunuz?"):
            response_templates.pop(idx)
            save_templates()
            self.refresh_templates_list()
            self.template_preview.configure(state='normal')
            self.template_preview.delete('1.0', 'end')
            self.template_preview.configure(state='disabled')
            self._set_status(f"Sablon silindi: {name}")

    # ══════════════════════════════════════════
    # TAB 4 — Kargo & Iade
    # ══════════════════════════════════════════
    def _build_orders_tab(self):
        top = ttk.Frame(self.tab_orders)
        top.pack(fill='x', padx=8, pady=6)

        ttk.Label(top, text="Son").pack(side='left')
        self.order_days_var = tk.StringVar(value='7')
        ttk.Combobox(
            top, textvariable=self.order_days_var,
            values=['3', '7', '14', '30'],
            width=5, state='readonly').pack(side='left', padx=4)
        ttk.Label(top, text="gun").pack(side='left')

        ttk.Button(top, text="Siparisleri Getir",
                   command=self.fetch_orders).pack(
            side='left', padx=(12, 0))
        ttk.Button(top, text="Iadeleri Getir",
                   command=self.fetch_claims).pack(
            side='left', padx=(6, 0))

        # Paned window
        paned = ttk.PanedWindow(self.tab_orders, orient='vertical')
        paned.pack(fill='both', expand=True, padx=8, pady=(0, 8))

        # Siparis frame
        order_frame = ttk.LabelFrame(paned, text="Siparisler", padding=4)
        paned.add(order_frame, weight=1)

        order_cols = ('siparis_no', 'tarih', 'durum',
                      'kargo', 'urun', 'musteri')
        self.order_tree = ttk.Treeview(
            order_frame, columns=order_cols,
            show='headings', height=10)
        for col, heading, w in [
            ('siparis_no', 'Siparis No', 130),
            ('tarih', 'Tarih', 130),
            ('durum', 'Durum', 100),
            ('kargo', 'Kargo', 140),
            ('urun', 'Urun', 250),
            ('musteri', 'Musteri', 150),
        ]:
            self.order_tree.heading(col, text=heading)
            self.order_tree.column(col, width=w, minwidth=80)

        o_scroll = ttk.Scrollbar(
            order_frame, orient='vertical',
            command=self.order_tree.yview)
        self.order_tree.configure(yscrollcommand=o_scroll.set)
        self.order_tree.pack(
            fill='both', expand=True, side='left')
        o_scroll.pack(side='right', fill='y')

        # Iade frame
        claim_frame = ttk.LabelFrame(
            paned, text="Iadeler / Talepler", padding=4)
        paned.add(claim_frame, weight=1)

        claim_cols = ('talep_no', 'tarih', 'durum', 'sebep', 'urun')
        self.claim_tree = ttk.Treeview(
            claim_frame, columns=claim_cols,
            show='headings', height=8)
        for col, heading, w in [
            ('talep_no', 'Talep No', 120),
            ('tarih', 'Tarih', 120),
            ('durum', 'Durum', 120),
            ('sebep', 'Sebep', 200),
            ('urun', 'Urun', 300),
        ]:
            self.claim_tree.heading(col, text=heading)
            self.claim_tree.column(col, width=w, minwidth=80)

        c_scroll = ttk.Scrollbar(
            claim_frame, orient='vertical',
            command=self.claim_tree.yview)
        self.claim_tree.configure(yscrollcommand=c_scroll.set)
        self.claim_tree.pack(
            fill='both', expand=True, side='left')
        c_scroll.pack(side='right', fill='y')

    def fetch_orders(self):
        self._set_status("Siparisler yukleniyor...")
        self.update_idletasks()

        def _fetch():
            days = int(self.order_days_var.get())
            orders = get_orders(days=days)
            self.after(0, lambda: self._populate_orders(orders))

        threading.Thread(target=_fetch, daemon=True).start()

    def _populate_orders(self, orders):
        for item in self.order_tree.get_children():
            self.order_tree.delete(item)
        count = 0
        for o in orders:
            for line in o.get('lines', [{}]):
                order_no = o.get('orderNumber', '')
                ts = o.get('orderDate')
                date_str = ''
                if ts:
                    date_str = datetime.fromtimestamp(
                        ts / 1000).strftime('%Y-%m-%d %H:%M')
                status = o.get('status', '')
                cargo = line.get('cargoProviderName', '')
                product = (line.get('productName') or '')[:60]
                customer = (
                    f"{o.get('customerFirstName', '')} "
                    f"{o.get('customerLastName', '')}")
                self.order_tree.insert(
                    '', 'end',
                    values=(order_no, date_str, status,
                            cargo, product, customer))
                count += 1
        self._set_status(f"{count} siparis satiri yuklendi")

    def fetch_claims(self):
        self._set_status("Iadeler yukleniyor...")
        self.update_idletasks()

        def _fetch():
            claims = get_claims()
            self.after(0, lambda: self._populate_claims(claims))

        threading.Thread(target=_fetch, daemon=True).start()

    def _populate_claims(self, claims):
        for item in self.claim_tree.get_children():
            self.claim_tree.delete(item)
        count = 0
        for c in claims:
            for ci in c.get('items', [{}]):
                claim_no = c.get('id', '')
                ts = c.get('createdDate')
                date_str = ''
                if ts:
                    date_str = datetime.fromtimestamp(
                        ts / 1000).strftime('%Y-%m-%d')
                status = ci.get(
                    'claimItemStatus', c.get('status', ''))
                reason_obj = ci.get('customerClaimItemReason')
                reason = ''
                if isinstance(reason_obj, dict):
                    reason = reason_obj.get('name', '')
                product = (ci.get('productName') or '')[:60]
                self.claim_tree.insert(
                    '', 'end',
                    values=(claim_no, date_str, status,
                            reason, product))
                count += 1
        self._set_status(f"{count} iade/talep yuklendi")

    # ══════════════════════════════════════════
    # TAB 5 — Soru Gecmisi
    # ══════════════════════════════════════════
    def _build_log_tab(self):
        top = ttk.Frame(self.tab_log)
        top.pack(fill='x', padx=8, pady=6)

        ttk.Label(top, text="Yontem:").pack(side='left')
        self.log_filter_var = tk.StringVar(value='Tumu')
        ttk.Combobox(
            top, textvariable=self.log_filter_var,
            values=[
                'Tumu', 'keyword', 'fuzzy', 'gemini',
                'manual_approved', 'manual_edited', 'template',
                'out_of_service', 'pending', 'no_match',
            ],
            width=16, state='readonly'
        ).pack(side='left', padx=4)

        ttk.Label(top, text="Kategori:").pack(side='left', padx=(8, 0))
        self.log_cat_filter_var = tk.StringVar(value='Tumu')
        ttk.Combobox(
            top, textvariable=self.log_cat_filter_var,
            values=['Tumu'] + [c['label']
                               for c in QUESTION_CATEGORIES.values()],
            width=18, state='readonly'
        ).pack(side='left', padx=4)

        ttk.Button(top, text="Filtrele",
                   command=self.refresh_log_list).pack(
            side='left', padx=4)
        ttk.Button(
            top, text="Yenile",
            command=lambda: [load_question_log(),
                             self.refresh_log_list()]
        ).pack(side='left', padx=4)
        ttk.Button(top, text="Gunluk Rapor",
                   command=self.show_daily_report).pack(
            side='right')
        ttk.Button(top, text="CSV Disa Aktar",
                   command=self.export_log_csv).pack(
            side='right', padx=(0, 6))

        # Treeview
        tree_frame = ttk.Frame(self.tab_log)
        tree_frame.pack(fill='both', expand=True, padx=8, pady=(0, 8))

        log_cols = ('zaman', 'kategori', 'soru', 'yanit', 'yontem')
        self.log_tree = ttk.Treeview(
            tree_frame, columns=log_cols,
            show='headings', height=25)
        self.log_tree.heading('zaman', text='Zaman')
        self.log_tree.heading('kategori', text='Kategori')
        self.log_tree.heading('soru', text='Soru')
        self.log_tree.heading('yanit', text='Yanit')
        self.log_tree.heading('yontem', text='Yontem')

        self.log_tree.column('zaman', width=120, minwidth=100)
        self.log_tree.column('kategori', width=100, minwidth=80)
        self.log_tree.column('soru', width=300, minwidth=200)
        self.log_tree.column('yanit', width=400, minwidth=200)
        self.log_tree.column('yontem', width=110, minwidth=80)

        l_scroll = ttk.Scrollbar(
            tree_frame, orient='vertical',
            command=self.log_tree.yview)
        self.log_tree.configure(yscrollcommand=l_scroll.set)
        self.log_tree.pack(
            fill='both', expand=True, side='left')
        l_scroll.pack(side='right', fill='y')

        self.log_tree.bind('<Double-1>', self._show_log_detail)

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

    def refresh_log_list(self):
        for item in self.log_tree.get_children():
            self.log_tree.delete(item)

        filt = 'Tumu'
        if hasattr(self, 'log_filter_var'):
            filt = self.log_filter_var.get()

        cat_filt = 'Tumu'
        if hasattr(self, 'log_cat_filter_var'):
            cat_filt = self.log_cat_filter_var.get()

        for entry in reversed(question_log):
            m = entry.get('method', '')
            if filt != 'Tumu' and m != filt:
                continue

            cat = entry.get('category', 'diger')
            cat_info = QUESTION_CATEGORIES.get(cat, {})
            cat_label = cat_info.get('label', cat)
            if cat_filt != 'Tumu' and cat_label != cat_filt:
                continue

            ts = entry.get('timestamp', '')[:16].replace('T', ' ')
            q = entry.get('question', '')[:80]
            a = entry.get('answer', '')[:80]
            self.log_tree.insert(
                '', 'end',
                values=(ts, cat_label, q, a,
                        self.METHOD_LABELS.get(m, m)))

    def _show_log_detail(self, event):
        sel = self.log_tree.selection()
        if not sel:
            return
        vals = self.log_tree.item(sel[0])['values']
        detail = (
            f"Zaman: {vals[0]}\n"
            f"Kategori: {vals[1]}\n\n"
            f"Soru: {vals[2]}\n\n"
            f"Yanit: {vals[3]}\n\n"
            f"Yontem: {vals[4]}"
        )

        win = tk.Toplevel(self)
        win.title("Soru Detayi")
        win.geometry("600x400")
        win.transient(self)
        txt = scrolledtext.ScrolledText(
            win, wrap='word', font=('Helvetica', 11))
        txt.pack(fill='both', expand=True, padx=10, pady=10)
        txt.insert('1.0', detail)
        txt.configure(state='disabled')

    def show_daily_report(self):
        """Gunluk raporu goster."""
        report = generate_daily_report()
        win = tk.Toplevel(self)
        win.title("Gunluk Rapor")
        win.geometry("650x500")
        win.transient(self)
        txt = scrolledtext.ScrolledText(
            win, wrap='word', font=('Courier', 11))
        txt.pack(fill='both', expand=True, padx=10, pady=10)
        txt.insert('1.0', report)
        txt.configure(state='disabled')

        btn_frame = ttk.Frame(win)
        btn_frame.pack(fill='x', padx=10, pady=(0, 10))

        def copy_report():
            self.clipboard_clear()
            self.clipboard_append(report)
            self._set_status("Rapor panoya kopyalandi")

        ttk.Button(btn_frame, text="Kopyala",
                   command=copy_report).pack(side='right')

    def export_log_csv(self):
        filepath = filedialog.asksaveasfilename(
            defaultextension='.csv',
            filetypes=[('CSV', '*.csv')],
            initialfile=(
                f'kozmopol_log_'
                f'{datetime.now().strftime("%Y%m%d")}.csv'),
        )
        if not filepath:
            return
        try:
            with open(filepath, 'w', newline='',
                      encoding='utf-8-sig') as f:
                writer = csv.writer(f)
                writer.writerow([
                    'Zaman', 'Soru ID', 'Soru',
                    'Yanit', 'Yontem', 'Kategori', 'Urun'])
                for entry in question_log:
                    writer.writerow([
                        entry.get('timestamp', ''),
                        entry.get('question_id', ''),
                        entry.get('question', ''),
                        entry.get('answer', ''),
                        entry.get('method', ''),
                        entry.get('category', ''),
                        entry.get('product_info', ''),
                    ])
            self._set_status(f"Log disa aktarildi: {filepath}")
        except Exception as e:
            messagebox.showerror(
                "Hata", f"Disa aktarma hatasi: {e}")

    # ══════════════════════════════════════════
    # TAB 6 — Yorumlar (Musteri Degerlendirmeleri)
    # ══════════════════════════════════════════
    def _build_reviews_tab(self):
        top = ttk.Frame(self.tab_reviews)
        top.pack(fill='x', padx=8, pady=6)

        ttk.Button(top, text="Yorumlari Cek (API)",
                   command=self.fetch_reviews_from_api).pack(
            side='left')
        ttk.Button(top, text="Yenile",
                   command=self.refresh_reviews_list).pack(
            side='left', padx=(6, 0))
        ttk.Button(top, text="Yorum Analizi",
                   command=self.show_review_analysis).pack(
            side='left', padx=(6, 0))
        ttk.Button(top, text="Yorumlari Temizle",
                   command=self.clear_reviews).pack(
            side='left', padx=(6, 0))

        ttk.Label(top, text="Ara:").pack(
            side='left', padx=(18, 0))
        self.review_search_var = tk.StringVar()
        ttk.Entry(top, textvariable=self.review_search_var,
                  width=25).pack(side='left', padx=(4, 0))
        ttk.Button(top, text="Filtrele",
                   command=self.refresh_reviews_list).pack(
            side='left', padx=(4, 0))

        # Urun filtresi
        filter_frame = ttk.Frame(self.tab_reviews)
        filter_frame.pack(fill='x', padx=8, pady=(0, 4))
        ttk.Label(filter_frame, text="Urun:").pack(side='left')
        self.review_product_var = tk.StringVar(value='Tumu')
        self.review_product_combo = ttk.Combobox(
            filter_frame, textvariable=self.review_product_var,
            values=['Tumu'], width=60, state='readonly')
        self.review_product_combo.pack(
            side='left', padx=(4, 8))
        ttk.Label(filter_frame, text="Min Puan:").pack(side='left')
        self.review_min_rate_var = tk.StringVar(value='0')
        ttk.Combobox(
            filter_frame,
            textvariable=self.review_min_rate_var,
            values=['0', '1', '2', '3', '4', '5'],
            width=4, state='readonly'
        ).pack(side='left', padx=(4, 0))

        # Ozet bilgisi
        self.review_summary_var = tk.StringVar(
            value="Henuz yorum yuklenmedi")
        ttk.Label(self.tab_reviews,
                  textvariable=self.review_summary_var,
                  foreground='#666').pack(
            anchor='w', padx=8, pady=(0, 4))

        # Yorum tablosu
        tree_frame = ttk.Frame(self.tab_reviews)
        tree_frame.pack(fill='both', expand=True,
                        padx=8, pady=(0, 8))

        rev_cols = ('urun', 'kullanici', 'puan',
                    'tarih', 'yorum')
        self.review_tree = ttk.Treeview(
            tree_frame, columns=rev_cols,
            show='headings', height=20)
        self.review_tree.heading('urun', text='Urun')
        self.review_tree.heading('kullanici', text='Kullanici')
        self.review_tree.heading('puan', text='Puan')
        self.review_tree.heading('tarih', text='Tarih')
        self.review_tree.heading('yorum', text='Yorum')

        self.review_tree.column('urun', width=200, minwidth=120)
        self.review_tree.column('kullanici', width=100, minwidth=70)
        self.review_tree.column('puan', width=60, minwidth=40)
        self.review_tree.column('tarih', width=90, minwidth=70)
        self.review_tree.column('yorum', width=500, minwidth=250)

        r_scroll = ttk.Scrollbar(
            tree_frame, orient='vertical',
            command=self.review_tree.yview)
        self.review_tree.configure(yscrollcommand=r_scroll.set)
        self.review_tree.pack(
            fill='both', expand=True, side='left')
        r_scroll.pack(side='right', fill='y')

        self.review_tree.bind(
            '<Double-1>', self._show_review_detail)

    def fetch_reviews_from_api(self):
        """Trendyol API'den yorumlari cek."""
        self._set_status("Yorumlar API'den cekiliyor...")
        self.update_idletasks()

        def _fetch():
            total, prod_count = fetch_all_reviews(max_pages=20)
            self.after(0, lambda: self._on_reviews_fetched(
                total, prod_count))

        threading.Thread(target=_fetch, daemon=True).start()

    def _on_reviews_fetched(self, total, prod_count):
        self._update_review_product_combo()
        self.refresh_reviews_list()
        self._set_status(
            f"{total} yorum cekildi ({prod_count} urun)")

    def _update_review_product_combo(self):
        products = ['Tumu'] + sorted(product_reviews.keys())
        self.review_product_combo['values'] = products

    def refresh_reviews_list(self):
        for item in self.review_tree.get_children():
            self.review_tree.delete(item)

        search = self.review_search_var.get().lower().strip()
        product_filter = self.review_product_var.get()
        min_rate = int(self.review_min_rate_var.get() or '0')

        total_count = 0
        shown_count = 0
        avg_rate_sum = 0
        avg_rate_n = 0

        for prod_name, reviews in sorted(
                product_reviews.items()):
            if (product_filter != 'Tumu'
                    and prod_name != product_filter):
                continue
            for rev in reviews:
                total_count += 1
                rate = rev.get('rate', 0)
                comment = rev.get('comment', '')
                user = rev.get('user', '').strip() or 'Anonim'
                date = rev.get('date', '')

                avg_rate_sum += rate
                avg_rate_n += 1

                if rate < min_rate:
                    continue
                if search and search not in comment.lower():
                    continue

                stars = '*' * rate
                self.review_tree.insert(
                    '', 'end',
                    values=(
                        prod_name[:40], user[:20],
                        f"{stars} ({rate})",
                        date, comment[:150]))
                shown_count += 1

        avg_str = ''
        if avg_rate_n > 0:
            avg_str = f" | Ort. puan: {avg_rate_sum/avg_rate_n:.1f}"
        self.review_summary_var.set(
            f"Toplam {total_count} yorum, "
            f"{len(product_reviews)} urun | "
            f"Gosterilen: {shown_count}{avg_str}")

    def _show_review_detail(self, event):
        sel = self.review_tree.selection()
        if not sel:
            return
        vals = self.review_tree.item(sel[0])['values']
        detail = (
            f"Urun: {vals[0]}\n"
            f"Kullanici: {vals[1]}\n"
            f"Puan: {vals[2]}\n"
            f"Tarih: {vals[3]}\n\n"
            f"Yorum:\n{vals[4]}")
        win = tk.Toplevel(self)
        win.title("Yorum Detayi")
        win.geometry("600x350")
        win.transient(self)
        txt = scrolledtext.ScrolledText(
            win, wrap='word', font=('Helvetica', 11))
        txt.pack(fill='both', expand=True, padx=10, pady=10)
        txt.insert('1.0', detail)
        txt.configure(state='disabled')

    def show_review_analysis(self):
        """Yorum duygu analizi penceresi."""
        stats = get_review_sentiment_stats()
        if not stats or stats.get('total', 0) == 0:
            messagebox.showinfo("Bilgi", "Henuz yorum yuklenmedi.")
            return

        win = tk.Toplevel(self)
        win.title("Yorum Analizi")
        win.geometry("700x550")
        win.transient(self)

        txt = scrolledtext.ScrolledText(
            win, wrap='word', font=('Courier', 11))
        txt.pack(fill='both', expand=True, padx=10, pady=10)

        lines = [
            "=== YORUM DUYGU ANALIZI ===\n",
            f"Toplam Yorum: {stats['total']}",
            f"Ortalama Puan: {stats['avg_rate']:.1f} / 5\n",
            f"Olumlu (4-5): {stats['positive']} "
            f"({stats['positive']/stats['total']*100:.0f}%)",
            f"Notr (3): {stats['neutral']} "
            f"({stats['neutral']/stats['total']*100:.0f}%)",
            f"Olumsuz (1-2): {stats['negative']} "
            f"({stats['negative']/stats['total']*100:.0f}%)\n",
            "--- Urun Bazinda Analiz ---",
        ]

        # Urun bazinda siralama (en dusuk puandan yuksege)
        sorted_products = sorted(
            stats['by_product'].items(),
            key=lambda x: x[1]['avg'])
        for prod_name, ps in sorted_products:
            lines.append(
                f"\n{prod_name[:50]}")
            lines.append(
                f"  Yorum: {ps['total']} | "
                f"Ort: {ps['avg']:.1f} | "
                f"Olumlu: {ps['positive']} | "
                f"Olumsuz: {ps['negative']}")

        # En sik gecen kelimeler
        all_words = Counter()
        stop_words = {'bir', 've', 'ile', 'bu', 'da', 'de', 'mi',
                      'cok', 'ama', 'icin', 'ben', 'var', 'yok',
                      'evet', 'hayir', 'olan', 'gibi', 'daha'}
        for reviews in product_reviews.values():
            for rev in reviews:
                comment = (rev.get('comment') or '').lower()
                words = re.findall(r'\w+', comment)
                for w in words:
                    if len(w) > 2 and w not in stop_words:
                        all_words[w] += 1

        if all_words:
            lines.append("\n--- En Sik Gecen Kelimeler ---")
            for word, count in all_words.most_common(20):
                bar = '#' * min(count, 30)
                lines.append(f"  {word:15s} {count:4d} {bar}")

        txt.insert('1.0', '\n'.join(lines))
        txt.configure(state='disabled')

    def clear_reviews(self):
        if messagebox.askyesno(
                "Temizle",
                "Tum cache'lenmis yorumlari silmek "
                "istediginize emin misiniz?"):
            product_reviews.clear()
            save_reviews()
            self.refresh_reviews_list()
            self._set_status("Yorumlar temizlendi")

    # ══════════════════════════════════════════
    # TAB 7 — AI Ayarlari
    # ══════════════════════════════════════════
    def _build_ai_tab(self):
        main = ttk.Frame(self.tab_ai)
        main.pack(fill='both', expand=True, padx=12, pady=8)

        # Sol: Ayarlar
        left = ttk.LabelFrame(
            main, text="Gemini AI Yapilandirmasi", padding=10)
        left.pack(side='left', fill='both', expand=True, padx=(0, 6))

        self.ai_enabled_var = tk.BooleanVar(
            value=gemini_config.get('enabled', True))
        ttk.Checkbutton(
            left, text="Gemini AI Aktif",
            variable=self.ai_enabled_var).grid(
            row=0, column=0, columnspan=2, sticky='w', pady=4)

        self.ai_autosend_var = tk.BooleanVar(
            value=gemini_config.get('auto_send', False))
        ttk.Checkbutton(
            left,
            text="AI yanitlarini otomatik gonder (guven esigi uzerinde)",
            variable=self.ai_autosend_var).grid(
            row=1, column=0, columnspan=2, sticky='w', pady=4)

        ttk.Label(left, text="Model:").grid(
            row=2, column=0, sticky='w', pady=4)
        self.ai_model_var = tk.StringVar(
            value=gemini_config.get('model', 'gemini-2.0-flash'))
        ttk.Combobox(
            left, textvariable=self.ai_model_var,
            values=[
                'gemini-2.0-flash',
                'gemini-2.0-flash-lite',
                'gemini-2.5-pro-preview-05-06',
                'gemini-2.5-flash-preview-05-20',
            ],
            width=35).grid(row=2, column=1, sticky='w', pady=4, padx=4)

        ttk.Label(left, text="Sicaklik (0-1):").grid(
            row=3, column=0, sticky='w', pady=4)
        self.ai_temp_var = tk.StringVar(
            value=str(gemini_config.get('temperature', 0.3)))
        ttk.Entry(left, textvariable=self.ai_temp_var,
                  width=10).grid(
            row=3, column=1, sticky='w', pady=4, padx=4)

        ttk.Label(left, text="Max Token:").grid(
            row=4, column=0, sticky='w', pady=4)
        self.ai_maxtok_var = tk.StringVar(
            value=str(gemini_config.get('max_tokens', 500)))
        ttk.Entry(left, textvariable=self.ai_maxtok_var,
                  width=10).grid(
            row=4, column=1, sticky='w', pady=4, padx=4)

        ttk.Label(left, text="Guven Esigi (0-1):").grid(
            row=5, column=0, sticky='w', pady=4)
        self.ai_conf_var = tk.StringVar(
            value=str(gemini_config.get('confidence_threshold', 0.7)))
        ttk.Entry(left, textvariable=self.ai_conf_var,
                  width=10).grid(
            row=5, column=1, sticky='w', pady=4, padx=4)

        ttk.Label(left, text="Bulanik Esik (0-1):").grid(
            row=6, column=0, sticky='w', pady=4)
        self.ai_fuzzy_var = tk.StringVar(
            value=str(gemini_config.get('fuzzy_threshold', 0.65)))
        ttk.Entry(left, textvariable=self.ai_fuzzy_var,
                  width=10).grid(
            row=6, column=1, sticky='w', pady=4, padx=4)

        ttk.Label(left, text="Sistem Promptu:").grid(
            row=7, column=0, sticky='nw', pady=4)
        self.ai_prompt_text = scrolledtext.ScrolledText(
            left, wrap='word', width=50, height=10,
            font=('Courier', 10))
        self.ai_prompt_text.grid(
            row=7, column=1, sticky='nsew', pady=4, padx=4)
        self.ai_prompt_text.insert(
            '1.0', gemini_config.get('system_prompt', ''))
        left.rowconfigure(7, weight=1)
        left.columnconfigure(1, weight=1)

        ttk.Button(left, text="Ayarlari Kaydet",
                   command=self.save_ai_settings).grid(
            row=8, column=0, columnspan=2, pady=(10, 0))

        # Sag: Test
        right = ttk.LabelFrame(main, text="AI Test", padding=10)
        right.pack(side='right', fill='both', expand=True, padx=(6, 0))

        ttk.Label(right, text="Test sorusu yazin:").pack(anchor='w')
        self.ai_test_input = scrolledtext.ScrolledText(
            right, wrap='word', height=4,
            font=('Helvetica', 11))
        self.ai_test_input.pack(fill='x', pady=4)

        ttk.Button(right, text="Test Et",
                   command=self.test_ai_response).pack(
            anchor='w', pady=4)

        ttk.Label(right, text="Sonuc:").pack(
            anchor='w', pady=(8, 0))
        self.ai_test_output = scrolledtext.ScrolledText(
            right, wrap='word', height=12,
            font=('Helvetica', 11))
        self.ai_test_output.pack(fill='both', expand=True, pady=4)

    def save_ai_settings(self):
        try:
            gemini_config['enabled'] = self.ai_enabled_var.get()
            gemini_config['auto_send'] = self.ai_autosend_var.get()
            gemini_config['model'] = self.ai_model_var.get()
            gemini_config['temperature'] = float(
                self.ai_temp_var.get())
            gemini_config['max_tokens'] = int(
                self.ai_maxtok_var.get())
            gemini_config['confidence_threshold'] = float(
                self.ai_conf_var.get())
            gemini_config['fuzzy_threshold'] = float(
                self.ai_fuzzy_var.get())
            gemini_config['system_prompt'] = (
                self.ai_prompt_text.get('1.0', 'end').strip())
            save_gemini_config()
            self._set_status("AI ayarlari kaydedildi")
        except ValueError as e:
            messagebox.showerror("Hata", f"Gecersiz deger: {e}")

    def test_ai_response(self):
        question = self.ai_test_input.get('1.0', 'end').strip()
        if not question:
            messagebox.showwarning("Uyari", "Bir soru yazin.")
            return

        self.ai_test_output.delete('1.0', 'end')
        self.ai_test_output.insert('1.0', "Yanit uretiliyor...\n")
        self.update_idletasks()

        def _run():
            results = []

            # 0. Kategori
            cat = categorize_question(question)
            cat_info = QUESTION_CATEGORIES.get(cat, {})
            results.append(
                f"[KATEGORI] {cat_info.get('icon', '')} "
                f"{cat_info.get('label', cat)}")

            # 1. Keyword
            kw = exact_keyword_match(question)
            if kw:
                results.append(
                    f"[ANAHTAR KELIME] ESLESME: {kw[:120]}")
            else:
                results.append("[ANAHTAR KELIME] Eslesme yok")

            # 2. Fuzzy
            fz, score = fuzzy_keyword_match(question)
            if fz:
                results.append(
                    f"[BULANIK] ESLESME (skor: {score:.0%}): "
                    f"{fz[:120]}")
            else:
                results.append("[BULANIK] Eslesme yok")

            # 3. Hizli oneriler
            suggestions = get_quick_suggestions(question, 3)
            if suggestions:
                sg_lines = ["[HIZLI ONERILER]"]
                for sq, sa in suggestions:
                    sg_lines.append(
                        f"  Soru: {sq[:60]}\n  Yanit: {sa[:100]}")
                results.append('\n'.join(sg_lines))

            # 4. Ilgili Yorumlar
            relevant = find_relevant_reviews(
                question, '', max_reviews=3)
            if relevant:
                rev_lines = ["[ILGILI YORUMLAR]"]
                for prod, rev, sc in relevant:
                    rev_lines.append(
                        f"  {prod[:40]} | {rev.get('user','')}: "
                        f"\"{rev.get('comment','')[:100]}\" "
                        f"({rev.get('rate',0)}/5)")
                results.append('\n'.join(rev_lines))
            else:
                results.append(
                    "[ILGILI YORUMLAR] Eslesen yorum yok")

            # 5. Gemini
            if not MISSING_GEMINI and gemini_config.get('enabled'):
                ai, conf = generate_gemini_response(question)
                if ai:
                    results.append(
                        f"[GEMINI AI] (guven: {conf:.0%}):\n{ai}")
                else:
                    results.append("[GEMINI AI] Yanit uretilemedi")
            else:
                results.append("[GEMINI AI] Devre disi")

            sep = '\n' + '-' * 50 + '\n'
            output = sep.join(results)
            self.after(
                0, lambda: self._display_test_result(output))

        threading.Thread(target=_run, daemon=True).start()

    def _display_test_result(self, text):
        self.ai_test_output.delete('1.0', 'end')
        self.ai_test_output.insert('1.0', text)

    # ══════════════════════════════════════════
    # TAB 8 — Istatistikler
    # ══════════════════════════════════════════
    def _build_stats_tab(self):
        self.stats_frame = ttk.Frame(self.tab_stats)
        self.stats_frame.pack(fill='both', expand=True, padx=12, pady=8)

        ttk.Button(
            self.stats_frame, text="Istatistikleri Guncelle",
            command=self.refresh_stats).pack(anchor='e', pady=(0, 8))

        self.stats_cards_frame = ttk.Frame(self.stats_frame)
        self.stats_cards_frame.pack(fill='x', pady=(0, 12))

        self.stats_detail_frame = ttk.Frame(self.stats_frame)
        self.stats_detail_frame.pack(fill='both', expand=True)

    def refresh_stats(self):
        if not hasattr(self, 'stats_cards_frame'):
            return
        for w in self.stats_cards_frame.winfo_children():
            w.destroy()
        for w in self.stats_detail_frame.winfo_children():
            w.destroy()

        metrics = get_performance_metrics()

        total = metrics['total_questions']
        today_count = metrics['today_questions']
        week_count = metrics['week_questions']
        method_counts = metrics['method_counts']

        active_pending = sum(
            1 for p in pending_questions
            if p.get('status') in ('pending', 'no_match'))

        auto_rate_pct = f"{metrics['auto_rate']:.0%}" if total > 0 else "N/A"

        # Kartlar
        cards = [
            ("Toplam Soru", str(total), '#2196F3'),
            ("Bugun", str(today_count), '#4CAF50'),
            ("Bu Hafta", str(week_count), '#FF9800'),
            ("Oto Yanit Kurali",
             str(len(automated_responses)), '#9C27B0'),
            ("Bekleyen", str(active_pending), '#f44336'),
            ("Oto Cozum Orani", auto_rate_pct, '#00BCD4'),
        ]

        for i, (label, value, color) in enumerate(cards):
            card = ttk.Frame(
                self.stats_cards_frame,
                relief='solid', borderwidth=1)
            card.grid(row=0, column=i, padx=5, pady=4,
                      sticky='nsew')
            self.stats_cards_frame.columnconfigure(i, weight=1)

            tk.Label(card, text=value,
                     font=('Helvetica', 24, 'bold'),
                     fg=color).pack(pady=(8, 0))
            tk.Label(card, text=label,
                     font=('Helvetica', 9),
                     fg='#666').pack(pady=(0, 8))

        # Sol: Yontem dagilimi, Sag: Kategori + Saatlik
        detail_paned = ttk.PanedWindow(
            self.stats_detail_frame, orient='horizontal')
        detail_paned.pack(fill='both', expand=True)

        # Sol panel: Yontem Dagilimi
        left_panel = ttk.LabelFrame(
            detail_paned, text="Yanit Yontemi Dagilimi", padding=8)
        detail_paned.add(left_panel, weight=1)

        colors = {
            'keyword': '#4CAF50',
            'fuzzy': '#8BC34A',
            'gemini': '#2196F3',
            'manual_approved': '#00BCD4',
            'manual_edited': '#009688',
            'template': '#3F51B5',
            'out_of_service': '#FF9800',
            'pending': '#FFC107',
            'no_match': '#f44336',
        }

        bar_frame = ttk.Frame(left_panel)
        bar_frame.pack(fill='x', padx=4)

        for method, count in sorted(
                method_counts.items(), key=lambda x: -x[1]):
            row = ttk.Frame(bar_frame)
            row.pack(fill='x', pady=2)

            label = self.METHOD_LABELS.get(method, method)
            pct = (count / total * 100) if total > 0 else 0

            ttk.Label(row, text=label, width=20).pack(side='left')

            bar_container = tk.Frame(
                row, bg='#e0e0e0', height=18)
            bar_container.pack(
                side='left', fill='x', expand=True, padx=4)
            bar_container.pack_propagate(False)

            if pct > 0:
                bar = tk.Frame(
                    bar_container,
                    bg=colors.get(method, '#999'),
                    height=18)
                bar.place(
                    relwidth=max(pct / 100, 0.01), relheight=1)

            ttk.Label(
                row, text=f"{count} ({pct:.0f}%)",
                width=12).pack(side='right')

        # Sag panel: Kategori + Saatlik Dagilim
        right_panel = ttk.Frame(detail_paned)
        detail_paned.add(right_panel, weight=1)

        # Kategori dagilimi
        cat_frame = ttk.LabelFrame(
            right_panel, text="Kategori Dagilimi", padding=8)
        cat_frame.pack(fill='x', padx=4, pady=(0, 8))

        cat_dist = metrics['category_distribution']
        for cat_code, count in sorted(
                cat_dist.items(), key=lambda x: -x[1]):
            cat_info = QUESTION_CATEGORIES.get(cat_code, {})
            cat_label = cat_info.get('label', cat_code)
            cat_icon = cat_info.get('icon', '')
            cat_color = cat_info.get('color', '#999')
            pct = (count / total * 100) if total > 0 else 0

            row = ttk.Frame(cat_frame)
            row.pack(fill='x', pady=1)
            tk.Label(row, text=f"{cat_icon} {cat_label}",
                     font=('Helvetica', 9), width=20,
                     anchor='w').pack(side='left')
            bar_c = tk.Frame(row, bg='#e0e0e0', height=14)
            bar_c.pack(side='left', fill='x', expand=True, padx=4)
            bar_c.pack_propagate(False)
            if pct > 0:
                bar = tk.Frame(bar_c, bg=cat_color, height=14)
                bar.place(relwidth=max(pct / 100, 0.01), relheight=1)
            ttk.Label(row, text=f"{count}", width=6).pack(side='right')

        # Saatlik dagilim
        hour_frame = ttk.LabelFrame(
            right_panel, text="Saatlik Dagilim", padding=8)
        hour_frame.pack(fill='both', expand=True, padx=4)

        hourly = metrics['hourly_distribution']
        max_hour_count = max(hourly.values()) if hourly else 1
        for hour in range(8, 22):  # 08:00 - 21:00
            count = hourly.get(hour, 0)
            pct = (count / max_hour_count) if max_hour_count > 0 else 0
            row = ttk.Frame(hour_frame)
            row.pack(fill='x', pady=0)
            tk.Label(row, text=f"{hour:02d}:00",
                     font=('Helvetica', 8), width=6).pack(side='left')
            bar_c = tk.Frame(row, bg='#f0f0f0', height=10)
            bar_c.pack(side='left', fill='x', expand=True, padx=2)
            bar_c.pack_propagate(False)
            if pct > 0:
                bar = tk.Frame(bar_c, bg='#2196F3', height=10)
                bar.place(relwidth=max(pct, 0.01), relheight=1)
            tk.Label(row, text=str(count),
                     font=('Helvetica', 8), width=4).pack(side='right')

    # ══════════════════════════════════════════
    # TAB 9 — Ayarlar
    # ══════════════════════════════════════════
    def _build_settings_tab(self):
        canvas = tk.Canvas(self.tab_settings, highlightthickness=0)
        scrollbar = ttk.Scrollbar(
            self.tab_settings, orient='vertical', command=canvas.yview)
        settings_frame = ttk.Frame(canvas)
        settings_frame.bind(
            '<Configure>',
            lambda e: canvas.configure(scrollregion=canvas.bbox('all')))
        canvas.create_window((0, 0), window=settings_frame, anchor='nw')
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')

        canvas.bind('<Enter>', lambda e: self._bind_mousewheel(canvas))
        canvas.bind('<Leave>', lambda e: self._unbind_mousewheel(canvas))

        # ─── Mesai Saatleri ───
        work_frame = ttk.LabelFrame(
            settings_frame, text="Mesai Saatleri", padding=12)
        work_frame.pack(fill='x', padx=12, pady=(12, 6))

        r = 0
        ttk.Label(work_frame, text="Baslangic:").grid(
            row=r, column=0, sticky='w', pady=4)
        self.settings_work_start = tk.StringVar(
            value=app_settings.get('work_hours_start', '10:00'))
        ttk.Entry(work_frame, textvariable=self.settings_work_start,
                  width=8).grid(row=r, column=1, sticky='w', padx=4)

        ttk.Label(work_frame, text="Bitis:").grid(
            row=r, column=2, sticky='w', pady=4, padx=(16, 0))
        self.settings_work_end = tk.StringVar(
            value=app_settings.get('work_hours_end', '18:00'))
        ttk.Entry(work_frame, textvariable=self.settings_work_end,
                  width=8).grid(row=r, column=3, sticky='w', padx=4)

        r += 1
        ttk.Label(work_frame, text="Calisma Gunleri:").grid(
            row=r, column=0, sticky='w', pady=4)
        days_frame = ttk.Frame(work_frame)
        days_frame.grid(row=r, column=1, columnspan=3, sticky='w')
        day_names = ['Pzt', 'Sal', 'Car', 'Per', 'Cum', 'Cmt', 'Paz']
        self.day_vars = []
        current_days = app_settings.get('work_days', [0, 1, 2, 3, 4])
        for i, day_name in enumerate(day_names):
            var = tk.BooleanVar(value=i in current_days)
            self.day_vars.append(var)
            ttk.Checkbutton(days_frame, text=day_name,
                            variable=var).pack(side='left', padx=2)

        # ─── Bildirimler ───
        notif_frame = ttk.LabelFrame(
            settings_frame, text="Bildirimler", padding=12)
        notif_frame.pack(fill='x', padx=12, pady=6)

        self.settings_notif_enabled = tk.BooleanVar(
            value=app_settings.get('notifications_enabled', True))
        ttk.Checkbutton(
            notif_frame, text="Masaustu bildirimleri",
            variable=self.settings_notif_enabled).pack(
            anchor='w', pady=2)

        ttk.Button(
            notif_frame, text="Test Bildirimi Gonder",
            command=lambda: send_notification(
                "Kozmopol Test", "Bildirimler calisiyor!")
        ).pack(anchor='w', pady=4)

        # ─── Sorgulama Ayarlari ───
        poll_frame = ttk.LabelFrame(
            settings_frame, text="API Sorgulama", padding=12)
        poll_frame.pack(fill='x', padx=12, pady=6)

        ttk.Label(poll_frame, text="Sorgulama araligi (saniye):").pack(
            anchor='w')
        self.settings_poll_interval = tk.StringVar(
            value=str(app_settings.get('poll_interval', 300)))
        ttk.Entry(poll_frame, textvariable=self.settings_poll_interval,
                  width=10).pack(anchor='w', pady=4)

        # ─── Kara Liste ───
        blacklist_frame = ttk.LabelFrame(
            settings_frame, text="Kelime Kara Listesi", padding=12)
        blacklist_frame.pack(fill='x', padx=12, pady=6)

        ttk.Label(
            blacklist_frame,
            text="AI yanitlarinda bulunmamasi gereken kelimeler. "
                 "Tespit edilirse yanit otomatik onaya alinir.",
            foreground='#666', wraplength=600).pack(anchor='w', pady=(0, 4))

        self.blacklist_text = scrolledtext.ScrolledText(
            blacklist_frame, wrap='word', height=4,
            font=('Helvetica', 11))
        self.blacklist_text.pack(fill='x')

        bl_btn_frame = ttk.Frame(blacklist_frame)
        bl_btn_frame.pack(fill='x', pady=(4, 0))
        ttk.Button(bl_btn_frame, text="Kelime Ekle",
                   command=self.add_blacklist_word).pack(side='left')
        ttk.Button(bl_btn_frame, text="Seciliyi Sil",
                   command=self.remove_blacklist_word).pack(
            side='left', padx=(4, 0))

        # ─── Genel ───
        gen_frame = ttk.LabelFrame(
            settings_frame, text="Genel", padding=12)
        gen_frame.pack(fill='x', padx=12, pady=6)

        self.settings_auto_cat = tk.BooleanVar(
            value=app_settings.get('auto_categorize', True))
        ttk.Checkbutton(
            gen_frame, text="Sorulari otomatik kategorize et",
            variable=self.settings_auto_cat).pack(anchor='w', pady=2)

        ttk.Label(gen_frame, text="Max yanit uzunlugu:").pack(
            anchor='w', pady=(8, 0))
        self.settings_max_resp_len = tk.StringVar(
            value=str(app_settings.get('max_response_length', 500)))
        ttk.Entry(gen_frame, textvariable=self.settings_max_resp_len,
                  width=10).pack(anchor='w', pady=4)

        # ─── Kaydet Butonu ───
        save_btn_frame = ttk.Frame(settings_frame)
        save_btn_frame.pack(fill='x', padx=12, pady=12)
        ttk.Button(save_btn_frame, text="Tum Ayarlari Kaydet",
                   command=self.save_all_settings).pack(side='right')
        ttk.Button(save_btn_frame, text="Varsayilanlara Don",
                   command=self.reset_settings).pack(
            side='right', padx=(0, 8))

    def refresh_blacklist_display(self):
        if not hasattr(self, 'blacklist_text'):
            return
        self.blacklist_text.delete('1.0', 'end')
        self.blacklist_text.insert(
            '1.0', ', '.join(word_blacklist))

    def add_blacklist_word(self):
        def do_save(text, win):
            words = [w.strip() for w in text.split(',') if w.strip()]
            if not words:
                messagebox.showerror(
                    "Hata", "En az bir kelime girin.", parent=win)
                return
            for w in words:
                if w not in word_blacklist:
                    word_blacklist.append(w)
            save_blacklist()
            self.refresh_blacklist_display()
            self._set_status(f"{len(words)} kelime kara listeye eklendi")
            win.destroy()

        self._open_edit_dialog(
            "Kara Listeye Ekle (virgul ile)", '',
            do_save, lambda w: w.destroy())

    def remove_blacklist_word(self):
        def do_save(text, win):
            words = [w.strip().lower() for w in text.split(',') if w.strip()]
            removed = 0
            for w in words:
                matching = [bw for bw in word_blacklist if bw.lower() == w]
                for m in matching:
                    word_blacklist.remove(m)
                    removed += 1
            save_blacklist()
            self.refresh_blacklist_display()
            self._set_status(f"{removed} kelime kara listeden cikarildi")
            win.destroy()

        self._open_edit_dialog(
            "Kara Listeden Cikar (virgul ile)",
            ', '.join(word_blacklist),
            do_save, lambda w: w.destroy())

    def save_all_settings(self):
        try:
            app_settings['work_hours_start'] = self.settings_work_start.get()
            app_settings['work_hours_end'] = self.settings_work_end.get()
            app_settings['work_days'] = [
                i for i, v in enumerate(self.day_vars) if v.get()]
            app_settings['notifications_enabled'] = (
                self.settings_notif_enabled.get())
            app_settings['poll_interval'] = int(
                self.settings_poll_interval.get())
            app_settings['auto_categorize'] = self.settings_auto_cat.get()
            app_settings['max_response_length'] = int(
                self.settings_max_resp_len.get())

            # Kara listeyi de kaydet
            bl_text = self.blacklist_text.get('1.0', 'end').strip()
            new_bl = [w.strip() for w in bl_text.split(',') if w.strip()]
            word_blacklist.clear()
            word_blacklist.extend(new_bl)
            save_blacklist()

            save_settings()
            self._update_work_status()
            self._set_status("Tum ayarlar kaydedildi")
        except ValueError as e:
            messagebox.showerror("Hata", f"Gecersiz deger: {e}")

    def reset_settings(self):
        if not messagebox.askyesno(
                "Onayla",
                "Tum ayarlari varsayilanlara dondurmek istiyor musunuz?"):
            return
        app_settings.clear()
        app_settings.update(DEFAULT_SETTINGS)
        save_settings()
        # UI'yi guncelle
        self.settings_work_start.set(
            app_settings['work_hours_start'])
        self.settings_work_end.set(app_settings['work_hours_end'])
        for i, v in enumerate(self.day_vars):
            v.set(i in app_settings['work_days'])
        self.settings_notif_enabled.set(
            app_settings['notifications_enabled'])
        self.settings_poll_interval.set(
            str(app_settings['poll_interval']))
        self.settings_auto_cat.set(
            app_settings['auto_categorize'])
        self.settings_max_resp_len.set(
            str(app_settings['max_response_length']))
        self._set_status("Ayarlar varsayilanlara donduruldu")

    # ══════════════════════════════════════════
    # ORTAK DUZENLEME DIYALOGU
    # ══════════════════════════════════════════
    def _open_edit_dialog(self, title, initial_text,
                          on_save, on_cancel):
        win = tk.Toplevel(self)
        win.title(title)
        W, H = 650, 350
        self.update_idletasks()
        x = (self.winfo_rootx()
             + (self.winfo_width() // 2) - (W // 2))
        y = (self.winfo_rooty()
             + (self.winfo_height() // 2) - (H // 2))
        win.geometry(f"{W}x{H}+{x}+{y}")
        win.resizable(True, True)
        win.transient(self)
        win.grab_set()
        win.focus_set()

        win.rowconfigure(0, weight=1)
        win.columnconfigure(0, weight=1)

        body = ttk.Frame(win)
        body.grid(row=0, column=0, sticky='nsew',
                  padx=12, pady=(10, 6))
        body.rowconfigure(0, weight=1)
        body.columnconfigure(0, weight=1)

        txt = scrolledtext.ScrolledText(
            body, wrap='word', font=('Helvetica', 11))
        txt.grid(row=0, column=0, sticky='nsew')
        txt.insert('1.0', initial_text)

        btnbar = ttk.Frame(win)
        btnbar.grid(row=1, column=0, sticky='e',
                    padx=12, pady=(0, 10))

        def _save(*_):
            val = txt.get('1.0', 'end').strip()
            on_save(val, win)

        def _cancel(*_):
            on_cancel(win)

        ttk.Button(btnbar, text="Kaydet",
                   command=_save).pack(side='right', padx=(6, 0))
        ttk.Button(btnbar, text="Iptal",
                   command=_cancel).pack(side='right')

        win.bind('<Control-s>', _save)
        win.bind('<Escape>', lambda e: win.destroy())
        txt.focus_set()
        return win

    # ══════════════════════════════════════════
    # MEVCUT ISLEVLER (uyarlanmis)
    # ══════════════════════════════════════════
    def edit_question(self, key_tuple):
        old_q = ', '.join(key_tuple)

        def do_save(new_text, win):
            new_key = normalize_key_text(new_text)
            if not new_key:
                messagebox.showerror(
                    "Hata",
                    "En az bir anahtar kelime girin.",
                    parent=win)
                return
            resp = automated_responses.get(key_tuple, '')
            if key_tuple in automated_responses:
                del automated_responses[key_tuple]
            automated_responses[new_key] = resp
            self._persist_and_refresh("Soru guncellendi")
            win.destroy()

        def do_delete(win):
            if messagebox.askyesno(
                    "Sil", "Bu kaydi silmek istiyor musunuz?",
                    parent=win):
                if key_tuple in automated_responses:
                    del automated_responses[key_tuple]
                self._persist_and_refresh("Kayit silindi")
                win.destroy()

        self._open_edit_dialog(
            "Soru Duzenle", old_q, do_save, do_delete)

    def edit_answer(self, key_tuple):
        old_a = automated_responses.get(key_tuple, '')

        def do_save(new_text, win):
            if not new_text:
                messagebox.showerror(
                    "Hata", "Cevap metni bos olamaz.",
                    parent=win)
                return
            automated_responses[key_tuple] = new_text
            self._persist_and_refresh("Cevap guncellendi")
            win.destroy()

        def do_delete(win):
            if messagebox.askyesno(
                    "Sil", "Bu kaydi silmek istiyor musunuz?",
                    parent=win):
                if key_tuple in automated_responses:
                    del automated_responses[key_tuple]
                self._persist_and_refresh("Kayit silindi")
                win.destroy()

        self._open_edit_dialog(
            "Cevap Duzenle", old_a, do_save, do_delete)

    def add_new(self):
        def do_save_soru(new_text, win):
            key = normalize_key_text(new_text)
            if not key:
                messagebox.showerror(
                    "Hata",
                    "En az bir anahtar kelime girin.",
                    parent=win)
                return
            win.destroy()

            def do_save_cevap(a_text, w2):
                if not a_text:
                    messagebox.showerror(
                        "Hata", "Cevap metni bos olamaz.",
                        parent=w2)
                    return
                automated_responses[key] = a_text
                self._persist_and_refresh("Yeni kayit eklendi")
                w2.destroy()

            self._open_edit_dialog(
                "Cevap Ekle", '',
                do_save_cevap, lambda w: w.destroy())

        self._open_edit_dialog(
            "Soru Ekle (anahtar kelimeler, virgul ile)", '',
            do_save_soru, lambda w: w.destroy())

    def delete_selected(self):
        if not self.selected_key:
            messagebox.showwarning(
                "Uyari", "Silmek icin bir kayit tiklayin.")
            return
        if messagebox.askyesno(
                "Sil",
                "Bu kaydi silmek istediginize emin misiniz?"):
            if self.selected_key in automated_responses:
                del automated_responses[self.selected_key]
            self._persist_and_refresh("Kayit silindi")
            self.selected_key = None

    def _persist_and_refresh(self, msg="Kaydedildi"):
        save_responses()
        load_responses()
        self.reload_responses_list()
        self.refresh_stats()
        self._set_status(msg)

    def _set_status(self, text):
        self.status_var.set(
            f"{text}  |  {datetime.now().strftime('%H:%M:%S')}")

    def refresh_all_tabs(self):
        """Tum sekmeleri guncelle (thread-safe)."""
        try:
            self.reload_responses_list()
            self.refresh_pending_list()
            self.refresh_log_list()
            self.refresh_reviews_list()
            self.refresh_stats()
            self.refresh_templates_list()
        except Exception:
            pass


# ════════════════════════════════════════════════════════
# ANA GIRIS NOKTASI
# ════════════════════════════════════════════════════════
if __name__ == '__main__':
    load_settings()
    load_responses()
    load_question_log()
    load_pending()
    load_gemini_config()
    load_reviews()
    load_templates()
    load_blacklist()

    logger.info("Kozmopol v3.0 baslatiliyor...")
    print("=" * 60)
    print("  Kozmopol — Trendyol Akilli Musteri Hizmetleri v3.0")
    print("=" * 60)
    print(f"  Otomatik yanit kurali : {len(automated_responses)}")
    print(f"  Soru logu             : {len(question_log)} kayit")
    print(f"  Bekleyen soru         : {len(pending_questions)}")
    total_revs = sum(len(v) for v in product_reviews.values())
    print(f"  Yorum cache           : {total_revs} yorum, "
          f"{len(product_reviews)} urun")
    print(f"  Yanit sablonu         : {len(response_templates)}")
    print(f"  Kara liste            : {len(word_blacklist)} kelime")
    print(f"  Gemini AI             : "
          f"{'AKTIF' if not MISSING_GEMINI else 'DEVRE DISI'}")
    print(f"  Trendyol API          : "
          f"{'AKTIF' if not MISSING_CREDS else 'DEVRE DISI'}")
    print(f"  Mesai                 : "
          f"{app_settings.get('work_hours_start', '10:00')}"
          f"-{app_settings.get('work_hours_end', '18:00')}")
    print(f"  Karanlik Mod          : "
          f"{'Acik' if app_settings.get('dark_mode') else 'Kapali'}")
    print("=" * 60)

    app = App()

    if not MISSING_CREDS:
        question_thread = threading.Thread(
            target=check_and_answer_questions, daemon=True)
        question_thread.start()
        logger.info("Soru kontrol thread'i baslatildi")
    else:
        print("[Bilgi] API kimlik bilgileri eksik — "
              "otomatik cevap thread'i baslatilmadi.")

    app.mainloop()
    logger.info("Kozmopol kapatildi")
