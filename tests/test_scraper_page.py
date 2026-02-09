"""
Mock Page unit tests for the TwitterScraper.

Tests scraper data extraction logic using mocked Playwright objects,
without launching a real browser. Covers: trend parsing, tweet content
extraction, handle extraction, and thread collection logic.

Run with: pytest tests/test_scraper_page.py -v
"""

import pytest
import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from scraper.scraper import TwitterScraper


@pytest.fixture
def scraper():
    return TwitterScraper(headless=True, max_interactions=50)


@pytest.fixture
def mock_page():
    """Create a mock Playwright Page object."""
    page = AsyncMock()
    page.goto = AsyncMock()
    page.wait_for_selector = AsyncMock()
    page.query_selector = AsyncMock()
    page.query_selector_all = AsyncMock(return_value=[])
    page.evaluate = AsyncMock(return_value=[])
    return page


# ==================== Trend Parsing Tests ====================

class TestTrendParsing:
    """Test trend element parsing from mocked DOM elements."""

    @pytest.mark.asyncio
    async def test_parse_trend_with_category_title_count(self, scraper, mock_page):
        """Test parsing a trend element with category, title, and count."""
        trend_el = AsyncMock()
        trend_el.inner_text = AsyncMock(return_value="Technology · Trending\nBitcoin ETF\n15.2K posts")

        mock_page.query_selector_all = AsyncMock(return_value=[trend_el])
        scraper.page = mock_page

        trends = await scraper.get_trending_topics(limit=5)

        assert len(trends) == 1
        assert trends[0]['title'] == 'Bitcoin ETF'
        assert trends[0]['category'] == 'Technology · Trending'
        assert '15.2K' in trends[0]['description']

    @pytest.mark.asyncio
    async def test_parse_trend_single_line(self, scraper, mock_page):
        """Test parsing a trend element with only a title."""
        trend_el = AsyncMock()
        trend_el.inner_text = AsyncMock(return_value="#Bitcoin")

        mock_page.query_selector_all = AsyncMock(return_value=[trend_el])
        scraper.page = mock_page

        trends = await scraper.get_trending_topics(limit=5)

        assert len(trends) == 1
        assert trends[0]['title'] == '#Bitcoin'
        assert trends[0]['category'] == 'Trending'
        assert trends[0]['description'] == ''

    @pytest.mark.asyncio
    async def test_parse_multiple_trends(self, scraper, mock_page):
        """Test parsing multiple trend elements."""
        trends_data = [
            "Crypto · Trending\nBitcoin\n50K posts",
            "Finance\nETF\n10K posts",
            "Tech\nAI Regulation\n5K posts",
        ]
        elements = []
        for text in trends_data:
            el = AsyncMock()
            el.inner_text = AsyncMock(return_value=text)
            elements.append(el)

        mock_page.query_selector_all = AsyncMock(return_value=elements)
        scraper.page = mock_page

        trends = await scraper.get_trending_topics(limit=10)

        assert len(trends) == 3
        assert trends[0]['title'] == 'Bitcoin'
        assert trends[1]['title'] == 'ETF'
        assert trends[2]['title'] == 'AI Regulation'

    @pytest.mark.asyncio
    async def test_parse_trend_limit_respected(self, scraper, mock_page):
        """Test that limit parameter caps trend count."""
        elements = []
        for i in range(10):
            el = AsyncMock()
            el.inner_text = AsyncMock(return_value=f"Category\nTrend {i}")
            elements.append(el)

        mock_page.query_selector_all = AsyncMock(return_value=elements)
        scraper.page = mock_page

        trends = await scraper.get_trending_topics(limit=3)

        assert len(trends) == 3

    @pytest.mark.asyncio
    async def test_parse_trend_element_error_skipped(self, scraper, mock_page):
        """Test that a failing trend element doesn't stop parsing."""
        good_el = AsyncMock()
        good_el.inner_text = AsyncMock(return_value="Tech\nGoodTrend\n1K")
        bad_el = AsyncMock()
        bad_el.inner_text = AsyncMock(side_effect=Exception("DOM error"))

        mock_page.query_selector_all = AsyncMock(return_value=[bad_el, good_el])
        scraper.page = mock_page

        trends = await scraper.get_trending_topics(limit=5)

        assert len(trends) == 1
        assert trends[0]['title'] == 'GoodTrend'


