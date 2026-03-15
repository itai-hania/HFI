# tests/test_brief_themer.py
"""Tests for BriefThemer — AI-powered story grouping."""

import json
import pytest
from unittest.mock import patch, MagicMock

from processor.brief_themer import BriefThemer


@pytest.fixture
def sample_stories():
    return [
        {"title": "NVIDIA beats earnings expectations", "summary": "Revenue surged 122%", "sources": ["Bloomberg", "CNBC"], "source_urls": ["https://b.com", "https://c.com"], "source_count": 2, "published_at": "2026-03-15T08:00:00+00:00", "relevance_score": 87},
        {"title": "OpenAI launches enterprise agents", "summary": "New AI platform for business", "sources": ["TechCrunch"], "source_urls": ["https://tc.com"], "source_count": 1, "published_at": "2026-03-15T07:00:00+00:00", "relevance_score": 65},
        {"title": "Israeli FinTech raises $50M", "summary": "Series C led by Sequoia", "sources": ["Investing.com", "Google News Israel"], "source_urls": ["https://inv.com", "https://gn.com"], "source_count": 2, "published_at": "2026-03-15T06:00:00+00:00", "relevance_score": 72},
        {"title": "Fed holds rates steady", "summary": "Markets rally on decision", "sources": ["CNBC", "MarketWatch"], "source_urls": ["https://cnbc.com", "https://mw.com"], "source_count": 2, "published_at": "2026-03-15T05:00:00+00:00", "relevance_score": 80},
    ]


def test_themer_returns_valid_structure(sample_stories):
    """Themes must have name, emoji, takeaway, and stories."""
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = json.dumps({
        "themes": [
            {"name": "AI Spending Surge", "emoji": "\U0001f916", "takeaway": "AI investment accelerating", "story_indices": [0, 1]},
            {"name": "Markets Digest Fed", "emoji": "\U0001f4b0", "takeaway": "Rate decision lifts stocks", "story_indices": [3]},
            {"name": "Israeli Tech Boom", "emoji": "\U0001f1ee\U0001f1f1", "takeaway": "Funding hits new high", "story_indices": [2]},
        ]
    })

    with patch("processor.brief_themer.OpenAI") as mock_openai:
        mock_openai.return_value.chat.completions.create.return_value = mock_response
        themer = BriefThemer()
        themes = themer.generate_themes(sample_stories)

    assert len(themes) == 3
    for theme in themes:
        assert "name" in theme
        assert "emoji" in theme
        assert "takeaway" in theme
        assert "stories" in theme
        assert len(theme["stories"]) > 0


def test_themer_fallback_on_api_error(sample_stories):
    """On OpenAI error, falls back to rule-based grouping."""
    with patch("processor.brief_themer.OpenAI") as mock_openai:
        mock_openai.return_value.chat.completions.create.side_effect = Exception("API down")
        themer = BriefThemer()
        themes = themer.generate_themes(sample_stories)

    assert len(themes) >= 1
    for theme in themes:
        assert "name" in theme
        assert "stories" in theme


def test_themer_all_stories_assigned(sample_stories):
    """Every story must appear in exactly one theme."""
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = json.dumps({
        "themes": [
            {"name": "Tech", "emoji": "\U0001f916", "takeaway": "AI is hot", "story_indices": [0, 1]},
            {"name": "Finance", "emoji": "\U0001f4b0", "takeaway": "Fed holds", "story_indices": [3]},
            {"name": "Israel", "emoji": "\U0001f1ee\U0001f1f1", "takeaway": "Funding up", "story_indices": [2]},
        ]
    })

    with patch("processor.brief_themer.OpenAI") as mock_openai:
        mock_openai.return_value.chat.completions.create.return_value = mock_response
        themer = BriefThemer()
        themes = themer.generate_themes(sample_stories)

    all_titles = {s["title"] for s in sample_stories}
    themed_titles = set()
    for theme in themes:
        for story in theme["stories"]:
            themed_titles.add(story["title"])
    assert themed_titles == all_titles


def test_themer_handles_invalid_json(sample_stories):
    """Invalid JSON response triggers fallback."""
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = "not json at all"

    with patch("processor.brief_themer.OpenAI") as mock_openai:
        mock_openai.return_value.chat.completions.create.return_value = mock_response
        themer = BriefThemer()
        themes = themer.generate_themes(sample_stories)

    assert len(themes) >= 1
