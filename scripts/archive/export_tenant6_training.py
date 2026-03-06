#!/usr/bin/env python3
"""
Tenant 6 AI Eğitim verilerini JSON'a export et.
Kullanım: python scripts/export_tenant6_training.py [--output data/tenant6_training.json]
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
from sqlalchemy import select


async def export_tenant6_training(output_path: Path) -> dict:
    """Tenant 6 AI eğitim verilerini export et."""
    tid = 6
    out = {"tenant_id": tid, "ai_training_examples": [], "tenant_settings_training": {}}

    async with AsyncSessionLocal() as db:
        # AI Training Examples
        result = await db.execute(
            select(AITrainingExample)
            .where(AITrainingExample.tenant_id == tid)
            .order_by(AITrainingExample.priority.desc(), AITrainingExample.id)
        )
        examples = result.scalars().all()
        for ex in examples:
            out["ai_training_examples"].append({
                "question": ex.question,
                "expected_answer": ex.expected_answer,
                "category": ex.category,
                "trigger_keywords": ex.trigger_keywords,
                "is_active": ex.is_active,
                "priority": ex.priority or 0,
            })

        # Tenant settings - sadece AI eğitim ile ilgili kısımlar
        result = await db.execute(select(Tenant).where(Tenant.id == tid))
        tenant = result.scalar_one_or_none()
        if tenant and tenant.settings:
            try:
                data = json.loads(tenant.settings)
                out["tenant_settings_training"] = {
                    "quick_reply_options": data.get("quick_reply_options"),
                    "ai_response_rules": data.get("ai_response_rules"),
                    "welcome_scenarios": data.get("welcome_scenarios"),
                }
            except (json.JSONDecodeError, TypeError):
                pass

    return out


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", "-o", default="data/tenant6_training.json",
                        help="Çıktı JSON dosyası")
    args = parser.parse_args()
    output_path = Path(args.output)
    if not output_path.is_absolute():
        output_path = ROOT / output_path

    output_path.parent.mkdir(parents=True, exist_ok=True)

    data = asyncio.run(export_tenant6_training(output_path))
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    n = len(data["ai_training_examples"])
    print(f"Export tamamlandı: {n} AI eğitim örneği, {output_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
