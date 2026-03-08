"""Entrypoint for Telegram bot service."""

import asyncio

from telegram_bot.bot import HFIBot
from telegram_bot.config import (
    TELEGRAM_BOT_TOKEN,
    TELEGRAM_CHAT_ID,
    API_BASE_URL,
    API_PASSWORD,
)
from telegram_bot.scheduler import setup_scheduler


async def main():
    if not TELEGRAM_BOT_TOKEN:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is required")
    if not TELEGRAM_CHAT_ID:
        raise RuntimeError("TELEGRAM_CHAT_ID is required")

    bot = HFIBot(
        token=TELEGRAM_BOT_TOKEN,
        chat_id=TELEGRAM_CHAT_ID,
        api_url=API_BASE_URL,
        api_password=API_PASSWORD,
    )

    scheduler = setup_scheduler(bot)
    scheduler.start()

    try:
        await bot.app.run_polling()
    finally:
        scheduler.shutdown(wait=False)
        await bot.close()


if __name__ == "__main__":
    asyncio.run(main())
