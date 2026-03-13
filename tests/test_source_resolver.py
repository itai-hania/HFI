"""Tests for shared source resolver and URL classification."""

import asyncio
from unittest.mock import AsyncMock

import pytest

from common.source_resolver import SourceResolverError, resolve_source_input


@pytest.mark.asyncio
async def test_resolve_source_rejects_non_status_x_url():
    with pytest.raises(SourceResolverError) as exc:
        await resolve_source_input(url="https://x.com/OpenAI")
    assert str(exc.value) == "Invalid X/Twitter status URL"


@pytest.mark.asyncio
async def test_resolve_source_accepts_plain_text():
    resolved = await resolve_source_input(text="Hello fintech world")
    assert resolved.source_type == "text"
    assert resolved.original_text == "Hello fintech world"


class TestSourceResolverSessionHandling:
    @pytest.mark.asyncio
    async def test_x_url_raises_on_session_expired(self):
        from scraper.errors import SessionExpiredError

        mock_scraper = AsyncMock()
        mock_scraper.ensure_logged_in = AsyncMock(side_effect=SessionExpiredError("expired"))
        mock_scraper.close = AsyncMock()
        with pytest.raises(SourceResolverError, match="expired"):
            await resolve_source_input(
                url="https://x.com/user/status/123",
                scraper_factory=lambda: mock_scraper,
            )
        mock_scraper.close.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_x_url_raises_on_timeout(self):
        mock_scraper = AsyncMock()
        mock_scraper.ensure_logged_in = AsyncMock()
        mock_scraper.fetch_raw_thread = AsyncMock(side_effect=asyncio.TimeoutError())
        mock_scraper.close = AsyncMock()
        with pytest.raises(SourceResolverError, match="timed out"):
            await resolve_source_input(
                url="https://x.com/user/status/123",
                scraper_factory=lambda: mock_scraper,
            )
        mock_scraper.close.assert_awaited_once()


class TestSourceResolverThreadDetection:
    @pytest.mark.asyncio
    async def test_x_thread_url_returns_consolidated_text(self):
        thread_data = {
            "author_handle": "@user",
            "author_name": "User",
            "tweet_count": 3,
            "tweets": [
                {"text": "First tweet in thread", "timestamp": "2026-01-01T00:00:00Z"},
                {"text": "Second tweet continues", "timestamp": "2026-01-01T00:01:00Z"},
                {"text": "Third tweet wraps up", "timestamp": "2026-01-01T00:02:00Z"},
            ],
        }
        mock_scraper = AsyncMock()
        mock_scraper.ensure_logged_in = AsyncMock()
        mock_scraper.fetch_raw_thread = AsyncMock(return_value=thread_data)
        mock_scraper.close = AsyncMock()
        result = await resolve_source_input(
            url="https://x.com/user/status/123",
            scraper_factory=lambda: mock_scraper,
        )
        assert "First tweet" in result.original_text
        assert "Second tweet" in result.original_text
        assert "Third tweet" in result.original_text
        assert result.source_type == "x_url"

    @pytest.mark.asyncio
    async def test_x_single_tweet_also_works(self):
        thread_data = {
            "tweets": [{"text": "Just one tweet", "timestamp": "2026-01-01T00:00:00Z"}],
            "author_handle": "@user",
        }
        mock_scraper = AsyncMock()
        mock_scraper.ensure_logged_in = AsyncMock()
        mock_scraper.fetch_raw_thread = AsyncMock(return_value=thread_data)
        mock_scraper.close = AsyncMock()
        result = await resolve_source_input(
            url="https://x.com/user/status/123",
            scraper_factory=lambda: mock_scraper,
        )
        assert result.original_text == "Just one tweet"

    @pytest.mark.asyncio
    async def test_x_empty_thread_raises_error(self):
        thread_data = {"tweets": [], "author_handle": "@user"}
        mock_scraper = AsyncMock()
        mock_scraper.ensure_logged_in = AsyncMock()
        mock_scraper.fetch_raw_thread = AsyncMock(return_value=thread_data)
        mock_scraper.close = AsyncMock()
        with pytest.raises(SourceResolverError, match="No content found"):
            await resolve_source_input(
                url="https://x.com/user/status/123",
                scraper_factory=lambda: mock_scraper,
            )

    @pytest.mark.asyncio
    async def test_x_thread_title_uses_first_tweet(self):
        thread_data = {
            "tweets": [
                {"text": "This is the first tweet which is quite long and should be the title source"},
                {"text": "This is a follow-up tweet"},
            ],
            "author_handle": "@user",
        }
        mock_scraper = AsyncMock()
        mock_scraper.ensure_logged_in = AsyncMock()
        mock_scraper.fetch_raw_thread = AsyncMock(return_value=thread_data)
        mock_scraper.close = AsyncMock()
        result = await resolve_source_input(
            url="https://x.com/user/status/123",
            scraper_factory=lambda: mock_scraper,
        )
        assert result.title.startswith("This is the first tweet")
