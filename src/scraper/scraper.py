"""
Twitter/X Scraper using Playwright

This module handles web scraping of Twitter/X for trending topics and tweet content.
Uses Playwright for browser automation with anti-detection measures.

Key Features:
- Session persistence (saves login state)
- Anti-bot detection (randomized delays, user agent spoofing)
- Headless browser automation
- Network interception for media URLs
"""

import asyncio
import json
import random
import logging
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime

from playwright.async_api import async_playwright, Browser, BrowserContext, Page
from fake_useragent import UserAgent

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class TwitterScraper:
    """
    Async Twitter/X scraper with session management and anti-detection
    """

    def __init__(self, headless: bool = True, max_interactions: int = 50):
        """
        Initialize the scraper

        Args:
            headless: Run browser in headless mode (default: True)
            max_interactions: Maximum interactions per session to avoid detection
        """
        self.headless = headless
        self.max_interactions = max_interactions
        self.interaction_count = 0

        # Paths
        self.session_dir = Path(__file__).parent.parent.parent / "data" / "session"
        self.session_dir.mkdir(parents=True, exist_ok=True)
        self.session_file = self.session_dir / "storage_state.json"

        # Playwright objects
        self.playwright = None
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None

        # User agent for anti-detection
        ua = UserAgent()
        self.user_agent = ua.random

        logger.info(f"TwitterScraper initialized (headless={headless})")

    async def _random_delay(self, min_seconds: float = 2.0, max_seconds: float = 5.0):
        """Add random delay to mimic human behavior"""
        delay = random.uniform(min_seconds, max_seconds)
        await asyncio.sleep(delay)

    async def _init_browser(self, use_session: bool = True):
        """Initialize Playwright browser with anti-detection measures"""
        self.playwright = await async_playwright().start()

        # Launch browser with anti-detection settings
        self.browser = await self.playwright.chromium.launch(
            headless=self.headless,
            args=[
                '--disable-blink-features=AutomationControlled',
                '--disable-dev-shm-usage',
                '--no-sandbox',
                '--disable-setuid-sandbox',
            ]
        )

        # Create context with saved session if available
        context_options = {
            'user_agent': self.user_agent,
            'viewport': {'width': 1920, 'height': 1080},
            'locale': 'en-US',
        }

        if use_session and self.session_file.exists():
            logger.info("Loading saved session...")
            context_options['storage_state'] = str(self.session_file)

        self.context = await self.browser.new_context(**context_options)

        # Disable webdriver flag for anti-detection
        await self.context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {
                get: () => false
            });
        """)

        self.page = await self.context.new_page()

        # Set up network interception for media URLs
        self.intercepted_media_urls = []

        async def route_handler(route):
            url = route.request.url
            # Intercept HLS video playlists (.m3u8)
            if '.m3u8' in url or 'video' in url:
                self.intercepted_media_urls.append(url)
                logger.debug(f"Intercepted media URL: {url}")
            await route.continue_()

        await self.page.route("**/*", route_handler)

        logger.info("Browser initialized successfully")

    async def ensure_logged_in(self):
        """
        Ensure user is logged in to X/Twitter

        If no session exists, launches browser in headful mode for manual login.
        Saves session state after successful login.
        """
        if self.session_file.exists():
            logger.info("Session file exists, attempting to use saved session...")
            await self._init_browser(use_session=True)

            # Verify session is valid by checking home page
            try:
                await self.page.goto('https://x.com/home', timeout=30000)
                await self.page.wait_for_selector('[data-testid="primaryColumn"]', timeout=10000)
                logger.info("✅ Session valid - logged in successfully")
                return
            except Exception as e:
                logger.warning(f"Session expired or invalid: {e}")
                await self.close()
                self.session_file.unlink()  # Delete invalid session

        # No valid session - need manual login
        logger.info("⚠️  No valid session found. Starting manual login process...")
        logger.info("📝 Please log in manually in the browser window that will open...")

        # Launch in headful mode for manual login
        original_headless = self.headless
        self.headless = False
        await self._init_browser(use_session=False)

        # Navigate to login page
        await self.page.goto('https://x.com/login', timeout=30000)

        logger.info("\n" + "="*60)
        logger.info("🔐 MANUAL LOGIN REQUIRED")
        logger.info("="*60)
        logger.info("1. Please log in to X/Twitter in the browser window")
        logger.info("2. Complete any 2FA if required")
        logger.info("3. Wait until you see your home feed")
        logger.info("4. Press ENTER in this terminal when done...")
        logger.info("="*60 + "\n")

        # Wait for user to complete login
        input("Press ENTER after you've logged in successfully: ")

        # Verify login by checking for home feed element
        try:
            await self.page.wait_for_selector('[data-testid="primaryColumn"]', timeout=5000)
            logger.info("✅ Login verified!")

            # Save session state
            await self.context.storage_state(path=str(self.session_file))
            logger.info(f"✅ Session saved to: {self.session_file}")

            # Restore original headless setting
            self.headless = original_headless

        except Exception as e:
            logger.error(f"❌ Login verification failed: {e}")
            raise Exception("Login was not successful. Please try again.")

    async def get_trending_topics(self, limit: int = 10) -> List[Dict]:
        """
        Scrape trending topics from X/Twitter explore page

        Args:
            limit: Maximum number of trends to return (default: 10)

        Returns:
            List of dicts with keys: title, description, tweets (if available)
        """
        logger.info(f"🔍 Fetching top {limit} trending topics...")

        if not self.page:
            await self.ensure_logged_in()

        try:
            # Navigate to trending page
            await self.page.goto('https://x.com/explore/tabs/trending', timeout=30000)
            await self._random_delay(3, 5)

            # Wait for trends to load
            await self.page.wait_for_selector('[data-testid="trend"]', timeout=15000)

            # Extract trends
            trends = []
            trend_elements = await self.page.query_selector_all('[data-testid="trend"]')

            for idx, element in enumerate(trend_elements[:limit]):
                try:
                    # Extract text content from the trend element
                    text_content = await element.inner_text()
                    lines = [line.strip() for line in text_content.split('\n') if line.strip()]

                    # Parse trend structure (usually: category, title, tweet_count)
                    trend_data = {
                        'title': lines[1] if len(lines) > 1 else lines[0],
                        'description': ' '.join(lines[2:]) if len(lines) > 2 else '',
                        'category': lines[0] if len(lines) > 1 else 'Trending',
                        'scraped_at': datetime.utcnow().isoformat()
                    }

                    trends.append(trend_data)
                    logger.info(f"  ✓ Trend {idx+1}: {trend_data['title']}")

                except Exception as e:
                    logger.warning(f"Failed to parse trend element {idx}: {e}")
                    continue

            self.interaction_count += 1
            logger.info(f"✅ Successfully scraped {len(trends)} trending topics")
            return trends

        except Exception as e:
            logger.error(f"❌ Failed to get trending topics: {e}")
            raise

    async def get_tweet_content(self, tweet_url: str) -> Dict:
        """
        Scrape content from a specific tweet

        Args:
            tweet_url: Full URL to the tweet (e.g., https://x.com/user/status/123...)

        Returns:
            Dict with keys:
                - text: Tweet text content
                - media_url: URL of video/image if exists (None otherwise)
                - author: Tweet author username
                - timestamp: When tweet was posted
        """
        logger.info(f"📥 Fetching tweet content from: {tweet_url}")

        if not self.page:
            await self.ensure_logged_in()

        try:
            # Clear previous intercepted URLs
            self.intercepted_media_urls = []

            # Navigate to tweet
            await self.page.goto(tweet_url, timeout=30000)
            await self._random_delay(2, 4)

            # Wait for tweet to load
            await self.page.wait_for_selector('[data-testid="tweetText"]', timeout=15000)

            # Extract tweet text
            tweet_text_element = await self.page.query_selector('[data-testid="tweetText"]')
            tweet_text = await tweet_text_element.inner_text() if tweet_text_element else ""

            # Extract author (username)
            author = "unknown"
            try:
                author_element = await self.page.query_selector('[data-testid="User-Name"] a')
                if author_element:
                    author_href = await author_element.get_attribute('href')
                    author = author_href.strip('/') if author_href else "unknown"
            except Exception as e:
                logger.debug(f"Could not extract author: {e}")

            # Extract timestamp
            timestamp = None
            try:
                time_element = await self.page.query_selector('time')
                if time_element:
                    timestamp = await time_element.get_attribute('datetime')
            except Exception as e:
                logger.debug(f"Could not extract timestamp: {e}")

            # Check for media (video/image)
            media_url = None

            # Wait a bit for network requests to complete
            await asyncio.sleep(2)

            # Check intercepted URLs for media
            if self.intercepted_media_urls:
                # Prefer .m3u8 URLs (HLS video)
                m3u8_urls = [url for url in self.intercepted_media_urls if '.m3u8' in url]
                if m3u8_urls:
                    # Get highest quality variant (usually has 'high' or largest resolution in URL)
                    media_url = sorted(m3u8_urls, reverse=True)[0]
                else:
                    media_url = self.intercepted_media_urls[0]

            # Fallback: Check for image in DOM
            if not media_url:
                try:
                    img_element = await self.page.query_selector('[data-testid="tweetPhoto"] img')
                    if img_element:
                        media_url = await img_element.get_attribute('src')
                except Exception as e:
                    logger.debug(f"No image found: {e}")

            tweet_data = {
                'text': tweet_text,
                'media_url': media_url,
                'author': author,
                'timestamp': timestamp,
                'source_url': tweet_url,
                'scraped_at': datetime.utcnow().isoformat()
            }

            self.interaction_count += 1
            logger.info(f"✅ Tweet scraped successfully")
            logger.info(f"   Text: {tweet_text[:100]}...")
            logger.info(f"   Media: {'Yes' if media_url else 'No'}")

            return tweet_data

        except Exception as e:
            logger.error(f"❌ Failed to get tweet content: {e}")
            raise

    async def search_tweets_by_topic(self, topic: str, limit: int = 5) -> List[str]:
        """
        Search for tweet URLs related to a topic

        Args:
            topic: Search query/hashtag
            limit: Maximum number of tweet URLs to return

        Returns:
            List of tweet URLs
        """
        logger.info(f"🔎 Searching tweets for topic: {topic}")

        if not self.page:
            await self.ensure_logged_in()

        try:
            # Navigate to search page
            search_url = f"https://x.com/search?q={topic}&src=trend_click&f=live"
            await self.page.goto(search_url, timeout=30000)
            await self._random_delay(3, 5)

            # Wait for tweets to load
            await self.page.wait_for_selector('[data-testid="tweet"]', timeout=15000)

            # Extract tweet URLs
            tweet_urls = []
            tweet_elements = await self.page.query_selector_all('[data-testid="tweet"]')

            for element in tweet_elements[:limit * 2]:  # Get extra in case some fail
                try:
                    # Find the link to the tweet
                    link_element = await element.query_selector('a[href*="/status/"]')
                    if link_element:
                        href = await link_element.get_attribute('href')
                        if href and '/status/' in href:
                            full_url = f"https://x.com{href}" if href.startswith('/') else href
                            if full_url not in tweet_urls:
                                tweet_urls.append(full_url)
                                logger.info(f"  ✓ Found tweet: {full_url}")

                            if len(tweet_urls) >= limit:
                                break

                except Exception as e:
                    logger.debug(f"Failed to extract tweet URL: {e}")
                    continue

            self.interaction_count += 1
            logger.info(f"✅ Found {len(tweet_urls)} tweets for topic: {topic}")
            return tweet_urls

        except Exception as e:
            logger.error(f"❌ Failed to search tweets: {e}")
            return []

    async def close(self):
        """Clean up resources"""
        logger.info("Closing browser...")

        if self.page:
            await self.page.close()
        if self.context:
            await self.context.close()
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()

        logger.info("✅ Browser closed")


# CLI test functionality
async def main():
    """Test the scraper"""
    scraper = TwitterScraper(headless=False)

    try:
        # Ensure logged in
        await scraper.ensure_logged_in()

        # Test: Get trending topics
        trends = await scraper.get_trending_topics(limit=5)
        print("\n📊 Trending Topics:")
        for i, trend in enumerate(trends, 1):
            print(f"{i}. {trend['title']} - {trend['description']}")

        # Test: Search tweets for first trend
        if trends:
            first_trend = trends[0]['title']
            tweet_urls = await scraper.search_tweets_by_topic(first_trend, limit=3)

            # Test: Get content from first tweet
            if tweet_urls:
                tweet_data = await scraper.get_tweet_content(tweet_urls[0])
                print(f"\n📝 Sample Tweet:")
                print(f"   Author: {tweet_data['author']}")
                print(f"   Text: {tweet_data['text'][:200]}")
                print(f"   Has Media: {bool(tweet_data['media_url'])}")

    finally:
        await scraper.close()


if __name__ == "__main__":
    asyncio.run(main())
