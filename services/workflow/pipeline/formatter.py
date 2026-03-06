"""
ResponseFormatter - AI/Handler yanıtını çıktı formatına dönüştür.
Markdown temizleme, JSON blok ayırma, platforma özel format.
"""
from typing import Any


class ResponseFormatter:
    """Yanıt formatlama - platforma göre uyarlama yapılabilir"""

    def format(self, response: dict[str, Any], platform: str = "whatsapp") -> dict[str, Any]:
        """
        Ham yanıtı platform formatına uyarla.
        - create_order JSON bloğunu metinden ayır
        - Gereksiz markdown/format temizle
        """
        if not response:
            return {}
        result = dict(response)

        # Metin varsa JSON bloklarını temizle (AI bazen ```json ... ``` döndürür)
        text = result.get("text", "")
        if isinstance(text, str) and "```json" in text:
            # Sadece JSON öncesi metni al (kullanıcıya gösterilecek kısım)
            parts = text.split("```json")
            if parts:
                result["text"] = parts[0].strip()
        if isinstance(text, str) and "```" in result.get("text", ""):
            result["text"] = (result.get("text", "") or "").split("```")[0].strip()

        return result
