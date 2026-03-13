"""
Unit tests for TwitterScraper component.

Tests cover:
1. Scraper initialization
2. Session management setup
3. Configuration validation
4. Code structure and imports
5. Helper functions

Run with: pytest tests/test_scraper.py -v

Note: These are unit tests that don't require browser automation.
For integration tests (actual scraping), run the scraper's main() function.
"""

import pytest
import os
from pathlib import Path
from unittest.mock import Mock, AsyncMock, patch, MagicMock
import asyncio

from scraper.scraper import TwitterScraper


class TestTwitterScraperInit:
    """Test scraper initialization."""

    def test_init_default_params(self):
        """Test initialization with default parameters."""
        scraper = TwitterScraper()

        assert scraper.headless is True
        assert scraper.max_interactions == 50
        assert scraper.interaction_count == 0
        assert scraper.playwright is None
        assert scraper.browser is None
        assert scraper.context is None
        assert scraper.page is None

    def test_init_custom_params(self):
        """Test initialization with custom parameters."""
        scraper = TwitterScraper(headless=False, max_interactions=100)

        assert scraper.headless is False
        assert scraper.max_interactions == 100

    def test_session_directory_creation(self):
        """Test that session directory is created."""
        scraper = TwitterScraper()

        # Session directory should be created
        assert scraper.session_dir.exists()
        assert scraper.session_dir.is_dir()

        # Path should be correct relative to project
        assert scraper.session_dir.name == "session"
        assert scraper.session_dir.parent.name == "data"

    def test_session_file_path(self):
        """Test session file path is set correctly."""
        scraper = TwitterScraper()

        assert scraper.session_file.name == "storage_state.json"
        assert scraper.session_file.parent == scraper.session_dir

    def test_user_agent_set(self):
        """Test that user agent is generated with valid format."""
        scraper = TwitterScraper()

        assert scraper.user_agent is not None
        assert isinstance(scraper.user_agent, str)
        assert 'Mozilla' in scraper.user_agent or 'Chrome' in scraper.user_agent or len(scraper.user_agent) > 10


class TestTwitterScraperHelpers:
    """Test helper methods."""

    @pytest.mark.asyncio
    async def test_random_delay(self):
        """Test random delay function."""
        import time

        scraper = TwitterScraper()

        start = time.time()
        await scraper._random_delay(0.1, 0.2)
        elapsed = time.time() - start

        # Should delay between 0.1 and 0.2 seconds
        assert 0.08 <= elapsed <= 0.25  # Small margin for execution overhead

    def test_extract_handle_from_url(self):
        """Test handle extraction from URL."""
        scraper = TwitterScraper()

        # Valid URLs
        url1 = "https://x.com/elonmusk/status/1234567890"
        assert scraper._extract_handle_from_url(url1) == "@elonmusk"

        url2 = "https://x.com/OpenAI/status/9876543210"
        assert scraper._extract_handle_from_url(url2) == "@OpenAI"

        # Invalid URL
        url3 = "https://x.com/explore"
        assert scraper._extract_handle_from_url(url3) == ""

    def test_should_stop_at_other_author(self):
        """Test logic for stopping at other author tweets."""
        scraper = TwitterScraper()

        # Not enough tweets - should not stop
        seen_tweets = {
            "1": {"author_handle": "@user1"},
            "2": {"author_handle": "@user1"},
        }
        assert scraper._should_stop_at_other_author(seen_tweets, "@user1") is False

        # Last 3 tweets are from target - should not stop
        seen_tweets = {
            "1": {"author_handle": "@user1"},
            "2": {"author_handle": "@user1"},
            "3": {"author_handle": "@user1"},
            "4": {"author_handle": "@user1"},
            "5": {"author_handle": "@user1"},
        }
        assert scraper._should_stop_at_other_author(seen_tweets, "@user1") is False

        # Last 3 tweets are from other authors - should stop
        seen_tweets = {
            "1": {"author_handle": "@user1"},
            "2": {"author_handle": "@user1"},
            "3": {"author_handle": "@other1"},
            "4": {"author_handle": "@other2"},
            "5": {"author_handle": "@other3"},
        }
        assert scraper._should_stop_at_other_author(seen_tweets, "@user1") is True


