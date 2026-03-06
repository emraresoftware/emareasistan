"""
api.gemini — Google Gemini AI Entegrasyonu
============================================
"""

from config import MISSING_GEMINI, GEMINI_API_KEY, GEMINI_AVAILABLE, logger
from core.data import (
    automated_responses, gemini_config, product_reviews,
    check_blacklist,
)
from api.trendyol import find_relevant_reviews, format_reviews_for_prompt


def generate_gemini_response(question_text: str, product_info: str = None):
    """Gemini API ile akilli yanit uret. -> (yanit, guven) veya (None, 0)."""
    if MISSING_GEMINI or not gemini_config.get('enabled', False):
        return None, 0.0

    try:
        import google.generativeai as genai

        genai.configure(api_key=GEMINI_API_KEY)
        model = genai.GenerativeModel(
            gemini_config.get('model', 'gemini-2.0-flash'))

        # Magaza tarzini ornek yanitlardan cikar
        examples = ""
        sample_items = list(automated_responses.items())[:5]
        if sample_items:
            examples = "\n\nOrnek Yanitlar (magazanin uslubu):\n"
            for keys, resp in sample_items:
                examples += f"- Anahtar: {', '.join(keys)} -> {resp[:120]}\n"

        # Ilgili musteri yorumlarini bul
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
                f"Gemini yanitinda kara liste kelimeleri: {blacklisted}")
            answer = f"[KARA_LISTE_UYARI: {', '.join(blacklisted)}] {answer}"
            confidence = min(confidence, 0.40)

        logger.info(f"Gemini yanit (guven: {confidence:.0%}): {answer[:80]}...")
        return answer, confidence

    except Exception as e:
        logger.error(f"Gemini API hatasi: {e}")
        return None, 0.0
