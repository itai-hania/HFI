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

from playwright.async_api import async_playwright, Browser, BrowserContext, Page, Response
from fake_useragent import UserAgent
import re

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

        # Initialize media URL tracking
        self.intercepted_media_urls = []

        logger.info(f"TwitterScraper initialized (headless={headless})")

    async def _random_delay(self, min_seconds: float = 2.0, max_seconds: float = 5.0):
        """Add random delay to mimic human behavior"""
        delay = random.uniform(min_seconds, max_seconds)
        await asyncio.sleep(delay)

    async def _init_browser(self, use_session: bool = True):
        """Initialize Playwright browser with Firefox (more stable on macOS)"""
        self.playwright = await async_playwright().start()

        # Launch Firefox browser
        self.browser = await self.playwright.firefox.launch(headless=self.headless)

        # Create context with session if available
        if use_session and self.session_file.exists():
            self.context = await self.browser.new_context(
                storage_state=str(self.session_file),
                locale='en-US',
            )
        else:
            self.context = await self.browser.new_context(locale='en-US')

        self.page = self.context.pages[0] if self.context.pages else await self.context.new_page()

        # Stealth mode: Patch navigator.webdriver to avoid bot detection
        await self.page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
            // Hide automation indicators
            window.chrome = { runtime: {} };
            Object.defineProperty(navigator, 'plugins', {
                get: () => [1, 2, 3, 4, 5]
            });
            Object.defineProperty(navigator, 'languages', {
                get: () => ['en-US', 'en']
            });
        """)

        # Set up cleanup for handlers
        self._handlers = []

        # Passive listener for media URLs (non-blocking)
        async def handle_request(request):
            url = request.url
            if '.m3u8' in url or 'video.twimg.com' in url:
                self.intercepted_media_urls.append(url)
                logger.debug(f"Intercepted media URL: {url}")

        self.page.on("request", handle_request)
        self._handlers.append(lambda: self.page.remove_listener("request", handle_request))

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

        logger.info("\n" + "🔴"*30)
        logger.info("   ACTION REQUIRED: MANUAL LOGIN")
        logger.info("🔴"*30)
        logger.info("1. The browser is open. CLICK on it.")
        logger.info("2. Log in with your credentials manually.")
        logger.info("3. Wait for the home page to load.")
        logger.info("4. COME BACK HERE and press ENTER.")
        logger.info("🔴"*30 + "\n")

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

    async def fetch_thread(self, thread_url: str, max_scroll_attempts: int = 50) -> List[Dict]:
        """
        Fetches a thread from X using authenticated browser session.
        
        Args:
            thread_url: URL of the main tweet
            max_scroll_attempts: Max number of scroll actions
            
        Returns:
            List of tweet dictionaries
        """
        logger.info(f"🧵 Fetching thread: {thread_url}")
        
        if not self.page:
            await self.ensure_logged_in()
            
        try:
            # Capture video streams (using response listener)
            self.video_streams = {}
            
            async def handle_response(response: Response):
                url = response.url
                if "video.twimg.com" in url and (".mp4" in url or ".m3u8" in url):
                    # Basic extraction of a video ID or just storing the URL
                    # In a real implementation, we'd map this to the tweet
                    # For now we store it to potentially map later
                    self.video_streams[url] = url

            self.page.on("response", handle_response)
            
            await self.page.goto(thread_url, timeout=60000)
            
            # Check if logged in (url shouldn't redirect to login)
            if "login" in self.page.url or "signin" in self.page.url:
                raise Exception("Not authenticated - redirected to login.")
                
            # Wait for tweets
            await self.page.wait_for_selector('article[data-testid="tweet"]', timeout=30000)
            
            target_handle = self._extract_handle_from_url(thread_url)

            # Scroll and collect
            raw_tweets = await self._scroll_and_collect(target_handle, max_scroll_attempts)

            # Cleanup listener
            self.page.remove_listener("response", handle_response)

            # Filter to only consecutive author tweets (proper thread extraction)
            tweets = self.filter_author_tweets_only(raw_tweets, target_handle)

            logger.info(f"✅ Scraped {len(tweets)} tweets from thread (filtered from {len(raw_tweets)} raw)")
            return tweets
            
        except Exception as e:
            logger.error(f"❌ Failed to fetch thread: {e}")
            raise

    async def _scroll_and_collect(self, target_handle: str, max_scroll_attempts: int = 50) -> List[Dict]:
        """Scroll page and collect all tweets from thread author."""
        seen = {}  # tweet_id -> tweet_data
        idle_scrolls = 0
        max_idle = 5
        
        for attempt in range(max_scroll_attempts):
            # Expand "Show more replies" buttons
            await self._expand_replies()
            
            # Scroll down
            scroll_distance = random.randint(600, 1000)
            await self.page.evaluate(f"window.scrollBy(0, {scroll_distance});")
            
            # Random delay
            await self._random_delay(1.2, 2.5)
            
            # Collect tweets
            new_tweets = await self._collect_tweets_from_page()
            
            changed = False
            for tweet in new_tweets:
                if tweet["tweet_id"] not in seen:
                    seen[tweet["tweet_id"]] = tweet
                    changed = True
            
            # Stop conditions
            if not changed:
                idle_scrolls += 1
                if idle_scrolls >= max_idle:
                    break  # No new content
            else:
                idle_scrolls = 0
            
            # Stop if we hit a different author's reply (heuristic)
            if self._should_stop_at_other_author(seen, target_handle):
                break
        
        return list(seen.values())

    async def _expand_replies(self):
        """Click 'Show more replies' buttons."""
        patterns = ["Show more", "View replies", "Show thread"]
        try:
            buttons = await self.page.query_selector_all('[role="button"], a[role="link"]')
            
            for btn in buttons:
                try:
                    text = await btn.inner_text()
                    aria = await btn.get_attribute("aria-label") or ""
                    label = f"{text or ''} {aria}".lower()
                    
                    if any(p.lower() in label for p in patterns):
                        await btn.scroll_into_view_if_needed(timeout=500)
                        await btn.click(timeout=700)
                        await asyncio.sleep(random.uniform(0.25, 0.4))
                except Exception:
                    continue
        except Exception:
            pass

    async def _collect_tweets_from_page(self) -> List[Dict]:
        """Run JS to extract tweets from DOM."""
        return await self.page.evaluate("""
            () => {
              const articles = Array.from(document.querySelectorAll('article[data-testid="tweet"]'));
              
              return articles.map(article => {
                // Get tweet link and ID
                const timeEl = article.querySelector("time");
                const link = timeEl?.closest("a") || article.querySelector('a[href*="/status/"]');
                const permalink = link?.href || "";
                const tweetId = permalink.split("/status/")[1]?.split("?")[0] || "";
                
                // Get author info
                const userSection = article.querySelector('div[data-testid="User-Name"]');
                let authorHandle = "";
                let authorName = "";
                for (const span of userSection?.querySelectorAll("span") || []) {
                  const text = span.textContent?.trim() || "";
                  if (text.startsWith("@")) authorHandle = text;
                  else if (!authorName) authorName = text;
                }
                
                // Get tweet text
                const textEl = article.querySelector('div[data-testid="tweetText"]');
                const text = textEl?.innerText || "";
                
                // Get timestamp
                const timestamp = timeEl?.getAttribute("datetime") || null;
                
                // Get media
                const mediaNodes = article.querySelectorAll(
                  '[data-testid="tweetPhoto"], [data-testid="videoPlayer"], [data-testid="videoComponent"]'
                );
                const media = Array.from(mediaNodes).map(node => {
                  const img = node.querySelector("img");
                  const video = node.querySelector("video");
                  return {
                    type: node.getAttribute("data-testid")?.includes("video") ? "video" : "photo",
                    src: img?.src || video?.src || "",
                    alt: img?.alt || ""
                  };
                });
                
                return { tweet_id: tweetId, author_handle: authorHandle, author_name: authorName, 
                         text, permalink, timestamp, media };
              }).filter(t => t.tweet_id && t.permalink);
            }
        """)

    def _extract_handle_from_url(self, url: str) -> str:
        """Extract handle from URL e.g. https://x.com/handle/status/..."""
        # Simple extraction
        # Matches https://x.com/[handle]/status/...
        match = re.search(r'x\.com/([^/]+)/status', url)
        if match:
            return f"@{match.group(1)}"
        return ""

    def _should_stop_at_other_author(self, seen_tweets: Dict, target_handle: str) -> bool:
        """
        Check if we should stop scrolling.
        Stop when we encounter a tweet from a different author AFTER the root tweet.
        This properly captures the thread and stops at replies from others.
        """
        if not target_handle:
            return False

        tweets = list(seen_tweets.values())
        if len(tweets) < 2:
            return False

        # Sort tweets by timestamp to get proper sequence
        sorted_tweets = sorted(tweets, key=lambda t: t.get('timestamp') or '')

        # Normalize target handle
        target = target_handle.lower().lstrip('@')

        # Find first occurrence of target author (root tweet)
        root_idx = -1
        for idx, t in enumerate(sorted_tweets):
            author = t.get('author_handle', '').lower().lstrip('@')
            if author == target:
                root_idx = idx
                break

        if root_idx == -1:
            return False  # Haven't found root yet

        # Check if ANY tweet after root is by different author
        for t in sorted_tweets[root_idx + 1:]:
            author = t.get('author_handle', '').lower().lstrip('@')
            if author and author != target:
                return True  # Stop: found non-author tweet

        return False

    def filter_author_tweets_only(self, tweets: List[Dict], target_handle: str) -> List[Dict]:
        """
        Filter collected tweets to only include consecutive author tweets.
        Sorts by timestamp, starts from root, stops at first non-author tweet.

        Args:
            tweets: List of tweet dicts
            target_handle: Target author handle (e.g., "@elonmusk" or "elonmusk")

        Returns:
            Filtered list of only the target author's consecutive tweets
        """
        if not tweets or not target_handle:
            return tweets

        # Normalize target
        target = target_handle.lower().lstrip('@')

        # Sort by timestamp
        sorted_tweets = sorted(tweets, key=lambda t: t.get('timestamp') or '')

        # Find root tweet (first by target author)
        root_idx = -1
        for idx, t in enumerate(sorted_tweets):
            author = t.get('author_handle', '').lower().lstrip('@')
            if author == target:
                root_idx = idx
                break

        if root_idx == -1:
            return []  # No tweets by target found

        # Collect consecutive author tweets starting from root
        result = []
        for t in sorted_tweets[root_idx:]:
            author = t.get('author_handle', '').lower().lstrip('@')
            if author == target:
                result.append(t)
            else:
                break  # Stop at first non-author tweet

        return result

    async def close(self):
        """Clean up resources"""
        logger.info("Closing browser...")

        try:
            # Clean up event handlers to prevent memory leaks
            if hasattr(self, '_handlers'):
                for handler_cleanup in self._handlers:
                    try:
                        handler_cleanup()
                    except Exception as e:
                        logger.debug(f"Error removing handler: {e}")
                self._handlers.clear()

            if self.context:
                await self.context.close()
            if self.browser:
                await self.browser.close()
            if self.playwright:
                await self.playwright.stop()
        except Exception as e:
            logger.warning(f"Error during cleanup: {e}")

        logger.info("✅ Browser closed")


# CLI test functionality
async def main():
    """Test the scraper"""
    # Run headless now that we have a session
    scraper = TwitterScraper(headless=True)

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

        # Test: Fetch thread
        print("\n🧵 Testing Thread Fetching...")
        if trends:
            # Just search for a tweet to use as 'thread' source or use a fixed one if you had one
            # For now we'll just skip unless we have a known thread URL.
            # But let's try to fetch the thread of the first tweet we found
            if tweet_urls:
                thread_tweets = await scraper.fetch_thread(tweet_urls[0], max_scroll_attempts=3)
                print(f"\n   Fetched {len(thread_tweets)} tweets from thread.")
                print(f"   First tweet: {thread_tweets[0]['text'][:50]}...")

    finally:
        await scraper.close()


if __name__ == "__main__":
    asyncio.run(main())
