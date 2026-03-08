"""Tests for Telegram bot message formatting."""

from telegram_bot.bot import format_brief_message, format_alert_message


class TestTelegramBot:
    def test_format_brief_message(self):
        stories = [
            {
                "title": "SEC approves Bitcoin ETF",
                "sources": ["Bloomberg", "WSJ"],
                "summary": "רגולציה חדשה",
            },
            {
                "title": "Stripe acquires startup",
                "sources": ["TechCrunch"],
                "summary": "רכישה",
            },
        ]
        msg = format_brief_message(stories, "morning")
        assert "SEC approves Bitcoin ETF" in msg
        assert "Bloomberg" in msg
        assert "/write_1" in msg
        assert "/write_2" in msg

    def test_format_alert_message(self):
        alert = {
            "title": "CBDC pilot program",
            "sources": ["Bloomberg", "WSJ", "Yahoo"],
            "summary": "בנק מרכזי",
        }
        msg = format_alert_message(alert)
        assert "CBDC pilot program" in msg
        assert "/write" in msg
