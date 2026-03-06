"""
Kozmopol — Trendyol Akilli Musteri Hizmetleri Sistemi v2.0
============================================================
Ozellikler:
  - Anahtar kelime bazli otomatik yanit
  - Google Gemini AI ile akilli yanit uretimi
  - Bulanik (fuzzy) eslestirme
  - Kargo & Iade takibi (Trendyol API)
  - Soru gecmisi & istatistikler
  - Bekleyen sorular kuyrugu (AI onay mekanizmasi)
  - CSV disa aktarim
  - Sekmeli modern arayuz
"""

import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext, filedialog
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
from dotenv import load_dotenv
from datetime import datetime, timedelta
from difflib import SequenceMatcher
from collections import Counter

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


def add_log_entry(question_id, question_text, answer_text, method, product_info=""):
    """Soru loguna kayit ekle."""
    entry = {
        'timestamp': datetime.now().isoformat(),
        'question_id': question_id,
        'question': question_text,
        'answer': answer_text,
        'method': method,
        'product_info': product_info,
    }
    question_log.append(entry)
    save_question_log()
    logger.info(f"[{method}] Q:{question_text[:60]}... -> A:{answer_text[:60]}...")


# ════════════════════════════════════════════════════════
# ZAMANLAMA
# ════════════════════════════════════════════════════════

def is_out_of_service_hours():
    now = datetime.now()
    t = now.time()
    start = datetime.strptime("18:00", "%H:%M").time()
    end = datetime.strptime("08:30", "%H:%M").time()
    return now.weekday() >= 5 or t >= start or t < end


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
    # 1. Exact keyword
    resp = exact_keyword_match(question_text)
    if resp:
        answer_question(question_id, resp)
        add_log_entry(question_id, question_text, resp, 'keyword', product_info)
        return True, 'keyword'

    # 2. Fuzzy
    fuzzy_resp, fuzzy_score = fuzzy_keyword_match(question_text)
    if fuzzy_resp:
        answer_question(question_id, fuzzy_resp)
        add_log_entry(question_id, question_text, fuzzy_resp, 'fuzzy', product_info)
        return True, 'fuzzy'

    # 3. Gemini AI
    if not MISSING_GEMINI and gemini_config.get('enabled', False):
        ai_response, confidence = generate_gemini_response(
            question_text, product_info)
        if ai_response:
            threshold = gemini_config.get('confidence_threshold', 0.7)
            if confidence >= threshold and gemini_config.get('auto_send', False):
                answer_question(question_id, ai_response)
                add_log_entry(question_id, question_text, ai_response,
                              'gemini', product_info)
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
                })
                save_pending()
                add_log_entry(question_id, question_text,
                              f"[BEKLEMEDE] {ai_response}",
                              'pending', product_info)
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
    })
    save_pending()
    add_log_entry(question_id, question_text, "[ESLESMEDI]",
                  'no_match', product_info)
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
        # Tarihi isle
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
    """Soruyla en ilgili yorumlari bul.

    Deger siralama: urun adi eslesmesi > yorum icerik benzerlig > puan.
    Doner: [(product, review_dict, score), ...]
    """
    qtext = question_text.lower()
    q_words = set(re.findall(r'\w+', qtext))
    # 2 karakterden kisa kelimeleri ele
    q_words = {w for w in q_words if len(w) > 2}

    scored: list = []

    for prod_name, reviews in product_reviews.items():
        pname_lower = prod_name.lower()
        # Urun adi eslese bonus
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
            # Kelime ortusme skoru
            overlap = len(q_words & c_words)
            if overlap == 0 and product_bonus == 0:
                continue
            # Benzerlik skoru
            score = overlap * 1.0 + product_bonus
            # Yuksek puanli yorumlara hafif bonus
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


# ════════════════════════════════════════════════════════
# ARKA PLAN IS PARCACIGI
# ════════════════════════════════════════════════════════

def check_and_answer_questions():
    """5 dakikada bir sorulari kontrol eden daemon thread."""
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

            time.sleep(300)

        except Exception as e:
            logger.error(f"Thread hatasi: {e}")
            time.sleep(300)


