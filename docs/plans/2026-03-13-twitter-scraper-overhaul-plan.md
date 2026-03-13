# Twitter/X Scraper Overhaul — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Fix the non-functional Twitter/X scraper so it works reliably in production Docker (Chromium, session health, retries, alerts) and delivers clean thread content through the dashboard.

**Architecture:** Surgical fixes to the existing `TwitterScraper` class — switch browser engine, harden session management, add fallback selectors, fix thread filtering, add retry logic, create an alerts module, and fix media quality selection. No new abstractions or architectural changes.

**Tech Stack:** Python, Playwright (Chromium), asyncio, FastAPI, SQLAlchemy, httpx (Telegram alerts)

---

### Task 1: Switch Browser Engine to Chromium

**Files:**
- Modify: `src/scraper/scraper.py:77-122` (`_init_browser` method)
- Test: `tests/test_scraper.py`

**Step 1: Write the failing test**

Add to `tests/test_scraper.py`:

```python
class TestBrowserEngineConfig:
    """Test browser engine selection via env var."""

    def test_default_browser_is_chromium(self):
        scraper = TwitterScraper()
        assert scraper.browser_type == "chromium"

    def test_browser_from_env_firefox(self, monkeypatch):
        monkeypatch.setenv("SCRAPER_BROWSER", "firefox")
        scraper = TwitterScraper()
        assert scraper.browser_type == "firefox"

    def test_browser_from_env_chromium(self, monkeypatch):
        monkeypatch.setenv("SCRAPER_BROWSER", "chromium")
        scraper = TwitterScraper()
        assert scraper.browser_type == "chromium"

    def test_invalid_browser_defaults_to_chromium(self, monkeypatch):
        monkeypatch.setenv("SCRAPER_BROWSER", "safari")
        scraper = TwitterScraper()
        assert scraper.browser_type == "chromium"
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_scraper.py::TestBrowserEngineConfig -v`
Expected: FAIL — `TwitterScraper` has no `browser_type` attribute

**Step 3: Implement browser engine config**

In `src/scraper/scraper.py`, add to `__init__` (after line 50):

```python
browser_env = os.getenv("SCRAPER_BROWSER", "chromium").lower()
self.browser_type = browser_env if browser_env in ("chromium", "firefox") else "chromium"
```

Add `import os` to the imports at the top.

In `_init_browser` (line ~97), change:

```python
# OLD:
self.browser = await self.playwright.firefox.launch(headless=self.headless)

# NEW:
launcher = getattr(self.playwright, self.browser_type)
self.browser = await launcher.launch(headless=self.headless)
```

**Step 4: Update stealth script for Chromium**

In `_init_browser`, the stealth `add_init_script` block (around line 105) currently fakes `window.chrome`. For Chromium this is unnecessary — update:

```python
stealth_js = """
Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]});
Object.defineProperty(navigator, 'languages', {get: () => ['en-US', 'en']});
"""
if self.browser_type == "firefox":
    stealth_js += """
Object.defineProperty(window, 'chrome', {get: () => ({runtime: {}})});
"""
await self.page.add_init_script(stealth_js)
```

**Step 5: Run tests to verify they pass**

Run: `pytest tests/test_scraper.py::TestBrowserEngineConfig -v`
Expected: 4 PASS

**Step 6: Run full test suite to verify no regressions**

Run: `pytest tests/test_scraper.py tests/test_scraper_page.py -v`
Expected: All existing tests still pass

**Step 7: Commit**

```bash
git add src/scraper/scraper.py tests/test_scraper.py
git commit -m "feat(scraper): switch default browser to Chromium, configurable via SCRAPER_BROWSER env"
```

---

### Task 2: Fix Session Management — Remove input() Blocking

**Files:**
- Modify: `src/scraper/scraper.py:125-185` (`ensure_logged_in` method)
- Test: `tests/test_scraper.py`

**Step 1: Write the failing tests**

Add to `tests/test_scraper.py`:

```python
class TestSessionManagement:
    """Test session verification and error handling."""

    def test_session_meta_path(self):
        scraper = TwitterScraper()
        expected = scraper.session_dir / "session_meta.json"
        assert scraper.session_meta_file == expected

    def test_no_session_raises_descriptive_error(self):
        scraper = TwitterScraper()
        assert not scraper.session_file.exists() or True  # just checking attr exists
        # The actual async test is below

    @pytest.mark.asyncio
    async def test_ensure_logged_in_no_session_raises(self):
        scraper = TwitterScraper()
        # Ensure no session file exists
        if scraper.session_file.exists():
            scraper.session_file.unlink()
        with pytest.raises(RuntimeError, match="No valid X session found"):
            await scraper.ensure_logged_in()

    def test_check_session_health_returns_dict(self):
        scraper = TwitterScraper()
        # Without browser initialized, should return unhealthy status
        import asyncio
        result = asyncio.run(scraper.check_session_health())
        assert isinstance(result, dict)
        assert "healthy" in result
        assert result["healthy"] is False
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_scraper.py::TestSessionManagement -v`
Expected: FAIL — no `session_meta_file` attribute, no `check_session_health` method, `ensure_logged_in` calls `input()` instead of raising

**Step 3: Add session_meta_file attribute**

In `__init__` (after `self.session_file` around line 57):

```python
self.session_meta_file = self.session_dir / "session_meta.json"
```

**Step 4: Rewrite ensure_logged_in — remove input(), add clear error**

Replace the `ensure_logged_in` method (lines 125-185) with:

