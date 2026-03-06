#!/usr/bin/env python3
"""Son sohbet mesajlarını listele"""
import asyncio
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from sqlalchemy import select, desc
from models.database import AsyncSessionLocal
from models import Message, Conversation


async def main(tenant_id: int = 1, limit: int = 50):
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Message, Conversation)
            .join(Conversation, Message.conversation_id == Conversation.id)
            .where(Conversation.tenant_id == tenant_id)
            .order_by(desc(Message.id))
            .limit(limit)
        )
        rows = result.all()
        if not rows:
            print("Henüz mesaj yok.")
            return
        print(f"Son {len(rows)} mesaj (tenant_id={tenant_id}):\n")
        for msg, conv in rows:
            role = (msg.role or "?").upper()
            content = (msg.content or "").replace("\n[Ürün resimleri gönderildi]", "").strip()
            ts = msg.created_at.strftime("%Y-%m-%d %H:%M:%S") if msg.created_at else "-"
            who = conv.customer_name or conv.platform_user_id or "?"
            platform = conv.platform or "?"
            if role == "USER":
                print(f"[{ts}] [{platform}] 👤 {who}: {content[:300]}{'...' if len(content) > 300 else ''}")
            else:
                print(f"[{ts}] [{platform}] 🤖 Asistan: {content[:300]}{'...' if len(content) > 300 else ''}")
            print()


if __name__ == "__main__":
    tid = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    n = int(sys.argv[2]) if len(sys.argv) > 2 else 50
    asyncio.run(main(tenant_id=tid, limit=n))
