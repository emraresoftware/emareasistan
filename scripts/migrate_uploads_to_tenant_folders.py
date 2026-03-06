#!/usr/bin/env python3
"""
Eski uploads/albums ve uploads/videos dosyalarını tenant bazlı klasörlere taşır.

Önceki yapı: uploads/albums/xyz.jpg, uploads/videos/abc.mp4
Yeni yapı:   uploads/albums/{tenant_id}/xyz.jpg, uploads/videos/{tenant_id}/abc.mp4

DB'deki ImageAlbum.image_urls, ResponseRule.image_urls ve Video.video_url güncellenir.

Çalıştırma: Proje kökünden, venv aktifken:
  python scripts/migrate_uploads_to_tenant_folders.py
"""
import asyncio
import json
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from models.database import AsyncSessionLocal
from models import ImageAlbum, Video, ResponseRule
from sqlalchemy import select


def _extract_filename_from_url(url: str, prefix: str) -> str | None:
    """URL'den dosya adını çıkar. /uploads/albums/xyz.jpg veya .../albums/1/xyz.jpg -> xyz.jpg"""
    if not url or not isinstance(url, str):
        return None
    # Son path segmenti = dosya adı
    match = re.search(rf"/uploads/{re.escape(prefix)}/(?:[^/]+/)?([^/]+)$", url)
    return match.group(1) if match else None


def _is_old_format_url(url: str, prefix: str) -> bool:
    """Eski format mı? (tenant id yok: /uploads/albums/xyz.jpg)"""
    if not url or not isinstance(url, str):
        return False
    # /uploads/albums/1/xyz.jpg -> yeni format (2 segment: tenant_id + filename)
    # /uploads/albums/xyz.jpg -> eski format (1 segment: filename)
    match = re.search(rf"/uploads/{re.escape(prefix)}/(.+)$", url)
    if not match:
        return False
    rest = match.group(1)
    parts = rest.split("/")
    return len(parts) == 1  # Sadece dosya adı = eski format


def _new_url(base_url: str, tid: int, filename: str, prefix: str) -> str:
    """Yeni URL oluştur. base_url = http://host veya boş"""
    base = (base_url or "").rstrip("/")
    return f"{base}/uploads/{prefix}/{tid}/{filename}"


async def migrate_albums():
    """Albüm resimlerini tenant klasörlerine taşı"""
    uploads_base = ROOT / "uploads" / "albums"
    if not uploads_base.exists():
        return 0

    moved = 0
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(ImageAlbum))
        albums = result.scalars().all()

    for album in albums:
        tid = album.tenant_id or 1
        urls = []
        try:
            urls = json.loads(album.image_urls or "[]")
        except json.JSONDecodeError:
            continue
        if not isinstance(urls, list):
            continue

        updated = False
        new_urls = []
        for url in urls:
            if not _is_old_format_url(url, "albums"):
                new_urls.append(url)
                continue

            filename = _extract_filename_from_url(url, "albums")
            if not filename:
                new_urls.append(url)
                continue

            # Kaynak: önce root, sonra diğer tenant klasörleri
            src = uploads_base / filename
            if not src.exists():
                for sub in uploads_base.iterdir():
                    if sub.is_dir() and sub.name.isdigit():
                        candidate = sub / filename
                        if candidate.exists():
                            src = candidate
                            break

            if not src.exists() or not src.is_file():
                new_urls.append(url)
                continue

            # Hedef: tenant klasörü
            dest_dir = uploads_base / str(tid)
            dest_dir.mkdir(parents=True, exist_ok=True)
            dest = dest_dir / filename

            if src != dest:
                shutil.copy2(src, dest)
                moved += 1
                # Root'taki orijinali silebiliriz (taşıma tamamlandıktan sonra)
                root_file = uploads_base / filename
                if root_file.exists() and root_file.is_file():
                    try:
                        root_file.unlink()
                    except OSError:
                        pass

            base_url = ""
            if "://" in url:
                from urllib.parse import urlparse
                parsed = urlparse(url)
                base_url = f"{parsed.scheme}://{parsed.netloc}"
            new_urls.append(_new_url(base_url, tid, filename, "albums"))
            updated = True

        if updated:
            async with AsyncSessionLocal() as db:
                r = await db.execute(select(ImageAlbum).where(ImageAlbum.id == album.id))
                a = r.scalar_one_or_none()
                if a:
                    a.image_urls = json.dumps(new_urls, ensure_ascii=False)
                    await db.commit()

    return moved


