"""Scheduler setup for Telegram bot periodic jobs."""

from __future__ import annotations

from typing import Iterable
from zoneinfo import ZoneInfo

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

ISRAEL_TZ = ZoneInfo("Asia/Jerusalem")


def _parse_time_hhmm(value: str) -> tuple[int, int] | None:
    parts = value.split(":", maxsplit=1)
    if len(parts) != 2:
        return None
    hour_text, minute_text = parts
    if not (hour_text.isdigit() and minute_text.isdigit()):
        return None
    hour = int(hour_text)
    minute = int(minute_text)
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        return None
    return hour, minute


def setup_scheduler(
    bot,
    brief_times: Iterable[str] | None = None,
    alert_interval_minutes: int = 15,
) -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler(timezone=ISRAEL_TZ)
    parsed_times = list(brief_times or ["08:00", "19:00"])

    added = 0
    for index, value in enumerate(parsed_times):
        parsed = _parse_time_hhmm(value)
        if parsed is None:
            continue
        hour, minute = parsed

        if index == 0:
            job_id = "morning-brief"
        elif index == 1:
            job_id = "evening-brief"
        else:
            job_id = f"brief-{index + 1}"

        scheduler.add_job(
            bot.send_scheduled_brief,
            CronTrigger(hour=hour, minute=minute, timezone=ISRAEL_TZ),
            id=job_id,
            replace_existing=True,
        )
        added += 1

    if added == 0:
        scheduler.add_job(
            bot.send_scheduled_brief,
            CronTrigger(hour=8, minute=0, timezone=ISRAEL_TZ),
            id="morning-brief",
            replace_existing=True,
        )
        scheduler.add_job(
            bot.send_scheduled_brief,
            CronTrigger(hour=19, minute=0, timezone=ISRAEL_TZ),
            id="evening-brief",
            replace_existing=True,
        )

    scheduler.add_job(
        bot.check_alerts,
        IntervalTrigger(minutes=max(1, int(alert_interval_minutes))),
        id="alert-poll",
        replace_existing=True,
    )
    return scheduler
