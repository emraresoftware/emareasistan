#!/usr/bin/env python3
"""
Canlı sohbet dinleyici - veritabanından yeni mesajları poll eder.
Durdurmak için Ctrl+C.
"""
import asyncio
import sys
from datetime import datetime
from pathlib import Path

# Proje kökü
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from sqlalchemy import select, desc
from models.database import AsyncSessionLocal
from models import Message, Conversation


async def monitor(tenant_id: int = 1, poll_interval: float = 1.5):
    """Son mesajları izle, yenileri yazdır."""
    last_id = 0
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Dinleniyor (tenant_id={tenant_id}, her {poll_interval}s)... Durdurmak için Ctrl+C\n")
    async with AsyncSessionLocal() as db:
        while True:
            try:
                result = await db.execute(
                    select(Message, Conversation)
                    .join(Conversation, Message.conversation_id == Conversation.id)
                    .where(Conversation.tenant_id == tenant_id, Message.id > last_id)
                    .order_by(Message.id)
                )
                rows = result.all()
                for msg, conv in rows:
                    last_id = max(last_id, msg.id)
                    role = (msg.role or "?").upper()
                    content = (msg.content or "").replace("\n[Ürün resimleri gönderildi]", "").strip()
                    ts = msg.created_at.strftime("%H:%M:%S") if msg.created_at else "-"
                    who = getattr(conv, "customer_name", None) or getattr(conv, "platform_user_id", "?") or "?"
                    if role == "USER":
                        print(f"[{ts}] 👤 {who}: {content[:200]}{'...' if len(content) > 200 else ''}")
                    else:
                        print(f"[{ts}] 🤖 Asistan: {content[:200]}{'...' if len(content) > 200 else ''}")
                    print()
            except Exception as e:
                print(f"[!] Hata: {e}", file=sys.stderr)
            await asyncio.sleep(poll_interval)


if __name__ == "__main__":
    tid = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    asyncio.run(monitor(tenant_id=tid))
