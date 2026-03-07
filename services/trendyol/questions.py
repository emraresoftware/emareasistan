"""
services/trendyol/questions.py — Trendyol Soru İşleme Zinciri
================================================================
Kozmopol'ün soru işleme mantığının web-tabanlı, multi-tenant versiyonu.
Anahtar kelime, bulanık eşleştirme, Gemini AI ve bekleyen soru kuyruğu.
"""
from __future__ import annotations

import re
import logging
from datetime import datetime
from difflib import SequenceMatcher
from typing import Any

from services.trendyol.api import answer_question

logger = logging.getLogger("trendyol.questions")


# ════════════════════════════════════════════════════════
# SORU KATEGORİLERİ
# ════════════════════════════════════════════════════════
QUESTION_CATEGORIES = {
    "kargo": {
        "label": "Kargo / Teslimat",
        "keywords": ["kargo", "teslimat", "gelir", "gelmedi", "nerede",
                      "gönderi", "takip", "süresi", "teslim", "ptt", "express"],
        "icon": "📦",
    },
    "iade": {
        "label": "İade / Para İade",
        "keywords": ["iade", "para iade", "geri gönder", "değişim", "iptal",
                      "ücret iade", "geri al", "değiştir"],
        "icon": "↩️",
    },
    "urun": {
        "label": "Ürün Bilgisi",
        "keywords": ["orijinal", "sahte", "içindekiler", "içerik", "nasıl kullanılır",
                      "etki", "sonuç", "fark", "renk", "boyut", "ml", "gram"],
        "icon": "🛍️",
    },
    "skt": {
        "label": "Son Kullanma Tarihi",
        "keywords": ["skt", "son kullanma", "tarih", "miat", "bozulma", "taze"],
        "icon": "📅",
    },
    "fiyat": {
        "label": "Fiyat / İndirim",
        "keywords": ["fiyat", "indirim", "kampanya", "kupon", "ucuz", "pahalı"],
        "icon": "💰",
    },
    "diger": {
        "label": "Diğer",
        "keywords": [],
        "icon": "❓",
    },
}


def categorize_question(text: str) -> str:
    """Soru metnini otomatik kategorize et."""
    qtext = text.lower()
    scores: dict[str, float] = {}
    for cat_code, cat_info in QUESTION_CATEGORIES.items():
        if cat_code == "diger":
            continue
        score = sum(1 + (0.5 if " " in kw else 0)
                    for kw in cat_info["keywords"] if kw in qtext)
        scores[cat_code] = score
    if not scores or max(scores.values()) == 0:
        return "diger"
    return max(scores, key=scores.get)


# ════════════════════════════════════════════════════════
# ANAHTAR KELİME EŞLEŞTİRME
# ════════════════════════════════════════════════════════

def _normalize_key(key_text: str) -> tuple[str, ...]:
    return tuple(w.strip().lower() for w in key_text.split(",") if w.strip())


def exact_keyword_match(question_text: str, auto_responses: dict) -> str | None:
    """Tam anahtar kelime eşleştirmesi. auto_responses: {keywords_csv: response}"""
    qtext = question_text.lower()
    for keys_csv, response in auto_responses.items():
        words = _normalize_key(keys_csv)
        if words and all(w in qtext for w in words):
            return response
    return None


def fuzzy_keyword_match(question_text: str, auto_responses: dict,
                         threshold: float = 0.65) -> tuple[str | None, float]:
    """Bulanık eşleştirme."""
    qtext = question_text.lower()
    q_words = set(re.findall(r"\w+", qtext))
    best_match = None
    best_score = 0.0
    for keys_csv, response in auto_responses.items():
        search_words = _normalize_key(keys_csv)
        if not search_words:
            continue
        matched = 0
        for sw in search_words:
            if sw in qtext:
                matched += 1
                continue
            for qw in q_words:
                if SequenceMatcher(None, sw, qw).ratio() > 0.80:
                    matched += 1
                    break
        score = matched / len(search_words)
        if score > best_score:
            best_score = score
            best_match = response
    if best_score >= threshold:
        return best_match, best_score
    return None, 0.0


# ════════════════════════════════════════════════════════
# KELİME KARA LİSTESİ
# ════════════════════════════════════════════════════════