async def migrate_response_rules():
    """ResponseRule image_urls referanslarını tenant klasörlerine taşı"""
    uploads_base = ROOT / "uploads" / "albums"
    if not uploads_base.exists():
        return 0

    moved = 0
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(ResponseRule))
        rules = result.scalars().all()

    for rule in rules:
        tid = rule.tenant_id or 1
        urls = []
        try:
            urls = json.loads(rule.image_urls or "[]")
        except json.JSONDecodeError:
            continue
        if not isinstance(urls, list):
            continue

        updated = False
        new_urls = []
        for url in urls:
            if not _is_old_format_url(url, "albums"):
                new_urls.append(url)
                continue

            filename = _extract_filename_from_url(url, "albums")
            if not filename:
                new_urls.append(url)
                continue

            src = uploads_base / filename
            if not src.exists():
                for sub in uploads_base.iterdir():
                    if sub.is_dir() and sub.name.isdigit():
                        candidate = sub / filename
                        if candidate.exists():
                            src = candidate
                            break

            if not src.exists() or not src.is_file():
                new_urls.append(url)
                continue

            dest_dir = uploads_base / str(tid)
            dest_dir.mkdir(parents=True, exist_ok=True)
            dest = dest_dir / filename

            if src != dest:
                shutil.copy2(src, dest)
                moved += 1
                root_file = uploads_base / filename
                if root_file.exists() and root_file.is_file():
                    try:
                        root_file.unlink()
                    except OSError:
                        pass

            base_url = ""
            if "://" in url:
                from urllib.parse import urlparse
                parsed = urlparse(url)
                base_url = f"{parsed.scheme}://{parsed.netloc}"
            new_urls.append(_new_url(base_url, tid, filename, "albums"))
            updated = True

        if updated:
            async with AsyncSessionLocal() as db:
                r = await db.execute(select(ResponseRule).where(ResponseRule.id == rule.id))
                rr = r.scalar_one_or_none()
                if rr:
                    rr.image_urls = json.dumps(new_urls, ensure_ascii=False)
                    await db.commit()

    return moved


async def migrate_videos():
    """Videoları tenant klasörlerine taşı"""
    uploads_base = ROOT / "uploads" / "videos"
    if not uploads_base.exists():
        return 0

    moved = 0
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Video))
        videos = result.scalars().all()

    for video in videos:
        tid = video.tenant_id or 1
        url = video.video_url or ""
        if not _is_old_format_url(url, "videos"):
            continue

        filename = _extract_filename_from_url(url, "videos")
        if not filename:
            continue

        src = uploads_base / filename
        if not src.exists():
            for sub in uploads_base.iterdir():
                if sub.is_dir() and sub.name.isdigit():
                    candidate = sub / filename
                    if candidate.exists():
                        src = candidate
                        break

        if not src.exists() or not src.is_file():
            continue

        dest_dir = uploads_base / str(tid)
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest = dest_dir / filename

        if src != dest:
            shutil.copy2(src, dest)
            moved += 1
            root_file = uploads_base / filename
            if root_file.exists() and root_file.is_file():
                try:
                    root_file.unlink()
                except OSError:
                    pass

        base_url = ""
        if "://" in url:
            from urllib.parse import urlparse
            parsed = urlparse(url)
            base_url = f"{parsed.scheme}://{parsed.netloc}"
        new_url = _new_url(base_url, tid, filename, "videos")

        async with AsyncSessionLocal() as db:
            r = await db.execute(select(Video).where(Video.id == video.id))
            v = r.scalar_one_or_none()
            if v:
                v.video_url = new_url
                await db.commit()

    return moved


async def main():
    print("Uploads tenant klasörlerine taşınıyor...")
    albums_moved = await migrate_albums()
    rules_moved = await migrate_response_rules()
    videos_moved = await migrate_videos()
    print(f"✓ Albüm resimleri: {albums_moved} dosya taşındı/kopyalandı")
    print(f"✓ Kural resimleri: {rules_moved} dosya taşındı/kopyalandı")
    print(f"✓ Videolar: {videos_moved} dosya taşındı/kopyalandı")


if __name__ == "__main__":
    asyncio.run(main())