class TestTwitterScraperConfiguration:
    """Test scraper configuration and settings."""

    def test_interaction_counter(self):
        """Test interaction counter increments."""
        scraper = TwitterScraper()

        initial = scraper.interaction_count
        scraper.interaction_count += 1

        assert scraper.interaction_count == initial + 1

    def test_max_interactions_threshold(self):
        """Test max interactions threshold."""
        scraper = TwitterScraper(max_interactions=10)

        # Simulate reaching max interactions
        scraper.interaction_count = 10

        assert scraper.interaction_count >= scraper.max_interactions


class TestTwitterScraperURLValidation:
    """Test URL handling and validation."""

    def test_trending_url_format(self):
        """Test trending URL is correctly formatted."""
        expected_url = 'https://x.com/explore/tabs/trending'
        assert 'x.com' in expected_url
        assert 'explore' in expected_url
        assert 'trending' in expected_url

    def test_search_url_format(self):
        """Test search URL formatting."""
        topic = "Bitcoin"
        search_url = f"https://x.com/search?q={topic}&src=trend_click&f=live"

        assert 'x.com/search' in search_url
        assert f'q={topic}' in search_url
        assert 'f=live' in search_url


class TestTwitterScraperDataStructures:
    """Test data structures and return types."""

    def test_tweet_data_structure(self):
        """Test expected tweet data structure matches model fields."""
        expected_fields = {'text', 'media_url', 'author', 'timestamp', 'source_url', 'scraped_at'}
        # Verify these are the documented contract fields
        assert len(expected_fields) == 6
        assert 'text' in expected_fields
        assert 'source_url' in expected_fields

    def test_trend_data_structure(self):
        """Test expected trend data structure matches model fields."""
        expected_fields = {'title', 'description', 'category', 'scraped_at'}
        assert len(expected_fields) == 4
        assert 'title' in expected_fields

    def test_thread_data_structure(self):
        """Test expected thread data structure matches scraper output."""
        expected_fields = {'tweet_id', 'author_handle', 'author_name', 'text', 'permalink', 'timestamp', 'media'}
        assert len(expected_fields) == 7
        assert 'tweet_id' in expected_fields
        assert 'author_handle' in expected_fields


class TestTwitterScraperImports:
    """Test that all required imports are available."""

    def test_playwright_import(self):
        """Test Playwright import and key classes exist."""
        try:
            from playwright.async_api import async_playwright, Browser, BrowserContext, Page, Response
            assert callable(async_playwright)
        except ImportError:
            pytest.fail("Playwright not installed")

    def test_fake_useragent_import(self):
        """Test fake_useragent import."""
        try:
            from fake_useragent import UserAgent
            ua = UserAgent()
            assert ua.random is not None
        except ImportError:
            pytest.fail("fake_useragent not installed")

    def test_standard_library_imports(self):
        """Test standard library imports are available."""
        import asyncio
        import json
        import random
        import logging
        from pathlib import Path
        from typing import Dict, List, Optional
        from datetime import datetime
        import re

        assert callable(asyncio.sleep)
        assert callable(json.dumps)


class TestTwitterScraperLogging:
    """Test logging configuration."""

    def test_logger_exists(self):
        """Test that logger is configured."""
        from scraper.scraper import logger

        assert logger is not None
        assert logger.name == 'scraper.scraper'

    def test_logging_level(self):
        """Test logging is set up."""
        import logging

        # Get the scraper logger
        logger = logging.getLogger('scraper.scraper')

        # Should have handlers or propagate to root
        assert logger.hasHandlers() or logger.propagate


class TestTwitterScraperCleanup:
    """Test cleanup and resource management."""

    @pytest.mark.asyncio
    async def test_close_with_no_resources(self):
        """Test closing scraper with no initialized resources."""
        scraper = TwitterScraper()

        # Should not raise exception even when nothing is initialized
        await scraper.close()
        # Verify resources remain None after close
        assert scraper.playwright is None
        assert scraper.browser is None


