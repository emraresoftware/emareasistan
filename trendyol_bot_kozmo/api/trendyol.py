"""
api.trendyol — Trendyol Seller API Islemleri
===============================================
Q&A, siparis, iade ve yorum API cagrilari.
"""

import re
import time
import requests
from datetime import datetime, timedelta

from config import (
    MISSING_CREDS, SUPPLIER_ID,
    QNA_BASE, ORDER_BASE, HEADERS, AUTH,
    logger,
)
from core.data import product_reviews, save_reviews


# ════════════════════════════════════════════════════════
# ORTAK API YARDIMCISI
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


# ════════════════════════════════════════════════════════
# SORU-CEVAP
# ════════════════════════════════════════════════════════

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


# ════════════════════════════════════════════════════════
# SIPARISLER
# ════════════════════════════════════════════════════════

def get_orders(days=7):
    """Son N gunun siparislerini cek."""
    if MISSING_CREDS:
        return []
    end_ts = int(datetime.now().timestamp() * 1000)
    start_ts = int((datetime.now() - timedelta(days=days)).timestamp() * 1000)
    data = _api_get(
        f"{ORDER_BASE}/orders?startDate={start_ts}&endDate={end_ts}")
    return data.get('content', []) if data else []


# ════════════════════════════════════════════════════════
# IADELER
# ════════════════════════════════════════════════════════

def get_claims(days=30):
    """Son N gunun iade/taleplerini cek."""
    if MISSING_CREDS:
        return []
    end_ts = int(datetime.now().timestamp() * 1000)
    start_ts = int((datetime.now() - timedelta(days=days)).timestamp() * 1000)
    data = _api_get(
        f"{ORDER_BASE}/claims?startDate={start_ts}&endDate={end_ts}")
    return data.get('content', []) if data else []


# ════════════════════════════════════════════════════════
# URUN YORUMLARI
# ════════════════════════════════════════════════════════

def fetch_product_reviews(page=0, size=100, approved=True):
    """Trendyol API'den urun yorumlarini cek."""
    if MISSING_CREDS:
        return []
    status = 'APPROVED' if approved else ''
    url = (f"https://apigw.trendyol.com/integration/"
           f"product/sellers/{SUPPLIER_ID}/products/reviews"
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
        time.sleep(0.5)

    # Urun bazinda gruplama
    grouped: dict = {}
    for r in all_reviews:
        product_name = (r.get('productName') or 'Bilinmeyen').strip()
        review_entry = {
            'comment': (r.get('comment') or '').strip(),
            'rate': r.get('rate', 0),
            'date': '',
            'user': ((r.get('customerFirstName') or '') + ' '
                     + (r.get('customerLastName') or '').strip()),
            'product_id': r.get('productId', ''),
        }
        ts = r.get('lastModifiedDate') or r.get('createdDate')
        if ts:
            try:
                review_entry['date'] = datetime.fromtimestamp(
                    ts / 1000).strftime('%Y-%m-%d')
            except Exception:
                pass

        if review_entry['comment']:
            grouped.setdefault(product_name, []).append(review_entry)

    product_reviews.clear()
    product_reviews.update(grouped)
    save_reviews()
    total = sum(len(v) for v in grouped.values())
    logger.info(f"Toplam {total} yorum, {len(grouped)} urun icin kaydedildi")
    return total, len(grouped)


# ════════════════════════════════════════════════════════
# YORUM ANALIZ YARDIMCILARI
# ════════════════════════════════════════════════════════

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
