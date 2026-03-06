import argparse

import torch
from peft import PeftModel
from transformers import AutoModelForCausalLM, AutoTokenizer


def pick_device() -> torch.device:
    if torch.cuda.is_available():
        return torch.device("cuda")
    if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
        return torch.device("mps")
    return torch.device("cpu")


def main() -> None:
    parser = argparse.ArgumentParser(description="Chat with base model + LoRA")
    parser.add_argument("--base-model", default="Qwen/Qwen2.5-0.5B-Instruct")
    parser.add_argument("--adapter-path", required=True)
    parser.add_argument("--prompt", required=True)
    parser.add_argument("--max-new-tokens", type=int, default=180)
    args = parser.parse_args()

    device = pick_device()
    tokenizer = AutoTokenizer.from_pretrained(args.base_model, use_fast=True)
    base_model = AutoModelForCausalLM.from_pretrained(
        args.base_model,
        torch_dtype=torch.float32 if device.type != "cuda" else torch.float16,
    )
    model = PeftModel.from_pretrained(base_model, args.adapter_path)
    model.to(device)
    model.eval()

    prompt = (
        "### Instruction:\nAsagidaki kullanici mesajina yardimci bir sekilde cevap ver.\n\n"
        f"### Input:\n{args.prompt}\n\n"
        "### Response:\n"
    )
    inputs = tokenizer(prompt, return_tensors="pt").to(device)
    with torch.no_grad():
        out = model.generate(
            **inputs,
            max_new_tokens=args.max_new_tokens,
            do_sample=True,
            temperature=0.7,
            top_p=0.9,
            eos_token_id=tokenizer.eos_token_id,
            pad_token_id=tokenizer.eos_token_id,
        )
    text = tokenizer.decode(out[0], skip_special_tokens=True)
    print(text.split("### Response:\n", 1)[-1].strip())


if __name__ == "__main__":
    main()
