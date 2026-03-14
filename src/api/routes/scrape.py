"""Scrape endpoints — expose X scraping capabilities to frontend and Telegram bot."""

import asyncio
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from api.dependencies import get_db, require_jwt
from api.schemas.scrape import (
    ContentFromThreadRequest,
    ContentFromThreadResponse,
    ScrapeUrlRequest,
    ScrapeTrendsRequest,
    ScrapedThreadResponse,
    ScrapedTweetResponse,
    ScrapeTrendsResponse,
)
from common.models import Tweet, TweetStatus

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/scrape",
    tags=["scrape"],
    dependencies=[Depends(require_jwt)],
)

_scraper_instance = None
_scraper_lock = asyncio.Lock()


async def get_scraper():
    """Lazy-init async singleton for TwitterScraper.

    The scraper manages a Playwright browser; creating multiple instances is
    wasteful and causes port conflicts.  A module-level lock ensures only one
    instance is initialised even under concurrent requests.
    """
    global _scraper_instance
    if _scraper_instance is not None:
        return _scraper_instance

    async with _scraper_lock:
        if _scraper_instance is not None:
            return _scraper_instance

        from scraper.scraper import TwitterScraper

        scraper = TwitterScraper(headless=True)
        await scraper.ensure_logged_in()
        _scraper_instance = scraper
        return _scraper_instance


async def release_scraper():
    """Close the singleton scraper and free browser memory."""
    global _scraper_instance
    if _scraper_instance is None:
        return
    try:
        await _scraper_instance.close()
    except Exception as exc:
        logger.warning(f"Error closing scraper: {exc}")
    _scraper_instance = None


def get_translation_service():
    """Factory kept separate for test patching."""
    from processor.processor import ProcessorConfig, TranslationService

    config = ProcessorConfig()
    return TranslationService(config)


@router.post("/thread", response_model=ScrapedThreadResponse)
async def scrape_thread(request: ScrapeUrlRequest):
    """Scrape an X thread via TwitterScraper.fetch_raw_thread()."""
    try:
        scraper = await get_scraper()
        result = await scraper.fetch_raw_thread(request.url, author_only=True)
        return ScrapedThreadResponse(**result)
    except Exception as exc:
        logger.error(f"Thread scrape failed for {request.url}: {exc}")
        raise HTTPException(status_code=502, detail=f"Scrape failed: {exc}") from exc


@router.post("/tweet", response_model=ScrapedTweetResponse)
async def scrape_tweet(request: ScrapeUrlRequest):
    """Scrape a single tweet via TwitterScraper.get_tweet_content()."""
    try:
        scraper = await get_scraper()
        result = await scraper.get_tweet_content(request.url)
        return ScrapedTweetResponse(**result)
    except Exception as exc:
        logger.error(f"Tweet scrape failed for {request.url}: {exc}")
        raise HTTPException(status_code=502, detail=f"Scrape failed: {exc}") from exc


@router.post("/trends", response_model=ScrapeTrendsResponse)
async def scrape_trends(request: Optional[ScrapeTrendsRequest] = None):
    """Scrape X trending topics."""
    limit = request.limit if request else 10
    try:
        scraper = await get_scraper()
        trends = await scraper.get_trending_topics(limit=limit)
        return ScrapeTrendsResponse(trends=trends, count=len(trends))
    except Exception as exc:
        logger.error(f"Trends scrape failed: {exc}")
        raise HTTPException(status_code=502, detail=f"Scrape failed: {exc}") from exc


# ---------------------------------------------------------------------------
# Task 4.2 — Content-from-Thread endpoint
# ---------------------------------------------------------------------------

content_router = APIRouter(
    prefix="/api/content",
    tags=["content"],
    dependencies=[Depends(require_jwt)],
)


