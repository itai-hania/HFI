#!/usr/bin/env python3
"""
Scrape engagement metrics for published HFI tweets from @FinancialEduX.

Visits the user's X profile, matches published tweets by text similarity,
and updates TweetEngagement records.

Usage:
    python tools/scrape_engagement.py
    python tools/scrape_engagement.py --username FinancialEduX
    python tools/scrape_engagement.py --dry-run
"""

import argparse
import asyncio
import logging
import math
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from scraper.scraper import TwitterScraper
from common.models import (
    SessionLocal,
    Tweet,
    TweetStatus,
    TweetEngagement,
    StyleExample,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

ENGAGEMENT_JS = """
() => {
  const articles = Array.from(document.querySelectorAll('article[data-testid="tweet"]'));
  const results = [];

  for (const article of articles) {
    const textEl = article.querySelector('div[data-testid="tweetText"]');
    const text = textEl ? textEl.innerText : "";

    const timeEl = article.querySelector("time");
    const link = timeEl?.closest("a") || article.querySelector('a[href*="/status/"]');
    const permalink = link?.href || "";
    const tweetId = permalink.split("/status/")[1]?.split("?")[0] || "";

    function parseCount(ariaLabel) {
      if (!ariaLabel) return 0;
      const match = ariaLabel.match(/([\\d,]+)/);
      if (match) return parseInt(match[1].replace(/,/g, ""), 10) || 0;
      return 0;
    }

    const replyBtn = article.querySelector('button[data-testid="reply"]');
    const retweetBtn = article.querySelector('button[data-testid="retweet"]');
    const likeBtn = article.querySelector('button[data-testid="like"]');
    const bookmarkBtn = article.querySelector('button[data-testid="bookmark"]');
    const analyticsLink = article.querySelector('a[href*="/analytics"]');

    results.push({
      tweet_id: tweetId,
      text: text,
      permalink: permalink,
      replies: parseCount(replyBtn?.getAttribute("aria-label")),
      retweets: parseCount(retweetBtn?.getAttribute("aria-label")),
      likes: parseCount(likeBtn?.getAttribute("aria-label")),
      bookmarks: parseCount(bookmarkBtn?.getAttribute("aria-label")),
      views: parseCount(analyticsLink?.getAttribute("aria-label")),
    });
  }
  return results;
}
"""


def _normalize_text(text: str) -> str:
    """Normalize whitespace and strip for comparison."""
    return re.sub(r'\s+', ' ', (text or "")).strip()


def match_tweet_text(scraped_text: str, db_text: str) -> bool:
    """Fuzzy match scraped tweet text against DB tweet text.

    Normalizes whitespace, compares first 100 characters.
    """
    a = _normalize_text(scraped_text)[:100]
    b = _normalize_text(db_text)[:100]
    if not a or not b:
        return False
    return a == b


def compute_engagement_score(likes: int, retweets: int, replies: int,
                              views: int, bookmarks: int = 0) -> int:
    """Compute weighted engagement score (same formula as TweetEngagement.compute_score)."""
    return (
        likes * 3 +
        retweets * 5 +
        replies * 2 +
        bookmarks * 4 +
        int(math.log2(max(views, 1)))
    )


def propagate_engagement_to_styles(db) -> int:
    """Copy engagement_score from TweetEngagement to linked StyleExamples.

    Returns count of style examples updated.
    """
    styles = (
        db.query(StyleExample)
        .filter(StyleExample.derived_from_tweet_id.isnot(None))
        .filter(StyleExample.is_active == True)
        .all()
    )
    if not styles:
        return 0

    tweet_ids = [s.derived_from_tweet_id for s in styles]
    engagements = (
        db.query(TweetEngagement)
        .filter(TweetEngagement.tweet_id.in_(tweet_ids))
        .all()
    )
    eng_map = {e.tweet_id: e.engagement_score for e in engagements}

    updated = 0
    for style in styles:
        score = eng_map.get(style.derived_from_tweet_id, 0)
        if style.engagement_score != score:
            style.engagement_score = score
            updated += 1

    if updated:
        db.commit()
    logger.info(f"Propagated engagement to {updated} style examples")
    return updated


async def scrape_engagement(username: str, dry_run: bool = False) -> int:
    """Scrape engagement metrics for published tweets.

    Args:
        username: X handle (without @).
        dry_run: If True, print results without writing to DB.

    Returns:
        Count of engagement records created or updated.
    """
    db = SessionLocal()
    try:
        published = (
            db.query(Tweet)
            .filter(Tweet.status == TweetStatus.PUBLISHED)
            .all()
        )
        if not published:
            logger.info("No published tweets found")
            return 0

        logger.info(f"Found {len(published)} published tweets to match")

        scraper = TwitterScraper(headless=True)
        try:
            await scraper.ensure_logged_in()

            url = f"https://x.com/{username}"
            logger.info(f"Navigating to profile: {url}")
            await scraper.page.goto(url, timeout=60000)

            if "login" in scraper.page.url or "signin" in scraper.page.url:
                raise RuntimeError("Not authenticated — redirected to login page.")

            await scraper.page.wait_for_selector(
                'article[data-testid="tweet"]', timeout=30000,
            )

            all_scraped = []
            seen_ids = set()
            idle_scrolls = 0
            max_idle = 5

            for _ in range(50):
                raw = await scraper.page.evaluate(ENGAGEMENT_JS)
                changed = False
                for item in (raw or []):
                    tid = item.get("tweet_id", "")
                    if tid and tid not in seen_ids:
                        seen_ids.add(tid)
                        all_scraped.append(item)
                        changed = True

                if not changed:
                    idle_scrolls += 1
                    if idle_scrolls >= max_idle:
                        break
                else:
                    idle_scrolls = 0

                await scraper.page.evaluate("window.scrollBy(0, 800)")
                await scraper._random_delay(1.0, 2.0)

        finally:
            await scraper.close()

        logger.info(f"Scraped {len(all_scraped)} tweets from @{username}")

        updated_count = 0
        now = datetime.now(timezone.utc)

        for scraped in all_scraped:
            scraped_text = scraped.get("text", "")
            x_post_id = scraped.get("tweet_id", "")

            matched_tweet = None
            for pub in published:
                if match_tweet_text(scraped_text, pub.hebrew_draft or ""):
                    matched_tweet = pub
                    break

            if not matched_tweet:
                continue

            if dry_run:
                score = compute_engagement_score(
                    scraped.get("likes", 0),
                    scraped.get("retweets", 0),
                    scraped.get("replies", 0),
                    scraped.get("views", 0),
                    scraped.get("bookmarks", 0),
                )
                preview = _normalize_text(scraped_text)[:80]
                print(f"  Match: tweet_id={matched_tweet.id} x_post={x_post_id} "
                      f"score={score} | {preview}")
                updated_count += 1
                continue

            eng = (
                db.query(TweetEngagement)
                .filter(TweetEngagement.tweet_id == matched_tweet.id)
                .first()
            )

            if eng:
                eng.likes = scraped.get("likes", 0)
                eng.retweets = scraped.get("retweets", 0)
                eng.replies = scraped.get("replies", 0)
                eng.views = scraped.get("views", 0)
                eng.bookmarks = scraped.get("bookmarks", 0)
                eng.last_scraped_at = now
                if x_post_id:
                    eng.x_post_id = x_post_id
            else:
                eng = TweetEngagement(
                    tweet_id=matched_tweet.id,
                    x_post_id=x_post_id or None,
                    likes=scraped.get("likes", 0),
                    retweets=scraped.get("retweets", 0),
                    replies=scraped.get("replies", 0),
                    views=scraped.get("views", 0),
                    bookmarks=scraped.get("bookmarks", 0),
                    first_scraped_at=now,
                    last_scraped_at=now,
                )
                db.add(eng)

            eng.compute_score()
            updated_count += 1

        if not dry_run:
            db.commit()
            propagate_engagement_to_styles(db)

        logger.info(f"{'Would update' if dry_run else 'Updated'} {updated_count} engagement records")
        return updated_count

    finally:
        db.close()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Scrape engagement metrics for published HFI tweets",
    )
    parser.add_argument(
        "--username",
        default=os.getenv("X_PERSONAL_HANDLE", "FinancialEduX"),
        help="X handle to scrape (default: env X_PERSONAL_HANDLE or FinancialEduX)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
        help="Print matches without saving to DB",
    )
    return parser


if __name__ == "__main__":
    parser = build_parser()
    args = parser.parse_args()
    count = asyncio.run(scrape_engagement(args.username, dry_run=args.dry_run))
    print(f"\nDone. Updated {count} engagement records.")
