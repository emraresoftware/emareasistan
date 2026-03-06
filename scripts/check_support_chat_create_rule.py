#!/usr/bin/env python3
"""
Web sohbet (yardım sohbeti) ile kural oluşturma akışını kontrol eder.
Sunucuda: cd /opt/asistan && PYTHONPATH=. venv/bin/python scripts/check_support_chat_create_rule.py
"""
import asyncio
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_parse_create_rule():
    """_parse_create_rule fonksiyonunun örnek yanıtta JSON bulduğunu doğrula."""
    from integrations.support_chat_api import _parse_create_rule

    sample_response = '''Kuralı oluşturdum. Şu JSON ile kaydedebilirsiniz:

```json
{"action":"create_rule","name":"Test Kural","trigger_type":"keyword","trigger_value":"test,deneme","product_ids":[],"image_urls":[],"custom_message":"","priority":0}
```

Kurallar sayfasından düzenleyebilirsiniz.'''
    data = _parse_create_rule(sample_response)
    if not data or data.get("action") != "create_rule":
        print("HATA: _parse_create_rule örnek yanıtta JSON bulamadı.")
        return False
    if data.get("name") != "Test Kural" or data.get("trigger_value") != "test,deneme":
        print("HATA: _parse_create_rule alanları yanlış parse etti:", data)
        return False
    print("OK: create_rule JSON parse çalışıyor.")
    return True


async def test_db_rule_create():
    """Geçici bir kural yazıp siliyoruz; tenant_id=1 (Emare)."""
    from models.database import AsyncSessionLocal
    from models import ResponseRule
    from sqlalchemy import select

    async with AsyncSessionLocal() as db:
        r = ResponseRule(
            tenant_id=1,
            name="[Test] Yardım sohbeti kural kontrolü",
            trigger_type="keyword",
            trigger_value="__test_create_rule_check__",
            product_ids="[]",
            image_urls="[]",
            is_active=False,
            priority=-999,
        )
        db.add(r)
        await db.commit()
        await db.refresh(r)
        rid = r.id
        # Sil
        await db.delete(r)
        await db.commit()
    print(f"OK: ResponseRule yazma/silme çalışıyor (geçici id={rid}).")
    return True


def main():
    print("--- Web sohbet kural oluşturma kontrolü ---")
    if not test_parse_create_rule():
        return 1
    try:
        asyncio.run(test_db_rule_create())
    except Exception as e:
        print(f"HATA: DB test: {e}")
        return 1
    print("--- Tüm kontroller geçti. ---")
    return 0


if __name__ == "__main__":
    sys.exit(main())
