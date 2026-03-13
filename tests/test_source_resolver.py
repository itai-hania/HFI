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
        mock_scraper.get_tweet_content = AsyncMock(side_effect=asyncio.TimeoutError())
        mock_scraper.close = AsyncMock()
        with pytest.raises(SourceResolverError, match="timed out"):
            await resolve_source_input(
                url="https://x.com/user/status/123",
                scraper_factory=lambda: mock_scraper,
            )
        mock_scraper.close.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_x_url_resolves_single_tweet(self):
        mock_scraper = AsyncMock()
        mock_scraper.ensure_logged_in = AsyncMock()
        mock_scraper.get_tweet_content = AsyncMock(return_value={"text": "Bitcoin ETF approved!"})
        mock_scraper.close = AsyncMock()
        result = await resolve_source_input(
            url="https://x.com/user/status/123",
            scraper_factory=lambda: mock_scraper,
        )
        assert result.source_type == "x_url"
        assert "Bitcoin ETF approved!" in result.original_text
        mock_scraper.close.assert_awaited_once()
