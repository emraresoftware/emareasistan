"""
Sanitizer - Mesaj temizleme ve normalizasyon.
Yazım hataları düzeltme, trim, lowercase.
"""
from typing import Optional


class MessageSanitizer:
    """Mesajı AI ve niyet tespiti için hazırla"""

    TYPOS = {
        "rsm": "resim", "res": "resim", "resime": "resim", "resimler": "resim",
        "resimleri": "resim", "resimlerini": "resim", "resimlerr": "resim",
        "goster": "göster", "gösterir": "göster", "göstermi": "göster",
        "gostermi": "göster", "gösterirmisin": "göster", "gösterir misin": "göster",
        "koltuğ": "koltuk", "koltuğu": "koltuk", "koltuklar": "koltuk",
        "koltukları": "koltuk", "koltu": "koltuk",
        "paspaş": "paspas", "paspaşlar": "paspas", "paspaşları": "paspas",
        "fiyatlar": "fiyat", "fiyatları": "fiyat",
        "bakayim": "bakayım", "bakaym": "bakayım",
        "fotolar": "foto", "fotoları": "foto", "fotoraft": "foto",
        "fotoğraf": "foto", "fotograf": "foto", "fotoraflar": "foto",
        "araba": "araç", "arabam": "araç", "arabalar": "araç",
        "döşem": "döşeme", "döseme": "döşeme", "doseme": "döşeme",
    }

    def sanitize(self, text: Optional[str]) -> str:
        """
        Mesajı temizle ve normalleştir.
        Returns: lowercase, trim, typo düzeltmeli metin
        """
        if not text or not isinstance(text, str):
            return ""
        text = text.strip().lower()
        if not text:
            return ""
        words = text.split()
        for i, w in enumerate(words):
            for wrong, correct in self.TYPOS.items():
                if wrong in w or w == wrong:
                    words[i] = w.replace(wrong, correct)
        return " ".join(words)
