"""Kargo takip servisi - Yurtiçi, Aras, MNG entegrasyonu"""
import re


class CargoService:
    """Kargo firmaları ile takip API entegrasyonu"""

    # Kargo firması takip URL'leri (müşteri linki)
    TRACKING_URLS = {
        "yurtici": "https://www.yurticikargo.com/tr/online-servisler/gonderi-sorgula?code={tracking_no}",
        "aras": "https://www.araskargo.com.tr/tr/kargo-takip/{tracking_no}",
        "mng": "https://www.mngkargo.com.tr/gonderi-takip/{tracking_no}",
        "ptt": "https://gonderitakip.ptt.gov.tr/Track/Verify?q={tracking_no}",
        "ups": "https://www.ups.com/track?tracknum={tracking_no}",
        "hepsijet": "https://www.hepsijet.com/takip/{tracking_no}",
        "sendeo": "https://www.sendeo.com.tr/gonderi-takip/{tracking_no}",
        "kolaygelsin": "https://www.kolaygelsin.com/gonderi-takip?trackingNumber={tracking_no}",
        "kargoist": "https://kargoist.com/tracking/{tracking_no}",
        "trendyolexpress": "https://www.trendyol.com/siparis/takip/{tracking_no}",
        "surat": "https://www.suratkargo.com.tr/KargoTakip/?kargotakipno={tracking_no}",
    }

    COMPANY_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
        ("ups", re.compile(r"^1Z[0-9A-Z]{16}$", re.I)),
        ("mng", re.compile(r"^MNG[0-9A-Z]{6,}$", re.I)),
        ("aras", re.compile(r"^(AR|ARAS)[0-9A-Z]{6,}$", re.I)),
        ("hepsijet", re.compile(r"^(HJ|HEP|HJT)[0-9A-Z]{6,}$", re.I)),
        ("sendeo", re.compile(r"^(SND|SEN)[0-9A-Z]{6,}$", re.I)),
        ("kolaygelsin", re.compile(r"^(KG|KLG)[0-9A-Z]{6,}$", re.I)),
        ("kargoist", re.compile(r"^(KRG|KIST)[0-9A-Z]{6,}$", re.I)),
        ("trendyolexpress", re.compile(r"^(TRE|TYX|TEX)[0-9A-Z]{6,}$", re.I)),
        ("ptt", re.compile(r"^[A-Z]{2}[0-9]{9}TR$", re.I)),
        ("yurtici", re.compile(r"^(YK|YT)[0-9A-Z]{8,}$", re.I)),
    ]

    async def track(self, tracking_no: str, company: str = "") -> dict:
        """
        Kargo takip bilgisi getir.
        company boşsa, numara formatına göre tahmin eder.
        Returns: {"status": str, "details": str, "tracking_url": str}
        """
        tracking_no = tracking_no.strip().upper()
        company = company.lower() if company else self._guess_company(tracking_no)

        tracking_url = self.TRACKING_URLS.get(
            company,
            "https://www.yurticikargo.com/tr/online-servisler/gonderi-sorgula",
        ).format(tracking_no=tracking_no)

        # Gerçek API entegrasyonu için burada ilgili API çağrıları yapılır
        # Şimdilik bilinen URL ile müşteri yönlendirmesi
        return {
            "status": "shipped",
            "details": f"Kargo takip numaranız: {tracking_no}. Detaylı bilgi için aşağıdaki linki kullanabilirsiniz.",
            "tracking_url": tracking_url,
            "company": company,
        }

    def _guess_company(self, tracking_no: str) -> str:
        """Takip numarası formatına göre kargo firması tahmini"""
        if not tracking_no:
            return "yurtici"
        cleaned = re.sub(r"[^A-Z0-9]", "", tracking_no.upper())
        if not cleaned:
            return "yurtici"

        for company, pattern in self.COMPANY_PATTERNS:
            if pattern.match(cleaned):
                return company

        # Sık görülen fallback kuralları
        if cleaned.isdigit():
            if len(cleaned) in (12, 13):
                return "yurtici"
            if len(cleaned) >= 10:
                return "aras"
        return "yurtici"