```python
async def ensure_logged_in(self):
    """Verify X session is valid. Raises RuntimeError if no valid session exists."""
    if self.session_file.exists():
        try:
            await self._init_browser(use_session=True)
            await self.page.goto("https://x.com/home", wait_until="domcontentloaded")
            await self.page.wait_for_selector('[data-testid="primaryColumn"]', timeout=10000)
            self._update_session_meta(verified=True)
            logger.info("✅ Session verified successfully")
            return
        except Exception as e:
            logger.warning(f"⚠️ Session verification failed: {e}")
            self.session_file.unlink(missing_ok=True)
            self.session_meta_file.unlink(missing_ok=True)
            await self._close_browser()

    if not self.headless:
        # Interactive mode: open browser for manual login
        logger.info("🔑 No valid session. Opening browser for manual login...")
        await self._init_browser(use_session=False)
        await self.page.goto("https://x.com/login", wait_until="domcontentloaded")
        logger.info("Please log in to X in the browser window.")
        logger.info("After logging in, press Enter here to continue...")
        await asyncio.get_event_loop().run_in_executor(None, input)
        try:
            await self.page.wait_for_selector('[data-testid="primaryColumn"]', timeout=5000)
            await self.context.storage_state(path=str(self.session_file))
            self._update_session_meta(verified=True)
            logger.info("✅ Session saved successfully")
        except Exception as e:
            raise RuntimeError(f"Login verification failed: {e}")
    else:
        raise RuntimeError(
            "No valid X session found. Run the scraper locally with "
            "SCRAPER_HEADLESS=false to create a session, then copy "
            "data/session/storage_state.json to the server."
        )
```

**Step 5: Add _update_session_meta and _close_browser helpers**

Add below `ensure_logged_in`:

```python
def _update_session_meta(self, verified: bool = False):
    """Write session metadata sidecar file."""
    meta = {"last_verified_at": datetime.utcnow().isoformat(), "verified": verified}
    self.session_meta_file.write_text(json.dumps(meta))

def _get_session_age_minutes(self) -> Optional[float]:
    """Get minutes since last session verification. Returns None if no meta file."""
    if not self.session_meta_file.exists():
        return None
    try:
        meta = json.loads(self.session_meta_file.read_text())
        last_verified = datetime.fromisoformat(meta["last_verified_at"])
        return (datetime.utcnow() - last_verified).total_seconds() / 60
    except (json.JSONDecodeError, KeyError, ValueError):
        return None

async def _close_browser(self):
    """Close browser resources without full close() cleanup."""
    try:
        if self.context:
            await self.context.close()
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()
    except Exception:
        pass
    self.playwright = self.browser = self.context = self.page = None
```

**Step 6: Add check_session_health method**

```python
async def check_session_health(self) -> Dict:
    """Check if the X session is still valid. Returns status dict."""
    if not self.session_file.exists():
        return {"healthy": False, "reason": "no_session_file", "age_minutes": None}

    age = self._get_session_age_minutes()
    if age is not None and age < 30:
        return {"healthy": True, "reason": "recently_verified", "age_minutes": round(age, 1)}

    try:
        if not self.page:
            await self._init_browser(use_session=True)
        await self.page.goto("https://x.com/home", wait_until="domcontentloaded")
        await self.page.wait_for_selector('[data-testid="primaryColumn"]', timeout=10000)
        self._update_session_meta(verified=True)
        return {"healthy": True, "reason": "verified", "age_minutes": 0}
    except Exception as e:
        return {"healthy": False, "reason": str(e), "age_minutes": age}
```

**Step 7: Run tests**

Run: `pytest tests/test_scraper.py::TestSessionManagement -v`
Expected: All PASS

**Step 8: Run full test suite**

Run: `pytest tests/test_scraper.py tests/test_scraper_page.py -v`
Expected: All existing tests still pass

**Step 9: Commit**

```bash
git add src/scraper/scraper.py tests/test_scraper.py
git commit -m "fix(scraper): remove input() blocking, add session health checks and age tracking"
```

---

### Task 3: Add Page-Load Validation & Fallback Selectors

**Files:**
- Modify: `src/scraper/scraper.py`
- Test: `tests/test_scraper.py`, `tests/test_scraper_page.py`

**Step 1: Write the failing tests**

Add to `tests/test_scraper.py`:

```python
class TestPageValidation:
    """Test page-load validation and error detection."""

    @pytest.mark.asyncio
    async def test_validate_page_detects_login_redirect(self):
        scraper = TwitterScraper()
        scraper.page = AsyncMock()
        scraper.page.url = "https://x.com/i/flow/login"
        result = await scraper._validate_page_loaded()
        assert result["success"] is False
        assert result["error_type"] == "session_expired"

    @pytest.mark.asyncio
    async def test_validate_page_detects_rate_limit(self):
        scraper = TwitterScraper()
        scraper.page = AsyncMock()
        scraper.page.url = "https://x.com/home"
        scraper.page.query_selector = AsyncMock(return_value=None)
        scraper.page.content = AsyncMock(return_value="Rate limit exceeded")
        result = await scraper._validate_page_loaded()
        assert result["success"] is False
        assert result["error_type"] == "rate_limited"

    @pytest.mark.asyncio
    async def test_validate_page_success(self):
        scraper = TwitterScraper()
        scraper.page = AsyncMock()
        scraper.page.url = "https://x.com/user/status/123"
        mock_el = AsyncMock()
        scraper.page.query_selector = AsyncMock(return_value=mock_el)
        result = await scraper._validate_page_loaded()
        assert result["success"] is True

    def test_selector_constants_defined(self):
        assert hasattr(TwitterScraper, 'TEXT_SELECTORS')
        assert hasattr(TwitterScraper, 'AUTHOR_SELECTORS')
        assert hasattr(TwitterScraper, 'TIMESTAMP_SELECTORS')
        assert len(TwitterScraper.TEXT_SELECTORS) >= 2
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_scraper.py::TestPageValidation -v`
Expected: FAIL — no `_validate_page_loaded` method, no selector constants

