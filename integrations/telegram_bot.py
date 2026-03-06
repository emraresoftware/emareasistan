"""
Telegram Bot - Emare Asistan AI
Telegram'dan gelen mesajları işler, AI yanıtı ve ürün resimleri gönderir
"""
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)
from time import perf_counter

from config import get_settings
from models.database import AsyncSessionLocal
from integrations import ChatHandler
from services.workflow.metrics import record_chat_response_event


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """ /start komutu"""
    await update.message.reply_text(
        "Merhaba, Emare Asistan müşteri hizmetlerine hoş geldiniz.\n\n"
        "Ürünlerimiz hakkında bilgi alabilir, "
        "ürün önerisi, sipariş ve kargo takibi için bize ulaşabilirsiniz.\n\n"
        "Size nasıl yardımcı olabilirim?"
    )


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Gelen mesajları AI ile işle"""
    text = update.message.text or ""

    if not text.strip():
        return

    user = update.effective_user
    started = perf_counter()
    ok = True
    replied_to_caption = None
    if update.message.reply_to_message:
        replied_to_caption = getattr(update.message.reply_to_message, "caption", None)
    try:
        async with AsyncSessionLocal() as db:
            handler = ChatHandler(db)
            response = await handler.process_message(
                platform="telegram",
                user_id=str(user.id),
                message_text=text,
                conversation_history=[],
                customer_name=f"{user.first_name or ''} {user.last_name or ''}".strip() or user.username,
                replied_to_caption=replied_to_caption,
            )
    except Exception:
        ok = False
        raise
    finally:
        duration_ms = int((perf_counter() - started) * 1000)
        record_chat_response_event(
            tenant_id=1,
            ok=ok,
            latency_ms=duration_ms,
            channel="telegram",
        )

    # Yanıt gönder - Channel abstraction
    from integrations.channels import get_channel
    channel = get_channel("telegram", update=update, context=context)
    if channel:
        await channel.send_response(str(user.id), response)
    else:
        # Fallback
        if response.get("text"):
            await update.message.reply_text(response["text"])
        if response.get("image_url"):
            await update.message.reply_photo(photo=response["image_url"], caption=response.get("image_caption", ""))
        for img in response.get("product_images", []):
            await update.message.reply_photo(photo=img["url"], caption=f"{img.get('name', '')} - {img.get('price', 0)} TL")
        if response.get("location"):
            loc = response["location"]
            await update.message.reply_location(latitude=loc["lat"], longitude=loc["lng"])


def run_telegram_bot():
    """Telegram botunu başlat"""
    token = get_settings().telegram_bot_token
    if not token:
        print("TELEGRAM_BOT_TOKEN .env dosyasında tanımlanmalı")
        return

    app = Application.builder().token(token).build()
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("Telegram bot başlatılıyor...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    run_telegram_bot()
