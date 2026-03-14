"""Tests for themed Telegram brief formatting."""
import html
from telegram_bot.bot import format_brief_message


def _make_themed_response():
    return {
        "themes": [
            {
                "name": "Chip War Heats Up",
                "emoji": "\U0001f916",
                "takeaway": "AI spending is accelerating",
                "stories": [
                    {"title": "NVIDIA beats earnings", "summary": "Revenue surged", "sources": ["Bloomberg"], "source_urls": ["https://b.com"], "source_count": 1, "published_at": "2026-03-15T08:00:00+00:00", "relevance_score": 87},
                ],
            },
            {
                "name": "Israeli Tech Boom",
                "emoji": "\U0001f1ee\U0001f1f1",
                "takeaway": "Funding hits new high",
                "stories": [
                    {"title": "FinTech raises $50M", "summary": "Series C led by Sequoia", "sources": ["Investing.com"], "source_urls": ["https://inv.com"], "source_count": 1, "published_at": "2026-03-15T06:00:00+00:00", "relevance_score": 72},
                ],
            },
        ],
        "stories": [
            {"title": "NVIDIA beats earnings", "summary": "Revenue surged", "sources": ["Bloomberg"], "source_urls": ["https://b.com"], "source_count": 1, "published_at": "2026-03-15T08:00:00+00:00", "relevance_score": 87},
            {"title": "FinTech raises $50M", "summary": "Series C led by Sequoia", "sources": ["Investing.com"], "source_urls": ["https://inv.com"], "source_count": 1, "published_at": "2026-03-15T06:00:00+00:00", "relevance_score": 72},
        ],
    }


def test_themed_format_contains_theme_headers():
    data = _make_themed_response()
    msg = format_brief_message(data["stories"], "morning", themes=data["themes"])
    assert "Chip War Heats Up" in msg
    assert "Israeli Tech Boom" in msg
    assert "AI spending is accelerating" in msg


def test_themed_format_continuous_numbering():
    data = _make_themed_response()
    msg = format_brief_message(data["stories"], "morning", themes=data["themes"])
    assert "<b>1.</b>" in msg
    assert "<b>2.</b>" in msg


def test_themed_format_footer():
    data = _make_themed_response()
    msg = format_brief_message(data["stories"], "morning", themes=data["themes"])
    assert "/write N" in msg
    assert "/skip N" in msg


def test_legacy_format_without_themes():
    """When themes is empty/None, falls back to flat list."""
    stories = [
        {"title": "Test story", "summary": "Summary", "sources": ["CNBC"], "source_urls": ["https://cnbc.com"], "source_count": 1, "relevance_score": 50},
    ]
    msg = format_brief_message(stories, "morning", themes=[])
    assert "<b>1.</b>" in msg
    assert "Test story" in msg


def test_skip_extracts_keywords():
    """_extract_story_keywords should extract meaningful keywords."""
    from telegram_bot.bot import _extract_story_keywords

    keywords = _extract_story_keywords("NVIDIA beats earnings expectations with record revenue")
    assert "nvidia" in keywords
    assert "earnings" in keywords
    assert "the" not in keywords  # stopword removed