# ==================== Tweet Content Extraction Tests ====================

class TestTweetContentExtraction:
    """Test tweet content extraction from mocked DOM."""

    @pytest.mark.asyncio
    async def test_extract_tweet_text(self, scraper, mock_page):
        """Test extracting tweet text from DOM."""
        text_el = AsyncMock()
        text_el.inner_text = AsyncMock(return_value="Bitcoin just hit $100K! This is huge.")

        mock_page.query_selector = AsyncMock(side_effect=lambda sel: {
            '[data-testid="tweetText"]': text_el,
            '[data-testid="User-Name"] a': None,
            'time': None,
            '[data-testid="tweetPhoto"] img': None,
        }.get(sel))

        scraper.page = mock_page
        scraper.intercepted_media_urls = []

        with patch.object(scraper, '_random_delay', new_callable=AsyncMock):
            with patch.object(scraper, '_expand_long_tweets', new_callable=AsyncMock):
                result = await scraper.get_tweet_content("https://x.com/user/status/123")

        assert result['text'] == "Bitcoin just hit $100K! This is huge."
        assert result['source_url'] == "https://x.com/user/status/123"
        assert result['scraped_at'] is not None

    @pytest.mark.asyncio
    async def test_extract_tweet_author(self, scraper, mock_page):
        """Test extracting author from User-Name element."""
        text_el = AsyncMock()
        text_el.inner_text = AsyncMock(return_value="Test tweet")

        author_el = AsyncMock()
        author_el.get_attribute = AsyncMock(return_value="/elonmusk")

        mock_page.query_selector = AsyncMock(side_effect=lambda sel: {
            '[data-testid="tweetText"]': text_el,
            '[data-testid="User-Name"] a': author_el,
            'time': None,
            '[data-testid="tweetPhoto"] img': None,
        }.get(sel))

        scraper.page = mock_page
        scraper.intercepted_media_urls = []

        with patch.object(scraper, '_random_delay', new_callable=AsyncMock):
            with patch.object(scraper, '_expand_long_tweets', new_callable=AsyncMock):
                result = await scraper.get_tweet_content("https://x.com/elonmusk/status/456")

        assert result['author'] == 'elonmusk'

    @pytest.mark.asyncio
    async def test_extract_tweet_timestamp(self, scraper, mock_page):
        """Test extracting timestamp from time element."""
        text_el = AsyncMock()
        text_el.inner_text = AsyncMock(return_value="Test")

        time_el = AsyncMock()
        time_el.get_attribute = AsyncMock(return_value="2026-02-08T12:00:00.000Z")

        mock_page.query_selector = AsyncMock(side_effect=lambda sel: {
            '[data-testid="tweetText"]': text_el,
            '[data-testid="User-Name"] a': None,
            'time': time_el,
            '[data-testid="tweetPhoto"] img': None,
        }.get(sel))

        scraper.page = mock_page
        scraper.intercepted_media_urls = []

        with patch.object(scraper, '_random_delay', new_callable=AsyncMock):
            with patch.object(scraper, '_expand_long_tweets', new_callable=AsyncMock):
                result = await scraper.get_tweet_content("https://x.com/user/status/789")

        assert result['timestamp'] == "2026-02-08T12:00:00.000Z"

    @pytest.mark.asyncio
    async def test_extract_tweet_image(self, scraper, mock_page):
        """Test extracting image URL from tweetPhoto."""
        text_el = AsyncMock()
        text_el.inner_text = AsyncMock(return_value="Check this out")

        img_el = AsyncMock()
        img_el.get_attribute = AsyncMock(return_value="https://pbs.twimg.com/media/test.jpg")

        mock_page.query_selector = AsyncMock(side_effect=lambda sel: {
            '[data-testid="tweetText"]': text_el,
            '[data-testid="User-Name"] a': None,
            'time': None,
            '[data-testid="tweetPhoto"] img': img_el,
        }.get(sel))

        scraper.page = mock_page
        scraper.intercepted_media_urls = []

        with patch.object(scraper, '_random_delay', new_callable=AsyncMock):
            with patch.object(scraper, '_expand_long_tweets', new_callable=AsyncMock):
                result = await scraper.get_tweet_content("https://x.com/user/status/111")

        assert result['media_url'] == "https://pbs.twimg.com/media/test.jpg"

    @pytest.mark.asyncio
    async def test_intercepted_media_preferred_over_dom(self, scraper, mock_page):
        """Test that intercepted m3u8 URLs are preferred over DOM images."""
        text_el = AsyncMock()
        text_el.inner_text = AsyncMock(return_value="Video tweet")

        mock_page.query_selector = AsyncMock(side_effect=lambda sel: {
            '[data-testid="tweetText"]': text_el,
            '[data-testid="User-Name"] a': None,
            'time': None,
            '[data-testid="tweetPhoto"] img': None,
        }.get(sel))

        # Simulate network interception: set URLs after goto (which happens after clear)
        async def fake_goto(*args, **kwargs):
            scraper.intercepted_media_urls = [
                "https://video.twimg.com/video.m3u8",
                "https://video.twimg.com/poster.jpg",
            ]
        mock_page.goto = AsyncMock(side_effect=fake_goto)

        scraper.page = mock_page

        with patch.object(scraper, '_random_delay', new_callable=AsyncMock):
            with patch.object(scraper, '_expand_long_tweets', new_callable=AsyncMock):
                result = await scraper.get_tweet_content("https://x.com/user/status/222")

        assert '.m3u8' in result['media_url']

    @pytest.mark.asyncio
    async def test_missing_tweet_text_returns_empty(self, scraper, mock_page):
        """Test that missing tweetText element returns empty string."""
        mock_page.query_selector = AsyncMock(return_value=None)
        scraper.page = mock_page
        scraper.intercepted_media_urls = []

        with patch.object(scraper, '_random_delay', new_callable=AsyncMock):
            with patch.object(scraper, '_expand_long_tweets', new_callable=AsyncMock):
                result = await scraper.get_tweet_content("https://x.com/user/status/333")

        assert result['text'] == ""


