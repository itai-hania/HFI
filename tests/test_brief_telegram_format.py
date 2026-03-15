"""Tests for themed Telegram brief formatting."""
import html
from telegram_bot.bot import (
    format_brief_message,
    _stories_in_theme_order,
    _slice_themes,
)


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


def test_stories_in_theme_order_flattens_correctly():
    """_stories_in_theme_order returns stories in theme-rendered order."""
    themes = [
        {"name": "A", "stories": [{"title": "S1"}, {"title": "S2"}]},
        {"name": "B", "stories": [{"title": "S3"}]},
    ]
    result = _stories_in_theme_order(themes)
    assert [s["title"] for s in result] == ["S1", "S2", "S3"]


def test_stories_in_theme_order_differs_from_flat():
    """When theme order differs from flat order, _stories_in_theme_order follows themes."""
    # Flat order: S1, S2, S3 — but themes reorder to S2, S3, S1
    themes = [
        {"name": "Group B", "stories": [{"title": "S2"}, {"title": "S3"}]},
        {"name": "Group A", "stories": [{"title": "S1"}]},
    ]
    result = _stories_in_theme_order(themes)
    assert [s["title"] for s in result] == ["S2", "S3", "S1"]


def test_slice_themes_limits_total_stories():
    """_slice_themes trims themes to fit within the requested count."""
    themes = [
        {"name": "A", "emoji": "X", "takeaway": "ta", "stories": [{"title": "S1"}, {"title": "S2"}, {"title": "S3"}]},
        {"name": "B", "emoji": "Y", "takeaway": "tb", "stories": [{"title": "S4"}, {"title": "S5"}]},
    ]
    sliced = _slice_themes(themes, 3)
    total = sum(len(t["stories"]) for t in sliced)
    assert total == 3
    # First theme contributes 3 stories, second theme is dropped
    assert len(sliced) == 1
    assert sliced[0]["name"] == "A"


def test_slice_themes_partial_second_theme():
    """_slice_themes includes partial second theme if count allows."""
    themes = [
        {"name": "A", "stories": [{"title": "S1"}, {"title": "S2"}]},
        {"name": "B", "stories": [{"title": "S3"}, {"title": "S4"}]},
    ]
    sliced = _slice_themes(themes, 3)
    assert len(sliced) == 2
    assert len(sliced[0]["stories"]) == 2
    assert len(sliced[1]["stories"]) == 1


def test_slice_themes_preserves_metadata():
    """_slice_themes keeps theme metadata (emoji, takeaway) intact."""
    themes = [
        {"name": "Tech", "emoji": "🤖", "takeaway": "AI is hot", "stories": [{"title": "S1"}]},
    ]
    sliced = _slice_themes(themes, 5)
    assert sliced[0]["emoji"] == "🤖"
    assert sliced[0]["takeaway"] == "AI is hot"