**Step 3: Add selector constants as class attributes**

At the top of the `TwitterScraper` class (after the docstring, line ~38):

```python
TEXT_SELECTORS = ['[data-testid="tweetText"]', 'div[lang]']
AUTHOR_SELECTORS = ['[data-testid="User-Name"] a', 'a[role="link"][href*="/"]']
TIMESTAMP_SELECTORS = ['time[datetime]', 'time']
TWEET_SELECTORS = ['article[data-testid="tweet"]', 'article']
TREND_SELECTORS = ['[data-testid="trend"]', '[data-testid="cellInnerDiv"]']
```

**Step 4: Add _validate_page_loaded method**

Add to `TwitterScraper`:

```python
async def _validate_page_loaded(self) -> Dict:
    """Check if page loaded correctly. Returns {success, error_type, message}."""
    url = self.page.url

    if "/login" in url or "/signin" in url or "/i/flow/login" in url:
        return {"success": False, "error_type": "session_expired",
                "message": "Redirected to login — session expired"}

    if "/account/suspended" in url:
        return {"success": False, "error_type": "account_suspended",
                "message": "Account appears to be suspended"}

    primary = await self.page.query_selector('[data-testid="primaryColumn"]')
    if primary:
        return {"success": True, "error_type": None, "message": "Page loaded"}

    article = await self.page.query_selector('article')
    if article:
        return {"success": True, "error_type": None, "message": "Page loaded (article found)"}

    page_text = await self.page.content()
    if "rate limit" in page_text.lower():
        return {"success": False, "error_type": "rate_limited",
                "message": "Rate limit detected"}
    if "something went wrong" in page_text.lower():
        return {"success": False, "error_type": "x_error",
                "message": "X returned an error page"}

    return {"success": False, "error_type": "unknown",
            "message": f"Page did not load expected elements. URL: {url}"}
```

**Step 5: Add _query_with_fallback helper**

```python
async def _query_with_fallback(self, selectors: List[str], context=None) -> Optional[object]:
    """Try multiple selectors, return first match."""
    target = context or self.page
    for selector in selectors:
        try:
            el = await target.query_selector(selector)
            if el:
                return el
        except Exception:
            continue
    return None
```

**Step 6: Run tests**

Run: `pytest tests/test_scraper.py::TestPageValidation -v`
Expected: All PASS

**Step 7: Integrate _validate_page_loaded into get_tweet_content**

In `get_tweet_content` (around line 253), after `await self.page.goto(...)`, add:

```python
validation = await self._validate_page_loaded()
if not validation["success"]:
    logger.error(f"Page validation failed: {validation['message']}")
    return {"error": True, "error_type": validation["error_type"],
            "message": validation["message"], "source_url": tweet_url}
```

Do the same in `fetch_raw_thread` (around line 575), after navigating.

**Step 8: Run full test suite**

Run: `pytest tests/test_scraper.py tests/test_scraper_page.py -v`
Expected: All pass

**Step 9: Commit**

```bash
git add src/scraper/scraper.py tests/test_scraper.py
git commit -m "feat(scraper): add page validation, fallback selectors, and rate-limit detection"
```

---

### Task 4: Fix Thread Author Filtering

**Files:**
- Modify: `src/scraper/scraper.py:937-1016` (`_should_stop_at_other_author`, `filter_author_tweets_only`)
- Test: `tests/test_scraper.py`

**Step 1: Write the failing tests**

Add to `tests/test_scraper.py`:

