#!/usr/bin/env python3
"""
Tenant 6 AI Eğitim verilerini JSON'dan import et.
Sunucuda çalıştırılır: python scripts/import_tenant6_training.py [data/tenant6_training.json]
"""
import argparse
import asyncio
import json
import sys
from pathlib import Path

# Proje kökü
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from models.database import AsyncSessionLocal
from models import AITrainingExample, Tenant
from sqlalchemy import select, delete


async def import_tenant6_training(input_path: Path) -> tuple[int, int]:
    """Tenant 6 AI eğitim verilerini import et. Returns (examples_count, settings_updated)."""
    tid = 6

    with open(input_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    examples = data.get("ai_training_examples") or []
    settings_training = data.get("tenant_settings_training") or {}

    async with AsyncSessionLocal() as db:
        # 1. Mevcut AI training örneklerini sil, yenilerini ekle
        await db.execute(delete(AITrainingExample).where(AITrainingExample.tenant_id == tid))
        for item in examples:
            ex = AITrainingExample(tenant_id=tid)
            ex.question = item.get("question", "")
            ex.expected_answer = item.get("expected_answer", "")
            ex.category = item.get("category")
            ex.trigger_keywords = item.get("trigger_keywords")
            ex.is_active = item.get("is_active", True)
            ex.priority = item.get("priority", 0) or 0
            db.add(ex)

        # 2. Tenant settings - sadece training kısımlarını merge et
        result = await db.execute(select(Tenant).where(Tenant.id == tid))
        tenant = result.scalar_one_or_none()
        settings_updated = 0
        if tenant:
            existing = {}
            if tenant.settings:
                try:
                    existing = json.loads(tenant.settings)
                except (json.JSONDecodeError, TypeError):
                    existing = {}
            # Merge training keys
            if settings_training.get("quick_reply_options") is not None:
                existing["quick_reply_options"] = settings_training["quick_reply_options"]
                settings_updated += 1
            if settings_training.get("ai_response_rules") is not None:
                existing["ai_response_rules"] = settings_training["ai_response_rules"]
                settings_updated += 1
            if settings_training.get("welcome_scenarios") is not None:
                existing["welcome_scenarios"] = settings_training["welcome_scenarios"]
                settings_updated += 1
            if settings_updated > 0:
                tenant.settings = json.dumps(existing, ensure_ascii=False)

        await db.commit()

    return len(examples), settings_updated


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("input", nargs="?", default="data/tenant6_training.json",
                        help="Import edilecek JSON dosyası")
    args = parser.parse_args()
    input_path = Path(args.input)
    if not input_path.is_absolute():
        input_path = ROOT / input_path

    if not input_path.exists():
        print(f"HATA: Dosya bulunamadı: {input_path}")
        return 1

    n_ex, n_set = asyncio.run(import_tenant6_training(input_path))
    print(f"Import tamamlandı: {n_ex} AI eğitim örneği, {n_set} ayar grubu güncellendi")
    return 0


if __name__ == "__main__":
    sys.exit(main())
