from __future__ import annotations
import argparse
import asyncio
import json
import re
from dataclasses import dataclass

from sqlalchemy import select

from models.database import AsyncSessionLocal
from models import Conversation, Message


EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
PHONE_RE = re.compile(r"\+?\d[\d\s().-]{8,}\d")
URL_RE = re.compile(r"https?://\S+|www\.\S+", re.IGNORECASE)
JSON_BLOCK_RE = re.compile(r"```json.*?```", re.DOTALL | re.IGNORECASE)


@dataclass
class Pair:
    instruction: str
    input: str
    output: str


def _normalize_text(text: str) -> str:
    t = (text or "").strip()
    if not t:
        return ""
    t = JSON_BLOCK_RE.sub("", t)
    t = t.replace("[Ürün resimleri gönderildi]", "")
    t = re.sub(r"\s+", " ", t).strip()
    return t


def _mask_pii(text: str) -> str:
    t = text
    t = EMAIL_RE.sub("<EMAIL>", t)
    t = PHONE_RE.sub("<PHONE>", t)
    t = URL_RE.sub("<URL>", t)
    return t


def _skip_text(text: str) -> bool:
    t = text.lower()
    if len(t) < 8:
        return True
    blocked = (
        "yanıt oluşturulamadı",
        "lütfen tekrar deneyin",
        "teknik bir gecikme",
        "quota",
        "resourceexhausted",
    )
    return any(b in t for b in blocked)


def _message_role(value: str) -> str:
    role = (value or "").strip().lower()
    if role == "assistant":
        return "assistant"
    if role == "user":
        return "user"
    return "other"


def _build_pair(prev_assistant: str, user_text: str, assistant_text: str) -> Pair:
    instruction = "Müşteri mesajına kısa, net ve profesyonel bir Türkçe yanıt ver."
    if prev_assistant:
        input_text = f"Önceki asistan mesajı: {prev_assistant}\nMüşteri mesajı: {user_text}"
    else:
        input_text = f"Müşteri mesajı: {user_text}"
    return Pair(instruction=instruction, input=input_text, output=assistant_text)


async def extract_pairs(tenant_id: int | None, max_rows: int, min_chars: int) -> list[Pair]:
    pairs: list[Pair] = []
    seen: set[tuple[str, str, str]] = set()

    async with AsyncSessionLocal() as db:
        q = select(Conversation.id).order_by(Conversation.id.asc())
        if tenant_id is not None:
            q = q.where(Conversation.tenant_id == tenant_id)
        conv_ids = [row[0] for row in (await db.execute(q)).all()]

        for conv_id in conv_ids:
            msg_res = await db.execute(
                select(Message)
                .where(Message.conversation_id == conv_id)
                .order_by(Message.created_at.asc(), Message.id.asc())
            )
            msgs = msg_res.scalars().all()
            if len(msgs) < 2:
                continue

            for idx, msg in enumerate(msgs):
                if _message_role(msg.role) != "assistant":
                    continue

                assistant_text = _normalize_text(msg.content or "")
                if len(assistant_text) < min_chars or _skip_text(assistant_text):
                    continue

                prev_user = None
                prev_assistant = ""
                for j in range(idx - 1, -1, -1):
                    role_j = _message_role(msgs[j].role)
                    if role_j == "assistant" and not prev_assistant:
                        prev_assistant = _normalize_text(msgs[j].content or "")
                    if role_j == "user":
                        prev_user = _normalize_text(msgs[j].content or "")
                        break

                if not prev_user or len(prev_user) < min_chars:
                    continue

                p = _build_pair(prev_assistant=prev_assistant, user_text=prev_user, assistant_text=assistant_text)
                inp = _mask_pii(p.input)
                out = _mask_pii(p.output)
                key = (p.instruction, inp, out)
                if key in seen:
                    continue
                seen.add(key)
                pairs.append(Pair(instruction=p.instruction, input=inp, output=out))
                if len(pairs) >= max_rows:
                    return pairs

    return pairs


async def main_async() -> None:
    parser = argparse.ArgumentParser(description="Extract local LLM training data from chat history")
    parser.add_argument("--out-file", required=True, help="Output JSONL path")
    parser.add_argument("--tenant-id", type=int, default=None, help="Optional tenant filter")
    parser.add_argument("--max-rows", type=int, default=1200)
    parser.add_argument("--min-chars", type=int, default=10)
    args = parser.parse_args()

    pairs = await extract_pairs(
        tenant_id=args.tenant_id,
        max_rows=args.max_rows,
        min_chars=args.min_chars,
    )

    with open(args.out_file, "w", encoding="utf-8") as f:
        for p in pairs:
            f.write(
                json.dumps(
                    {"instruction": p.instruction, "input": p.input, "output": p.output},
                    ensure_ascii=False,
                )
                + "\n"
            )

    print(f"rows={len(pairs)} out={args.out_file}")


if __name__ == "__main__":
    asyncio.run(main_async())
