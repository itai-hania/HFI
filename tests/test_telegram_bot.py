"""Tests for Telegram command rendering and message formatting."""

import re
from datetime import datetime, timedelta, timezone

import pytest

from common.url_validation import URLValidationError, validate_x_status_url
from telegram_bot.bot import format_alert_message, format_brief_message
from telegram_bot.command_catalog import render_start_text, visible_start_commands


class TestTelegramBotFormatting:
    def test_format_brief_message(self):
        stories = [
            {
                "title": "SEC approves Bitcoin ETF",
                "sources": ["Bloomberg", "WSJ"],
                "summary": "רגולציה חדשה",
                "source_urls": ["https://bloomberg.com/sec-etf", "https://wsj.com/etf"],
                "source_count": 2,
                "published_at": None,
                "relevance_score": 75,
            },
            {
                "title": "Stripe acquires startup",
                "sources": ["TechCrunch"],
                "summary": "רכישה",
                "source_urls": [],
                "source_count": 1,
                "published_at": None,
                "relevance_score": 40,
            },
        ]
        msg = format_brief_message(stories, "morning")
        assert "SEC approves Bitcoin ETF" in msg
        assert "<b>" in msg, "Must use HTML bold tags"
        assert '<a href="https://bloomberg.com/sec-etf">Bloomberg</a>' in msg
        assert "/write N to create" in msg

    def test_format_alert_message(self):
        alert = {
            "title": "CBDC pilot program",
            "sources": ["Bloomberg", "WSJ", "Yahoo"],
            "source_urls": ["https://b.com", "https://wsj.com", "https://yf.com"],
            "summary": "בנק מרכזי",
            "source_count": 3,
        }
        msg = format_alert_message(alert)
        assert "CBDC pilot program" in msg
        assert "<b>" in msg, "Must use HTML bold tags"
        assert "📡 3 sources" in msg
        assert "/write alert to create content" in msg

    def test_brief_message_uses_html(self):
        stories = [
            {
                "title": "Fed Signals Rate Cut",
                "summary": "Powell says more data needed.",
                "sources": ["Bloomberg", "WSJ"],
                "source_urls": ["https://bloomberg.com/1", "https://wsj.com/1"],
                "source_count": 2,
                "published_at": "2026-03-13T07:00:00Z",
                "relevance_score": 87,
            }
        ]
        msg = format_brief_message(stories, "morning")
        assert "<b>" in msg, "Must use HTML bold tags"
        assert "Morning Brief" in msg
        assert "87" in msg, "Relevance score must be shown"
        assert "2 sources" in msg or "📡 2" in msg, "Source count must be shown"
        assert "<a href=" in msg, "Source links must be HTML anchors"

    def test_brief_message_shows_story_age(self):
        recent = datetime.now(timezone.utc) - timedelta(hours=2)
        stories = [
            {
                "title": "Test Story",
                "summary": "Summary here.",
                "sources": ["Bloomberg"],
                "source_urls": ["https://bloomberg.com/1"],
                "source_count": 1,
                "published_at": recent.isoformat(),
                "relevance_score": 50,
            }
        ]
        msg = format_brief_message(stories, "on-demand")
        assert "2h ago" in msg, "Story age should be shown"

    def test_brief_message_shows_generation_timestamp(self):
        stories = [{"title": "Test", "summary": "", "sources": ["WSJ"],
                     "source_urls": ["https://wsj.com"], "source_count": 1,
                     "published_at": None, "relevance_score": 30}]
        msg = format_brief_message(stories, "morning")
        assert re.search(r'\d{1,2}:\d{2}', msg), "Generation timestamp must be shown"

    def test_brief_message_israel_badge(self):
        stories = [{"title": "Wix Growth", "summary": "Strong quarter.",
                     "sources": ["Calcalist", "Globes"],
                     "source_urls": ["https://calcalist.com/1", "https://globes.com/1"],
                     "source_count": 2, "published_at": None, "relevance_score": 60}]
        msg = format_brief_message(stories, "morning")
        assert "🔵" in msg or "Israel" in msg, "Israel badge should appear"

    def test_alert_message_shows_source_count(self):
        alert = {
            "title": "NASDAQ Drops 3%",
            "summary": "Markets react to inflation data.",
            "sources": ["Bloomberg", "WSJ", "Yahoo Finance"],
            "source_urls": ["https://b.com", "https://wsj.com", "https://yf.com"],
            "source_count": 3,
        }
        msg = format_alert_message(alert)
        assert "<b>" in msg, "Must use HTML bold"
        assert "3 sources" in msg or "📡 3" in msg
        assert "<a href=" in msg, "Source links must be clickable"

    def test_start_output_lists_all_visible_commands(self):
        start_text = render_start_text()
        assert start_text.startswith("HFI Content Studio Bot is online.\n\nCommands:\n")
        for command in visible_start_commands():
            assert command.syntax in start_text

    def test_start_output_contract(self):
        expected = (
            "HFI Content Studio Bot is online.\n\n"
            "Commands:\n"
            "/brief [1-8|refresh] - Fetch the latest brief, limit the number of stories, or force a refresh.\n"
            "/story <n> - Show the source links and fuller context for story n from the latest brief.\n"
            "/lastbrief - Re-open the most recent brief without regenerating it.\n"
            "/write <n|x_url|https_url|text> - Turn a brief item, X post, article URL, or pasted text into Hebrew draft variants.\n"
            "/save <variant_index> - Save one variant from your last /write session as a draft in the queue.\n"
            "/queue - Show queue counts and the newest review-ready draft IDs.\n"
            "/draft <id> - Show the status, preview, and studio link for a saved draft.\n"
            "/approve <id> - Mark a saved draft as approved for the publishing workflow.\n"
            "/status - Show quick counts for drafts, scheduled, and published content.\n"
            "/schedule - Show the configured brief and alert automation times.\n"
            "/scrape <url> - Scrape an X thread, translate it, and save as a draft.\n"
            "/xtrends - Show the top trending topics on X.\n"
            "/health - Check API and database health.\n"
            "/help - Show examples and supported input formats."
        )
        assert render_start_text() == expected

    def test_brief_input_accepts_1_to_8(self):
        """_brief_input should accept any number 1-8, not just 3/4/5."""
        from telegram_bot.bot import HFIBot

        assert HFIBot._brief_input(["1"]) == (1, False)
        assert HFIBot._brief_input(["6"]) == (6, False)
        assert HFIBot._brief_input(["8"]) == (8, False)
        assert HFIBot._brief_input(["refresh"]) == (5, True)
        assert HFIBot._brief_input([]) == (5, False)

        import pytest
        with pytest.raises(ValueError):
            HFIBot._brief_input(["9"])
        with pytest.raises(ValueError):
            HFIBot._brief_input(["0"])


