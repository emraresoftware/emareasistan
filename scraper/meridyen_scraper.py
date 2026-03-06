"""
Meridyen Oto (meridyenoto.com) ürün scraping modülü
Ana sayfa ve kategori sayfalarından ürün bilgilerini çeker
"""
import re
import json
import asyncio
from pathlib import Path
from typing import Optional
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup


BASE_URL = "https://meridyenoto.com"

# Kategori eşlemesi (sayfa başlıkları -> slug)
CATEGORY_MAP = {
    "elit serisi": "elit_serisi",
    "7d zemİn dÖŞeme": "7d_zemin_doseme",
    "7d zemin döşeme": "7d_zemin_doseme",
    "gt premıum serİsİ": "gt_premium_serisi",
    "gt premium serisi": "gt_premium_serisi",
    "araca Özel tasarim": "araca_ozel_tasarim",
    "araca özel tasarım": "araca_ozel_tasarim",
    "ekonom serİsİ": "ekonom_serisi",
    "ekonom serisi": "ekonom_serisi",
    "klas serİsİ": "klas_serisi",
    "klas serisi": "klas_serisi",
    "modern serİsİ": "modern_serisi",
    "modern serisi": "modern_serisi",
    "royal serİsİ": "royal_serisi",
    "royal serisi": "royal_serisi",
    "elİt tay tÜyÜ serİsİ": "elit_tay_tuyu_serisi",
    "elit tay tüyü serisi": "elit_tay_tuyu_serisi",
    "oto paspas ve bagaj": "oto_paspas_ve_bagaj",
}


def normalize_price(price_str: str) -> float:
    """5.999,00 TL -> 5999.0"""
    numbers = re.sub(r"[^\d,]", "", price_str)
    numbers = numbers.replace(".", "").replace(",", ".")
    try:
        return float(numbers)
    except ValueError:
        return 0.0


def normalize_category(text: str) -> str:
    """Sayfa başlığından kategori slug"""
    text_lower = text.strip().lower()
    return CATEGORY_MAP.get(text_lower, text_lower.replace(" ", "_").replace("ı", "i"))


