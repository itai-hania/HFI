"""
Unit tests for dashboard pure helper functions.

Tests get_source_badge_class, parse_media_info, and format_status_str
without any Streamlit dependency.

Run with: pytest tests/test_dashboard_helpers.py -v
"""

import pytest
import json

from dashboard.helpers import get_source_badge_class, parse_media_info, format_status_str


# ==================== get_source_badge_class ====================

class TestGetSourceBadgeClass:
    """Test CSS class mapping for source badges."""

    @pytest.mark.parametrize("source,expected", [
        ("Yahoo Finance", "source-yahoo-finance"),
        ("WSJ", "source-wsj"),
        ("TechCrunch", "source-techcrunch"),
        ("Bloomberg", "source-bloomberg"),
        ("MarketWatch", "source-marketwatch"),
        ("Manual", "source-manual"),
        ("X", "source-x"),
    ])
    def test_known_sources(self, source, expected):
        assert get_source_badge_class(source) == expected

    def test_unknown_source_returns_manual(self):
        assert get_source_badge_class("UnknownSource") == "source-manual"

    def test_empty_string_returns_manual(self):
        assert get_source_badge_class("") == "source-manual"

    def test_case_sensitive(self):
        assert get_source_badge_class("wsj") == "source-manual"
        assert get_source_badge_class("WSJ") == "source-wsj"


# ==================== parse_media_info ====================

class TestParseMediaInfo:
    """Test media JSON parsing."""

    def test_empty_string(self):
        count, label = parse_media_info("")
        assert count == 0
        assert label == ""

    def test_none_input(self):
        count, label = parse_media_info(None)
        assert count == 0
        assert label == ""

    def test_single_photo(self):
        data = json.dumps([{"type": "photo", "path": "/media/img.jpg"}])
        count, label = parse_media_info(data)
        assert count == 1
        assert label == "Image"

    def test_single_video(self):
        data = json.dumps([{"type": "video", "path": "/media/vid.mp4"}])
        count, label = parse_media_info(data)
        assert count == 1
        assert label == "Video"

    def test_video_preferred_over_photo(self):
        data = json.dumps([
            {"type": "photo", "path": "/media/img.jpg"},
            {"type": "video", "path": "/media/vid.mp4"},
        ])
        count, label = parse_media_info(data)
        assert count == 2
        assert label == "Video"

    def test_multiple_photos(self):
        data = json.dumps([
            {"type": "photo", "path": "/media/img1.jpg"},
            {"type": "photo", "path": "/media/img2.jpg"},
            {"type": "photo", "path": "/media/img3.jpg"},
        ])
        count, label = parse_media_info(data)
        assert count == 3
        assert label == "Image"

    def test_no_type_field(self):
        data = json.dumps([{"path": "/media/file.bin"}])
        count, label = parse_media_info(data)
        assert count == 1
        assert label == ""

    def test_invalid_json(self):
        count, label = parse_media_info("{bad json")
        assert count == 0
        assert label == ""

    def test_non_list_json(self):
        count, label = parse_media_info('"just a string"')
        assert count == 0
        assert label == ""

    def test_empty_list(self):
        count, label = parse_media_info("[]")
        assert count == 0
        assert label == ""


# ==================== format_status_str ====================

class TestFormatStatusStr:
    """Test status enum/string formatting."""

    def test_enum_with_value(self):
        class FakeEnum:
            value = "processed"
        assert format_status_str(FakeEnum()) == "processed"

    def test_plain_string(self):
        assert format_status_str("pending") == "pending"

    def test_real_tweet_status(self):
        from common.models import TweetStatus
        assert format_status_str(TweetStatus.PENDING) == "pending"
        assert format_status_str(TweetStatus.APPROVED) == "approved"
        assert format_status_str(TweetStatus.PUBLISHED) == "published"
        assert format_status_str(TweetStatus.FAILED) == "failed"

    def test_integer_fallback(self):
        assert format_status_str(42) == "42"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
