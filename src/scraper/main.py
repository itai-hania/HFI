"""
Main entry point for the Scraper service

This script orchestrates the scraping workflow:
1. Ensures logged in to X/Twitter
2. Fetches trending topics
3. Searches for tweets related to top trends
4. Saves data to database
"""

import asyncio
import sys
import os
import logging
from pathlib import Path
from datetime import datetime

# Add parent directory to path for imports
sys.path.append(str(Path(__file__).parent.parent))

from scraper import TwitterScraper
from common.models import create_tables, get_db_session, Tweet, Trend

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def scrape_trending_workflow(
    max_trends: int = 5,
    tweets_per_trend: int = 3,
    headless: bool = True
):
    """
    Main scraping workflow

    Args:
        max_trends: Maximum number of trending topics to process
        tweets_per_trend: Number of tweets to scrape per trend
        headless: Run browser in headless mode
    """
    logger.info("🚀 Starting HFI Scraper Service")
    logger.info("="*60)

    # Initialize database
    try:
        create_tables()
        db = get_db_session()
        logger.info("✅ Database initialized")
    except Exception as e:
        logger.error(f"❌ Database initialization failed: {e}")
        return

    # Initialize scraper
    scraper = TwitterScraper(headless=headless)

    try:
        # Step 1: Ensure logged in
        logger.info("\n📝 Step 1: Verifying X/Twitter login...")
        await scraper.ensure_logged_in()

        # Step 2: Get trending topics
        logger.info(f"\n📊 Step 2: Fetching top {max_trends} trending topics...")
        trends = await scraper.get_trending_topics(limit=max_trends)

        if not trends:
            logger.warning("⚠️  No trends found. Exiting.")
            return

        # Save trends to database
        saved_trends = []
        for trend_data in trends:
            # Check if trend already exists (by title and today's date)
            existing = db.query(Trend).filter(
                Trend.title == trend_data['title']
            ).filter(
                Trend.discovered_at >= datetime.utcnow().replace(hour=0, minute=0, second=0)
            ).first()

            if not existing:
                db_trend = Trend(
                    title=trend_data['title'],
                    description=trend_data.get('description', ''),
                    source='X'
                )
                db.add(db_trend)
                saved_trends.append(trend_data)
                logger.info(f"  ✓ Saved trend: {trend_data['title']}")
            else:
                logger.info(f"  ⊙ Trend already exists: {trend_data['title']}")
                saved_trends.append(trend_data)

        db.commit()
        logger.info(f"✅ Saved {len(saved_trends)} trends to database")

        # Step 3: Scrape tweets for each trend
        logger.info(f"\n🐦 Step 3: Scraping {tweets_per_trend} tweets per trend...")

        total_tweets_scraped = 0

        for trend_data in saved_trends[:max_trends]:
            topic = trend_data['title']
            logger.info(f"\n--- Processing trend: {topic} ---")

            try:
                # Search for tweets related to this trend
                tweet_urls = await scraper.search_tweets_by_topic(topic, limit=tweets_per_trend)

                if not tweet_urls:
                    logger.warning(f"  ⚠️  No tweets found for: {topic}")
                    continue

                # Scrape content from each tweet
                for tweet_url in tweet_urls:
                    try:
                        # Check if tweet already exists
                        existing_tweet = db.query(Tweet).filter(
                            Tweet.source_url == tweet_url
                        ).first()

                        if existing_tweet:
                            logger.info(f"  ⊙ Tweet already exists: {tweet_url}")
                            continue

                        # Scrape tweet content
                        tweet_data = await scraper.get_tweet_content(tweet_url)

                        # Save to database
                        db_tweet = Tweet(
                            source_url=tweet_data['source_url'],
                            original_text=tweet_data['text'],
                            media_url=tweet_data.get('media_url'),
                            trend_topic=topic,
                            status='pending'  # Will be processed by Processor service
                        )
                        db.add(db_tweet)
                        db.commit()

                        total_tweets_scraped += 1
                        logger.info(f"  ✓ Saved tweet {total_tweets_scraped}: {tweet_url}")

                        # Random delay between tweets to avoid rate limiting
                        await asyncio.sleep(2)

                    except Exception as e:
                        logger.error(f"  ❌ Failed to scrape tweet {tweet_url}: {e}")
                        continue

            except Exception as e:
                logger.error(f"❌ Failed to process trend '{topic}': {e}")
                continue

        logger.info("\n" + "="*60)
        logger.info(f"🎉 Scraping completed!")
        logger.info(f"   Total trends: {len(saved_trends)}")
        logger.info(f"   Total tweets scraped: {total_tweets_scraped}")
        logger.info("="*60)

    except Exception as e:
        logger.error(f"❌ Scraping workflow failed: {e}")
        raise

    finally:
        # Cleanup
        await scraper.close()
        db.close()
        logger.info("✅ Resources cleaned up")


def main():
    """Entry point"""
    # Configuration from environment variables
    max_trends = int(os.getenv('SCRAPER_MAX_TRENDS', '5'))
    tweets_per_trend = int(os.getenv('SCRAPER_TWEETS_PER_TREND', '3'))
    headless = os.getenv('SCRAPER_HEADLESS', 'true').lower() == 'true'

    logger.info(f"Configuration:")
    logger.info(f"  Max trends: {max_trends}")
    logger.info(f"  Tweets per trend: {tweets_per_trend}")
    logger.info(f"  Headless mode: {headless}")

    # Run the scraping workflow
    try:
        asyncio.run(scrape_trending_workflow(
            max_trends=max_trends,
            tweets_per_trend=tweets_per_trend,
            headless=headless
        ))
    except KeyboardInterrupt:
        logger.info("\n⚠️  Scraper interrupted by user")
    except Exception as e:
        logger.error(f"❌ Scraper failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
