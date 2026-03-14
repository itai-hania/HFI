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
import os
import random
import logging
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime
from urllib.parse import quote

from playwright.async_api import async_playwright, Browser, BrowserContext, Page, Response
from fake_useragent import UserAgent
import re

from scraper.errors import SessionExpiredError

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

_VALID_BROWSERS = {"chromium", "firefox", "webkit"}


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

        self.browser_type = os.environ.get("SCRAPER_BROWSER", "chromium").lower()
        if self.browser_type not in _VALID_BROWSERS:
            self.browser_type = "chromium"

        # Paths — honour SESSION_DIR env var for persistent session across deploys.
        # Falls back to <repo>/data/session/ for local dev.
        env_session_dir = os.environ.get("SESSION_DIR")
        if env_session_dir:
            self.session_dir = Path(env_session_dir)
        else:
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
        """Initialize Playwright browser (configurable via SCRAPER_BROWSER env var)"""
        self.playwright = await async_playwright().start()

        launcher = getattr(self.playwright, self.browser_type)
        self.browser = await launcher.launch(headless=self.headless)

        # Create context with session if available
        if use_session and self.session_file.exists():
            self.context = await self.browser.new_context(
                storage_state=str(self.session_file),
                locale='en-US',
            )
        else:
            self.context = await self.browser.new_context(locale='en-US')

        self.page = self.context.pages[0] if self.context.pages else await self.context.new_page()

        # Stealth mode: browser-appropriate anti-detection scripts
        if self.browser_type == "chromium":
            await self.page.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
                window.chrome = { runtime: {} };
                Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
                Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en'] });
            """)
        else:
            await self.page.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
                Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en'] });
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
        In headless mode, raises SessionExpiredError instead of blocking on input().
        """
        if self.session_file.exists():
            logger.info("Session file exists, attempting to use saved session...")
            await self._init_browser(use_session=True)

            # Verify session is valid by checking home page
            try:
                await self.page.goto('https://x.com/home', timeout=15000)
                await self.page.wait_for_selector('[data-testid="primaryColumn"]', timeout=10000)
                logger.info("✅ Session valid - logged in successfully")
                return
            except Exception as e:
                logger.warning(f"Session expired or invalid: {e}")
                await self.close()
                if self.session_file.exists():
                    self.session_file.unlink()
                if self.headless:
                    raise SessionExpiredError(
                        "X session expired. Run 'python tools/refresh_session.py' "
                        "locally, then copy data/session/storage_state.json to the server."
                    ) from e

        if self.headless:
            raise SessionExpiredError(
                "X session expired or missing. Run 'python tools/refresh_session.py' "
                "locally, then copy data/session/storage_state.json to the server."
            )

        # Non-headless manual login path
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

            # Expand truncated long tweets
            await self._expand_long_tweets()
            await asyncio.sleep(0.3)

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

    async def search_by_user_engagement(
        self,
        username: str,
        min_faves: int = 100,
        keyword: str = "",
        limit: int = 20,
        since: str | None = None,
        until: str | None = None,
    ) -> List[Dict]:
        """
        Search X for high-engagement posts by user.

        Returns a list of dicts with:
        tweet_id, text, permalink, likes, retweets, views, timestamp, author_handle.
        """
        if not username:
            return []

        query = f"from:{username} min_faves:{int(min_faves)}"
        if keyword and keyword.strip():
            query = f"{query} {keyword.strip()}"
        if since:
            query = f"{query} since:{since}"
        if until:
            query = f"{query} until:{until}"

        if not self.page:
            await self.ensure_logged_in()

        logger.info(f"🔎 Searching engagement posts: {query}")
        search_url = f"https://x.com/search?q={quote(query)}&src=typed_query&f=top"

        try:
            await self.page.goto(search_url, timeout=45000)
            await self._random_delay(1.5, 2.8)
            await self.page.wait_for_selector('article[data-testid=\"tweet\"]', timeout=15000)
            await self._validate_page_loaded()

            collected: Dict[str, Dict] = {}
            max_scrolls = 10

            for _ in range(max_scrolls):
                rows = await self.page.evaluate(
                    """
                    () => {
                      const parseCount = (value) => {
                        if (!value) return 0;
                        const clean = value.replace(/,/g, '').trim();
                        const match = clean.match(/(\\d+(?:\\.\\d+)?)([KkMm])?/);
                        if (!match) return 0;
                        let num = parseFloat(match[1]);
                        const suffix = (match[2] || '').toUpperCase();
                        if (suffix === 'K') num *= 1000;
                        if (suffix === 'M') num *= 1000000;
                        return Math.round(num);
                      };

                      const readMetric = (article, testid, pattern) => {
                        const el = article.querySelector(`[data-testid="${testid}"]`);
                        if (!el) return 0;
                        const label = el.getAttribute('aria-label') || el.textContent || '';
                        const m = label.match(pattern);
                        if (!m) return parseCount(label);
                        return parseCount(m[1]);
                      };

                      const rows = [];
                      const articles = Array.from(document.querySelectorAll('article[data-testid="tweet"]'));
                      for (const article of articles) {
                        const timeEl = article.querySelector('time');
                        const link = timeEl?.closest('a') || article.querySelector('a[href*="/status/"]');
                        const permalink = link?.href || '';
                        const tweetId = permalink.includes('/status/') ? permalink.split('/status/')[1]?.split('?')[0] : '';
                        if (!tweetId) continue;

                        const textEl = article.querySelector('[data-testid="tweetText"]');
                        const text = textEl?.innerText || '';

                        const userSection = article.querySelector('div[data-testid="User-Name"]');
                        let authorHandle = '';
                        for (const span of userSection?.querySelectorAll('span') || []) {
                          const t = span.textContent?.trim() || '';
                          if (t.startsWith('@')) {
                            authorHandle = t;
                            break;
                          }
                        }

                        const likes = readMetric(article, 'like', /(\\d[\\d,.]*[KkMm]?)\\s+likes?/i);
                        const retweets = readMetric(article, 'retweet', /(\\d[\\d,.]*[KkMm]?)\\s+(reposts?|retweets?)/i);
                        let views = 0;
                        const analytics = article.querySelector('a[href*=\"/analytics\"]');
                        if (analytics) {
                          const label = analytics.getAttribute('aria-label') || analytics.textContent || '';
                          const m = label.match(/(\\d[\\d,.]*[KkMm]?)\\s+views?/i);
                          views = parseCount(m ? m[1] : label);
                        }

                        rows.push({
                          tweet_id: tweetId,
                          text,
                          permalink,
                          likes,
                          retweets,
                          views,
                          timestamp: timeEl?.getAttribute('datetime') || null,
                          author_handle: authorHandle,
                        });
                      }
                      return rows;
                    }
                    """
                )

                changed = False
                for row in rows:
                    tweet_id = row.get("tweet_id")
                    if not tweet_id:
                        continue
                    current = collected.get(tweet_id)
                    # Keep the richer row if we observe updated metrics.
                    if not current or (
                        int(row.get("likes", 0)) + int(row.get("retweets", 0)) + int(row.get("views", 0))
                        > int(current.get("likes", 0)) + int(current.get("retweets", 0)) + int(current.get("views", 0))
                    ):
                        collected[tweet_id] = row
                        changed = True

                high_engagement = [r for r in collected.values() if int(r.get("likes", 0)) >= int(min_faves)]
                if len(high_engagement) >= limit:
                    break

                if not changed and len(collected) >= limit * 2:
                    break

                await self.page.evaluate("window.scrollBy(0, 1200)")
                await self._random_delay(0.8, 1.6)

            results = [r for r in collected.values() if int(r.get("likes", 0)) >= int(min_faves)]
            results.sort(key=lambda item: int(item.get("likes", 0)), reverse=True)
            logger.info(f"✅ Found {len(results)} posts for {username} with likes>={min_faves}")
            return results[:limit]

        except SessionExpiredError:
            raise
        except Exception as e:
            logger.error(f"❌ Failed user engagement search for {username}: {e}")
            return []

    async def fetch_raw_thread(self, thread_url: str, max_scroll_attempts: int = 20, author_only: bool = True) -> Dict:
        """
        Fetches a thread from X. By default, filters to only the author's consecutive tweets.

        A THREAD is defined as consecutive tweets by the SAME author.
        When author_only=True (default):
        - Starts from the root tweet
        - Collects consecutive tweets by the same author
        - Stops when encountering a tweet from a different author

        Args:
            thread_url: URL of the main tweet
            max_scroll_attempts: Max number of scroll actions (default: 20)
            author_only: If True (default), only return author's consecutive tweets.
                        If False, return all tweets including replies.

        Returns:
            Dict with thread metadata and tweets:
            {
                'source_url': str,
                'author_handle': str,
                'author_name': str,
                'tweet_count': int,
                'tweets': List[Dict],
                'scraped_at': str
            }
        """
        mode = "AUTHOR ONLY" if author_only else "ALL (raw)"
        logger.info(f"🧵 Fetching thread ({mode}): {thread_url}")

        if not self.page:
            await self.ensure_logged_in()

        try:
            # Capture video streams
            self.video_streams = {}

            async def handle_response(response: Response):
                url = response.url
                if "video.twimg.com" in url and (".mp4" in url or ".m3u8" in url):
                    match = re.search(r'ext_tw_video/(\d+)/', url)
                    if match:
                        self.video_streams[match.group(1)] = url
                    else:
                        self.video_streams[url] = url

            self.page.on("response", handle_response)

            await self.page.goto(thread_url, timeout=60000)
            await self.page.wait_for_selector('article[data-testid="tweet"]', timeout=30000)
            await self._validate_page_loaded()

            target_handle = self._extract_handle_from_url(thread_url)

            # Scroll and collect tweets
            all_tweets = await self._scroll_and_collect_all(max_scroll_attempts)

            # Cleanup listener
            self.page.remove_listener("response", handle_response)

            # Filter to author's consecutive tweets if author_only=True
            if author_only and target_handle:
                filtered_tweets = self.filter_author_tweets_only(all_tweets, target_handle)
                logger.info(f"   Filtered: {len(all_tweets)} raw -> {len(filtered_tweets)} author tweets")
                tweets_to_return = filtered_tweets
            else:
                tweets_to_return = all_tweets

            tweets_to_return = self._merge_video_streams(tweets_to_return)

            # Find author info from first matching tweet
            author_name = ""
            for t in tweets_to_return:
                if t.get('author_handle', '').lower().lstrip('@') == target_handle.lower().lstrip('@'):
                    author_name = t.get('author_name', '')
                    break

            result = {
                'source_url': thread_url,
                'author_handle': target_handle,
                'author_name': author_name,
                'tweet_count': len(tweets_to_return),
                'tweets': tweets_to_return,
                'scraped_at': datetime.utcnow().isoformat()
            }

            logger.info(f"✅ Scraped {len(tweets_to_return)} tweets from thread ({mode})")
            return result

        except Exception as e:
            logger.error(f"❌ Failed to fetch thread: {e}")
            raise

    async def _scroll_and_collect_all(self, max_scroll_attempts: int = 50) -> List[Dict]:
        """Scroll page and collect ALL tweets without filtering."""
        seen = {}
        idle_scrolls = 0
        max_idle = 5

        # First, scroll to top to make sure we see the beginning
        await self.page.evaluate("window.scrollTo(0, 0)")
        await asyncio.sleep(1)
        
        # Try to click "Show more" buttons ONLY within the main content area (not sidebar)
        for _ in range(3):  # Try 3 times
            clicked = await self.page.evaluate("""
                () => {
                    // Only look within the primary column (main content area)
                    const mainContent = document.querySelector('[data-testid="primaryColumn"]');
                    if (!mainContent) return 0;
                    
                    const elements = mainContent.querySelectorAll('span, div[role="button"]');
                    let clicked = 0;
                    for (const el of elements) {
                        const text = el.textContent?.trim().toLowerCase() || '';
                        // Only click exact matches for thread expansion
                        if (text === 'show more' || text === 'show this thread') {
                            // Make sure it's visible and not navigation
                            const rect = el.getBoundingClientRect();
                            if (rect.width > 0 && rect.height > 0) {
                                el.click();
                                clicked++;
                            }
                        }
                    }
                    return clicked;
                }
            """)
            if clicked > 0:
                await asyncio.sleep(2)  # Wait for content to load
            else:
                break

        for attempt in range(max_scroll_attempts):
            # Expand "Show more replies" buttons
            await self._expand_replies()
            # Expand truncated long tweets
            await self._expand_long_tweets()

            # Scroll down
            scroll_distance = random.randint(600, 1000)
            await self.page.evaluate("(dist) => window.scrollBy(0, dist)", scroll_distance)

            # Random delay
            await self._random_delay(1.2, 2.5)

            # Collect tweets
            new_tweets = await self._collect_tweets_from_page()

            changed = False
            for tweet in new_tweets:
                if tweet["tweet_id"] not in seen:
                    seen[tweet["tweet_id"]] = tweet
                    changed = True

            # Stop conditions - only when no new content
            if not changed:
                idle_scrolls += 1
                if idle_scrolls >= max_idle:
                    break
            else:
                idle_scrolls = 0

        # Return ALL tweets sorted by timestamp
        tweets = list(seen.values())
        tweets.sort(key=lambda t: t.get('timestamp') or '')
        return tweets

    async def _expand_replies(self):
        """Click 'Show more replies' buttons using JavaScript (more reliable)."""
        try:
            # Use JavaScript to click Show more within the main content area only
            clicked = await self.page.evaluate("""
                () => {
                    const mainContent = document.querySelector('[data-testid="primaryColumn"]');
                    if (!mainContent) return 0;
                    
                    const elements = mainContent.querySelectorAll('span, div[role="button"]');
                    let clicked = 0;
                    
                    for (const el of elements) {
                        const text = el.textContent?.trim().toLowerCase() || '';
                        if (text === 'show more' || text === 'show this thread' || 
                            text === 'view replies' || text.includes('more replies')) {
                            const rect = el.getBoundingClientRect();
                            if (rect.width > 0 && rect.height > 0) {
                                el.click();
                                clicked++;
                            }
                        }
                    }
                    return clicked;
                }
            """)
            
            if clicked > 0:
                await asyncio.sleep(1.5)

        except (TimeoutError, Exception) as e:
            logger.debug(f"Could not expand thread replies: {e}")


    async def _expand_long_tweets(self):
        """Click 'Show more' links inside individual tweets to expand truncated text."""
        try:
            articles = await self.page.query_selector_all('article[data-testid="tweet"]')

            for article in articles:
                try:
                    # Try X's specific data-testid first
                    show_more = await article.query_selector('[data-testid="tweet-text-show-more-link"]')

                    if not show_more:
                        # Fallback: look for role="link" elements near tweetText containing "show more"
                        candidates = await article.query_selector_all('[role="link"]')
                        for candidate in candidates:
                            try:
                                text = (await candidate.inner_text()).strip().lower()
                                if text == "show more":
                                    show_more = candidate
                                    break
                            except (TimeoutError, Exception):
                                continue

                    if show_more:
                        await show_more.scroll_into_view_if_needed(timeout=500)
                        await show_more.click(timeout=700)
                        await asyncio.sleep(random.uniform(0.3, 0.6))
                except (TimeoutError, Exception):
                    continue
        except (TimeoutError, Exception) as e:
            logger.debug(f"Could not expand long tweets: {e}")

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
                  else if (!authorName && text && !text.includes("\u00b7")) authorName = text;
                }
                if (!authorHandle && permalink) {
                  const handleMatch = permalink.match(/(?:x\\.com|twitter\\.com)\\/([^/]+)\\/status/);
                  if (handleMatch) authorHandle = "@" + handleMatch[1];
                }
                if (!authorHandle) {
                  const userLink = userSection?.querySelector('a[href^="/"]');
                  if (userLink) {
                    const href = userLink.getAttribute("href") || "";
                    const parts = href.split("/").filter(Boolean);
                    if (parts.length >= 1) authorHandle = "@" + parts[0];
                  }
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
        match = re.search(r'(?:x\.com|twitter\.com)/([^/]+)/status', url)
        if match:
            return f"@{match.group(1)}"
        return ""

    def filter_author_tweets_only(self, tweets: List[Dict], target_handle: str) -> List[Dict]:
        """
        Filter to target author's thread tweets.
        Tolerates single interspersed non-author tweets (quoted tweets, UI artifacts)
        but stops at 2+ consecutive non-author tweets (end of thread).
        """
        if not tweets or not target_handle:
            return tweets
        target = target_handle.lower().lstrip('@')
        sorted_tweets = sorted(tweets, key=lambda t: t.get('timestamp') or '')
        root_idx = -1
        for idx, t in enumerate(sorted_tweets):
            author = t.get('author_handle', '').lower().lstrip('@')
            if author == target:
                root_idx = idx
                break
        if root_idx == -1:
            return []
        result = []
        consecutive_non_author = 0
        for t in sorted_tweets[root_idx:]:
            author = t.get('author_handle', '').lower().lstrip('@')
            if author == target:
                result.append(t)
                consecutive_non_author = 0
            else:
                consecutive_non_author += 1
                if consecutive_non_author >= 2:
                    break
        return result

    async def _validate_page_loaded(self):
        """Check page loaded correctly (not rate-limited, not redirected to login)."""
        url = self.page.url.lower()
        if "login" in url or "signin" in url or "/flow/login" in url:
            raise SessionExpiredError("Redirected to login page - session expired.")
        title = await self.page.title()
        title_lower = (title or "").lower()
        if "rate limit" in title_lower or "rate_limit" in url:
            raise Exception("X rate limit detected. Wait before retrying.")
        has_content = await self.page.query_selector('[data-testid="primaryColumn"]')
        if not has_content:
            await asyncio.sleep(1)
            has_content = await self.page.query_selector('[data-testid="primaryColumn"]')
            if not has_content:
                logger.warning("Page loaded but primaryColumn not found - possible X error page")

    def _merge_video_streams(self, tweets: List[Dict]) -> List[Dict]:
        """Replace empty video src with captured stream URLs."""
        if not hasattr(self, 'video_streams') or not self.video_streams:
            return tweets
        for tweet in tweets:
            tweet_id = tweet.get("tweet_id", "")
            stream_url = self.video_streams.get(tweet_id)
            if not stream_url:
                continue
            for media_item in tweet.get("media", []):
                if media_item.get("type") == "video" and not media_item.get("src"):
                    media_item["src"] = stream_url
                    break
        return tweets

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