class MeridyenScraper:
    """meridyenoto.com scraping"""

    def __init__(self, base_url: str = BASE_URL, delay: float = 1.0):
        self.base_url = base_url
        self.delay = delay
        self.headers = {
            "User-Agent": "Mozilla/5.0 (compatible; MeridyenAsistan/1.0; +https://meridyenoto.com)",
            "Accept": "text/html,application/xhtml+xml",
            "Accept-Language": "tr-TR,tr;q=0.9,en;q=0.8",
        }

    async def _fetch(self, url: str) -> str:
        """HTML içeriği getir"""
        async with httpx.AsyncClient(
            follow_redirects=True,
            timeout=30.0,
            headers=self.headers,
        ) as client:
            response = await client.get(url)
            response.raise_for_status()
            return response.text

    def _parse_main_page(self, html: str) -> list[dict]:
        """Ana sayfa HTML'inden ürünleri parse et"""
        soup = BeautifulSoup(html, "html.parser")
        products = []
        current_category = "genel"

        # Yöntem 1: Meridyen Oto product div yapısı (class içinde "product")
        cards = soup.find_all("div", class_=lambda c: c and "product" in str(c).lower())
        if cards:
            for card in cards:
                product = self._extract_product_from_card(card, current_category)
                if product and product.get("name") and product.get("price", 0) > 0:
                    products.append(product)

        if products:
            return products

        # Yöntem 2: Regex fallback
        products = self._parse_by_regex(html)
        if products:
            return products

        # Yöntem 3: Genel link + fiyat eşleştirme
        products = self._parse_products_from_links(soup)
        return products

    def _parse_by_regex(self, html: str) -> list[dict]:
        """Regex ile hızlı parse - meridyenoto.com link ve fiyat pattern'leri"""
        products = []
        current_category = "genel"

        # Kategori başlıkları
        cat_pattern = re.compile(
            r"<(?:h[2-4]|strong)[^>]*>([^<]*(?:ELİT|SERİSİ|PASPAS|PREMIUM|ÖZEL|EKONOM|KLAS|MODERN|ROYAL|TAY|BAGAJ|DÖŞEME)[^<]*)</(?:h[2-4]|strong)>",
            re.I,
        )

        # Ürün link + fiyat (yakın bloklarda)
        # Örnek: <a href="/elit-siyah-deri...">Elit Siyah Deri Araç Koltuk Kılıfı</a> ... 5.999,00 TL
        link_pattern = re.compile(
            r'<a[^>]+href="([^"]+)"[^>]*>([^<]*(?:Koltuk|Kılıf|Paspas|Döşeme|Bagaj|Dikim)[^<]*)</a>',
            re.I,
        )
        price_pattern = re.compile(r"(\d{1,3}(?:\.\d{3})*,\d{2})\s*TL")

        # HTML'i parçalara böl (ürün kartları genelde benzer div içinde)
        for block in re.split(r"<h[2-4][^>]*>", html):
            cat_match = re.search(r"([^<]+)", block[:200])
            if cat_match:
                cat_text = cat_match.group(1).strip()
                if any(x in cat_text.upper() for x in ["SERİSİ", "PASPAS", "ÖZEL", "DÖŞEME", "BAGAJ"]):
                    current_category = normalize_category(cat_text)

            for link_match in link_pattern.finditer(block):
                href, name = link_match.group(1), link_match.group(2).strip()
                if not name or len(name) < 10 or "İNCELE" in name or "HEMEN" in name:
                    continue
                if href.startswith("#") or "javascript" in href or "giris" in href or "uye" in href:
                    continue

                # Bu linke yakın fiyat ara
                start = max(0, link_match.start() - 200)
                end = min(len(block), link_match.end() + 300)
                nearby = block[start:end]
                price_match = price_pattern.search(nearby)
                price = normalize_price(price_match.group(0)) if price_match else 0

                url = urljoin(self.base_url, href) if href.startswith("/") else href
                slug = href.strip("/").split("/")[-1] if "/" in href else href

                # Resim - aynı blokta img
                img_match = re.search(r'<img[^>]+src="([^"]+)"', nearby)
                image_url = ""
                if img_match:
                    src = img_match.group(1)
                    if "logo" not in src.lower() and "icon" not in src.lower():
                        image_url = urljoin(self.base_url, src) if src.startswith("/") else src

                products.append({
                    "name": name,
                    "slug": slug,
                    "url": url,
                    "external_url": url,
                    "price": price,
                    "category": current_category,
                    "image_url": image_url,
                    "description": f"Meridyen Oto {name}",
                    "vehicle_compatibility": [],
                })

        return products

    def _extract_product_from_card(self, card, category: str) -> Optional[dict]:
        """Kart elemanından ürün bilgisi çıkar - Meridyen Oto yapısı"""
        link = card.find("a", href=True)
        if not link:
            return None

        href = link.get("href", "")
        if not href or "meridyenoto.com" not in href and not href.startswith("/"):
            return None
        if any(x in href.lower() for x in ["giris", "uye", "sepet", "kategori", "hakkimizda"]):
            return None

        # İsim: img alt > link title > link text
        name = ""
        img = link.find("img")
        if img:
            name = img.get("alt") or img.get("title") or ""
        if not name:
            name = link.get("title") or link.get_text(strip=True)
        if not name or "incele" in name.lower() or "hemen al" in name.lower():
            return None

        url = urljoin(self.base_url, href) if href.startswith("/") else href

        # Fiyat - kart içinde
        price = 0.0
        price_el = card.find(string=re.compile(r"[\d.]+\s*,\s*\d+\s*TL"))
        if price_el:
            price = normalize_price(price_el)
        else:
            for el in card.find_all(class_=re.compile(r"price|fiyat", re.I)):
                price = normalize_price(el.get_text())
                if price > 0:
                    break

        # Resim
        image_url = ""
        if img:
            src = img.get("src") or img.get("data-src")
            if src and "logo" not in src.lower() and "icon" not in src.lower():
                image_url = urljoin(self.base_url, src) if src.startswith("/") else src

        slug = href.strip("/").split("/")[-1] if "/" in href else href
        # Kategori tahmini (ürün adı/slug'dan - "genel" ise tahmin et)
        cat = self._guess_category_from_name(name, slug) if category == "genel" else category
        return {
            "name": name,
            "slug": slug,
            "url": url,
            "external_url": url,
            "price": price,
            "category": cat,
            "image_url": image_url,
            "description": f"Meridyen Oto {name}",
            "vehicle_compatibility": [],
        }

    def _guess_category_from_name(self, name: str, slug: str) -> str:
        """Ürün adı/slug'dan kategori tahmin et"""
        n = (name + " " + slug).lower()
        if "araca özel" in n or "araca-ozel" in n or "dikim" in n:
            return "araca_ozel_tasarim"
        if "elit" in n and "tay" in n:
            return "elit_tay_tuyu_serisi"
        if "elit" in n:
            return "elit_serisi"
        if "gt premium" in n or "gt-premium" in n:
            return "gt_premium_serisi"
        if "ekonom" in n:
            return "ekonom_serisi"
        if "klas" in n or "klass" in n:
            return "klas_serisi"
        if "modern" in n or "keten" in n:
            return "modern_serisi"
        if "royal" in n:
            return "royal_serisi"
        if "bagaj" in n and ("deri" in n or "döşeme" in n):
            return "oto_paspas_ve_bagaj"
        if "5d" in n or "7d" in n or "eva" in n or "havuzlu" in n:
            return "7d_zemin_doseme"
        if "paspas" in n or "3d" in n or "4d" in n or "bagaj" in n or "havuzu" in n:
            return "oto_paspas_ve_bagaj"
        if "yastık" in n or "kolçak" in n or "organizer" in n:
            return "oto_yastik_kolcak_organizer"
        return "genel"

    def _parse_products_from_links(self, soup: BeautifulSoup) -> list[dict]:
        """Link ve fiyat pattern'lerinden ürün çıkar (fallback)"""
        products = []
        seen_urls = set()
        current_category = "genel"

        # Tüm linkleri tara
        for a in soup.find_all("a", href=True):
            href = a.get("href", "")
            if not href or href.startswith("#") or "javascript" in href:
                continue
            if "meridyenoto.com" in href or (href.startswith("/") and len(href) > 2):
                full_url = urljoin(self.base_url, href)
                if full_url in seen_urls:
                    continue

            # Ürün sayfası gibi görünen linkler (kategori/ana sayfa değil)
            excluded = ["/uye-ol", "/giris", "/hakkimizda", "/iletisim", "/sepet", "/kategori"]
            if any(ex in href.lower() for ex in excluded):
                continue

            # Başlık (h2, h3) kontrolü - kategori değişimi
            parent = a.parent
            for _ in range(5):
                if not parent:
                    break
                heading = parent.find(["h2", "h3", "h4"])
                if heading and heading.get_text(strip=True):
                    cat_text = heading.get_text(strip=True)
                    if len(cat_text) < 50 and ("serisi" in cat_text.lower() or "paspas" in cat_text.lower() or "özel" in cat_text.lower()):
                        current_category = normalize_category(cat_text)
                parent = getattr(parent, "parent", None)

            name = a.get_text(strip=True)
            if len(name) < 5 or len(name) > 150:
                continue
            if name.lower() in ["incele", "hemen al", "sepete ekle", "detay"]:
                continue

            # Aynı satırda/ yakında fiyat ara
            price = 0.0
            container = a.find_parent(["div", "li", "article"])
            if container:
                price_match = re.search(r"(\d{1,3}(?:\.\d{3})*(?:,\d{2})?)\s*TL", container.get_text())
                if price_match:
                    price = normalize_price(price_match.group(0))

            slug = href.strip("/").split("/")[-1] if "/" in href else href
            full_url = urljoin(self.base_url, href) if href.startswith("/") else href

            # Resim
            img = a.find("img", src=True) if a else None
            image_url = ""
            if img:
                src = img.get("src") or img.get("data-src")
                if src and "logo" not in src.lower():
                    image_url = urljoin(self.base_url, src) if src.startswith("/") else src

            products.append({
                "name": name,
                "slug": slug,
                "url": full_url,
                "external_url": full_url,
                "price": price,
                "category": current_category,
                "image_url": image_url,
                "description": f"Meridyen Oto {name}",
            })
            seen_urls.add(full_url)

        return products

    async def scrape_main_page(self) -> list[dict]:
        """Ana sayfadan tüm ürünleri çek"""
        html = await self._fetch(self.base_url)
        products = self._parse_main_page(html)
        await asyncio.sleep(self.delay)
        return products

    async def scrape_product_detail(self, product_url: str) -> dict:
        """Ürün detay sayfasından açıklama ve resimleri çek"""
        try:
            html = await self._fetch(product_url)
            soup = BeautifulSoup(html, "html.parser")

            # Açıklama
            desc_el = soup.find(class_=re.compile(r"description|aciklama|product-detail", re.I))
            description = desc_el.get_text(strip=True)[:500] if desc_el else ""

            # Resimler
            images = []
            for img in soup.find_all("img", src=True):
                src = img.get("src") or img.get("data-src")
                if src and "product" in src.lower() or "uploads" in src.lower() or "urun" in src.lower():
                    if "logo" not in src.lower():
                        full_url = urljoin(self.base_url, src) if src.startswith("/") else src
                        images.append(full_url)

            await asyncio.sleep(self.delay)
            return {"description": description, "image_urls": images[:5]}
        except Exception:
            return {"description": "", "image_urls": []}

    async def run(
        self,
        fetch_details: bool = False,
        output_path: Optional[Path] = None,
    ) -> list[dict]:
        """
        Ana sayfayı scrape et, isteğe bağlı detay çek ve JSON'a kaydet.
        """
        products = await self.scrape_main_page()

        if fetch_details and products:
            for i, p in enumerate(products[:20]):  # İlk 20 ürün için detay (rate limit)
                detail = await self.scrape_product_detail(p.get("url", ""))
                p["description"] = detail.get("description") or p.get("description", "")
                if detail.get("image_urls") and not p.get("image_url"):
                    p["image_url"] = detail["image_urls"][0]
                p["image_urls"] = json.dumps(detail.get("image_urls", []))
                await asyncio.sleep(self.delay)

        if output_path:
            output_path = Path(output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(products, f, ensure_ascii=False, indent=2)

        return products


async def main():
    """CLI çalıştırma"""
    scraper = MeridyenScraper(delay=1.5)
    output = Path(__file__).parent.parent / "data" / "products_scraped.json"
    products = await scraper.run(fetch_details=False, output_path=output)
    print(f"Toplam {len(products)} ürün çekildi -> {output}")


if __name__ == "__main__":
    asyncio.run(main())
