#!/bin/bash
# AITrainingExample senkron + LoRA yeniden eğitim (tek komut)
set -e
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"
source venv/bin/activate

echo "1. AITrainingExample -> sample_train.jsonl"
python scripts/sync_training_to_local_llm.py --tenant-ids 1,6

echo "2. prepare_dataset"
cd scripts/local_llm
source .venv/bin/activate
python prepare_dataset.py --in-file sample_train.jsonl --out-file data/train_sft.jsonl

echo "3. train_lora (5 epoch)"
python train_lora.py \
  --dataset-path data/train_sft.jsonl \
  --output-dir artifacts/local_lora \
  --num-train-epochs 5 \
  --batch-size 1 \
  --grad-accum 4

echo "✓ LoRA adapter guncellendi: artifacts/local_lora"
