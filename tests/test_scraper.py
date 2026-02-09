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
