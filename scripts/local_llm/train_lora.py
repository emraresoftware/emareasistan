import argparse
from dataclasses import dataclass

import torch
from datasets import load_dataset
from peft import LoraConfig, get_peft_model
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    DataCollatorForLanguageModeling,
    Trainer,
    TrainingArguments,
)


def pick_device() -> torch.device:
    if torch.cuda.is_available():
        return torch.device("cuda")
    if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
        return torch.device("mps")
    return torch.device("cpu")


@dataclass
class Config:
    base_model: str
    dataset_path: str
    output_dir: str
    num_train_epochs: int
    learning_rate: float
    batch_size: int
    grad_accum: int
    max_seq_len: int


def parse_args() -> Config:
    parser = argparse.ArgumentParser(description="Local LoRA fine-tuning script")
    parser.add_argument("--base-model", default="Qwen/Qwen2.5-0.5B-Instruct")
    parser.add_argument("--dataset-path", required=True, help="JSONL with `text` field")
    parser.add_argument("--output-dir", default="./artifacts/local_lora")
    parser.add_argument("--num-train-epochs", type=int, default=2)
    parser.add_argument("--learning-rate", type=float, default=2e-4)
    parser.add_argument("--batch-size", type=int, default=1)
    parser.add_argument("--grad-accum", type=int, default=8)
    parser.add_argument("--max-seq-len", type=int, default=512)
    args = parser.parse_args()
    return Config(
        base_model=args.base_model,
        dataset_path=args.dataset_path,
        output_dir=args.output_dir,
        num_train_epochs=args.num_train_epochs,
        learning_rate=args.learning_rate,
        batch_size=args.batch_size,
        grad_accum=args.grad_accum,
        max_seq_len=args.max_seq_len,
    )


def main() -> None:
    cfg = parse_args()
    device = pick_device()
    print(f"Using device: {device}")

    tokenizer = AutoTokenizer.from_pretrained(cfg.base_model, use_fast=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    model = AutoModelForCausalLM.from_pretrained(
        cfg.base_model,
        torch_dtype=torch.float32 if device.type != "cuda" else torch.float16,
    )
    model.to(device)

    lora_cfg = LoraConfig(
        r=16,
        lora_alpha=32,
        lora_dropout=0.05,
        bias="none",
        task_type="CAUSAL_LM",
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj"],
    )
    model = get_peft_model(model, lora_cfg)
    model.print_trainable_parameters()

    dataset = load_dataset("json", data_files=cfg.dataset_path, split="train")
    if "text" not in dataset.column_names:
        raise ValueError("Dataset must contain a `text` field.")

    def _tokenize(batch: dict) -> dict:
        enc = tokenizer(
            batch["text"],
            truncation=True,
            max_length=cfg.max_seq_len,
            padding=False,
        )
        enc["labels"] = enc["input_ids"].copy()
        return enc

    tokenized = dataset.map(_tokenize, batched=True, remove_columns=dataset.column_names)

    args = TrainingArguments(
        output_dir=cfg.output_dir,
        num_train_epochs=cfg.num_train_epochs,
        per_device_train_batch_size=cfg.batch_size,
        gradient_accumulation_steps=cfg.grad_accum,
        learning_rate=cfg.learning_rate,
        logging_steps=10,
        save_steps=100,
        save_total_limit=2,
        lr_scheduler_type="cosine",
        warmup_ratio=0.03,
        report_to=[],
        fp16=device.type == "cuda",
        bf16=False,
    )

    data_collator = DataCollatorForLanguageModeling(tokenizer=tokenizer, mlm=False)

    trainer = Trainer(
        model=model,
        train_dataset=tokenized,
        data_collator=data_collator,
        args=args,
    )
    trainer.train()

    trainer.model.save_pretrained(cfg.output_dir)
    tokenizer.save_pretrained(cfg.output_dir)
    print(f"LoRA adapter saved to: {cfg.output_dir}")


if __name__ == "__main__":
    main()