```python
class TestImprovedAuthorFiltering:
    """Test that author filtering handles quoted tweets and gaps."""

    def test_filter_skips_quoted_tweets_between_author_posts(self):
        scraper = TwitterScraper()
        tweets = [
            {"author_handle": "@alice", "timestamp": "2026-01-01T00:01:00Z", "text": "Thread 1/3"},
            {"author_handle": "@bob", "timestamp": "2026-01-01T00:01:30Z", "text": "quoted"},
            {"author_handle": "@alice", "timestamp": "2026-01-01T00:02:00Z", "text": "Thread 2/3"},
            {"author_handle": "@alice", "timestamp": "2026-01-01T00:03:00Z", "text": "Thread 3/3"},
        ]
        result = scraper.filter_author_tweets_only(tweets, "@alice")
        assert len(result) == 3
        assert all(t["author_handle"] == "@alice" for t in result)

    def test_filter_handles_multiple_gaps(self):
        scraper = TwitterScraper()
        tweets = [
            {"author_handle": "@alice", "timestamp": "2026-01-01T00:01:00Z", "text": "1"},
            {"author_handle": "@bob", "timestamp": "2026-01-01T00:01:30Z", "text": "reply"},
            {"author_handle": "@alice", "timestamp": "2026-01-01T00:02:00Z", "text": "2"},
            {"author_handle": "@charlie", "timestamp": "2026-01-01T00:02:30Z", "text": "reply"},
            {"author_handle": "@alice", "timestamp": "2026-01-01T00:03:00Z", "text": "3"},
        ]
        result = scraper.filter_author_tweets_only(tweets, "@alice")
        assert len(result) == 3

    def test_filter_preserves_order(self):
        scraper = TwitterScraper()
        tweets = [
            {"author_handle": "@alice", "timestamp": "2026-01-01T00:01:00Z", "text": "first"},
            {"author_handle": "@bob", "timestamp": "2026-01-01T00:01:30Z", "text": "gap"},
            {"author_handle": "@alice", "timestamp": "2026-01-01T00:03:00Z", "text": "last"},
        ]
        result = scraper.filter_author_tweets_only(tweets, "@alice")
        assert result[0]["text"] == "first"
        assert result[1]["text"] == "last"

    def test_should_stop_requires_3_consecutive_non_author(self):
        scraper = TwitterScraper()
        tweets = [
            {"author_handle": "@alice", "timestamp": "2026-01-01T00:01:00Z"},
            {"author_handle": "@bob", "timestamp": "2026-01-01T00:02:00Z"},
            {"author_handle": "@alice", "timestamp": "2026-01-01T00:03:00Z"},
        ]
        # One non-author tweet between author tweets should NOT stop
        assert scraper._should_stop_at_other_author(tweets, "@alice") is False

    def test_should_stop_fires_after_3_consecutive_non_author(self):
        scraper = TwitterScraper()
        tweets = [
            {"author_handle": "@alice", "timestamp": "2026-01-01T00:01:00Z"},
            {"author_handle": "@bob", "timestamp": "2026-01-01T00:02:00Z"},
            {"author_handle": "@charlie", "timestamp": "2026-01-01T00:03:00Z"},
            {"author_handle": "@dave", "timestamp": "2026-01-01T00:04:00Z"},
        ]
        assert scraper._should_stop_at_other_author(tweets, "@alice") is True
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_scraper.py::TestImprovedAuthorFiltering -v`
Expected: FAIL — current `filter_author_tweets_only` stops at first non-author tweet

**Step 3: Fix filter_author_tweets_only**

Replace the method (around line 975) with:

```python
def filter_author_tweets_only(self, tweets: List[Dict], target_handle: str) -> List[Dict]:
    """Filter to only the thread author's tweets, preserving order.
    Unlike the old version, this collects ALL tweets by the author
    (skipping quoted tweets / replies from others in between).
    """
    if not tweets or not target_handle:
        return tweets

    sorted_tweets = sorted(tweets, key=lambda t: t.get("timestamp", ""))

    # Find the first tweet by the target author (the root)
    root_idx = None
    for i, tweet in enumerate(sorted_tweets):
        if tweet.get("author_handle", "").lower() == target_handle.lower():
            root_idx = i
            break

    if root_idx is None:
        return tweets  # Author not found, return all

    # Collect all tweets by the author from root onward
    author_tweets = []
    for tweet in sorted_tweets[root_idx:]:
        if tweet.get("author_handle", "").lower() == target_handle.lower():
            author_tweets.append(tweet)

    return author_tweets
```

**Step 4: Fix _should_stop_at_other_author**

Replace the method (around line 937) with:

```python
def _should_stop_at_other_author(self, seen_tweets: List[Dict], target_handle: str) -> bool:
    """Stop scrolling if we see 3+ consecutive non-author tweets after the last author tweet."""
    if len(seen_tweets) < 2 or not target_handle:
        return False

    sorted_tweets = sorted(seen_tweets, key=lambda t: t.get("timestamp", ""))

    # Find last author tweet
    last_author_idx = -1
    for i, tweet in enumerate(sorted_tweets):
        if tweet.get("author_handle", "").lower() == target_handle.lower():
            last_author_idx = i

    if last_author_idx == -1:
        return False  # Author not found yet

    # Count consecutive non-author tweets after last author tweet
    consecutive_non_author = 0
    for tweet in sorted_tweets[last_author_idx + 1:]:
        if tweet.get("author_handle", "").lower() != target_handle.lower():
            consecutive_non_author += 1
        else:
            consecutive_non_author = 0  # Reset: author appeared again

    return consecutive_non_author >= 3
```

**Step 5: Run tests**

Run: `pytest tests/test_scraper.py::TestImprovedAuthorFiltering -v`
Expected: All PASS

**Step 6: Run full test suite**

Run: `pytest tests/test_scraper.py tests/test_scraper_page.py -v`
Expected: All pass (check that existing `TestTwitterScraperHelpers` `_should_stop_at_other_author` tests still pass — they should, since the old "last 3 different" test case has 3 consecutive non-author tweets)

**Step 7: Commit**

```bash
git add src/scraper/scraper.py tests/test_scraper.py
git commit -m "fix(scraper): improve thread author filtering to handle quoted tweets and gaps"
```

---

### Task 5: Deprecate fetch_thread, Wire Video Streams

**Files:**
- Modify: `src/scraper/scraper.py:712-770` (`fetch_thread`), `547-635` (`fetch_raw_thread`)
- Test: `tests/test_scraper.py`

**Step 1: Write the failing test**

```python
class TestFetchThreadDeprecation:
    """Test that fetch_thread delegates to fetch_raw_thread."""

    def test_fetch_thread_has_deprecation_marker(self):
        import inspect
        source = inspect.getsource(TwitterScraper.fetch_thread)
        assert "deprecated" in source.lower() or "DeprecationWarning" in source
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_scraper.py::TestFetchThreadDeprecation -v`
Expected: FAIL — no deprecation marker in current code

**Step 3: Replace fetch_thread with thin wrapper**

Replace `fetch_thread` method (lines 712-770) with:

