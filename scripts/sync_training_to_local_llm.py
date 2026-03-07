#!/usr/bin/env python3
"""
AITrainingExample (veritabanı) → sample_train.jsonl senkronizasyonu.
Panelden eklenen örnekleri lokal LoRA eğitimi için export eder.
"""
from __future__ import annotations
import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from models.database import AsyncSessionLocal
from models import AITrainingExample
from sqlalchemy import select


def to_instruction_format(question: str, expected_answer: str) -> dict:
    """Soru/cevap → instruction/input/output formatına çevir."""
    instruction = question.strip()
    if not instruction:
        return None
    # "X sorulduğunda" veya "X nedir?" gibi instruction'a çevir
    if "?" in instruction or "mı" in instruction or "mi" in instruction:
        inst = instruction
    else:
        inst = f"Musteri '{instruction}' sordugunda ne cevap verilmeli?"
    return {
        "instruction": inst,
        "input": "",
        "output": expected_answer.strip() if expected_answer else "",
    }


async def export_training_examples(
    tenant_ids: list[int] | None = None,
    output_path: Path | None = None,
    merge_with_existing: bool = True,
) -> int:
    """
    AITrainingExample kayıtlarını sample_train.jsonl formatında export et.
    tenant_ids: None = tüm tenant'lar, [1,6] = sadece bu tenant'lar
    """
    output_path = output_path or ROOT / "scripts/local_llm/sample_train.jsonl"
    existing: list[dict] = []

    if merge_with_existing and output_path.exists():
        with output_path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        existing.append(json.loads(line))
                    except json.JSONDecodeError:
                        pass

    async with AsyncSessionLocal() as db:
        q = (
            select(AITrainingExample)
            .where(AITrainingExample.is_active == True)
            .order_by(AITrainingExample.tenant_id, AITrainingExample.priority.desc())
        )
        if tenant_ids is not None:
            q = q.where(AITrainingExample.tenant_id.in_(tenant_ids))
        result = await db.execute(q)
        examples = result.scalars().all()

    seen_questions: set[str] = set()
    new_rows: list[dict] = []

    for ex in examples:
        rec = to_instruction_format(ex.question, ex.expected_answer)
        if not rec or not rec.get("output"):
            continue
        key = (rec["instruction"].lower()[:80], rec["output"].lower()[:80])
        if key in seen_questions:
            continue
        seen_questions.add(key)
        new_rows.append(rec)

    # Mevcut örneklerdeki instruction'ları koru (merge)
    existing_keys = {(r.get("instruction", "").lower()[:80], r.get("output", "").lower()[:80]) for r in existing}
    for r in new_rows:
        key = (r["instruction"].lower()[:80], r["output"].lower()[:80])
        if key not in existing_keys:
            existing.append(r)
            existing_keys.add(key)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as f:
        for row in existing:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    return len(existing)


async def main():
    import argparse
    parser = argparse.ArgumentParser(description="AITrainingExample → sample_train.jsonl")
    parser.add_argument("--tenant-ids", type=str, default=None, help="Virgülle: 1,6 (yoksa tümü)")
    parser.add_argument("--output", type=str, default=None, help="Çıktı dosyası")
    parser.add_argument("--no-merge", action="store_true", help="Mevcut sample_train.jsonl ile birleştirme")
    args = parser.parse_args()

    tenant_ids = None
    if args.tenant_ids:
        tenant_ids = [int(x.strip()) for x in args.tenant_ids.split(",") if x.strip()]

    output_path = Path(args.output) if args.output else None
    n = await export_training_examples(
        tenant_ids=tenant_ids,
        output_path=output_path,
        merge_with_existing=not args.no_merge,
    )
    print(f"✓ {n} ornek sample_train.jsonl'a yazildi")


if __name__ == "__main__":
    asyncio.run(main())
