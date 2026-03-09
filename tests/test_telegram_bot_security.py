"""Security tests for Telegram formatting helpers and chat authorization."""

from telegram_bot.bot import HFIBot, format_alert_message, format_brief_message


def test_brief_message_escapes_html():
    stories = [
        {
            "title": "<script>alert(1)</script>",
            "sources": ["<b>Bad</b>"],
            "summary": "<i>Summary</i>",
        }
    ]
    rendered = format_brief_message(stories, "morning")
    assert "<script>" not in rendered
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in rendered


def test_alert_message_escapes_html():
    alert = {
        "title": "<b>owned</b>",
        "sources": ["<img src=x onerror=1>"],
        "summary": "<a href='x'>x</a>",
    }
    rendered = format_alert_message(alert)
    assert "<img" not in rendered
    assert "&lt;b&gt;owned&lt;/b&gt;" in rendered


def test_is_authorized_chat_accepts_configured_chat_id():
    bot = HFIBot.__new__(HFIBot)
    bot.chat_id = "12345"

    class _Chat:
        id = 12345

    class _Update:
        effective_chat = _Chat()

    assert bot._is_authorized_chat(_Update()) is True


def test_is_authorized_chat_rejects_other_chat_id():
    bot = HFIBot.__new__(HFIBot)
    bot.chat_id = "12345"

    class _Chat:
        id = 99999

    class _Update:
        effective_chat = _Chat()

    assert bot._is_authorized_chat(_Update()) is False
