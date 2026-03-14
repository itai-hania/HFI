"""Tests for Telegram scheduler wiring."""

import pytest

pytest.importorskip("apscheduler", reason="apscheduler not installed")

from telegram_bot.scheduler import setup_scheduler


class _BotStub:
    async def send_scheduled_brief(self):
        return None

    async def check_alerts(self):
        return None


def test_setup_scheduler_jobs():
    bot = _BotStub()
    scheduler = setup_scheduler(bot)

    jobs = {job.id: job for job in scheduler.get_jobs()}
    assert "morning-brief" in jobs
    assert "evening-brief" in jobs
    assert "alert-poll" in jobs
