"""Tests for shared source resolver and URL classification."""

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
