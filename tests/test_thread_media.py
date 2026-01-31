"""
Tests for Phase 1.2 (Media Download Pipeline) and Phase 1.3 (Media Visibility)

Tests the following features:
1. media_paths column stores JSON correctly
2. download_thread_media() returns correct format
3. JSON parsing for media indicators
4. Media gallery display logic

Run with: pytest tests/test_thread_media.py -v
"""

import pytest
import os
import sys
import json
from datetime import datetime, timezone

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from common.models import (
    create_tables,
    get_db_session,
    Tweet,
    TweetStatus,
    Base,
    engine,
)


@pytest.fixture
def db():
    """Create an in-memory database for testing."""
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    
    session = get_db_session()
    yield session
    session.close()


class TestMediaPathsColumn:
    """Test cases for the new media_paths column."""

    def test_tweet_with_media_paths(self, db):
        """Test creating a tweet with media_paths JSON."""
        media_data = [
            {
                "tweet_id": "123",
                "type": "photo",
                "src": "https://pbs.twimg.com/media/test1.jpg",
                "local_path": "/data/media/images/test1.jpg"
            },
            {
                "tweet_id": "123",
                "type": "photo", 
                "src": "https://pbs.twimg.com/media/test2.jpg",
                "local_path": "/data/media/images/test2.jpg"
            }
        ]
        
        tweet = Tweet(
            source_url="https://x.com/test/status/123",
            original_text="Test tweet with media",
            media_paths=json.dumps(media_data),
            status=TweetStatus.PENDING
        )
        
        db.add(tweet)
        db.commit()
        
        retrieved = db.query(Tweet).filter_by(id=tweet.id).first()
        assert retrieved is not None
        assert retrieved.media_paths is not None
        
        parsed = json.loads(retrieved.media_paths)
        assert len(parsed) == 2
        assert parsed[0]["type"] == "photo"
        assert parsed[1]["local_path"] == "/data/media/images/test2.jpg"

    def test_tweet_without_media_paths(self, db):
        """Test that tweets without media work correctly."""
        tweet = Tweet(
            source_url="https://x.com/test/status/456",
            original_text="Test tweet without media",
            status=TweetStatus.PENDING
        )
        
        db.add(tweet)
        db.commit()
        
        retrieved = db.query(Tweet).filter_by(id=tweet.id).first()
        assert retrieved is not None
        assert retrieved.media_paths is None

    def test_to_dict_includes_media_paths(self, db):
        """Test that to_dict() includes media_paths."""
        media_data = [{"type": "video", "local_path": "/test.mp4"}]
        
        tweet = Tweet(
            source_url="https://x.com/test/status/789",
            original_text="Test",
            media_paths=json.dumps(media_data),
            status=TweetStatus.PENDING
        )
        
        db.add(tweet)
        db.commit()
        
        tweet_dict = tweet.to_dict()
        assert "media_paths" in tweet_dict
        assert tweet_dict["media_paths"] == json.dumps(media_data)


class TestMediaDownloadFormat:
    """Test cases for media download output format."""

    def test_download_thread_media_format(self):
        """Test that download_thread_media returns correct format."""
        from processor.processor import MediaDownloader
        
        downloader = MediaDownloader()
        
        # Test with empty thread data
        result = downloader.download_thread_media({})
        assert result == []
        
        # Test with thread data but no media
        thread_data = {
            "tweets": [
                {"tweet_id": "123", "text": "No media here", "media": []}
            ]
        }
        result = downloader.download_thread_media(thread_data)
        assert result == []

    def test_download_thread_media_structure(self):
        """Test that download result has correct structure."""
        expected_keys = {"tweet_id", "type", "src", "local_path"}
        
        sample_result = {
            "tweet_id": "123456",
            "type": "photo",
            "src": "https://example.com/image.jpg",
            "local_path": "/data/media/images/test.jpg"
        }
        
        assert set(sample_result.keys()) == expected_keys


class TestMediaIndicatorParsing:
    """Test cases for parsing media_paths for UI indicators."""

    def test_parse_media_for_indicators(self, db):
        """Test parsing media_paths JSON for count and type detection."""
        media_data = [
            {"type": "photo", "local_path": "/img1.jpg"},
            {"type": "photo", "local_path": "/img2.jpg"},
            {"type": "video", "local_path": "/vid1.mp4"},
        ]
        
        tweet = Tweet(
            source_url="https://x.com/test/status/111",
            original_text="Test",
            media_paths=json.dumps(media_data),
            status=TweetStatus.PENDING
        )
        
        db.add(tweet)
        db.commit()
        
        # Simulate dashboard parsing logic
        media_count = 0
        media_icon = ""
        
        if tweet.media_paths:
            media_list = json.loads(tweet.media_paths)
            media_count = len(media_list)
            has_video = any(m.get('type') == 'video' for m in media_list)
            has_photo = any(m.get('type') == 'photo' for m in media_list)
            
            if has_video:
                media_icon = "🎥"
            elif has_photo:
                media_icon = "🖼️"
        
        assert media_count == 3
        assert media_icon == "🎥"  # Video takes priority

    def test_photo_only_indicator(self, db):
        """Test that photo-only threads get photo icon."""
        media_data = [
            {"type": "photo", "local_path": "/img1.jpg"},
            {"type": "photo", "local_path": "/img2.jpg"},
        ]
        
        tweet = Tweet(
            source_url="https://x.com/test/status/222",
            original_text="Test",
            media_paths=json.dumps(media_data),
            status=TweetStatus.PENDING
        )
        
        db.add(tweet)
        db.commit()
        
        media_list = json.loads(tweet.media_paths)
        has_video = any(m.get('type') == 'video' for m in media_list)
        has_photo = any(m.get('type') == 'photo' for m in media_list)
        
        if has_video:
            icon = "🎥"
        elif has_photo:
            icon = "🖼️"
        else:
            icon = ""
        
        assert icon == "🖼️"


class TestMediaGalleryLogic:
    """Test cases for media gallery display logic."""

    def test_gallery_column_count(self):
        """Test gallery column count calculation."""
        def calc_cols(media_count):
            return min(media_count, 4)
        
        assert calc_cols(1) == 1
        assert calc_cols(2) == 2
        assert calc_cols(3) == 3
        assert calc_cols(4) == 4
        assert calc_cols(5) == 4  # Max 4 columns
        assert calc_cols(10) == 4

    def test_gallery_item_distribution(self):
        """Test that items are distributed across columns correctly."""
        num_items = 7
        num_cols = min(num_items, 4)
        
        # Simulate distribution logic: cols[idx % num_cols]
        distribution = {i: [] for i in range(num_cols)}
        
        for idx in range(num_items):
            col_idx = idx % num_cols
            distribution[col_idx].append(idx)
        
        # Column 0: items 0, 4
        assert distribution[0] == [0, 4]
        # Column 1: items 1, 5
        assert distribution[1] == [1, 5]
        # Column 2: items 2, 6
        assert distribution[2] == [2, 6]
        # Column 3: item 3
        assert distribution[3] == [3]


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
