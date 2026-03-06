"""
Celery uygulaması - arka plan işleri.
Kullanım:
  celery -A celery_app worker -l info
  celery -A celery_app beat -l info  # Periyodik görevler için
"""
from celery import Celery
from config import get_settings

settings = get_settings()
redis_url = (settings.redis_url or "redis://localhost:6379/0").strip()

app = Celery(
    "emare_asistan",
    broker=redis_url,
    backend=redis_url,
    include=["tasks"],
)
app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Europe/Istanbul",
    enable_utc=True,
    task_track_started=True,
    beat_schedule={
        "abandoned-cart-every-10-min": {
            "task": "tasks.abandoned_cart_reminder_task",
            "schedule": 600,  # 10 dakika (saniye)
        },
        "proactive-message-every-30-min": {
            "task": "tasks.proactive_message_task",
            "schedule": 1800,  # 30 dakika
        },
    },
)