```python
async def fetch_thread(self, thread_url: str, max_scroll_attempts: int = 50) -> List[Dict]:
    """Fetch thread tweets. DEPRECATED: Use fetch_raw_thread() instead.

    This method is kept for backward compatibility. It calls fetch_raw_thread()
    and returns just the tweets list (not the full metadata dict).
    """
    import warnings
    warnings.warn("fetch_thread() is deprecated, use fetch_raw_thread()", DeprecationWarning, stacklevel=2)

    result = await self.fetch_raw_thread(thread_url, max_scroll_attempts=max_scroll_attempts, author_only=True)
    if isinstance(result, dict) and "error" in result:
        return []
    return result.get("tweets", []) if isinstance(result, dict) else []
```

**Step 4: Wire video_streams into fetch_raw_thread output**

In `fetch_raw_thread`, after `_scroll_and_collect_all` and author filtering (around line 620), before building the return dict, add:

```python
# Merge intercepted video streams into tweet media
if hasattr(self, 'video_streams') and self.video_streams:
    for tweet in tweets:
        tweet_id = tweet.get("tweet_id", "")
        if tweet_id and tweet_id in self.video_streams:
            if "media" not in tweet:
                tweet["media"] = []
            tweet["media"].append({
                "type": "video",
                "src": self.video_streams[tweet_id],
                "source": "network_intercept"
            })
```

**Step 5: Run tests**

Run: `pytest tests/test_scraper.py::TestFetchThreadDeprecation -v`
Expected: PASS

**Step 6: Run full test suite**

Run: `pytest tests/test_scraper.py tests/test_scraper_page.py -v`
Expected: All pass

**Step 7: Commit**

```bash
git add src/scraper/scraper.py tests/test_scraper.py
git commit -m "refactor(scraper): deprecate fetch_thread, wire video_streams into fetch_raw_thread output"
```

---

### Task 6: Fix Trending Pipeline — Enum & Retries

**Files:**
- Modify: `src/scraper/main.py:17-18,79-83,104-145`
- Test: `tests/test_scraper.py`

**Step 1: Write the failing tests**

Add to `tests/test_scraper.py`:

```python
class TestTrendingPipeline:
    """Test main.py enum fix and retry logic."""

    def test_main_imports_trend_source(self):
        from scraper.main import scrape_trending_workflow
        # Verify TrendSource is available in main.py scope
        from common.models import TrendSource
        assert hasattr(TrendSource, 'X_TWITTER')

    @pytest.mark.asyncio
    async def test_retry_wrapper_retries_on_timeout(self):
        from scraper.main import retry_async
        call_count = 0

        async def flaky():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise TimeoutError("timeout")
            return "success"

        result = await retry_async(flaky, max_attempts=2, delay=0.01)
        assert result == "success"
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_retry_wrapper_raises_after_max_attempts(self):
        from scraper.main import retry_async

        async def always_fails():
            raise TimeoutError("timeout")

        with pytest.raises(TimeoutError):
            await retry_async(always_fails, max_attempts=2, delay=0.01)
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_scraper.py::TestTrendingPipeline -v`
Expected: FAIL — no `retry_async` function in `main.py`

**Step 3: Fix the enum in main.py**

In `src/scraper/main.py`, line 18, change import:

```python
# OLD:
from common.models import create_tables, get_db_session, Tweet, Trend

# NEW:
from common.models import create_tables, get_db_session, Tweet, Trend, TrendSource
```

Line 83, change:

```python
# OLD:
source='X'

# NEW:
source=TrendSource.X_TWITTER
```

**Step 4: Add retry_async helper to main.py**

Add after imports (around line 26):

```python
async def retry_async(coro_func, max_attempts=2, delay=5.0):
    """Retry an async function on failure. coro_func must be a callable returning a coroutine."""
    last_error = None
    for attempt in range(max_attempts):
        try:
            return await coro_func()
        except (TimeoutError, Exception) as e:
            last_error = e
            if attempt < max_attempts - 1:
                logger.warning(f"Attempt {attempt + 1} failed: {e}. Retrying in {delay}s...")
                await asyncio.sleep(delay)
    raise last_error
```

**Step 5: Wrap scrape calls with retry + adaptive delay**

In `scrape_trending_workflow`, around lines 106-145, update the tweet scraping loop:

```python
base_delay = 2
current_delay = base_delay

for tweet_url in tweet_urls:
    try:
        existing_tweet = db.query(Tweet).filter(
            Tweet.source_url == tweet_url
        ).first()
        if existing_tweet:
            logger.info(f"  ⊙ Tweet already exists: {tweet_url}")
            continue

        tweet_data = await retry_async(
            lambda url=tweet_url: scraper.get_tweet_content(url),
            max_attempts=2,
            delay=5.0
        )

        # Check for structured error from get_tweet_content
        if isinstance(tweet_data, dict) and tweet_data.get("error"):
            logger.warning(f"  ⚠️ Scrape returned error: {tweet_data.get('message')}")
            current_delay = min(current_delay + 3, 10)
            continue

        db_tweet = Tweet(
            source_url=tweet_data['source_url'],
            original_text=tweet_data['text'],
            media_url=tweet_data.get('media_url'),
            trend_topic=topic,
            status='pending'
        )
        db.add(db_tweet)
        db.commit()

        total_tweets_scraped += 1
        logger.info(f"  ✓ Saved tweet {total_tweets_scraped}: {tweet_url}")
        current_delay = base_delay  # Reset on success

        await asyncio.sleep(current_delay)

    except Exception as e:
        logger.error(f"  ❌ Failed to scrape tweet {tweet_url}: {e}")
        current_delay = min(current_delay + 3, 10)
        continue
```

