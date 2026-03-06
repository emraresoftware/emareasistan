import argparse
import json
from pathlib import Path


def format_record(instruction: str, input_text: str, output_text: str) -> dict:
    prompt = f"### Instruction:\n{instruction.strip()}\n\n"
    if input_text.strip():
        prompt += f"### Input:\n{input_text.strip()}\n\n"
    prompt += "### Response:\n"
    return {"text": prompt + output_text.strip()}


def main() -> None:
    parser = argparse.ArgumentParser(description="Convert JSONL to SFT text format")
    parser.add_argument("--in-file", required=True, help="Source JSONL")
    parser.add_argument("--out-file", required=True, help="Output JSONL for training")
    args = parser.parse_args()

    in_path = Path(args.in_file)
    out_path = Path(args.out_file)

    if not in_path.exists():
        raise FileNotFoundError(f"Input file not found: {in_path}")

    rows = []
    with in_path.open("r", encoding="utf-8") as f:
        for line_no, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            obj = json.loads(line)
            instruction = str(obj.get("instruction", "")).strip()
            input_text = str(obj.get("input", "")).strip()
            output_text = str(obj.get("output", "")).strip()
            if not instruction or not output_text:
                raise ValueError(f"Line {line_no}: instruction/output required")
            rows.append(format_record(instruction, input_text, output_text))

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    print(f"Wrote {len(rows)} rows -> {out_path}")


if __name__ == "__main__":
    main()