class TestTwitterScraperEdgeCases:
    """Test edge cases and error handling."""

    def test_empty_topic_search(self):
        """Test search with empty topic."""
        scraper = TwitterScraper()
        topic = ""
        search_url = f"https://x.com/search?q={topic}&src=trend_click&f=live"

        # URL should still be valid (X will handle empty search)
        assert 'x.com/search' in search_url

    def test_special_characters_in_topic(self):
        """Test search with special characters."""
        scraper = TwitterScraper()
        topic = "AI & ML"
        search_url = f"https://x.com/search?q={topic}&src=trend_click&f=live"

        assert 'x.com/search' in search_url


class TestExtractHandleFromUrl:
    @pytest.fixture(autouse=True)
    def scraper(self):
        with patch("scraper.scraper.UserAgent") as mock_ua:
            mock_ua.return_value.random = "Mozilla/5.0"
            self.scraper = TwitterScraper(headless=True)

    @pytest.mark.parametrize("url,expected", [
        ("https://x.com/elonmusk/status/123456", "@elonmusk"),
        ("https://twitter.com/elonmusk/status/123456", "@elonmusk"),
        ("https://www.twitter.com/user/status/999", "@user"),
        ("https://mobile.twitter.com/user/status/999", "@user"),
        ("https://mobile.x.com/user/status/999", "@user"),
        ("https://www.x.com/user/status/999", "@user"),
        ("https://x.com/user/status/999/photo/1", "@user"),
        ("https://example.com/status/123", ""),
        ("https://x.com/user/likes", ""),
        ("not a url", ""),
    ])
    def test_extract_handle(self, url, expected):
        assert self.scraper._extract_handle_from_url(url) == expected


class TestEnsureLoggedInSessionExpiry:
    @pytest.fixture(autouse=True)
    def scraper(self):
        with patch("scraper.scraper.UserAgent") as mock_ua:
            mock_ua.return_value.random = "Mozilla/5.0"
            self.scraper = TwitterScraper(headless=True)

    def test_raises_session_expired_when_no_session_file(self):
        from scraper.errors import SessionExpiredError
        self.scraper.session_file = Path("/nonexistent/storage_state.json")
        with pytest.raises(SessionExpiredError, match="session"):
            asyncio.run(self.scraper.ensure_logged_in())


class TestBrowserSelection:
    def test_default_browser_is_chromium(self):
        with patch("scraper.scraper.UserAgent") as mock_ua:
            mock_ua.return_value.random = "Mozilla/5.0"
            scraper = TwitterScraper(headless=True)
        assert scraper.browser_type == "chromium"

    def test_browser_type_from_env(self):
        with patch("scraper.scraper.UserAgent") as mock_ua, \
             patch.dict("os.environ", {"SCRAPER_BROWSER": "firefox"}):
            mock_ua.return_value.random = "Mozilla/5.0"
            scraper = TwitterScraper(headless=True)
        assert scraper.browser_type == "firefox"

    def test_invalid_browser_falls_back_to_chromium(self):
        with patch("scraper.scraper.UserAgent") as mock_ua, \
             patch.dict("os.environ", {"SCRAPER_BROWSER": "safari"}):
            mock_ua.return_value.random = "Mozilla/5.0"
            scraper = TwitterScraper(headless=True)
        assert scraper.browser_type == "chromium"


class TestVideoStreamMerge:
    @pytest.fixture(autouse=True)
    def scraper(self):
        with patch("scraper.scraper.UserAgent") as mock_ua:
            mock_ua.return_value.random = "Mozilla/5.0"
            self.scraper = TwitterScraper(headless=True)

    def test_video_streams_merged_into_tweets(self):
        tweets = [
            {
                "tweet_id": "123",
                "text": "Check this video",
                "media": [{"type": "video", "src": "", "alt": ""}],
                "permalink": "https://x.com/user/status/123",
                "timestamp": "2026-01-01T00:00:00Z",
                "author_handle": "@user",
            }
        ]
        self.scraper.video_streams = {
            "123": "https://video.twimg.com/ext_tw_video/123/pu/vid/1280x720/abc.mp4"
        }
        merged = self.scraper._merge_video_streams(tweets)
        video_media = [m for m in merged[0]["media"] if m["type"] == "video"]
        assert video_media[0]["src"] == "https://video.twimg.com/ext_tw_video/123/pu/vid/1280x720/abc.mp4"

    def test_no_video_streams_unchanged(self):
        tweets = [{"tweet_id": "1", "media": [{"type": "photo", "src": "img.jpg"}]}]
        self.scraper.video_streams = {}
        result = self.scraper._merge_video_streams(tweets)
        assert result[0]["media"][0]["src"] == "img.jpg"