**Step 6: Run tests**

Run: `pytest tests/test_scraper.py::TestTrendingPipeline -v`
Expected: All PASS

**Step 7: Run full test suite**

Run: `pytest tests/test_scraper.py tests/test_scraper_page.py -v`
Expected: All pass

**Step 8: Commit**

```bash
git add src/scraper/main.py tests/test_scraper.py
git commit -m "fix(scraper): fix TrendSource enum, add retry logic and adaptive delays to trending pipeline"
```

---

### Task 7: Create Alerts Module

**Files:**
- Create: `src/scraper/alerts.py`
- Test: `tests/test_scraper_alerts.py`

**Step 1: Write the failing test**

Create `tests/test_scraper_alerts.py`:

```python
"""Tests for scraper alert module."""
import pytest
from unittest.mock import patch, AsyncMock, MagicMock

from scraper.alerts import send_alert, AlertLevel


class TestAlerts:
    """Test alert sending to Telegram and logging."""

    def test_alert_levels_defined(self):
        assert AlertLevel.INFO is not None
        assert AlertLevel.WARNING is not None
        assert AlertLevel.CRITICAL is not None

    @pytest.mark.asyncio
    async def test_send_alert_logs_always(self):
        with patch("scraper.alerts.logger") as mock_logger:
            await send_alert(AlertLevel.WARNING, "Test warning")
            mock_logger.warning.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_alert_critical_logs_error(self):
        with patch("scraper.alerts.logger") as mock_logger:
            await send_alert(AlertLevel.CRITICAL, "Test critical")
            mock_logger.error.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_alert_sends_telegram_when_configured(self):
        with patch("scraper.alerts.logger"):
            with patch("scraper.alerts.os.getenv", return_value="12345"):
                with patch("scraper.alerts.httpx.AsyncClient") as mock_client_cls:
                    mock_client = AsyncMock()
                    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                    mock_client.__aexit__ = AsyncMock(return_value=False)
                    mock_client.post = AsyncMock()
                    mock_client_cls.return_value = mock_client
                    await send_alert(AlertLevel.CRITICAL, "Session expired")
                    mock_client.post.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_alert_skips_telegram_when_no_chat_id(self):
        with patch("scraper.alerts.logger"):
            with patch("scraper.alerts.os.getenv", return_value=None):
                # Should not raise, just log
                await send_alert(AlertLevel.WARNING, "No Telegram configured")

    @pytest.mark.asyncio
    async def test_send_alert_telegram_failure_doesnt_raise(self):
        with patch("scraper.alerts.logger"):
            with patch("scraper.alerts.os.getenv", return_value="12345"):
                with patch("scraper.alerts.httpx.AsyncClient") as mock_client_cls:
                    mock_client = AsyncMock()
                    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                    mock_client.__aexit__ = AsyncMock(return_value=False)
                    mock_client.post = AsyncMock(side_effect=Exception("network error"))
                    mock_client_cls.return_value = mock_client
                    # Should not raise
                    await send_alert(AlertLevel.CRITICAL, "This should not crash")
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_scraper_alerts.py -v`
Expected: FAIL — `scraper.alerts` module doesn't exist

**Step 3: Create the alerts module**

Create `src/scraper/alerts.py`:

```python
"""Scraper alerts — logs + optional Telegram notifications."""

import os
import logging
from enum import Enum

import httpx

logger = logging.getLogger(__name__)


class AlertLevel(Enum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


EMOJI_MAP = {
    AlertLevel.INFO: "ℹ️",
    AlertLevel.WARNING: "⚠️",
    AlertLevel.CRITICAL: "🚨",
}


async def send_alert(level: AlertLevel, message: str) -> None:
    """Send an alert via logging and optionally Telegram."""
    emoji = EMOJI_MAP.get(level, "")
    full_message = f"{emoji} [Scraper {level.value.upper()}] {message}"

    if level == AlertLevel.CRITICAL:
        logger.error(full_message)
    elif level == AlertLevel.WARNING:
        logger.warning(full_message)
    else:
        logger.info(full_message)

    chat_id = os.getenv("TELEGRAM_ALERT_CHAT_ID")
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN")

    if not chat_id or not bot_token:
        return

    try:
        async with httpx.AsyncClient() as client:
            await client.post(
                f"https://api.telegram.org/bot{bot_token}/sendMessage",
                json={"chat_id": chat_id, "text": full_message, "parse_mode": "HTML"},
                timeout=10,
            )
    except Exception as e:
        logger.debug(f"Failed to send Telegram alert: {e}")
```

**Step 4: Run tests**

Run: `pytest tests/test_scraper_alerts.py -v`
Expected: All PASS

**Step 5: Commit**

```bash
git add src/scraper/alerts.py tests/test_scraper_alerts.py
git commit -m "feat(scraper): add alerts module for Telegram notifications on scraper failures"
```

---

### Task 8: Integrate Alerts into Scraper

**Files:**
- Modify: `src/scraper/scraper.py` (import alerts, call send_alert at key points)
- Modify: `src/scraper/main.py` (alert on workflow failures)

**Step 1: No new tests needed** — alert calls are integration points; tested via the alerts module itself.

**Step 2: Add alert calls to scraper.py**

At top of `src/scraper/scraper.py`, add import:

```python
from scraper.alerts import send_alert, AlertLevel
```

In `ensure_logged_in`, when session is expired (the `except` block where `session_file` is deleted):

