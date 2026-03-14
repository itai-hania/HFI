#!/usr/bin/env python3
"""
Scrape @FinancialEduX's own X/Twitter profile to collect tweets as style examples.

Navigates to the user's profile page, scrolls to collect tweets, filters for
quality Hebrew content, extracts engagement metrics, and stores passing tweets
as StyleExample records for voice learning.

Usage:
    python tools/scrape_self_tweets.py --username FinancialEduX --limit 100 --dry-run
"""

import argparse
import asyncio
import hashlib
import json
import logging
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from scraper.scraper import TwitterScraper
from processor.style_manager import (
    add_style_example,
    is_hebrew_content,
    count_words,
    _fallback_topic_tags,
)
from common.models import SessionLocal, StyleExample

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

ENGAGEMENT_OUTPUT_PATH = PROJECT_ROOT / "data" / "self_tweets_engagement.json"


# ---------------------------------------------------------------------------
# Filtering helpers
# ---------------------------------------------------------------------------

def is_retweet(tweet: Dict, target_handle: str) -> bool:
    """Return True if the tweet is a retweet (author doesn't match target)."""
    author = (tweet.get("author_handle") or "").lower().lstrip("@")
    target = target_handle.lower().lstrip("@")
    return author != target


def is_reply(tweet: Dict) -> bool:
    """Return True if the tweet text starts with @mention (a reply)."""
    text = (tweet.get("text") or "").strip()
    return text.startswith("@")


def passes_min_words(tweet: Dict, min_words: int) -> bool:
    """Return True if the tweet meets the minimum word count."""
    return count_words(tweet.get("text") or "") >= min_words


def passes_language_filter(tweet: Dict, include_english: bool) -> bool:
    """Return True if the tweet passes the language filter.

    When *include_english* is False (default), only Hebrew content is accepted.
    """
    if include_english:
        return True
    return is_hebrew_content(tweet.get("text") or "")


def content_hash(text: str) -> str:
    """SHA-256 hex digest of normalised text for deduplication."""
    normalised = " ".join(text.split()).strip().lower()
    return hashlib.sha256(normalised.encode("utf-8")).hexdigest()


def get_existing_hashes(db) -> set:
    """Return a set of content hashes for existing StyleExample records."""
    rows = db.query(StyleExample.content).filter(StyleExample.is_active == True).all()
    return {content_hash(row.content) for row in rows}


def filter_tweets(
    tweets: List[Dict],
    target_handle: str,
    min_words: int = 15,
    include_english: bool = False,
) -> List[Dict]:
    """Apply the full filtering pipeline, returning tweets that pass all checks."""
    result = []
    for tweet in tweets:
        if is_retweet(tweet, target_handle):
            continue
        if is_reply(tweet):
            continue
        if not passes_min_words(tweet, min_words):
            continue
        if not passes_language_filter(tweet, include_english):
            continue
        result.append(tweet)
    return result


# ---------------------------------------------------------------------------
# Engagement metrics extraction
# ---------------------------------------------------------------------------

ENGAGEMENT_JS = """
() => {
  const articles = Array.from(document.querySelectorAll('article[data-testid="tweet"]'));
  const results = {};

  for (const article of articles) {
    const timeEl = article.querySelector("time");
    const link = timeEl?.closest("a") || article.querySelector('a[href*="/status/"]');
    const permalink = link?.href || "";
    const tweetId = permalink.split("/status/")[1]?.split("?")[0] || "";
    if (!tweetId) continue;

    function parseCount(ariaLabel) {
      if (!ariaLabel) return 0;
      const match = ariaLabel.match(/([\\d,]+)/);
      if (match) return parseInt(match[1].replace(/,/g, ""), 10) || 0;
      return 0;
    }

    const replyBtn = article.querySelector('button[data-testid="reply"]');
    const retweetBtn = article.querySelector('button[data-testid="retweet"]');
    const likeBtn = article.querySelector('button[data-testid="like"]');
    const analyticsLink = article.querySelector('a[href*="/analytics"]');

    results[tweetId] = {
      replies: parseCount(replyBtn?.getAttribute("aria-label")),
      retweets: parseCount(retweetBtn?.getAttribute("aria-label")),
      likes: parseCount(likeBtn?.getAttribute("aria-label")),
      views: parseCount(analyticsLink?.getAttribute("aria-label")),
    };
  }
  return results;
}
"""


def parse_engagement_from_js(raw: Dict) -> Dict[str, Dict[str, int]]:
    """Normalise the JS-returned engagement mapping.

    Returns ``{tweet_id: {replies, retweets, likes, views}}``.
    """
    out: Dict[str, Dict[str, int]] = {}
    for tweet_id, metrics in (raw or {}).items():
        out[str(tweet_id)] = {
            "replies": int(metrics.get("replies", 0)),
            "retweets": int(metrics.get("retweets", 0)),
            "likes": int(metrics.get("likes", 0)),
            "views": int(metrics.get("views", 0)),
        }
    return out


# ---------------------------------------------------------------------------
# Storage
# ---------------------------------------------------------------------------

def store_tweets(
    tweets: List[Dict],
    engagement: Dict[str, Dict[str, int]],
    existing_hashes: set,
    db,
) -> Tuple[int, int]:
    """Store filtered tweets as StyleExample records.

    Returns (saved_count, skipped_dup_count).
    """
    saved = 0
    skipped = 0
    for tweet in tweets:
        text = (tweet.get("text") or "").strip()
        h = content_hash(text)
        if h in existing_hashes:
            skipped += 1
            continue

        tags = _fallback_topic_tags(text)
        example = add_style_example(
            db=db,
            content=text,
            source_type="self_scraped",
            source_url=tweet.get("permalink"),
            topic_tags=tags,
        )
        if example:
            saved += 1
            existing_hashes.add(h)

    return saved, skipped


