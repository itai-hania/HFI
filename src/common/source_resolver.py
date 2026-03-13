"""Shared source resolution for text, X URLs, and article URLs."""

from __future__ import annotations

import asyncio
import re
from dataclasses import asdict, dataclass
from typing import Any, Callable, Literal
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup

from common.url_validation import (
    URLValidationError,
    is_x_or_twitter_host,
    is_safe_article_content_type,
    is_x_status_url,
    validate_article_url,
    validate_x_status_url,
)

SourceType = Literal["text", "x_url", "article_url"]
_MAX_ARTICLE_BYTES = 2 * 1024 * 1024
_MAX_ARTICLE_REDIRECTS = 5
_MIN_ARTICLE_TEXT_LENGTH = 200


class SourceResolverError(ValueError):
    """Raised when source text cannot be resolved safely."""


@dataclass(frozen=True)
class SourceResolution:
    source_type: SourceType
    original_text: str
    preview_text: str
    title: str | None = None
    canonical_url: str | None = None
    source_domain: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _collapse_whitespace(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def _build_preview(value: str, max_chars: int = 280) -> str:
    text = _collapse_whitespace(value)
    if len(text) <= max_chars:
        return text
    return f"{text[: max_chars - 1].rstrip()}…"


def _extract_title(soup: BeautifulSoup) -> str | None:
    for selector in (
        ('meta[property="og:title"]', "content"),
        ('meta[name="twitter:title"]', "content"),
    ):
        tag = soup.select_one(selector[0])
        if tag:
            content = _collapse_whitespace(tag.get(selector[1], ""))
            if content:
                return content
    if soup.title:
        text = _collapse_whitespace(soup.title.get_text(" ", strip=True))
        if text:
            return text
    return None


def _extract_article_text(html_text: str) -> tuple[str, str | None]:
    soup = BeautifulSoup(html_text, "html.parser")
    title = _extract_title(soup)

    for tag_name in ("script", "style", "nav", "footer", "aside", "form", "noscript"):
        for tag in soup.find_all(tag_name):
            tag.decompose()

    container = soup.find("article") or soup.find("main") or soup.body or soup
    blocks = container.find_all(["p", "li", "blockquote", "h1", "h2", "h3"])

    parts: list[str] = []
    for block in blocks:
        text = _collapse_whitespace(block.get_text(" ", strip=True))
        if text and len(text) >= 20:
            parts.append(text)

    if not parts:
        fallback = _collapse_whitespace(container.get_text(" ", strip=True))
        if fallback:
            parts = [fallback]

    text = "\n".join(parts).strip()
    return text, title


def _source_domain(url: str | None) -> str | None:
    if not url:
        return None
    parsed = urlparse(url)
    return parsed.hostname.lower() if parsed.hostname else None


async def _resolve_x_url(
    url: str,
    *,
    scraper_factory: Callable[[], Any] | None = None,
) -> SourceResolution:
    if scraper_factory is None:
        from scraper.scraper import TwitterScraper

        scraper_factory = lambda: TwitterScraper(headless=True)  # noqa: E731

    from scraper.errors import SessionExpiredError

    scraper = scraper_factory()
    try:
        await asyncio.wait_for(scraper.ensure_logged_in(), timeout=20)
        thread_data = await asyncio.wait_for(
            scraper.fetch_raw_thread(url, author_only=True),
            timeout=120,
        )
    except SessionExpiredError as exc:
        raise SourceResolverError(str(exc)) from exc
    except asyncio.TimeoutError:
        raise SourceResolverError("X scraping timed out. The session may be expired.")
    finally:
        await scraper.close()

    tweets = thread_data.get("tweets", [])
    if not tweets:
        raise SourceResolverError("No content found at this X/Twitter URL")

    parts = [t.get("text", "").strip() for t in tweets if t.get("text", "").strip()]
    text = "\n\n".join(parts)
    if not text:
        raise SourceResolverError("No content found at this X/Twitter URL")

    title = _build_preview(parts[0] if parts else text, max_chars=120)
    return SourceResolution(
        source_type="x_url",
        original_text=text,
        title=title,
        canonical_url=url,
        source_domain=_source_domain(url),
        preview_text=_build_preview(text),
    )


async def _resolve_article_url(
    url: str,
    *,
    client_factory: Callable[[], httpx.AsyncClient] | None = None,
) -> SourceResolution:
    if client_factory is None:
        client_factory = lambda: httpx.AsyncClient(  # noqa: E731
            timeout=20.0,
            follow_redirects=False,
            headers={"User-Agent": "HFI-SourceResolver/1.0"},
        )

    try:
        async with client_factory() as client:
            current_url = url
            payload = bytearray()
            final_url = current_url

            for redirect_hops in range(_MAX_ARTICLE_REDIRECTS + 1):
                async with client.stream("GET", current_url) as response:
                    if response.is_redirect:
                        location = response.headers.get("location")
                        if not location:
                            raise SourceResolverError("Redirect target is missing")
                        current_url = str(response.url.join(location))
                        validate_article_url(current_url)
                        continue

                    response.raise_for_status()
                    final_url = str(response.url)
                    validate_article_url(final_url)

                    content_type = response.headers.get("content-type", "")
                    if not is_safe_article_content_type(content_type):
                        raise SourceResolverError("Unsupported article content type")

                    async for chunk in response.aiter_bytes():
                        payload.extend(chunk)
                        if len(payload) > _MAX_ARTICLE_BYTES:
                            raise SourceResolverError("Article response is too large")
                    break
            else:
                raise SourceResolverError("Too many redirects while fetching article URL")
    except URLValidationError as exc:
        raise SourceResolverError(str(exc)) from exc
    except httpx.HTTPError as exc:
        raise SourceResolverError("Couldn't extract article text from this URL. Paste the text instead.") from exc

    html_text = payload.decode("utf-8", errors="ignore")
    article_text, title = _extract_article_text(html_text)
    if len(article_text) < _MIN_ARTICLE_TEXT_LENGTH:
        raise SourceResolverError("Couldn't extract article text from this URL. Paste the text instead.")

    canonical_url = final_url
    return SourceResolution(
        source_type="article_url",
        original_text=article_text,
        title=title,
        canonical_url=canonical_url,
        source_domain=_source_domain(canonical_url),
        preview_text=_build_preview(article_text),
    )


async def resolve_source_input(
    *,
    text: str | None = None,
    url: str | None = None,
    scraper_factory: Callable[[], Any] | None = None,
    client_factory: Callable[[], httpx.AsyncClient] | None = None,
) -> SourceResolution:
    """Resolve source content from free text or validated URL input."""
    if url:
        try:
            if is_x_status_url(url):
                normalized = validate_x_status_url(url)
                return await _resolve_x_url(normalized, scraper_factory=scraper_factory)
            if is_x_or_twitter_host(url):
                raise SourceResolverError("Invalid X/Twitter status URL")

            normalized = validate_article_url(url)
        except URLValidationError as exc:
            raise SourceResolverError(str(exc)) from exc

        return await _resolve_article_url(normalized, client_factory=client_factory)

    plain_text = _collapse_whitespace(text or "")
    if not plain_text:
        raise SourceResolverError("No source text found")

    return SourceResolution(
        source_type="text",
        original_text=plain_text,
        preview_text=_build_preview(plain_text),
    )