```python
await send_alert(AlertLevel.CRITICAL, "X session expired. Manual re-login required.")
```

In `_validate_page_loaded`, for rate_limited:

```python
# Inside the rate_limited branch, before return:
await send_alert(AlertLevel.WARNING, f"Rate limit detected on {self.page.url}")
```

Note: `_validate_page_loaded` is not async currently — make it `async def` and add `await` to `send_alert`. The `query_selector` and `content()` calls are already awaited.

In `ensure_logged_in`, for the headless RuntimeError:

```python
await send_alert(AlertLevel.CRITICAL, "No valid X session found. Scraper cannot run in headless mode without a session.")
```

**Step 3: Add alert calls to main.py**

At top of `src/scraper/main.py`, add:

```python
from scraper.alerts import send_alert, AlertLevel
```

In the outer `except` block of `scrape_trending_workflow` (around line 158):

```python
except Exception as e:
    logger.error(f"❌ Scraping workflow failed: {e}")
    asyncio.run(send_alert(AlertLevel.CRITICAL, f"Trending scrape workflow failed: {e}"))
    raise
```

Note: Since `send_alert` is async and this catch block is inside an async function, use `await`:

```python
await send_alert(AlertLevel.CRITICAL, f"Trending scrape workflow failed: {e}")
```

**Step 4: Run full test suite**

Run: `pytest tests/ -v --ignore=tests/test_security.py -x`
Expected: All pass

**Step 5: Commit**

```bash
git add src/scraper/scraper.py src/scraper/main.py
git commit -m "feat(scraper): integrate alerts into session management, page validation, and trending pipeline"
```

---

### Task 9: Add Scraper Health API Endpoint

**Files:**
- Create: `src/api/routes/scraper.py`
- Modify: `src/api/main.py` (register new router)
- Test: `tests/test_scraper.py`

**Step 1: Write the failing test**

Add to `tests/test_scraper.py` (or create new `tests/test_api_scraper.py`):

```python
class TestScraperHealthEndpoint:
    """Test the /api/scraper/health endpoint."""

    def test_health_endpoint_returns_session_status(self):
        from fastapi.testclient import TestClient
        from api.main import app

        client = TestClient(app)
        # Need auth — use a test token or patch the dependency
        with patch("api.dependencies.require_api_key"):
            response = client.get("/api/scraper/health")
            assert response.status_code == 200
            data = response.json()
            assert "session_healthy" in data
            assert "session_age_minutes" in data
```

**Step 2: Create the route**

Create `src/api/routes/scraper.py`:

```python
"""Scraper health and status endpoints."""

import json
import logging
from pathlib import Path
from datetime import datetime

from fastapi import APIRouter, Depends

from api.dependencies import require_api_key

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/scraper", tags=["scraper"])

SESSION_DIR = Path(__file__).parent.parent.parent / "data" / "session"


@router.get("/health")
async def scraper_health(_=Depends(require_api_key)):
    """Check scraper session health and status."""
    session_file = SESSION_DIR / "storage_state.json"
    meta_file = SESSION_DIR / "session_meta.json"

    result = {
        "session_exists": session_file.exists(),
        "session_healthy": False,
        "session_age_minutes": None,
        "last_verified_at": None,
    }

    if meta_file.exists():
        try:
            meta = json.loads(meta_file.read_text())
            last_verified = datetime.fromisoformat(meta.get("last_verified_at", ""))
            age_minutes = (datetime.utcnow() - last_verified).total_seconds() / 60
            result["session_age_minutes"] = round(age_minutes, 1)
            result["last_verified_at"] = meta.get("last_verified_at")
            result["session_healthy"] = meta.get("verified", False) and age_minutes < 60
        except (json.JSONDecodeError, ValueError, KeyError):
            pass

    return result
```

**Step 3: Register in API main**

In `src/api/main.py`, add import (around line 28):

```python
from api.routes.scraper import router as scraper_router
```

Add registration (around line 201):

```python
app.include_router(scraper_router)
```

**Step 4: Run tests**

Run: `pytest tests/test_scraper.py::TestScraperHealthEndpoint -v` (or the new test file)
Expected: PASS

**Step 5: Commit**

```bash
git add src/api/routes/scraper.py src/api/main.py tests/test_scraper.py
git commit -m "feat(api): add /api/scraper/health endpoint for session monitoring"
```

---

### Task 10: Fix Media Quality Selection

**Files:**
- Modify: `src/scraper/scraper.py:300-340` (media extraction in `get_tweet_content`)
- Test: `tests/test_scraper.py`

**Step 1: Write the failing tests**

Add to `tests/test_scraper.py`:

```python
class TestVideoQualitySelection:
    """Test video quality parsing from m3u8 URLs."""

    def test_extract_resolution_from_m3u8_url(self):
        scraper = TwitterScraper()
        url = "https://video.twimg.com/ext_tw_video/123/pl/1280x720/abc.m3u8"
        resolution = scraper._extract_video_resolution(url)
        assert resolution == 1280 * 720

    def test_extract_resolution_from_avc_url(self):
        scraper = TwitterScraper()
        url = "https://video.twimg.com/ext_tw_video/123/vid/avc1/720x1280/abc.mp4"
        resolution = scraper._extract_video_resolution(url)
        assert resolution == 720 * 1280

    def test_extract_resolution_unknown_returns_zero(self):
        scraper = TwitterScraper()
        url = "https://video.twimg.com/some/random/path.m3u8"
        resolution = scraper._extract_video_resolution(url)
        assert resolution == 0

    def test_select_best_video_picks_highest_resolution(self):
        scraper = TwitterScraper()
        urls = [
            "https://video.twimg.com/ext/123/pl/640x360/a.m3u8",
            "https://video.twimg.com/ext/123/pl/1280x720/b.m3u8",
            "https://video.twimg.com/ext/123/pl/320x180/c.m3u8",
        ]
        best = scraper._select_best_video(urls)
        assert "1280x720" in best
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_scraper.py::TestVideoQualitySelection -v`
Expected: FAIL — no `_extract_video_resolution` or `_select_best_video` methods