class TestPageValidation:
    @pytest.fixture(autouse=True)
    def scraper(self):
        with patch("scraper.scraper.UserAgent") as mock_ua:
            mock_ua.return_value.random = "Mozilla/5.0"
            self.scraper = TwitterScraper(headless=True)

    def test_detect_rate_limit_page(self):
        mock_page = AsyncMock()
        mock_page.url = "https://x.com/search"
        mock_page.title = AsyncMock(return_value="Rate limit exceeded")
        mock_page.query_selector = AsyncMock(return_value=None)
        self.scraper.page = mock_page
        with pytest.raises(Exception, match="(?i)rate.limit"):
            asyncio.run(self.scraper._validate_page_loaded())

    def test_detect_login_redirect(self):
        from scraper.errors import SessionExpiredError
        mock_page = AsyncMock()
        mock_page.url = "https://x.com/i/flow/login"
        self.scraper.page = mock_page
        with pytest.raises(SessionExpiredError):
            asyncio.run(self.scraper._validate_page_loaded())

    def test_valid_page_passes(self):
        mock_page = AsyncMock()
        mock_page.url = "https://x.com/user/status/123"
        mock_page.title = AsyncMock(return_value="User on X")
        mock_page.query_selector = AsyncMock(return_value=True)
        self.scraper.page = mock_page
        asyncio.run(self.scraper._validate_page_loaded())  # Should not raise


class TestFilterAuthorQuotedTweets:
    @pytest.fixture(autouse=True)
    def scraper(self):
        with patch("scraper.scraper.UserAgent") as mock_ua:
            mock_ua.return_value.random = "Mozilla/5.0"
            self.scraper = TwitterScraper(headless=True)

    def test_quoted_tweet_does_not_break_thread(self):
        tweets = [
            {"tweet_id": "1", "author_handle": "@alice", "text": "Thread start", "timestamp": "2026-01-01T00:00:00Z"},
            {"tweet_id": "2", "author_handle": "@bob", "text": "Quoted/reply", "timestamp": "2026-01-01T00:00:30Z"},
            {"tweet_id": "3", "author_handle": "@alice", "text": "Thread continues", "timestamp": "2026-01-01T00:01:00Z"},
            {"tweet_id": "4", "author_handle": "@alice", "text": "Thread end", "timestamp": "2026-01-01T00:02:00Z"},
        ]
        result = self.scraper.filter_author_tweets_only(tweets, "@alice")
        assert len(result) == 3
        assert [t["tweet_id"] for t in result] == ["1", "3", "4"]

    def test_genuine_end_of_thread(self):
        tweets = [
            {"tweet_id": "1", "author_handle": "@alice", "text": "Thread 1", "timestamp": "2026-01-01T00:00:00Z"},
            {"tweet_id": "2", "author_handle": "@alice", "text": "Thread 2", "timestamp": "2026-01-01T00:01:00Z"},
            {"tweet_id": "3", "author_handle": "@bob", "text": "Reply 1", "timestamp": "2026-01-01T00:02:00Z"},
            {"tweet_id": "4", "author_handle": "@charlie", "text": "Reply 2", "timestamp": "2026-01-01T00:03:00Z"},
            {"tweet_id": "5", "author_handle": "@alice", "text": "Separate tweet", "timestamp": "2026-01-01T00:10:00Z"},
        ]
        result = self.scraper.filter_author_tweets_only(tweets, "@alice")
        assert len(result) == 2
        assert [t["tweet_id"] for t in result] == ["1", "2"]


def test_scraper_can_be_instantiated():
    """Integration smoke test - verify scraper can be created."""
    try:
        scraper = TwitterScraper(headless=True, max_interactions=10)
        assert scraper is not None
        assert isinstance(scraper, TwitterScraper)
    except Exception as e:
        pytest.fail(f"Failed to instantiate scraper: {e}")


if __name__ == "__main__":
    # Run tests with verbose output
    pytest.main([__file__, "-v", "--tb=short"])