class TestXUrlValidation:
    def test_validate_x_status_url_accepts_valid(self):
        result = validate_x_status_url("https://x.com/user/status/123456789")
        assert "x.com" in result
        assert "123456789" in result

    def test_validate_x_status_url_accepts_twitter_domain(self):
        result = validate_x_status_url("https://twitter.com/user/status/999")
        assert "twitter.com" in result

    def test_validate_x_status_url_rejects_non_x(self):
        with pytest.raises((URLValidationError, ValueError)):
            validate_x_status_url("https://google.com/something")

    def test_validate_x_status_url_rejects_x_non_status(self):
        with pytest.raises((URLValidationError, ValueError)):
            validate_x_status_url("https://x.com/user/likes")


def test_bot_commands_list():
    """Verify bot_commands() returns BotCommand-compatible tuples for set_my_commands."""
    from telegram_bot.command_catalog import bot_commands
    commands = bot_commands()
    assert len(commands) == 10
    names = [c[0] for c in commands]
    assert "brief" in names
    assert "start" in names
    assert "help" in names
    assert "lastbrief" not in names
    assert "queue" not in names
    assert "draft" not in names
    assert "approve" not in names
    assert "status" not in names
    for name, description in commands:
        assert isinstance(name, str)
        assert isinstance(description, str)
        assert len(description) <= 256


class TestNewCommandsInCatalog:
    def test_scrape_in_start_text(self):
        text = render_start_text()
        assert "/scrape" in text

    def test_xtrends_in_start_text(self):
        text = render_start_text()
        assert "/xtrends" in text

    def test_scrape_visible_in_start_commands(self):
        names = [cmd.name for cmd in visible_start_commands()]
        assert "scrape" in names
        assert "xtrends" in names
