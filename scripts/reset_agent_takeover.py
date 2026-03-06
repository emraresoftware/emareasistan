#!/usr/bin/env python3
"""
Temsilci devralmasını sıfırla - tüm sohbetleri AI'ya bırak.
AI yanıt vermiyor, "Mesajınız temsilcimize iletildi" geliyorsa çalıştırın.

Çalıştırma: source venv/bin/activate && python scripts/reset_agent_takeover.py
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


async def main():
    from models.database import AsyncSessionLocal, init_db
    from models import Conversation
    from sqlalchemy import select

    await init_db()
    async with AsyncSessionLocal() as db:
        r = await db.execute(select(Conversation).where(Conversation.agent_taken_over_at.isnot(None)))
        convs = r.scalars().all()
        for c in convs:
            c.agent_taken_over_at = None
            c.agent_name = None
        await db.commit()
        print(f"✅ {len(convs)} sohbet AI'ya bırakıldı. Artık yapay zeka yanıt verecek.")


if __name__ == "__main__":
    asyncio.run(main())