@content_router.post("/from-thread", response_model=ContentFromThreadResponse)
async def content_from_thread(
    request: ContentFromThreadRequest,
    db: Session = Depends(get_db),
):
    """One-click endpoint: scrape thread -> optionally translate -> save to queue.

    Modes:
      - consolidated: merge all thread tweets into one Hebrew post
      - separate: save each tweet as a separate content item
    """
    try:
        scraper = await get_scraper()
        thread = await scraper.fetch_raw_thread(request.url, author_only=True)
    except Exception as exc:
        logger.error(f"Thread scrape failed for {request.url}: {exc}")
        raise HTTPException(status_code=502, detail=f"Scrape failed: {exc}") from exc

    tweets_data = thread.get("tweets", [])
    if not tweets_data:
        raise HTTPException(status_code=404, detail="No tweets found in thread")

    translator = None
    if request.auto_translate:
        try:
            translator = get_translation_service()
        except Exception as exc:
            logger.warning(f"Translation service unavailable, saving without translation: {exc}")

    saved_items: list[dict] = []

    if request.mode == "consolidated":
        existing = db.query(Tweet).filter_by(source_url=request.url).first()
        if existing:
            raise HTTPException(
                status_code=409,
                detail=f"Thread already saved (id={existing.id})",
            )

        original_text = "\n\n".join(
            t.get("text", "") for t in tweets_data if t.get("text")
        )
        hebrew_draft = None
        status = TweetStatus.PENDING

        if translator and original_text:
            try:
                hebrew_draft = await asyncio.to_thread(
                    translator.translate_long_text,
                    [t.get("text", "") for t in tweets_data if t.get("text")],
                )
                status = TweetStatus.PROCESSED
            except Exception as exc:
                logger.warning(f"Translation failed, saving as pending: {exc}")

        tweet = Tweet(
            source_url=request.url,
            original_text=original_text,
            hebrew_draft=hebrew_draft,
            content_type="thread_consolidated",
            status=status,
            generation_metadata={
                "origin": "from-thread",
                "mode": "consolidated",
                "tweet_count": len(tweets_data),
                "author_handle": thread.get("author_handle"),
            },
        )
        db.add(tweet)
        db.commit()
        db.refresh(tweet)
        saved_items.append({
            "id": tweet.id,
            "status": tweet.status.value,
            "original_text": tweet.original_text,
            "hebrew_draft": tweet.hebrew_draft,
        })

    else:  # separate
        for t in tweets_data:
            text = t.get("text", "")
            if not text:
                continue

            hebrew_draft = None
            status = TweetStatus.PENDING

            if translator:
                try:
                    hebrew_draft = await asyncio.to_thread(
                        translator.translate_and_rewrite, text
                    )
                    status = TweetStatus.PROCESSED
                except Exception as exc:
                    logger.warning(f"Translation failed for tweet {t.get('tweet_id')}: {exc}")

            tweet_url = request.url
            tweet_id = t.get("tweet_id")
            if tweet_id:
                parts = request.url.rstrip("/").rsplit("/status/", 1)
                if len(parts) == 2:
                    base = parts[0]
                    tweet_url = f"{base}/status/{tweet_id}"

            existing = db.query(Tweet).filter_by(source_url=tweet_url).first()
            if existing:
                saved_items.append({
                    "id": existing.id,
                    "status": existing.status.value,
                    "original_text": existing.original_text,
                    "hebrew_draft": existing.hebrew_draft,
                })
                continue

            tweet = Tweet(
                source_url=tweet_url,
                original_text=text,
                hebrew_draft=hebrew_draft,
                content_type="thread_separate",
                status=status,
                generation_metadata={
                    "origin": "from-thread",
                    "mode": "separate",
                    "thread_url": request.url,
                    "author_handle": thread.get("author_handle"),
                },
            )
            db.add(tweet)
            db.commit()
            db.refresh(tweet)
            saved_items.append({
                "id": tweet.id,
                "status": tweet.status.value,
                "original_text": tweet.original_text,
                "hebrew_draft": tweet.hebrew_draft,
            })

    return ContentFromThreadResponse(
        mode=request.mode,
        thread_url=request.url,
        tweet_count=len(tweets_data),
        saved_items=saved_items,
    )
