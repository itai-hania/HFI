"""Entrypoint for Telegram bot service."""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path

import httpx
from common.env_utils import SingleInstanceFileLock
from common.logging_utils import log_event
from telegram_bot.bot import HFIBot
from telegram_bot.config import load_bot_config

try:
    from telegram.error import BadRequest, Conflict
except Exception:  # pragma: no cover - fallback in test environments without telegram
    BadRequest = RuntimeError  # type: ignore
    Conflict = RuntimeError  # type: ignore

from telegram_bot.scheduler import setup_scheduler

logger = logging.getLogger(__name__)
_LOCK_PATH = Path(__file__).resolve().parents[2] / "data" / "runtime" / "telegram-bot.lock"


async def _run(bot: HFIBot, runtime_lock: SingleInstanceFileLock):
    scheduler = setup_scheduler(
        bot,
        brief_times=bot.brief_times,
        alert_interval_minutes=bot.alert_interval_minutes,
    )
    await bot.run_startup_self_checks()
    scheduler.start()

    initialized = False
    started = False
    updater_started = False

    try:
        await bot.app.initialize()
        initialized = True
        await bot.app.start()
        started = True

        if bot.app.updater is None:
            raise RuntimeError("Telegram updater is not available")

        try:
            await bot.app.updater.start_polling()
        except Conflict as exc:
            log_event(
                logger,
                "telegram_poll_conflict",
                level=logging.ERROR,
                error=str(exc),
            )
            raise RuntimeError("Telegram polling conflict. Another poller may already be running.") from exc

        updater_started = True

        log_event(logger, "bot_started", chat_id=bot.chat_id)
        await asyncio.Event().wait()
    finally:
        if updater_started and bot.app.updater is not None:
            await bot.app.updater.stop()
        if started:
            await bot.app.stop()
        if initialized:
            await bot.app.shutdown()
        scheduler.shutdown(wait=False)
        await bot.close()
        runtime_lock.release()


def main():
    config = load_bot_config()

    runtime_lock = SingleInstanceFileLock(_LOCK_PATH)
    runtime_lock.acquire()

    bot = HFIBot(
        token=config.token,
        chat_id=config.chat_id,
        api_url=config.api_base_url,
        api_password=config.api_password,
        brief_times=config.brief_times,
        alert_interval_minutes=config.alert_interval_minutes,
        frontend_base_url=config.frontend_base_url,
    )

    try:
        asyncio.run(_run(bot, runtime_lock))
    except Conflict as exc:
        log_event(logger, "telegram_poll_conflict", level=logging.ERROR, error=str(exc))
        raise RuntimeError("Telegram polling conflict. Ensure only one bot process is running.") from exc
    except BadRequest as exc:
        log_event(logger, "telegram_rejected_message", level=logging.ERROR, error=str(exc))
        raise RuntimeError(f"Telegram rejected request: {exc}") from exc
    except httpx.ConnectError as exc:
        log_event(logger, "api_unreachable", level=logging.ERROR, error=str(exc))
        raise RuntimeError("Cannot connect to API service for bot startup.") from exc
    except KeyboardInterrupt:
        log_event(logger, "bot_stopped", reason="keyboard_interrupt")
    finally:
        runtime_lock.release()


if __name__ == "__main__":
    main()
