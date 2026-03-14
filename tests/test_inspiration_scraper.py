"""Tests for TwitterScraper.search_by_user_engagement."""

import asyncio
from unittest.mock import AsyncMock
from unittest.mock import patch

from scraper.scraper import TwitterScraper


class TestInspirationScraper:
    def test_search_by_user_engagement(self):
        with patch("scraper.scraper.UserAgent") as mock_ua:
            mock_ua.return_value.random = "Mozilla/5.0"
            scraper = TwitterScraper(headless=True)

        page = AsyncMock()
        page.url = "https://x.com/search?q=from%3Afintech_guru"
        page.title = AsyncMock(return_value="Search / X")
        page.query_selector = AsyncMock(return_value=True)
        page.evaluate = AsyncMock(
            return_value=[
                {
                    "tweet_id": "123",
                    "text": "Bitcoin ETF update",
                    "permalink": "https://x.com/a/status/123",
                    "likes": 350,
                    "retweets": 40,
                    "views": 5000,
                    "timestamp": "2026-03-08T10:00:00Z",
                    "author_handle": "@a",
                }
            ]
        )
        scraper.page = page
        scraper._random_delay = AsyncMock(return_value=None)

        results = asyncio.run(
            scraper.search_by_user_engagement(
                username="fintech_guru",
                min_faves=100,
                keyword="bitcoin",
                limit=1,
            )
        )

        assert len(results) == 1
        assert results[0]["tweet_id"] == "123"
        assert results[0]["likes"] == 350

    def test_search_uses_live_tab_for_latest(self):
        with patch("scraper.scraper.UserAgent") as mock_ua:
            mock_ua.return_value.random = "Mozilla/5.0"
            scraper = TwitterScraper(headless=True)

        page = AsyncMock()
        page.url = "https://x.com/search?q=from%3Afintech_guru"
        page.title = AsyncMock(return_value="Search / X")
        page.query_selector = AsyncMock(return_value=True)
        page.evaluate = AsyncMock(
            return_value=[
                {
                    "tweet_id": "456",
                    "text": "Latest post",
                    "permalink": "https://x.com/a/status/456",
                    "likes": 150,
                    "retweets": 10,
                    "views": 2000,
                    "timestamp": "2026-03-10T10:00:00Z",
                    "author_handle": "@a",
                }
            ]
        )
        scraper.page = page
        scraper._random_delay = AsyncMock(return_value=None)

        results = asyncio.run(
            scraper.search_by_user_engagement(
                username="fintech_guru",
                min_faves=100,
                keyword="bitcoin",
                limit=1,
                sort_by="latest",
            )
        )

        assert len(results) == 1
        # Verify the URL used ?f=live instead of ?f=top
        goto_url = page.goto.call_args[0][0]
        assert "f=live" in goto_url
        assert "f=top" not in goto_url