DEFAULT_BLACKLIST = [
    "sahte", "fake", "zararlı", "tehlikeli", "kanser",
    "ölüm", "zehir", "dava", "şikayet", "dolandırıcı",
]


def check_blacklist(text: str, blacklist: list[str] | None = None) -> list[str]:
    """Metinde kara listedeki kelimeleri kontrol et."""
    bl = blacklist or DEFAULT_BLACKLIST
    text_lower = text.lower()
    return [w for w in bl if w.lower() in text_lower]


# ════════════════════════════════════════════════════════
# YORUM BAĞLAM EŞLEŞTİRME (Gemini prompt için)
# ════════════════════════════════════════════════════════

def find_relevant_reviews(question_text: str, reviews_by_product: dict,
                           product_name: str = "", max_reviews: int = 5) -> list:
    """Soruyla en ilgili yorumları bul. reviews_by_product: {product: [review,...]}"""
    qtext = question_text.lower()
    q_words = {w for w in re.findall(r"\w+", qtext) if len(w) > 2}
    scored = []
    for prod, reviews in reviews_by_product.items():
        pname_lower = prod.lower()
        bonus = 0.0
        if product_name:
            pn = product_name.lower()
            if pn in pname_lower or pname_lower in pn:
                bonus = 2.0
            else:
                bonus = len(set(pn.split()) & set(pname_lower.split())) * 0.3
        for rev in reviews:
            comment = (rev.get("comment") or "").lower()
            if not comment or len(comment) < 10:
                continue
            c_words = set(re.findall(r"\w+", comment))
            overlap = len(q_words & c_words)
            if overlap == 0 and bonus == 0:
                continue
            score = overlap + bonus + (0.3 if rev.get("rate", 0) >= 4 else -0.2 if rev.get("rate", 0) <= 2 else 0)
            scored.append((prod, rev, score))
    scored.sort(key=lambda x: -x[2])
    return scored[:max_reviews]


def format_reviews_for_prompt(relevant: list) -> str:
    if not relevant:
        return ""
    lines = ["\n\n=== MÜŞTERİ YORUMLARI (gerçek kullanıcı deneyimleri) ==="]
    for i, (prod, rev, _) in enumerate(relevant, 1):
        user = (rev.get("user") or "Anonim").strip()
        rate = rev.get("rate", 0)
        comment = rev.get("comment", "")[:300]
        lines.append(f"Yorum {i} | Ürün: {prod[:50]} | {user} | {'⭐'*rate}\n  \"{comment}\"")
    lines.append("Bu yorumları yanıtında kullan.")
    return "\n".join(lines)


# ════════════════════════════════════════════════════════
# GEMİNİ AI YANIT ÜRETİMİ
# ════════════════════════════════════════════════════════

async def generate_ai_response(question_text: str, product_info: str = "",
                                 trendyol_settings: dict | None = None,
                                 auto_responses: dict | None = None,
                                 reviews_by_product: dict | None = None) -> tuple[str | None, float]:
    """Gemini AI ile yanıt üret. -> (yanıt, güven) veya (None, 0)"""
    settings = trendyol_settings or {}
    if not settings.get("gemini_enabled", True):
        return None, 0.0

    try:
        import google.generativeai as genai
    except ImportError:
        logger.warning("google-generativeai kurulu değil")
        return None, 0.0

    # Gemini API anahtarı — tenant ayarlarından veya genel ayarlardan
    from config import get_settings
    api_key = settings.get("gemini_api_key") or get_settings().gemini_api_key
    if not api_key:
        return None, 0.0

    try:
        genai.configure(api_key=api_key)
        model_name = settings.get("gemini_model", "gemini-2.5-flash-lite")
        model = genai.GenerativeModel(model_name)

        # Mağaza tarz örnekleri
        examples = ""
        if auto_responses:
            sample = list(auto_responses.items())[:5]
            if sample:
                examples = "\n\nÖrnek Yanıtlar (mağaza üslubu):\n"
                for keys, resp in sample:
                    examples += f"- Anahtar: {keys} -> {resp[:120]}\n"

        # İlgili yorumlar
        review_ctx = ""
        if reviews_by_product:
            relevant = find_relevant_reviews(question_text, reviews_by_product, product_info)
            review_ctx = format_reviews_for_prompt(relevant)

        system_prompt = settings.get("system_prompt",
            "Sen bir Trendyol mağazasının müşteri hizmetleri asistanısın. "
            "Nazik ve profesyonel ol. Kısa ve öz yanıtlar ver. "
            "Emin olmadığın bilgileri VERME.\n"
            "Yanıtından emin değilsen [MANUAL_REVIEW] etiketi ekle.")

        prompt = (f"{system_prompt}{examples}{review_ctx}"
                  f"\n\nMüşteri Sorusu: {question_text}")
        if product_info:
            prompt += f"\nÜrün Bilgisi: {product_info}"
        prompt += "\n\nYanıtını ver:"

        temperature = settings.get("gemini_temperature", 0.3)
        max_tokens = settings.get("gemini_max_tokens", 500)

        response = model.generate_content(
            prompt,
            generation_config=genai.GenerationConfig(
                temperature=temperature,
                max_output_tokens=max_tokens,
            ),
        )
        answer = response.text.strip()
        needs_review = "[MANUAL_REVIEW]" in answer
        answer = answer.replace("[MANUAL_REVIEW]", "").strip()
        confidence = 0.50 if needs_review else 0.85

        # Kara liste
        blacklisted = check_blacklist(answer, settings.get("blacklist"))
        if blacklisted:
            logger.warning("Trendyol AI yanıtında kara liste: %s", blacklisted)
            confidence = min(confidence, 0.40)

        return answer, confidence

    except Exception as e:
        logger.error("Gemini AI hatası: %s", e)
        return None, 0.0


