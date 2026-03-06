# Local trainable language model (LoRA)

This folder provides a minimal local fine-tuning pipeline.

- Base model: `Qwen/Qwen2.5-0.5B-Instruct`
- Method: LoRA SFT
- Works on: CPU / CUDA / Apple MPS (slow on CPU, but works)

## 1) Create virtual environment

```bash
cd /Users/emre/Desktop/asistan/scripts/local_llm
python3 -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install -r requirements.txt
```

## 2) Prepare training dataset

Your source format (`sample_train.jsonl`):

```json
{"instruction":"...", "input":"...", "output":"..."}
```

Convert to trainer format:

```bash
python prepare_dataset.py \
  --in-file sample_train.jsonl \
  --out-file data/train_sft.jsonl
```

### Optional: AITrainingExample'dan senkron

Panelden eklenen eğitim örneklerini sample_train.jsonl'a aktarmak için:

```bash
cd asistan
source venv/bin/activate
python scripts/sync_training_to_local_llm.py --tenant-ids 1,6
```

`--tenant-ids 1,6` ile sadece bu tenant'ların örnekleri eklenir. Belirtilmezse tüm tenant'lar.

**Tek komutla senkron + eğitim:** `./retrain.sh`

### Optional: auto-extract from real chats

```bash
cd /Users/emre/Desktop/asistan
source venv/bin/activate
python scripts/local_llm/extract_training_data.py \
  --out-file scripts/local_llm/data/raw_from_chats.jsonl \
  --tenant-id 2 \
  --max-rows 1500

cd scripts/local_llm
source .venv/bin/activate
python prepare_dataset.py \
  --in-file data/raw_from_chats.jsonl \
  --out-file data/train_sft.jsonl
```

## 3) Train LoRA adapter locally

```bash
python train_lora.py \
  --dataset-path data/train_sft.jsonl \
  --output-dir artifacts/local_lora \
  --num-train-epochs 5 \
  --batch-size 1 \
  --grad-accum 4
```

Notes:

- CPU training is slow; keep dataset small first.
- If you have GPU, training is much faster.
- 5 epoch + 56+ ornek ile daha iyi ogrenme saglanir.

## 4) Test the trained adapter

```bash
python chat.py \
  --adapter-path artifacts/local_lora \
  --prompt "Musteri e-posta verdiyse tekrar ne sormaliyim?"
```

## 5) Integrate into app (next step)

If you want, I can wire this adapter into your current `AIAssistant` flow as a fallback route (for example: `LOCAL_LLM_ENABLED=true`).
