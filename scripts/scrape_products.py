#!/usr/bin/env python3
"""
Ürün scraping scripti (Meridyen Oto tenant örneği)
Kullanım: python scripts/scrape_products.py
         python scripts/scrape_products.py --details  # Ürün detay sayfalarından resim/açıklama çeker
"""
import asyncio
import argparse
import sys
from pathlib import Path

# Proje root'unu path'e ekle
sys.path.insert(0, str(Path(__file__).parent.parent))

from scraper import MeridyenScraper


async def main():
    parser = argparse.ArgumentParser(description="Ürün verisi çek (scraper)")
    parser.add_argument(
        "--details",
        action="store_true",
        help="Ürün detay sayfalarından açıklama ve resim çek (yavaş, ilk 20 ürün)",
    )
    parser.add_argument(
        "--output",
        "-o",
        default=None,
        help="Çıktı JSON dosya yolu (varsayılan: data/products_scraped.json)",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=1.5,
        help="İstekler arası bekleme (saniye)",
    )
    args = parser.parse_args()

    output = Path(args.output) if args.output else Path(__file__).parent.parent / "data" / "products_scraped.json"

    scraper = MeridyenScraper(delay=args.delay)
    print("Scraping başlıyor...")
    products = await scraper.run(fetch_details=args.details, output_path=output)
    print(f"Toplam {len(products)} ürün çekildi -> {output}")
    return len(products)


if __name__ == "__main__":
    asyncio.run(main())
