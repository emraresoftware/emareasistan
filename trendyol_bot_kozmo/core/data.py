"""
core.data — Veri Depolari, JSON I/O, Yardimci Fonksiyonlar
============================================================
Tum global veri yapiları, yukleme/kaydetme isleri ve yardimci fonksiyonlar.
"""

import json
import os
import re
import subprocess
import platform
import threading
from datetime import datetime

from config import (
    RESPONSES_FILE, LOG_FILE, PENDING_FILE, GEMINI_CONFIG_FILE,
    REVIEWS_FILE, TEMPLATES_FILE, BLACKLIST_FILE, SETTINGS_FILE,
    DEFAULT_SETTINGS, DEFAULT_GEMINI_CONFIG, DEFAULT_TEMPLATES,
    DEFAULT_BLACKLIST, QUESTION_CATEGORIES,
    logger,
)

# ════════════════════════════════════════════════════════
# THREAD KILIDI
# ════════════════════════════════════════════════════════
data_lock = threading.Lock()

# ════════════════════════════════════════════════════════
# GLOBAL VERI DEPOLARI
# ════════════════════════════════════════════════════════
automated_responses: dict = {}   # {('anahtar','kelime'): 'cevap', ...}
question_log: list = []
pending_questions: list = []
product_reviews: dict = {}       # {product_name: [{'comment','rate','date','user'}, ...]}
response_templates: list = []    # [{'name','text','variables'}, ...]
word_blacklist: list = []        # ['yasakli_kelime', ...]
app_settings: dict = {}
gemini_config: dict = {}


# ════════════════════════════════════════════════════════
# NORMALIZE FONKSIYONLARI
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


# ════════════════════════════════════════════════════════
# KATEGORIZASYON
# ════════════════════════════════════════════════════════

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
                if ' ' in kw:
                    score += 0.5
        scores[cat_code] = score
    if not scores or max(scores.values()) == 0:
        return 'diger'
    return max(scores, key=scores.get)


# ════════════════════════════════════════════════════════
# KARA LISTE & SABLON YARDIMCILARI
# ════════════════════════════════════════════════════════

def check_blacklist(text: str) -> list:
    """Metinde kara listedeki kelimeleri kontrol et."""
    if not word_blacklist:
        return []
    text_lower = text.lower()
    return [w for w in word_blacklist if w.lower() in text_lower]


def fill_template(template_text: str, variables: dict) -> str:
    """Sablondaki {{degisken}} ifadelerini doldur."""
    result = template_text
    for key, value in variables.items():
        result = result.replace(f'{{{{{key}}}}}', str(value))
    return result


# ════════════════════════════════════════════════════════
# BILDIRIMLER
# ════════════════════════════════════════════════════════

def send_notification(title: str, message: str):
    """Masaustu bildirimi gonder (macOS / Linux)."""
    if not app_settings.get('notifications_enabled', True):
        return
    try:
        if platform.system() == 'Darwin':
            subprocess.run([
                'osascript', '-e',
                f'display notification "{message}" with title "{title}"'
            ], capture_output=True, timeout=5)
        elif platform.system() == 'Linux':
            subprocess.run(
                ['notify-send', title, message],
                capture_output=True, timeout=5)
    except Exception as e:
        logger.debug(f"Bildirim gonderilemedi: {e}")


# ════════════════════════════════════════════════════════
# JSON I/O
# ════════════════════════════════════════════════════════

def _safe_load_json(filepath, default):
    if os.path.exists(filepath) and os.path.getsize(filepath) > 0:
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            logger.error(f"{filepath} okuma hatasi: {e}")
    return default


def _safe_save_json(filepath, data):
    try:
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except IOError as e:
        logger.error(f"{filepath} yazma hatasi: {e}")


# ════════════════════════════════════════════════════════
# YUKLEME / KAYDETME
# ════════════════════════════════════════════════════════

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
        response_templates = list(DEFAULT_TEMPLATES)
        save_templates()


def save_templates():
    _safe_save_json(TEMPLATES_FILE, response_templates)


def load_blacklist():
    global word_blacklist
    saved = _safe_load_json(BLACKLIST_FILE, None)
    if saved is not None:
        word_blacklist = saved
    else:
        word_blacklist = list(DEFAULT_BLACKLIST)
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


# ════════════════════════════════════════════════════════
# LOG KAYDI
# ════════════════════════════════════════════════════════

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
    logger.info(
        f"[{method}][{category}] "
        f"Q:{question_text[:60]}... -> A:{answer_text[:60]}...")


# ════════════════════════════════════════════════════════
# TUM VERILERI YUKLE
# ════════════════════════════════════════════════════════

def load_all():
    """Tum veri dosyalarini sirayla yukle."""
    load_settings()
    load_responses()
    load_question_log()
    load_pending()
    load_gemini_config()
    load_reviews()
    load_templates()
    load_blacklist()
