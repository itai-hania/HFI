"""Startup checks for Telegram bot runtime hardening."""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import pytest

from telegram_bot.bot import HFIBot


def _json_response(status: int, payload: dict, method: str = "GET", path: str = "/") -> httpx.Response:
    request = httpx.Request(method, f"http://test{path}")
    return httpx.Response(status_code=status, json=payload, request=request)


@pytest.mark.asyncio
async def test_run_startup_self_checks_success():
    bot = HFIBot.__new__(HFIBot)
    bot.api_password = "secret"
    bot.jwt_token = None
    bot.http = SimpleNamespace(
        get=AsyncMock(return_value=_json_response(200, {"status": "healthy", "database": {"status": "healthy"}})),
        post=AsyncMock(return_value=_json_response(200, {"access_token": "jwt-token"}, "POST", "/api/auth/login")),
    )
    bot._request = AsyncMock(return_value=_json_response(200, {"pending": 0}, "GET", "/api/content/queue/summary"))

    await bot.run_startup_self_checks()

    assert bot.jwt_token == "jwt-token"
    bot._request.assert_awaited_once_with("GET", "/api/content/queue/summary")


@pytest.mark.asyncio
async def test_run_startup_self_checks_raises_on_connect_error():
    bot = HFIBot.__new__(HFIBot)
    bot.api_password = "secret"
    bot.jwt_token = None
    bot.http = SimpleNamespace(
        get=AsyncMock(side_effect=httpx.ConnectError("boom")),
        post=AsyncMock(),
    )
    bot._request = AsyncMock()

    with pytest.raises(httpx.ConnectError):
        await bot.run_startup_self_checks()


@pytest.mark.asyncio
async def test_run_startup_self_checks_raises_on_login_failure():
    bot = HFIBot.__new__(HFIBot)
    bot.api_password = "secret"
    bot.jwt_token = None
    bot.http = SimpleNamespace(
        get=AsyncMock(return_value=_json_response(200, {"status": "healthy", "database": {"status": "healthy"}})),
        post=AsyncMock(
            return_value=_json_response(
                401,
                {"detail": "Invalid credentials"},
                "POST",
                "/api/auth/login",
            )
        ),
    )
    bot._request = AsyncMock()

    with pytest.raises(httpx.HTTPStatusError):
        await bot.run_startup_self_checks()


@pytest.mark.asyncio
async def test_send_scheduled_brief_caches_last_brief_for_follow_up_commands():
    bot = HFIBot.__new__(HFIBot)
    bot.chat_id = "12345"
    bot._chat_states = {}
    bot.app = SimpleNamespace(bot=SimpleNamespace(send_message=AsyncMock()))
    stories = [
        {
            "title": "Scheduled ETF story",
            "summary": "Summary",
            "source_urls": ["https://example.com/story"],
        }
    ]
    bot._request = AsyncMock(
        return_value=_json_response(
            200,
            {"stories": stories},
            "POST",
            "/api/notifications/brief",
        )
    )

    await bot.send_scheduled_brief()

    assert bot._chat_states["12345"].last_brief == stories
    bot.app.bot.send_message.assert_awaited_once()
