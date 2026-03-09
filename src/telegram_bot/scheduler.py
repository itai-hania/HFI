"""Scheduler setup for Telegram bot periodic jobs."""

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger


def setup_scheduler(bot):
    scheduler = AsyncIOScheduler()
    scheduler.add_job(bot.send_scheduled_brief, CronTrigger(hour=8, minute=0), id="morning-brief")
    scheduler.add_job(bot.send_scheduled_brief, CronTrigger(hour=19, minute=0), id="evening-brief")
    scheduler.add_job(bot.check_alerts, IntervalTrigger(minutes=15), id="alert-poll")
    return scheduler