def save_engagement_json(
    tweets: List[Dict],
    engagement: Dict[str, Dict[str, int]],
    output_path: Path,
) -> None:
    """Persist full tweet data + engagement metrics to JSON."""
    records = []
    for tweet in tweets:
        tid = tweet.get("tweet_id", "")
        record = {
            **tweet,
            "engagement": engagement.get(tid, {"replies": 0, "retweets": 0, "likes": 0, "views": 0}),
        }
        records.append(record)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=2)
    logger.info(f"Engagement data saved to {output_path}")


# ---------------------------------------------------------------------------
# Profile scraping (async core)
# ---------------------------------------------------------------------------

async def scrape_profile(
    scraper: TwitterScraper,
    username: str,
    limit: int,
) -> Tuple[List[Dict], Dict[str, Dict[str, int]]]:
    """Navigate to profile, scroll/collect tweets, extract engagement.

    Args:
        scraper: Authenticated TwitterScraper instance.
        username: X handle (without @).
        limit: Maximum scroll attempts.

    Returns:
        (all_tweets, engagement_map)
    """
    url = f"https://x.com/{username}"
    logger.info(f"Navigating to profile: {url}")

    await scraper.page.goto(url, timeout=60000)

    if "login" in scraper.page.url or "signin" in scraper.page.url:
        raise RuntimeError("Not authenticated — redirected to login page.")

    await scraper.page.wait_for_selector(
        'article[data-testid="tweet"]', timeout=30000,
    )

    seen: Dict[str, Dict] = {}
    idle_scrolls = 0
    max_idle = 5

    for _attempt in range(limit):
        new_tweets = await scraper._collect_tweets_from_page()

        changed = False
        for tweet in new_tweets:
            if tweet["tweet_id"] not in seen:
                seen[tweet["tweet_id"]] = tweet
                changed = True

        if not changed:
            idle_scrolls += 1
            if idle_scrolls >= max_idle:
                break
        else:
            idle_scrolls = 0

        scroll_distance = 800
        await scraper.page.evaluate("(d) => window.scrollBy(0, d)", scroll_distance)
        await scraper._random_delay(1.0, 2.0)

    # Extract engagement metrics for all visible articles
    raw_engagement = await scraper.page.evaluate(ENGAGEMENT_JS)
    engagement = parse_engagement_from_js(raw_engagement)

    all_tweets = sorted(seen.values(), key=lambda t: t.get("timestamp") or "")
    logger.info(f"Collected {len(all_tweets)} raw tweets from @{username}")
    return all_tweets, engagement


# ---------------------------------------------------------------------------
# Main orchestration
# ---------------------------------------------------------------------------

async def run(args: argparse.Namespace) -> None:
    username = args.username.lstrip("@")
    logger.info(f"Starting self-tweet scrape for @{username}")

    scraper = TwitterScraper(headless=True)
    try:
        await scraper.ensure_logged_in()
        all_tweets, engagement = await scrape_profile(scraper, username, args.limit)
    finally:
        await scraper.close()

    filtered = filter_tweets(
        all_tweets,
        target_handle=username,
        min_words=args.min_words,
        include_english=args.include_english,
    )
    logger.info(
        f"Filtered to {len(filtered)} tweets "
        f"(from {len(all_tweets)} raw, min_words={args.min_words}, "
        f"include_english={args.include_english})"
    )

    if args.dry_run:
        print(f"\n{'='*70}")
        print(f"DRY RUN — {len(filtered)} tweets would be saved")
        print(f"{'='*70}\n")
        for i, tweet in enumerate(filtered, 1):
            tid = tweet.get("tweet_id", "")
            eng = engagement.get(tid, {})
            print(f"#{i}  {tweet.get('permalink', '')}")
            print(f"    Words: {count_words(tweet.get('text', ''))}  |  "
                  f"Likes: {eng.get('likes', 0)}  Retweets: {eng.get('retweets', 0)}  "
                  f"Views: {eng.get('views', 0)}")
            print(f"    Tags: {_fallback_topic_tags(tweet.get('text', ''))}")
            preview = (tweet.get("text") or "")[:120].replace("\n", " ")
            print(f"    {preview}{'...' if len(tweet.get('text', '')) > 120 else ''}")
            print()
    else:
        db = SessionLocal()
        try:
            existing_hashes = get_existing_hashes(db)
            saved, skipped = store_tweets(filtered, engagement, existing_hashes, db)
            logger.info(f"Stored {saved} new style examples, skipped {skipped} duplicates")
        finally:
            db.close()

    save_engagement_json(filtered, engagement, ENGAGEMENT_OUTPUT_PATH)

    print(f"\nDone. Raw={len(all_tweets)}  Filtered={len(filtered)}  "
          f"{'(dry-run)' if args.dry_run else ''}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Scrape own X profile tweets for style learning",
    )
    parser.add_argument(
        "--username",
        default=os.getenv("X_PERSONAL_HANDLE", "FinancialEduX"),
        help="X handle to scrape (default: env X_PERSONAL_HANDLE or FinancialEduX)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=50,
        help="Max scroll attempts (default: 50)",
    )
    parser.add_argument(
        "--min-words",
        type=int,
        default=15,
        help="Minimum word count per tweet (default: 15)",
    )
    parser.add_argument(
        "--include-english",
        action="store_true",
        default=False,
        help="Include English tweets (default: Hebrew only)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
        help="Print tweets without saving to DB",
    )
    return parser


if __name__ == "__main__":
    parser = build_parser()
    args = parser.parse_args()
    asyncio.run(run(args))