# ════════════════════════════════════════════════════════
# UI — ANA UYGULAMA
# ════════════════════════════════════════════════════════

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Kozmopol — Trendyol Akilli Musteri Hizmetleri v2.0")
        self.geometry("1200x800")
        self.minsize(1000, 600)

        self.out_of_office_var = tk.BooleanVar(value=True)
        self.status_var = tk.StringVar(value="Hazir")
        self.selected_key = None

        self._build_ui()

        # Ilk yukleme
        self.reload_responses_list()
        self.refresh_pending_list()
        self.refresh_log_list()
        self.refresh_stats()

    # ───────────────────────────────────────────
    # UI OLUSTURMA
    # ───────────────────────────────────────────
    def _build_ui(self):
        style = ttk.Style()
        try:
            style.theme_use('clam')
        except Exception:
            pass
        style.configure('TNotebook.Tab', padding=[14, 6],
                        font=('Helvetica', 10))
        style.configure('Header.TLabel',
                        font=('Helvetica', 13, 'bold'))
        style.configure('Success.TLabel', foreground='#4CAF50',
                        font=('Helvetica', 10, 'bold'))
        style.configure('Warning.TLabel', foreground='#FF9800',
                        font=('Helvetica', 10, 'bold'))
        style.configure('Danger.TLabel', foreground='#f44336',
                        font=('Helvetica', 10, 'bold'))

        # Ust bar
        topbar = ttk.Frame(self)
        topbar.pack(fill='x', padx=10, pady=(8, 4))
        ttk.Label(
            topbar, text="Kozmopol Akilli Cevap Sistemi",
            style='Header.TLabel').pack(side='left')
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

        # Sekmeler
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill='both', expand=True, padx=10, pady=(0, 4))

        self.tab_responses = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_responses, text='  Otomatik Yanitlar  ')
        self._build_responses_tab()

        self.tab_pending = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_pending, text='  Bekleyen Sorular  ')
        self._build_pending_tab()

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

        # Durum cubugu
        status_bar = ttk.Frame(self, relief='sunken')
        status_bar.pack(fill='x', side='bottom')
        ttk.Label(status_bar, textvariable=self.status_var).pack(
            fill='x', padx=8, pady=2)

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
        ttk.Button(
            top, text="Yenile",
            command=lambda: [load_responses(),
                             self.reload_responses_list()]
        ).pack(side='right')

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

            lbl_sk.grid(row=0, column=0, sticky='nw',
                        padx=(8, 4), pady=(6, 2))
            lbl_sv.grid(row=0, column=1, sticky='nw',
                        padx=(0, 8), pady=(6, 2))
            lbl_ck.grid(row=1, column=0, sticky='nw',
                        padx=(8, 4), pady=(0, 8))
            lbl_cv.grid(row=1, column=1, sticky='w',
                        padx=(0, 8), pady=(0, 8))

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
            for lab in (lbl_sk, lbl_sv, lbl_ck, lbl_cv):
                lab.bind(
                    '<Button-1>',
                    lambda e, k=key_tuple: self._select_response(k),
                    add='+')

    def _select_response(self, key_tuple):
        self.selected_key = key_tuple

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

        # Alt butonlar (pack order: bottom first)
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
        ttk.Button(btn_frame, text="Yanit Olarak Kaydet",
                   command=self.save_pending_as_response).pack(side='right')

        # Treeview
        columns = ('zaman', 'soru', 'oneri', 'guven', 'durum')
        tree_frame = ttk.Frame(self.tab_pending)
        tree_frame.pack(fill='both', expand=True, padx=8, pady=(0, 4))

        self.pending_tree = ttk.Treeview(
            tree_frame, columns=columns, show='headings', height=20)
        self.pending_tree.heading('zaman', text='Zaman')
        self.pending_tree.heading('soru', text='Soru')
        self.pending_tree.heading('oneri', text='AI Onerisi')
        self.pending_tree.heading('guven', text='Guven')
        self.pending_tree.heading('durum', text='Durum')

        self.pending_tree.column('zaman', width=130, minwidth=100)
        self.pending_tree.column('soru', width=300, minwidth=200)
        self.pending_tree.column('oneri', width=400, minwidth=200)
        self.pending_tree.column('guven', width=70, minwidth=50)
        self.pending_tree.column('durum', width=100, minwidth=80)

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

        for i, p in enumerate(pending_questions):
            if p.get('status') in ('sent', 'rejected'):
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
                values=(ts, q, a, c, status_map.get(s, s)))

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
        if answer_question(p['question_id'], p['suggested_answer']):
            p['status'] = 'sent'
            save_pending()
            add_log_entry(p['question_id'], p['question'],
                          p['suggested_answer'], 'manual_approved')
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

        self._open_edit_dialog(
            f"Yaniti Duzenle — {p['question'][:50]}...",
            p.get('suggested_answer', ''),
            do_save, lambda w: w.destroy())

    def reject_pending(self):
        idx = self._get_selected_pending_idx()
        if idx is None:
            return
        pending_questions[idx]['status'] = 'rejected'
        save_pending()
        self.refresh_pending_list()
        self._set_status("Soru reddedildi")

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
    # TAB 3 — Kargo & Iade
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

        # Paned window — ust: siparisler, alt: iadeler
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
    # TAB 4 — Soru Gecmisi
    # ══════════════════════════════════════════
    def _build_log_tab(self):
        top = ttk.Frame(self.tab_log)
        top.pack(fill='x', padx=8, pady=6)

        ttk.Label(top, text="Filtre:").pack(side='left')
        self.log_filter_var = tk.StringVar(value='Tumu')
        ttk.Combobox(
            top, textvariable=self.log_filter_var,
            values=[
                'Tumu', 'keyword', 'fuzzy', 'gemini',
                'manual_approved', 'manual_edited',
                'out_of_service', 'pending', 'no_match',
            ],
            width=16, state='readonly'
        ).pack(side='left', padx=4)
        ttk.Button(top, text="Filtrele",
                   command=self.refresh_log_list).pack(
            side='left', padx=4)
        ttk.Button(
            top, text="Yenile",
            command=lambda: [load_question_log(),
                             self.refresh_log_list()]
        ).pack(side='left', padx=4)
        ttk.Button(top, text="CSV Disa Aktar",
                   command=self.export_log_csv).pack(side='right')

        # Treeview
        tree_frame = ttk.Frame(self.tab_log)
        tree_frame.pack(fill='both', expand=True, padx=8, pady=(0, 8))

        log_cols = ('zaman', 'soru', 'yanit', 'yontem')
        self.log_tree = ttk.Treeview(
            tree_frame, columns=log_cols,
            show='headings', height=25)
        self.log_tree.heading('zaman', text='Zaman')
        self.log_tree.heading('soru', text='Soru')
        self.log_tree.heading('yanit', text='Yanit')
        self.log_tree.heading('yontem', text='Yontem')

        self.log_tree.column('zaman', width=130, minwidth=100)
        self.log_tree.column('soru', width=350, minwidth=200)
        self.log_tree.column('yanit', width=450, minwidth=200)
        self.log_tree.column('yontem', width=120, minwidth=80)

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

        for entry in reversed(question_log):
            m = entry.get('method', '')
            if filt != 'Tumu' and m != filt:
                continue
            ts = entry.get('timestamp', '')[:16].replace('T', ' ')
            q = entry.get('question', '')[:80]
            a = entry.get('answer', '')[:80]
            self.log_tree.insert(
                '', 'end',
                values=(ts, q, a, self.METHOD_LABELS.get(m, m)))

    def _show_log_detail(self, event):
        sel = self.log_tree.selection()
        if not sel:
            return
        vals = self.log_tree.item(sel[0])['values']
        detail = (
            f"Zaman: {vals[0]}\n\n"
            f"Soru: {vals[1]}\n\n"
            f"Yanit: {vals[2]}\n\n"
            f"Yontem: {vals[3]}"
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
                    'Yanit', 'Yontem', 'Urun'])
                for entry in question_log:
                    writer.writerow([
                        entry.get('timestamp', ''),
                        entry.get('question_id', ''),
                        entry.get('question', ''),
                        entry.get('answer', ''),
                        entry.get('method', ''),
                        entry.get('product_info', ''),
                    ])
            self._set_status(f"Log disa aktarildi: {filepath}")
        except Exception as e:
            messagebox.showerror(
                "Hata", f"Disa aktarma hatasi: {e}")

    # ══════════════════════════════════════════
    # TAB — Yorumlar (Musteri Degerlendirmeleri)
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
    # TAB — AI Ayarlari
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

            # 3. Ilgili Yorumlar
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

            # 4. Gemini
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
    # TAB 6 — Istatistikler
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
        for w in self.stats_cards_frame.winfo_children():
            w.destroy()
        for w in self.stats_detail_frame.winfo_children():
            w.destroy()

        total = len(question_log)
        method_counts = Counter(
            e.get('method', '') for e in question_log)

        today_str = datetime.now().date().isoformat()
        today_count = sum(
            1 for e in question_log
            if e.get('timestamp', '').startswith(today_str))

        week_start = (
            datetime.now()
            - timedelta(days=datetime.now().weekday())
        ).date().isoformat()
        week_count = sum(
            1 for e in question_log
            if e.get('timestamp', '') >= week_start)

        active_pending = sum(
            1 for p in pending_questions
            if p.get('status') in ('pending', 'no_match'))

        # Kartlar
        cards = [
            ("Toplam Soru", str(total), '#2196F3'),
            ("Bugun", str(today_count), '#4CAF50'),
            ("Bu Hafta", str(week_count), '#FF9800'),
            ("Oto Yanit Kurali",
             str(len(automated_responses)), '#9C27B0'),
            ("Bekleyen", str(active_pending), '#f44336'),
        ]

        for i, (label, value, color) in enumerate(cards):
            card = ttk.Frame(
                self.stats_cards_frame,
                relief='solid', borderwidth=1)
            card.grid(row=0, column=i, padx=6, pady=4,
                      sticky='nsew')
            self.stats_cards_frame.columnconfigure(i, weight=1)

            tk.Label(card, text=value,
                     font=('Helvetica', 28, 'bold'),
                     fg=color).pack(pady=(10, 0))
            tk.Label(card, text=label,
                     font=('Helvetica', 10),
                     fg='#666').pack(pady=(0, 10))

        # Yontem dagilimi
        ttk.Label(
            self.stats_detail_frame,
            text="Yanit Yontemi Dagilimi",
            style='Header.TLabel').pack(anchor='w', pady=(0, 8))

        colors = {
            'keyword': '#4CAF50',
            'fuzzy': '#8BC34A',
            'gemini': '#2196F3',
            'manual_approved': '#00BCD4',
            'manual_edited': '#009688',
            'out_of_service': '#FF9800',
            'pending': '#FFC107',
            'no_match': '#f44336',
        }

        bar_frame = ttk.Frame(self.stats_detail_frame)
        bar_frame.pack(fill='x', padx=8)

        for method, count in sorted(
                method_counts.items(), key=lambda x: -x[1]):
            row = ttk.Frame(bar_frame)
            row.pack(fill='x', pady=2)

            label = self.METHOD_LABELS.get(method, method)
            pct = (count / total * 100) if total > 0 else 0

            ttk.Label(row, text=label, width=22).pack(side='left')

            bar_container = tk.Frame(
                row, bg='#e0e0e0', height=20)
            bar_container.pack(
                side='left', fill='x', expand=True, padx=4)
            bar_container.pack_propagate(False)

            if pct > 0:
                bar = tk.Frame(
                    bar_container,
                    bg=colors.get(method, '#999'),
                    height=20)
                bar.place(
                    relwidth=max(pct / 100, 0.01), relheight=1)

            ttk.Label(
                row, text=f"{count} ({pct:.0f}%)",
                width=12).pack(side='right')

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
        except Exception:
            pass


# ════════════════════════════════════════════════════════
# ANA GIRIS NOKTASI
# ════════════════════════════════════════════════════════
if __name__ == '__main__':
    load_responses()
    load_question_log()
    load_pending()
    load_gemini_config()
    load_reviews()

    logger.info("Kozmopol v2.0 baslatiliyor...")
    print("=" * 55)
    print("  Kozmopol — Trendyol Akilli Musteri Hizmetleri v2.0")
    print("=" * 55)
    print(f"  Otomatik yanit kurali : {len(automated_responses)}")
    print(f"  Soru logu             : {len(question_log)} kayit")
    print(f"  Bekleyen soru         : {len(pending_questions)}")
    total_revs = sum(len(v) for v in product_reviews.values())
    print(f"  Yorum cache           : {total_revs} yorum, "
          f"{len(product_reviews)} urun")
    print(f"  Gemini AI             : "
          f"{'AKTIF' if not MISSING_GEMINI else 'DEVRE DISI'}")
    print(f"  Trendyol API          : "
          f"{'AKTIF' if not MISSING_CREDS else 'DEVRE DISI'}")
    print("=" * 55)

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
