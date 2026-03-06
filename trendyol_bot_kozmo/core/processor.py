"""
core.processor — Soru Isleme Zinciri & Arka Plan Zamanlayici
=============================================================
process_question(), check_and_answer_questions(), is_out_of_service_hours().
"""

import time
import threading
from datetime import datetime

from config import (
    MISSING_CREDS, MISSING_GEMINI, QUESTION_CATEGORIES,
    OUT_OF_SERVICE_MSG, logger,
)
from core.data import (
    pending_questions, save_pending, add_log_entry,
    categorize_question, send_notification,
    app_settings, gemini_config,
)
from core.matcher import exact_keyword_match, fuzzy_keyword_match
from api.trendyol import get_customer_questions, answer_question
from api.gemini import generate_gemini_response


# ════════════════════════════════════════════════════════
# ZAMANLAMA
# ════════════════════════════════════════════════════════

def is_out_of_service_hours() -> bool:
    """Mesai saatleri disinda mi?"""
    now = datetime.now()
    work_start = app_settings.get('work_hours_start', '10:00')
    work_end = app_settings.get('work_hours_end', '18:00')
    work_days = app_settings.get('work_days', [0, 1, 2, 3, 4])

    t = now.time()
    start_t = datetime.strptime(work_start, "%H:%M").time()
    end_t = datetime.strptime(work_end, "%H:%M").time()

    if now.weekday() not in work_days:
        return True
    if t < start_t or t >= end_t:
        return True
    return False


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
                send_notification(
                    "Kozmopol — Yeni Bekleyen Soru",
                    f"Kategori: {QUESTION_CATEGORIES.get(category, {}).get('label', category)}"
                    f" | {question_text[:60]}...")
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
# ARKA PLAN THREAD'I
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
                        # app referansını import cycle olmadan al
                        import ui.app as _app_mod
                        app_ref = getattr(_app_mod, '_app_instance', None)
                        if (is_out_of_service_hours()
                                and app_ref
                                and getattr(app_ref, 'out_of_office_var', None)
                                and app_ref.out_of_office_var.get()):
                            answer_question(qid, OUT_OF_SERVICE_MSG)
                            add_log_entry(qid, qtext, OUT_OF_SERVICE_MSG,
                                          'out_of_service', product_info)

                    answered_ids.add(qid)

                    # UI guncelle
                    import ui.app as _app_mod
                    app_ref = getattr(_app_mod, '_app_instance', None)
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


def start_background_thread():
    """Soru kontrol thread'ini baslat."""
    if not MISSING_CREDS:
        t = threading.Thread(
            target=check_and_answer_questions, daemon=True)
        t.start()
        logger.info("Soru kontrol thread'i baslatildi")
        return t
    else:
        print("[Bilgi] API kimlik bilgileri eksik — "
              "otomatik cevap thread'i baslatilmadi.")
        return None
