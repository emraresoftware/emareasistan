"""
core.matcher — Eslestirme Motoru
==================================
Tam anahtar kelime, bulanik eslestirme ve hizli oneri fonksiyonlari.
"""

import re
from difflib import SequenceMatcher

from core.data import automated_responses, gemini_config, question_log


# ════════════════════════════════════════════════════════
# TAM ANAHTAR KELIME ESLESMESI
# ════════════════════════════════════════════════════════

def exact_keyword_match(question_text: str):
    """AND mantigi: tuple'daki tum kelimeler soru metninde gecmeli."""
    qtext = question_text.lower()
    for search_words, response_text in list(automated_responses.items()):
        if all(word in qtext for word in search_words):
            return response_text
    return None


# ════════════════════════════════════════════════════════
# BULANIK ESLESTIRME
# ════════════════════════════════════════════════════════

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
# HIZLI ONERI
# ════════════════════════════════════════════════════════

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
