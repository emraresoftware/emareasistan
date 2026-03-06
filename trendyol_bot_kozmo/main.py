#!/usr/bin/env python3
"""
main.py — Kozmopol Giris Noktasi
===================================
Veri yukler, uygulamayi baslatir, arka plan thread'ini calistirir.
"""

import sys

from core.data import (
    load_all,
    automated_responses, question_log, pending_questions,
    product_reviews, response_templates, word_blacklist,
    app_settings, gemini_config,
)
from core.processor import start_background_thread
from ui.app import App
from config import MISSING_CREDS, MISSING_GEMINI


def main():
    # Tum verileri yukle
    load_all()

    print("=" * 55)
    print("  Kozmopol — Trendyol Akilli Musteri Hizmetleri v3.0")
    print("=" * 55)
    print(f"  Otomatik yanit kurali  : {len(automated_responses)}")
    print(f"  Gelen soru gecmisi     : {len(question_log)}")
    print(f"  Bekleyen sorular       : {len(pending_questions)}")
    print(f"  Urun yorumlari         : {len(product_reviews)} urun")
    print(f"  Yanit sablonlari       : {len(response_templates)}")
    print(f"  Kara liste kelime      : {len(word_blacklist)}")
    print(f"  Trendyol API           : {'DEVRE DISI' if MISSING_CREDS else 'Aktif'}")
    print(f"  Gemini AI              : {'DEVRE DISI' if MISSING_GEMINI else 'Aktif'}")
    print(f"  Polling aralik         : {app_settings.get('max_interval', 180)} sn")
    print(f"  Mesai saatleri         : {app_settings.get('work_hours_start', '10:00')}"
          f" - {app_settings.get('work_hours_end', '18:00')}")
    print("=" * 55)

    # Uygulamayi baslat
    app = App()

    # Arka plan polling thread
    start_background_thread()

    # Ana dongu
    app.mainloop()


if __name__ == '__main__':
    main()
