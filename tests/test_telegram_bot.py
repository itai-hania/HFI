"""Tests for Telegram command rendering and message formatting."""

from telegram_bot.bot import format_alert_message, format_brief_message
from telegram_bot.command_catalog import render_start_text, visible_start_commands


class TestTelegramBotFormatting:
    def test_format_brief_message(self):
        stories = [
            {
                "title": "SEC approves Bitcoin ETF",
                "sources": ["Bloomberg", "WSJ"],
                "summary": "רגולציה חדשה",
                "source_urls": ["https://bloomberg.com/sec-etf"],
            },
            {
                "title": "Stripe acquires startup",
                "sources": ["TechCrunch"],
                "summary": "רכישה",
                "source_urls": [],
            },
        ]
        msg = format_brief_message(stories, "morning")
        assert "SEC approves Bitcoin ETF" in msg
        assert "Source: https://bloomberg.com/sec-etf" in msg
        assert "Use /write <n|x_url|https_url|text>" in msg

    def test_format_alert_message(self):
        alert = {
            "title": "CBDC pilot program",
            "sources": ["Bloomberg", "WSJ", "Yahoo"],
            "summary": "בנק מרכזי",
        }
        msg = format_alert_message(alert)
        assert "CBDC pilot program" in msg
        assert "Use /write <n|x_url|https_url|text>" in msg

    def test_start_output_lists_all_visible_commands(self):
        start_text = render_start_text()
        assert start_text.startswith("HFI Content Studio Bot is online.\n\nCommands:\n")
        for command in visible_start_commands():
            assert command.syntax in start_text

    def test_start_output_contract(self):
        expected = (
            "HFI Content Studio Bot is online.\n\n"
            "Commands:\n"
            "/brief [3|4|5|refresh] - Fetch the latest brief, limit the number of stories, or force a refresh.\n"
            "/story <n> - Show the source links and fuller context for story n from the latest brief.\n"
            "/lastbrief - Re-open the most recent brief without regenerating it.\n"
            "/write <n|x_url|https_url|text> - Turn a brief item, X post, article URL, or pasted text into Hebrew draft variants.\n"
            "/save <variant_index> - Save one variant from your last /write session as a draft in the queue.\n"
            "/queue - Show queue counts and the newest review-ready draft IDs.\n"
            "/draft <id> - Show the status, preview, and studio link for a saved draft.\n"
            "/approve <id> - Mark a saved draft as approved for the publishing workflow.\n"
            "/status - Show quick counts for drafts, scheduled, and published content.\n"
            "/schedule - Show the configured brief and alert automation times.\n"
            "/health - Check API and database health.\n"
            "/help - Show examples and supported input formats."
        )
        assert render_start_text() == expected
