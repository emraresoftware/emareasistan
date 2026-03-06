"""
Celery görevleri - arka plan işleri.
Örnek: abandoned_cart, e-posta gönderimi, rapor oluşturma.
"""
from celery_app import app


@app.task
def abandoned_cart_reminder_task():
    """Sepet terk hatırlatması - Celery ile arka planda"""
    import asyncio
    from models.database import AsyncSessionLocal
    from services.order.abandoned_cart import send_abandoned_cart_reminders

    async def _run():
        async with AsyncSessionLocal() as db:
            return await send_abandoned_cart_reminders(db)

    return asyncio.run(_run())


@app.task
def health_check_task():
    """Basit sağlık kontrolü - Celery çalışıyor mu test"""
    return {"ok": True, "celery": "running"}


@app.task
def proactive_message_task():
    """Proaktif mesaj tetikleyicisi - pasif sohbetlere mesaj"""
    import asyncio
    from models.database import AsyncSessionLocal
    from services.workflow.proactive import send_proactive_messages

    async def _run():
        async with AsyncSessionLocal() as db:
            return await send_proactive_messages(db)

    return asyncio.run(_run())
