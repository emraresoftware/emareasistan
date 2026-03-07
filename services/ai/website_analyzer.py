"""
Genel web sitesi analiz servisi - herhangi bir e-ticaret sitesinden
ürün kataloğu, firma bilgisi ve sektör tespiti
"""
from __future__ import annotations
import re
import json
import asyncio
from pathlib import Path
from typing import Optional
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup


def _normalize_url(url: str) -> str:
    """URL'yi temizle ve base URL'ye çevir"""
    url = url.strip().rstrip("/")
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    parsed = urlparse(url)
    return f"{parsed.scheme}://{parsed.netloc}"


def _normalize_price(price_str: str) -> float:
    """5.999,00 TL veya 5999 TL -> 5999.0"""
    numbers = re.sub(r"[^\d,.]", "", str(price_str))
    numbers = numbers.replace(".", "").replace(",", ".")
    try:
        return float(numbers)
    except ValueError:
        return 0.0


def _slug_from_name(name: str) -> str:
    """Firma adından slug oluştur"""
    t = name.lower().strip()
    t = re.sub(r"[^a-z0-9\s-]", "", t)
    t = re.sub(r"\s+", "-", t)
    return t[:50] if t else "site"


class WebsiteAnalyzer:
    """Herhangi bir web sitesini analiz et - ürünler, firma adı, sektör"""

    def __init__(self, base_url: str, delay: float = 0.8):
        self.base_url = _normalize_url(base_url)
        self.delay = delay
        self.headers = {
            "User-Agent": "Mozilla/5.0 (compatible; AsistanBot/1.0; +https://asistan.hosting)",
            "Accept": "text/html,application/xhtml+xml",
            "Accept-Language": "tr-TR,tr;q=0.9,en;q=0.8",
        }
        self._parsed = urlparse(self.base_url)
        self._domain = self._parsed.netloc.replace("www.", "")

    async def _fetch(self, url: str) -> str:
        async with httpx.AsyncClient(
            follow_redirects=True,
            timeout=20.0,
            headers=self.headers,
        ) as client:
            response = await client.get(url)
            response.raise_for_status()
            return response.text

    def _extract_site_name(self, soup: BeautifulSoup) -> str:
        """Sayfadan firma/site adı çıkar"""
        # title
        title = soup.find("title")
        if title:
            t = title.get_text(strip=True)
            if t and len(t) < 80:
                # "Firma Adı | Ürün Açıklaması" -> Firma Adı
                return t.split("|")[0].split("-")[0].strip() or self._domain
        # og:site_name
        og = soup.find("meta", property="og:site_name")
        if og and og.get("content"):
            return og["content"].strip()
        # h1
        h1 = soup.find("h1")
        if h1:
            return h1.get_text(strip=True)[:50]
        return self._domain.split(".")[0].replace("-", " ").title()

    def _detect_sector(self, soup: BeautifulSoup, products: list) -> str:
        """İçerikten sektör tahmin et"""
        text = soup.get_text().lower()
        product_names = " ".join(p.get("name", "").lower() for p in products[:20])
        combined = text + " " + product_names

        # Telekom - önce kontrol (güven, ev gibi kelimeler emlak ile karışmasın)
        if any(k in combined for k in ["telekom", "santral", "voip", "fiber", "metro ethernet", "sd-wan", "ip telefon", "veri merkezi", "bulut bağlantı"]):
            return "telekom"
        if any(k in combined for k in ["koltuk", "paspas", "döşeme", "araç", "oto", "jant", "far"]):
            return "otomobil"
        if any(k in combined for k in ["mobilya", "masa", "sandalye", "kanepe"]):
            return "mobilya"
        if any(k in combined for k in ["giyim", "tekstil", "kumaş", "perde", "havlu"]):
            return "tekstil"
        if any(k in combined for k in ["emlak", "daire", "satılık", "kiralık", "konut", "ev ilan"]):
            return "emlak"
        if any(k in combined for k in ["elektronik", "telefon", "bilgisayar"]):
            return "elektronik"
        if any(k in combined for k in ["restoran", "gıda", "yemek", "kahve", "cafe", "lokanta", "market"]):
            return "gida"
        if any(k in combined for k in ["eczane", "ilaç", "sağlık", "hastane", "tıbbi"]):
            return "saglik"
        if any(k in combined for k in ["kozmetik", "makyaj", "cilt bakım", "parfüm", "güzellik"]):
            return "kozmetik"
        if any(k in combined for k in ["spor", "fitness", "gym", "antrenman", "protein"]):
            return "spor"
        if any(k in combined for k in ["otel", "turizm", "tatil", "rezervasyon", "konaklama"]):
            return "turizm"
        if any(k in combined for k in ["inşaat", "yapı", "beton", "demir", "çimento"]):
            return "insaat"
        if any(k in combined for k in ["tarım", "ziraat", "tohum", "gübre", "traktör"]):
            return "tarim"
        if any(k in combined for k in ["eğitim", "kurs", "öğretim", "akademi"]):
            return "egitim"
        if any(k in combined for k in ["perakende", "mağaza", "retail"]):
            return "perakende"
        if any(k in combined for k in ["oto tamir", "kaporta", "lastik", "akü", "motor yağı"]):
            return "otomotiv"
        if any(k in combined for k in ["kuaför", "berber", "saç", "saç kesimi"]):
            return "kuaför"
        if any(k in combined for k in ["evcil hayvan", "pet", "köpek maması", "kedi"]):
            return "evcil"
        if any(k in combined for k in ["ofis", "kırtasiye", "toner", "kağıt"]):
            return "ofis"
        if any(k in combined for k in ["kitap", "yayın", "yayınevi"]):
            return "kitap"
        if any(k in combined for k in ["sinema", "tiyatro", "konser", "etkinlik"]):
            return "sinema"
        if any(k in combined for k in ["sigorta", "polis"]):
            return "sigorta"
        if any(k in combined for k in ["finans", "banka", "kredi", "yatırım"]):
            return "finans"
        if any(k in combined for k in ["hukuk", "avukat", "dava"]):
            return "hukuk"
        if any(k in combined for k in ["lojistik", "kargo", "nakliye"]):
            return "lojistik"
        if any(k in combined for k in ["maden", "madencilik"]):
            return "madencilik"
        if any(k in combined for k in ["enerji", "elektrik", "doğalgaz"]):
            return "enerji"
        if any(k in combined for k in ["yazılım", "bilişim", "software", "web sitesi"]):
            return "bilisim"
        return "genel"

    def _parse_products_generic(self, soup: BeautifulSoup) -> list[dict]:
        """Genel e-ticaret pattern'leri ile ürün çıkar"""
        products = []
        seen = set()
        price_re = re.compile(r"(\d{1,3}(?:\.\d{3})*[,\.]\d{2}|\d+)\s*(?:TL|₺|tl)?")

        # Yaygın ürün container sınıfları
        product_selectors = [
            "div.product",
            "div.products",
            "article.product",
            "li.product",
            "div[class*='product-item']",
            "div[class*='product-card']",
            "div[class*='urun']",
            "div[class*='ürün']",
        ]

        for sel in product_selectors:
            for card in soup.select(sel):
                p = self._extract_from_card(card, price_re)
                if p and p.get("name") and p.get("external_url") not in seen:
                    products.append(p)
                    seen.add(p.get("external_url", ""))
            if products:
                break

        if not products:
            # Fallback: link + fiyat pattern
            products = self._parse_from_links(soup, price_re)

        return products[:100]  # Max 100 ürün

    def _extract_from_card(self, card, price_re) -> Optional[dict]:
        """Ürün kartından bilgi çıkar"""
        link = card.find("a", href=True)
        if not link:
            return None

        href = link.get("href", "")
        if not href or href.startswith("#") or "javascript" in href:
            return None
        if any(x in href.lower() for x in ["giris", "uye", "sepet", "iletisim", "hakkimizda"]):
            return None

        full_url = urljoin(self.base_url, href)
        if self._domain not in full_url and not href.startswith("/"):
            return None

        name = ""
        img = link.find("img") or card.find("img")
        if img:
            name = img.get("alt") or img.get("title") or ""
        if not name:
            name = link.get("title") or link.get_text(strip=True)
        if not name or len(name) < 3 or len(name) > 200:
            return None

        price = 0.0
        text = card.get_text()
        m = price_re.search(text)
        if m:
            price = _normalize_price(m.group(0))

        image_url = ""
        if img:
            src = img.get("src") or img.get("data-src")
            if src and "logo" not in (src or "").lower():
                image_url = urljoin(self.base_url, src) if src.startswith("/") else src

        slug = href.strip("/").split("/")[-1] or name[:30].replace(" ", "-")

        return {
            "name": name,
            "slug": slug,
            "description": f"{name}",
            "price": price,
            "category": "genel",
            "image_url": image_url,
            "external_url": full_url,
            "vehicle_compatibility": [],
        }

    def _parse_from_links(self, soup: BeautifulSoup, price_re) -> list[dict]:
        """Linklerden ürün çıkar (fallback)"""
        products = []
        seen = set()

        for a in soup.find_all("a", href=True):
            href = a.get("href", "")
            if not href or href.startswith("#") or "javascript" in href:
                continue
            if any(x in href.lower() for x in ["giris", "uye", "sepet", "iletisim", "hakkimizda", "kategori"]):
                continue

            full_url = urljoin(self.base_url, href)
            if full_url in seen:
                continue
            if self._domain not in full_url and not href.startswith("/"):
                continue

            name = a.get_text(strip=True)
            if len(name) < 5 or len(name) > 150:
                continue
            if name.lower() in ["incele", "detay", "sepete ekle", "hemen al", "tıkla"]:
                continue

            container = a.find_parent(["div", "li", "article"])
            price = 0.0
            if container:
                m = price_re.search(container.get_text())
                if m:
                    price = _normalize_price(m.group(0))

            img = a.find("img")
            image_url = ""
            if img:
                src = img.get("src") or img.get("data-src")
                if src and "logo" not in (src or "").lower():
                    image_url = urljoin(self.base_url, src) if src.startswith("/") else src

            slug = href.strip("/").split("/")[-1] or name[:30].replace(" ", "-")
            products.append({
                "name": name,
                "slug": slug,
                "description": f"{name}",
                "price": price,
                "category": "genel",
                "image_url": image_url,
                "external_url": full_url,
                "vehicle_compatibility": [],
            })
            seen.add(full_url)

        return products[:80]

    async def analyze(self) -> dict:
        """
        Siteyi analiz et.
        Returns: {
            "name": str,
            "slug": str,
            "sector": str,
            "products": list[dict],
            "success": bool,
            "error": str | None,
        }
        """
        try:
            html = await self._fetch(self.base_url)
            soup = BeautifulSoup(html, "html.parser")

            name = self._extract_site_name(soup)
            products = self._parse_products_generic(soup)
            sector = self._detect_sector(soup, products)
            slug = _slug_from_name(name)

            # Benzersiz slug için domain ekle
            if len(slug) < 5:
                slug = self._domain.split(".")[0].replace("-", "_")

            await asyncio.sleep(self.delay)

            return {
                "name": name,
                "slug": slug,
                "sector": sector,
                "products": products,
                "success": True,
                "error": None,
            }
        except Exception as e:
            return {
                "name": self._domain,
                "slug": _slug_from_name(self._domain),
                "sector": "genel",
                "products": [],
                "success": False,
                "error": str(e),
            }
