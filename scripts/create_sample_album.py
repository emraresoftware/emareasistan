#!/usr/bin/env python3
"""Örnek albüm oluştur - indirilen resimlerle"""
import asyncio
import json
import sys
from pathlib import Path

# Proje kökünü path'e ekle
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from models.database import AsyncSessionLocal, init_db
from models import ImageAlbum


# WhatsApp için erişilebilir olması gereken URL'ler (Unsplash - her zaman çalışır)
SAMPLE_IMAGE_URLS = [
    "https://images.unsplash.com/photo-1494976388531-d1058494cdd8?w=600",
    "https://images.unsplash.com/photo-1503376780353-7e6692767b70?w=600",
    "https://images.unsplash.com/photo-1553440569-bcc63803a83d?w=600",
    "https://images.unsplash.com/photo-1580273916550-e323be2ae537?w=600",
]


async def main():
    await init_db()
    # Unsplash URL'leri WhatsApp'tan erişilebilir. Local uploads deploy edilmişse base_url kullanılabilir.
    urls = SAMPLE_IMAGE_URLS

    async with AsyncSessionLocal() as db:
        album = ImageAlbum(
            name="Örnek Araç Galerisi",
            image_urls=json.dumps(urls, ensure_ascii=False),
            vehicle_models="",
            custom_message="Ürün kataloğumuzdan örnekler. Detaylar için yazabilirsiniz.",
            is_active=True,
            priority=10,
        )
        db.add(album)
        await db.commit()
        await db.refresh(album)
        print(f"Albüm oluşturuldu: {album.name} (id={album.id}, {len(urls)} resim)")
        print("(WhatsApp için Unsplash URL'leri - her zaman erişilebilir)")


if __name__ == "__main__":
    asyncio.run(main())