# ════════════════════════════════════════════════════════
# ANA SORU İŞLEME ZİNCİRİ
# ════════════════════════════════════════════════════════

async def process_question(tenant_id: int,
                            question_id: int, question_text: str,
                            product_info: str = "",
                            trendyol_settings: dict | None = None) -> dict:
    """
    İşleme sırası:
      1) Tam anahtar kelime eşleşmesi
      2) Bulanık eşleştirme
      3) Gemini AI
      4) Bekleyen sorulara ekle
    Döner: {answered, method, answer, confidence, category}
    """
    settings = trendyol_settings or {}
    auto_responses = settings.get("auto_responses", {})
    reviews = settings.get("reviews_cache", {})
    category = categorize_question(question_text)

    result = {
        "question_id": question_id,
        "question": question_text,
        "product_info": product_info,
        "category": category,
        "answered": False,
        "method": "no_match",
        "answer": "",
        "confidence": 0.0,
        "timestamp": datetime.now().isoformat(),
    }

    # 1. Exact keyword
    resp = exact_keyword_match(question_text, auto_responses)
    if resp:
        auto_send = settings.get("auto_send_keyword", True)
        if auto_send:
            ok, msg = await answer_question(tenant_id, question_id, resp)
            result.update(answered=ok, method="keyword", answer=resp, confidence=1.0)
        else:
            result.update(answered=False, method="keyword_pending", answer=resp, confidence=1.0)
        return result

    # 2. Fuzzy
    fuzzy_threshold = settings.get("fuzzy_threshold", 0.65)
    fuzzy_resp, fuzzy_score = fuzzy_keyword_match(question_text, auto_responses, fuzzy_threshold)
    if fuzzy_resp:
        auto_send = settings.get("auto_send_fuzzy", True)
        if auto_send:
            ok, msg = await answer_question(tenant_id, question_id, fuzzy_resp)
            result.update(answered=ok, method="fuzzy", answer=fuzzy_resp, confidence=fuzzy_score)
        else:
            result.update(answered=False, method="fuzzy_pending", answer=fuzzy_resp, confidence=fuzzy_score)
        return result

    # 3. Gemini AI
    ai_answer, ai_confidence = await generate_ai_response(
        question_text, product_info, settings, auto_responses, reviews)
    if ai_answer:
        conf_threshold = settings.get("confidence_threshold", 0.7)
        auto_send_ai = settings.get("auto_send_ai", False)
        if ai_confidence >= conf_threshold and auto_send_ai and "[KARA_LISTE" not in ai_answer:
            ok, msg = await answer_question(tenant_id, question_id, ai_answer)
            result.update(answered=ok, method="gemini", answer=ai_answer, confidence=ai_confidence)
        else:
            result.update(answered=False, method="pending", answer=ai_answer, confidence=ai_confidence)
        return result

    # 4. Eşleşme yok
    result.update(method="no_match", answer="", confidence=0.0)
    return result