# ==================== Handle Extraction Tests ====================

class TestHandleExtraction:
    """Test _extract_handle_from_url with various URL formats."""

    def test_standard_status_url(self, scraper):
        assert scraper._extract_handle_from_url("https://x.com/elonmusk/status/123") == "@elonmusk"

    def test_url_with_query_params(self, scraper):
        assert scraper._extract_handle_from_url("https://x.com/openai/status/456?s=20") == "@openai"

    def test_non_status_url(self, scraper):
        assert scraper._extract_handle_from_url("https://x.com/explore") == ""

    def test_url_without_handle(self, scraper):
        assert scraper._extract_handle_from_url("https://x.com") == ""

    def test_empty_string(self, scraper):
        assert scraper._extract_handle_from_url("") == ""


# ==================== Should Stop Tests ====================

class TestShouldStopAtOtherAuthor:
    """Test thread boundary detection logic."""

    def test_empty_tweets(self, scraper):
        assert scraper._should_stop_at_other_author({}, "@user") is False

    def test_no_target_handle(self, scraper):
        tweets = {"1": {"author_handle": "@user"}}
        assert scraper._should_stop_at_other_author(tweets, "") is False

    def test_all_same_author(self, scraper):
        tweets = {
            "1": {"author_handle": "@user"},
            "2": {"author_handle": "@user"},
            "3": {"author_handle": "@user"},
            "4": {"author_handle": "@user"},
            "5": {"author_handle": "@user"},
        }
        assert scraper._should_stop_at_other_author(tweets, "@user") is False

    def test_stops_after_consecutive_other_authors(self, scraper):
        tweets = {
            "1": {"author_handle": "@user"},
            "2": {"author_handle": "@user"},
            "3": {"author_handle": "@other1"},
            "4": {"author_handle": "@other2"},
            "5": {"author_handle": "@other3"},
        }
        assert scraper._should_stop_at_other_author(tweets, "@user") is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