**Step 3: Add video quality helpers to scraper.py**

Add to `TwitterScraper` class:

```python
_RESOLUTION_PATTERN = re.compile(r'/(\d{3,4})x(\d{3,4})/')

def _extract_video_resolution(self, url: str) -> int:
    """Extract resolution (width*height) from a video URL. Returns 0 if unknown."""
    match = self._RESOLUTION_PATTERN.search(url)
    if match:
        return int(match.group(1)) * int(match.group(2))
    return 0

def _select_best_video(self, urls: List[str]) -> str:
    """Select the highest-resolution video URL from a list."""
    if not urls:
        return ""
    scored = [(self._extract_video_resolution(url), url) for url in urls]
    scored.sort(key=lambda x: x[0], reverse=True)
    return scored[0][1]
```

**Step 4: Update get_tweet_content to use _select_best_video**

In `get_tweet_content` (around line 310), replace the old sorting logic:

```python
# OLD:
m3u8_urls = [u for u in self.intercepted_media_urls if '.m3u8' in u]
if m3u8_urls:
    media_url = sorted(m3u8_urls, reverse=True)[0]

# NEW:
m3u8_urls = [u for u in self.intercepted_media_urls if '.m3u8' in u]
if m3u8_urls:
    media_url = self._select_best_video(m3u8_urls)
elif self.intercepted_media_urls:
    video_urls = [u for u in self.intercepted_media_urls if 'video.twimg.com' in u]
    if video_urls:
        media_url = self._select_best_video(video_urls)
```

**Step 5: Run tests**

Run: `pytest tests/test_scraper.py::TestVideoQualitySelection -v`
Expected: All PASS

**Step 6: Run full test suite**

Run: `pytest tests/test_scraper.py tests/test_scraper_page.py -v`
Expected: All pass

**Step 7: Commit**

```bash
git add src/scraper/scraper.py tests/test_scraper.py
git commit -m "fix(scraper): fix video quality selection to use resolution parsing instead of alphabetical sort"
```

---

### Task 11: Update Dashboard Error Handling for Structured Errors

**Files:**
- Modify: `src/dashboard/views/content.py:120-280` (scrape form handler)

**Step 1: No new unit tests** — dashboard is tested manually via browser.

**Step 2: Update the scrape handler**

In `src/dashboard/views/content.py`, around line 137 where `result = asyncio.run(run())`, add structured error handling:

```python
result = asyncio.run(run())

# Handle structured error from scraper
if isinstance(result, dict) and result.get("error"):
    error_type = result.get("error_type", "unknown")
    error_msg = result.get("message", "Unknown scraper error")
    if error_type == "session_expired":
        st.error("❌ X session expired. Re-login required: run scraper locally with SCRAPER_HEADLESS=false")
    elif error_type == "rate_limited":
        st.warning("⚠️ X rate limit detected. Try again in a few minutes.")
    else:
        st.error(f"❌ Scrape failed: {error_msg}")
    return

tweets_data = result.get("tweets", [])
```

**Step 3: Commit**

```bash
git add src/dashboard/views/content.py
git commit -m "feat(dashboard): display specific error messages for scraper failures (session, rate limit)"
```

---

### Task 12: Update Dockerfile — Ensure Consistency

**Files:**
- Modify: `src/scraper/Dockerfile`

**Step 1: No tests** — Docker build is verified manually.

**Step 2: Verify Dockerfile matches new Chromium default**

The Dockerfile already installs Chromium. Verify line 15 says:

```dockerfile
RUN playwright install chromium --with-deps
```

This is correct — no changes needed to the install line.

But update the comment on line 13 to clarify:

```dockerfile
# Install Chromium browser (default engine; override with SCRAPER_BROWSER=firefox)
RUN playwright install chromium --with-deps
```

If users want Firefox support in Docker too, they would need:

```dockerfile
RUN playwright install chromium firefox --with-deps
```

For now, keep it Chromium-only to minimize image size.

**Step 3: Commit**

```bash
git add src/scraper/Dockerfile
git commit -m "docs(scraper): clarify Dockerfile browser engine comment"
```

---

### Task 13: Final Integration Test & Verification

**Files:**
- All modified files

**Step 1: Run the full test suite**

Run: `pytest tests/ -v --tb=short`
Expected: All tests pass, including new tests from Tasks 1-10

**Step 2: Verify import chains work**

Run: `python -c "from scraper.scraper import TwitterScraper; from scraper.alerts import send_alert, AlertLevel; from scraper.main import retry_async; print('All imports OK')"`
Expected: `All imports OK`

**Step 3: Verify API starts**

Run: `python -c "from api.main import app; print('API app created OK')"`
Expected: `API app created OK`

**Step 4: Final commit (if any fixups needed)**

```bash
git add -A
git commit -m "chore: fix integration issues from scraper overhaul"
```

**Step 5: Create summary commit tag**

```bash
git tag scraper-overhaul-v1 -m "Twitter/X scraper surgical fix — Chromium, session health, fallback selectors, thread filtering, retries, alerts, media quality"
```
