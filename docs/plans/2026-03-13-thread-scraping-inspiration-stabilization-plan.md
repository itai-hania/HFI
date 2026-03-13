# Thread Scraping & Inspiration Stabilization — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Fix the broken thread scraping and inspiration features so they work reliably on the production Azure VM.

**Architecture:** Fix the scraper foundation (URL handling, session management, DOM selectors, browser engine), then fix the API layer (timeouts, error handling, session checks), then fix the frontend (error states, provenance, session indicators). TDD throughout.

**Tech Stack:** Python (Playwright, FastAPI, SQLAlchemy), TypeScript (Next.js, React Query), pytest

**Total Tasks:** 19 (original 15 + 4 merged from scraper hardening plan)

---

### Task 1: Create `SessionExpiredError` exception class

**Files:**
- Create: `src/scraper/errors.py`
- Test: `tests/test_scraper_errors.py`

**Step 1: Write the test**

```python
# tests/test_scraper_errors.py
"""Tests for scraper error classes."""

from scraper.errors import SessionExpiredError


class TestSessionExpiredError:
    def test_is_exception(self):
        err = SessionExpiredError("Session expired")
        assert isinstance(err, Exception)
        assert str(err) == "Session expired"

    def test_default_message(self):
        err = SessionExpiredError()
        assert "session" in str(err).lower()

    def test_has_action_hint(self):
        err = SessionExpiredError("gone")
        assert err.action == "refresh_session"
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_scraper_errors.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'scraper.errors'`

**Step 3: Write the implementation**

```python
# src/scraper/errors.py
"""Scraper-specific error classes."""


class SessionExpiredError(Exception):
    """Raised when the X browser session is expired or missing."""

    action = "refresh_session"

    def __init__(self, message: str = "X session expired or missing. Please refresh the session file."):
        super().__init__(message)
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_scraper_errors.py -v`
Expected: PASS (3 tests)

**Step 5: Commit**

```bash
git add src/scraper/errors.py tests/test_scraper_errors.py
git commit -m "feat(scraper): add SessionExpiredError exception class"
```

---

### Task 2: Fix `_extract_handle_from_url` to support `twitter.com`

**Files:**
- Modify: `src/scraper/scraper.py:928-935`
- Test: `tests/test_scraper.py` (add new test cases)

**Step 1: Write the failing tests**

Add to `tests/test_scraper.py` (find the existing test class or create new one):

```python
# Add these test cases to tests/test_scraper.py
import pytest
from unittest.mock import patch
from scraper.scraper import TwitterScraper


class TestExtractHandleFromUrl:
    @pytest.fixture(autouse=True)
    def scraper(self):
        with patch("scraper.scraper.UserAgent") as mock_ua:
            mock_ua.return_value.random = "Mozilla/5.0"
            self.scraper = TwitterScraper(headless=True)

    @pytest.mark.parametrize("url,expected", [
        ("https://x.com/elonmusk/status/123456", "@elonmusk"),
        ("https://twitter.com/elonmusk/status/123456", "@elonmusk"),
        ("https://www.twitter.com/user/status/999", "@user"),
        ("https://mobile.twitter.com/user/status/999", "@user"),
        ("https://mobile.x.com/user/status/999", "@user"),
        ("https://www.x.com/user/status/999", "@user"),
        ("https://x.com/user/status/999/photo/1", "@user"),
        ("https://example.com/status/123", ""),
        ("https://x.com/user/likes", ""),
        ("not a url", ""),
    ])
    def test_extract_handle(self, url, expected):
        assert self.scraper._extract_handle_from_url(url) == expected
```

**Step 2: Run test to verify the `twitter.com` cases fail**

Run: `pytest tests/test_scraper.py::TestExtractHandleFromUrl -v`
Expected: FAIL on `twitter.com`, `www.twitter.com`, `mobile.twitter.com` cases

**Step 3: Fix the implementation**

In `src/scraper/scraper.py`, change `_extract_handle_from_url` (line ~930):

Old:
```python
match = re.search(r'x\.com/([^/]+)/status', url)
```

New:
```python
match = re.search(r'(?:x\.com|twitter\.com)/([^/]+)/status', url)
```

**Step 4: Run test to verify all pass**

Run: `pytest tests/test_scraper.py::TestExtractHandleFromUrl -v`
Expected: PASS (all 10 cases)

**Step 5: Commit**

```bash
git add src/scraper/scraper.py tests/test_scraper.py
git commit -m "fix(scraper): support twitter.com URLs in handle extraction"
```

---

### Task 3: Add robust author handle fallback in `_collect_tweets_from_page` JS

**Files:**
- Modify: `src/scraper/scraper.py:878-926` (the JS in `_collect_tweets_from_page`)

**Step 1: Write the failing test**

Add to `tests/test_scraper.py`:

```python
class TestCollectTweetsHandleFallback:
    """Ensure _collect_tweets_from_page JS extracts handle from permalink when span fails."""

    @pytest.fixture(autouse=True)
    def scraper(self):
        with patch("scraper.scraper.UserAgent") as mock_ua:
            mock_ua.return_value.random = "Mozilla/5.0"
            self.scraper = TwitterScraper(headless=True)

    def test_handle_extracted_from_permalink_fallback(self):
        """When author_handle is empty, it should fall back to extracting from permalink URL."""
        tweets = [
            {"tweet_id": "1", "author_handle": "", "permalink": "https://x.com/testuser/status/1", "text": "hi", "timestamp": "2026-01-01T00:00:00Z", "media": []},
        ]
        result = self.scraper.filter_author_tweets_only(tweets, "@testuser")
        # With empty handle and no fallback, filter returns [] - this tests the downstream effect
        # After fix, the JS will fill handle from permalink, so filter should work
        # For now we test filter_author_tweets_only directly with empty handle
        assert result == []  # This proves the problem: empty handle = lost tweets
```

**Step 2: Run test to verify it shows the problem**

Run: `pytest tests/test_scraper.py::TestCollectTweetsHandleFallback -v`
Expected: PASS (confirms the bug — empty handle means all tweets filtered out)

**Step 3: Fix the JS in `_collect_tweets_from_page`**

In `src/scraper/scraper.py`, modify the JS inside `_collect_tweets_from_page` (line ~888-904). Replace the author handle extraction block:

Old JS (inside the `articles.map` callback):
```javascript
const userSection = article.querySelector('div[data-testid="User-Name"]');
let authorHandle = "";
let authorName = "";
for (const span of userSection?.querySelectorAll("span") || []) {
  const text = span.textContent?.trim() || "";
  if (text.startsWith("@")) authorHandle = text;
  else if (!authorName) authorName = text;
}
```

New JS:
```javascript
const userSection = article.querySelector('div[data-testid="User-Name"]');
let authorHandle = "";
let authorName = "";
for (const span of userSection?.querySelectorAll("span") || []) {
  const text = span.textContent?.trim() || "";
  if (text.startsWith("@")) authorHandle = text;
  else if (!authorName && text && !text.includes("·")) authorName = text;
}
if (!authorHandle && permalink) {
  const handleMatch = permalink.match(/(?:x\.com|twitter\.com)\/([^/]+)\/status/);
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
```

**Step 4: Run full scraper test suite to verify no regressions**

Run: `pytest tests/test_scraper.py -v`
Expected: PASS (all existing + new tests)

**Step 5: Commit**

```bash
git add src/scraper/scraper.py
git commit -m "fix(scraper): add fallback chain for author handle extraction in JS"
```

---

### Task 4: Fix `ensure_logged_in` to raise `SessionExpiredError` instead of blocking

**Files:**
- Modify: `src/scraper/scraper.py:125-185`
- Test: `tests/test_scraper.py` (add new tests)

**Step 1: Write the failing test**

```python
class TestEnsureLoggedInSessionExpiry:
    @pytest.fixture(autouse=True)
    def scraper(self):
        with patch("scraper.scraper.UserAgent") as mock_ua:
            mock_ua.return_value.random = "Mozilla/5.0"
            self.scraper = TwitterScraper(headless=True)

    def test_raises_session_expired_when_no_session_file(self):
        """When session file doesn't exist and headless=True, raise SessionExpiredError."""
        from scraper.errors import SessionExpiredError

        self.scraper.session_file = Path("/nonexistent/storage_state.json")

        with pytest.raises(SessionExpiredError, match="session"):
            asyncio.run(self.scraper.ensure_logged_in())

    def test_raises_session_expired_when_session_invalid(self):
        """When session file exists but is invalid, raise SessionExpiredError."""
        import tempfile
        from scraper.errors import SessionExpiredError

        with tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode="w") as f:
            f.write("{}")
            self.scraper.session_file = Path(f.name)

        # Mock _init_browser to avoid launching real browser
        self.scraper._init_browser = AsyncMock()
        mock_page = AsyncMock()
        mock_page.goto = AsyncMock(side_effect=Exception("Navigation failed"))
        self.scraper.page = mock_page
        self.scraper.close = AsyncMock()

        with pytest.raises(SessionExpiredError):
            asyncio.run(self.scraper.ensure_logged_in())

        Path(f.name).unlink()
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_scraper.py::TestEnsureLoggedInSessionExpiry -v`
Expected: FAIL — currently `ensure_logged_in` calls `input()` instead of raising

**Step 3: Fix `ensure_logged_in`**

In `src/scraper/scraper.py`, add import at top:
```python
from scraper.errors import SessionExpiredError
```

Replace the manual login branch in `ensure_logged_in` (lines ~163-185):

Old:
```python
        logger.info("⚠️  No valid session found. Starting manual login process...")
        logger.info("📝 Please log in manually in the browser window that will open...")
        original_headless = self.headless
        self.headless = False
        await self._init_browser(use_session=False)
        await self.page.goto('https://x.com/login', timeout=30000)
        # ...
        input("Press ENTER after you've logged in successfully: ")
        # ...
```

New:
```python
        if self.headless:
            raise SessionExpiredError(
                "X session expired or missing. Run 'python tools/refresh_session.py' "
                "locally, then copy data/session/storage_state.json to the server."
            )

        logger.info("⚠️  No valid session found. Starting manual login process...")
        logger.info("📝 Please log in manually in the browser window that will open...")
        original_headless = self.headless
        self.headless = False
        await self._init_browser(use_session=False)
        await self.page.goto('https://x.com/login', timeout=30000)
        # ... keep existing input() path for non-headless only ...
        input("Press ENTER after you've logged in successfully: ")
        # ... rest unchanged ...
```

Also wrap the session-validation navigation in a timeout (line ~131-139):

```python
            try:
                await self.page.goto('https://x.com/home', timeout=15000)
                await self.page.wait_for_selector('[data-testid="primaryColumn"]', timeout=10000)
```

And in the `except` block after session validation fails, add the `SessionExpiredError` raise instead of falling through:

```python
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
```

**Step 4: Run tests**

Run: `pytest tests/test_scraper.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/scraper/scraper.py
git commit -m "fix(scraper): raise SessionExpiredError instead of blocking on input()"
```

---

### Task 5: Add session health check to API

**Files:**
- Modify: `src/api/main.py:215-235` (add scraper-session endpoint near existing health check)
- Test: `tests/test_api_endpoints.py` (add new tests)

**Step 1: Write the failing test**

```python
# Add to tests/test_api_endpoints.py or create tests/test_session_health.py

from unittest.mock import patch
from pathlib import Path
import time


class TestScraperSessionHealth:
    def test_session_missing(self, client):
        """GET /health/scraper-session returns 'missing' when no session file."""
        with patch("api.main.Path") as mock_path:
            mock_path.return_value.exists.return_value = False
            response = client.get("/health/scraper-session")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "missing"
        assert data["file_exists"] is False

    def test_session_valid(self, client, tmp_path):
        """GET /health/scraper-session returns 'valid' for fresh session file."""
        session_file = tmp_path / "storage_state.json"
        session_file.write_text('{"cookies": []}')
        with patch("api.main._get_session_path", return_value=session_file):
            response = client.get("/health/scraper-session")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "valid"
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_session_health.py -v` (or wherever placed)
Expected: FAIL — endpoint doesn't exist

**Step 3: Implement the endpoint**

In `src/api/main.py`, add after the existing `/health` endpoint:

```python
def _get_session_path() -> Path:
    return Path(__file__).parent.parent / "data" / "session" / "storage_state.json"


@app.get("/health/scraper-session")
def scraper_session_health():
    """Check X scraper session file status without launching a browser."""
    session_path = _get_session_path()

    if not session_path.exists():
        return {
            "status": "missing",
            "file_exists": False,
            "age_hours": None,
            "message": "No session file found. Run tools/refresh_session.py locally.",
        }

    import os
    mtime = os.path.getmtime(session_path)
    age_hours = round((time.time() - mtime) / 3600, 1)

    if age_hours > 168:  # 7 days
        status = "expired"
        message = "Session is over 7 days old and likely expired."
    elif age_hours > 120:  # 5 days
        status = "warning"
        message = "Session is over 5 days old and may expire soon."
    else:
        status = "valid"
        message = "Session file looks fresh."

    return {
        "status": status,
        "file_exists": True,
        "age_hours": age_hours,
        "message": message,
    }
```

Add `import time` and `from pathlib import Path` to the imports in `main.py` if not already present.

**Step 4: Run tests**

Run: `pytest tests/test_session_health.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/api/main.py tests/test_session_health.py
git commit -m "feat(api): add /health/scraper-session endpoint"
```

---

### Task 6: Add timeout and session check to inspiration `search_posts`

**Files:**
- Modify: `src/api/routes/inspiration.py:113-211`
- Test: `tests/test_api_inspiration.py` (add new test cases)

**Step 1: Write the failing tests**

```python
# Add to existing tests/test_api_inspiration.py or wherever inspiration API tests live

class TestInspirationSessionAndTimeout:
    def test_search_returns_503_when_session_expired(self, client, auth_headers):
        """POST /api/inspiration/search returns 503 when session is expired."""
        # First add the account so it exists
        client.post("/api/inspiration/accounts",
                     json={"username": "testuser"}, headers=auth_headers)

        with patch("api.routes.inspiration.get_scraper") as mock_get:
            from scraper.errors import SessionExpiredError
            scraper = AsyncMock()
            scraper.search_by_user_engagement = AsyncMock(side_effect=SessionExpiredError())
            scraper.close = AsyncMock()
            mock_get.return_value = scraper

            response = client.post("/api/inspiration/search",
                json={"username": "testuser", "min_likes": 100, "keyword": "", "limit": 10},
                headers=auth_headers)

        assert response.status_code == 503
        assert "session" in response.json()["detail"].lower()

    def test_search_returns_504_on_timeout(self, client, auth_headers):
        """POST /api/inspiration/search returns 504 on timeout."""
        client.post("/api/inspiration/accounts",
                     json={"username": "testuser2"}, headers=auth_headers)

        with patch("api.routes.inspiration.get_scraper") as mock_get:
            scraper = AsyncMock()
            scraper.search_by_user_engagement = AsyncMock(side_effect=asyncio.TimeoutError())
            scraper.close = AsyncMock()
            mock_get.return_value = scraper

            response = client.post("/api/inspiration/search",
                json={"username": "testuser2", "min_likes": 100, "keyword": "", "limit": 10},
                headers=auth_headers)

        assert response.status_code == 504
        assert "timeout" in response.json()["detail"].lower()
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/test_api_inspiration.py::TestInspirationSessionAndTimeout -v`
Expected: FAIL — currently returns 500 on SessionExpiredError, no timeout wrapper

**Step 3: Fix `search_posts` in `src/api/routes/inspiration.py`**

Add imports at top:
```python
import asyncio
from scraper.errors import SessionExpiredError
```

Replace the scraper call block (lines 145-156):

Old:
```python
    scraper = get_scraper()
    try:
        posts = await scraper.search_by_user_engagement(
            username=payload.username,
            min_faves=payload.min_likes,
            keyword=payload.keyword,
            limit=payload.limit,
            since=payload.since,
            until=payload.until,
        )
    finally:
        await scraper.close()
```

New:
```python
    scraper = get_scraper()
    try:
        posts = await asyncio.wait_for(
            scraper.search_by_user_engagement(
                username=payload.username,
                min_faves=payload.min_likes,
                keyword=payload.keyword,
                limit=payload.limit,
                since=payload.since,
                until=payload.until,
            ),
            timeout=90,
        )
    except SessionExpiredError as exc:
        raise HTTPException(
            status_code=503,
            detail=str(exc),
        ) from exc
    except asyncio.TimeoutError:
        raise HTTPException(
            status_code=504,
            detail="X search timed out. The session may be expired or X may be slow.",
        )
    finally:
        await scraper.close()
```

Also remove the auto-create account behavior (lines 121-125):

Old:
```python
    if not account:
        account = InspirationAccount(username=payload.username, display_name=payload.username)
        db.add(account)
        db.commit()
        db.refresh(account)
```

New:
```python
    if not account:
        raise HTTPException(status_code=404, detail=f"Account @{payload.username} not tracked. Add it first.")
```

**Step 4: Run tests**

Run: `pytest tests/test_api_inspiration.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/api/routes/inspiration.py tests/test_api_inspiration.py
git commit -m "fix(inspiration): add timeout, session check, remove auto-create accounts"
```

---

### Task 7: Add timeout and session check to source resolver

**Files:**
- Modify: `src/common/source_resolver.py:106-135`
- Modify: `src/api/routes/generation.py:65-73`
- Test: `tests/test_source_resolver.py` (add/update tests)

**Step 1: Write the failing tests**

```python
# Add to tests/test_source_resolver.py or create it

import asyncio
import pytest
from unittest.mock import AsyncMock, patch

from common.source_resolver import resolve_source_input, SourceResolverError


class TestSourceResolverSessionHandling:
    def test_x_url_raises_on_session_expired(self):
        from scraper.errors import SessionExpiredError

        mock_scraper = AsyncMock()
        mock_scraper.ensure_logged_in = AsyncMock(side_effect=SessionExpiredError("expired"))
        mock_scraper.close = AsyncMock()

        with pytest.raises(SourceResolverError, match="session"):
            asyncio.run(resolve_source_input(
                url="https://x.com/user/status/123",
                scraper_factory=lambda: mock_scraper,
            ))

    def test_x_url_raises_on_timeout(self):
        mock_scraper = AsyncMock()
        mock_scraper.ensure_logged_in = AsyncMock()
        mock_scraper.get_tweet_content = AsyncMock(side_effect=asyncio.TimeoutError())
        mock_scraper.close = AsyncMock()

        with pytest.raises(SourceResolverError, match="timed out"):
            asyncio.run(resolve_source_input(
                url="https://x.com/user/status/123",
                scraper_factory=lambda: mock_scraper,
            ))
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/test_source_resolver.py::TestSourceResolverSessionHandling -v`
Expected: FAIL — no timeout wrapper, SessionExpiredError not caught

**Step 3: Fix `_resolve_x_url` in `src/common/source_resolver.py`**

Add imports:
```python
import asyncio
```

Wrap the scraper call in timeout and catch `SessionExpiredError`:

```python
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
        tweet_data = await asyncio.wait_for(scraper.get_tweet_content(url), timeout=60)
    except SessionExpiredError as exc:
        raise SourceResolverError(str(exc)) from exc
    except asyncio.TimeoutError:
        raise SourceResolverError("X scraping timed out. The session may be expired.")
    finally:
        await scraper.close()

    text = _collapse_whitespace((tweet_data or {}).get("text", ""))
    if not text:
        raise SourceResolverError("Invalid X/Twitter URL")

    title = _build_preview(text, max_chars=120)
    return SourceResolution(
        source_type="x_url",
        original_text=text,
        title=title,
        canonical_url=url,
        source_domain=_source_domain(url),
        preview_text=_build_preview(text),
    )
```

Also update `src/api/routes/generation.py` `resolve_source` to surface 503/504:

```python
@router.post("/source/resolve", response_model=SourceResolveResponse)
async def resolve_source(request: SourceResolveRequest):
    """Resolve text or URL source into canonical generation input."""
    try:
        resolved = await resolve_source_input(text=request.text, url=request.url)
    except SourceResolverError as exc:
        msg = str(exc).lower()
        if "session" in msg:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        if "timed out" in msg:
            raise HTTPException(status_code=504, detail=str(exc)) from exc
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return SourceResolveResponse(**resolved.to_dict())
```

Apply the same pattern to the `/translate` endpoint.

**Step 4: Run tests**

Run: `pytest tests/test_source_resolver.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/common/source_resolver.py src/api/routes/generation.py tests/test_source_resolver.py
git commit -m "fix(resolver): add timeout and session error handling for X URL resolution"
```

---

### Task 8: Fix thread-aware source resolution (full thread, not just first tweet)

**Files:**
- Modify: `src/common/source_resolver.py:106-135` (`_resolve_x_url`)
- Test: `tests/test_source_resolver.py` (add thread test)

**Step 1: Write the failing test**

```python
class TestSourceResolverThreadDetection:
    def test_x_thread_url_returns_consolidated_text(self):
        """When resolving an X status URL that is a thread, return all tweets consolidated."""
        thread_data = {
            "author_handle": "@user",
            "author_name": "User",
            "tweet_count": 3,
            "tweets": [
                {"text": "First tweet in thread", "timestamp": "2026-01-01T00:00:00Z"},
                {"text": "Second tweet continues", "timestamp": "2026-01-01T00:01:00Z"},
                {"text": "Third tweet wraps up", "timestamp": "2026-01-01T00:02:00Z"},
            ],
        }

        mock_scraper = AsyncMock()
        mock_scraper.ensure_logged_in = AsyncMock()
        mock_scraper.fetch_raw_thread = AsyncMock(return_value=thread_data)
        mock_scraper.close = AsyncMock()

        result = asyncio.run(resolve_source_input(
            url="https://x.com/user/status/123",
            scraper_factory=lambda: mock_scraper,
        ))

        assert "First tweet" in result.original_text
        assert "Second tweet" in result.original_text
        assert "Third tweet" in result.original_text
        assert result.source_type == "x_url"
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_source_resolver.py::TestSourceResolverThreadDetection -v`
Expected: FAIL — currently calls `get_tweet_content` (single tweet only)

**Step 3: Modify `_resolve_x_url` to use `fetch_raw_thread`**

Replace `get_tweet_content` with `fetch_raw_thread` in `_resolve_x_url`:

```python
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

    # Consolidate thread tweets into one text block
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
```

**Step 4: Run tests**

Run: `pytest tests/test_source_resolver.py -v`
Expected: PASS (both thread test and existing tests)

**Step 5: Commit**

```bash
git add src/common/source_resolver.py tests/test_source_resolver.py
git commit -m "feat(resolver): use fetch_raw_thread for full thread extraction from X URLs"
```

---

### Task 9: Fix PostCard to pass `post_url` to Create page

**Files:**
- Modify: `frontend/src/components/inspiration/PostCard.tsx:41`
- Modify: `frontend/src/app/(app)/create/page.tsx:296,106-110`

**Step 1: Update PostCard to include URL**

In `frontend/src/components/inspiration/PostCard.tsx`, line 41:

Old:
```tsx
router.push(`/create?source=inspiration&text=${encodeURIComponent(post.content || "")}`)
```

New:
```tsx
router.push(
  `/create?text=${encodeURIComponent(post.content || "")}${
    post.post_url ? `&url=${encodeURIComponent(post.post_url)}` : ""
  }`
)
```

**Step 2: Update Create page to read `url` param and use it as source**

In `frontend/src/app/(app)/create/page.tsx`, line 296:

Old:
```tsx
const initialSource = params.get("text") || "";
```

New:
```tsx
const urlParam = params.get("url") || "";
const textParam = params.get("text") || "";
const initialSource = urlParam || textParam;
```

This way, when a URL is provided, it becomes the source text (which `looksLikeUrl` will detect on line 97 and resolve as a URL). When only text is provided, it works as before.

**Step 3: Verify manually (no automated test for frontend TSX)**

The logic is straightforward: `PostCard` now includes `post_url` as a `url` query param, and `CreatePage` prefers `url` over `text` for the source input.

**Step 4: Commit**

```bash
git add frontend/src/components/inspiration/PostCard.tsx frontend/src/app/\(app\)/create/page.tsx
git commit -m "fix(frontend): pass post_url from inspiration PostCard to Create page"
```

---

### Task 10: Add error states to Inspiration page

**Files:**
- Modify: `frontend/src/app/(app)/inspiration/page.tsx:77-101,173-178`
- Modify: `frontend/src/hooks/useInspiration.ts` (if needed for error type)

**Step 1: Update the `handleSearch` error handling**

In `frontend/src/app/(app)/inspiration/page.tsx`, replace the catch block (line 99-101):

Old:
```tsx
    } catch {
      toast.error("Search failed");
    }
```

New:
```tsx
    } catch (error: unknown) {
      const err = error as { response?: { status?: number; data?: { detail?: string } } };
      const status = err?.response?.status;
      const detail = err?.response?.data?.detail;

      if (status === 503) {
        toast.error(detail || "X session expired. Refresh the session file on the server.");
      } else if (status === 504) {
        toast.error(detail || "Search timed out. Try again later.");
      } else if (status === 404) {
        toast.error(detail || "Account not tracked. Add it first using the + Add button above.");
      } else {
        toast.error(detail || "Search failed. Check server logs.");
      }
    }
```

**Step 2: Improve the empty state (lines 175-178)**

Old:
```tsx
      ) : posts.length === 0 ? (
        <div className="rounded-2xl border border-[var(--border)] bg-[var(--card)]/60 px-4 py-5 text-sm text-[var(--muted)]">
          No posts yet. Run a search.
        </div>
```

New:
```tsx
      ) : posts.length === 0 && searchMutation.isSuccess ? (
        <div className="rounded-2xl border border-[var(--border)] bg-[var(--card)]/60 px-4 py-5 text-sm text-[var(--muted)]">
          No posts found matching your criteria. Try lowering the minimum likes or broadening the date range.
        </div>
      ) : posts.length === 0 ? (
        <div className="rounded-2xl border border-[var(--border)] bg-[var(--card)]/60 px-4 py-5 text-sm text-[var(--muted)]">
          Search for high-engagement posts from tracked accounts.
        </div>
```

**Step 3: Commit**

```bash
git add frontend/src/app/\(app\)/inspiration/page.tsx
git commit -m "fix(frontend): add specific error messages for inspiration search failures"
```

---

### Task 11: Add `SessionStatus` component to frontend

**Files:**
- Create: `frontend/src/components/SessionStatus.tsx`
- Create: `frontend/src/hooks/useSessionStatus.ts`
- Modify: `frontend/src/app/(app)/inspiration/page.tsx` (add component)

**Step 1: Create the hook**

```typescript
// frontend/src/hooks/useSessionStatus.ts
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";

interface SessionHealth {
  status: "valid" | "warning" | "expired" | "missing";
  file_exists: boolean;
  age_hours: number | null;
  message: string;
}

export function useSessionStatus() {
  return useQuery<SessionHealth>({
    queryKey: ["scraper-session-health"],
    queryFn: async () => {
      const res = await api.get("/health/scraper-session");
      return res.data;
    },
    staleTime: 60_000,    // Re-check every minute
    refetchInterval: 60_000,
  });
}
```

**Step 2: Create the component**

```tsx
// frontend/src/components/SessionStatus.tsx
"use client";

import { useSessionStatus } from "@/hooks/useSessionStatus";

export function SessionStatus() {
  const { data, isLoading } = useSessionStatus();

  if (isLoading || !data) return null;

  if (data.status === "valid") return null;

  const colors = {
    warning: "border-yellow-500/30 bg-yellow-500/10 text-yellow-200",
    expired: "border-red-500/30 bg-red-500/10 text-red-200",
    missing: "border-red-500/30 bg-red-500/10 text-red-200",
  };

  const color = colors[data.status] || colors.missing;

  return (
    <div className={`rounded-xl border px-4 py-3 text-sm ${color}`}>
      <strong>X Session:</strong> {data.message}
    </div>
  );
}
```

**Step 3: Add to inspiration page**

In `frontend/src/app/(app)/inspiration/page.tsx`, add import and render:

```tsx
import { SessionStatus } from "@/components/SessionStatus";
```

Place it right after the header `</header>` tag:

```tsx
      <SessionStatus />
```

**Step 4: Commit**

```bash
git add frontend/src/components/SessionStatus.tsx frontend/src/hooks/useSessionStatus.ts frontend/src/app/\(app\)/inspiration/page.tsx
git commit -m "feat(frontend): add SessionStatus indicator to inspiration page"
```

---

### Task 12: Create `tools/refresh_session.py`

**Files:**
- Create: `tools/refresh_session.py`

**Step 1: Write the script**

```python
#!/usr/bin/env python3
"""Refresh X session cookie by opening a browser for manual login.

Run this script locally (NOT on the server), log in to X manually,
then copy the session file to the server.
"""

import asyncio
import sys
from pathlib import Path

# Allow running from project root
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


async def main():
    from scraper.scraper import TwitterScraper

    session_dir = Path(__file__).parent.parent / "data" / "session"
    session_dir.mkdir(parents=True, exist_ok=True)
    session_file = session_dir / "storage_state.json"

    print("=" * 60)
    print("  HFI — X Session Refresh Tool")
    print("=" * 60)
    print()
    print("This will open a browser window.")
    print("Log in to X (twitter.com) manually.")
    print()

    scraper = TwitterScraper(headless=False)
    try:
        await scraper._init_browser(use_session=False)
        await scraper.page.goto("https://x.com/login", timeout=30000)

        print("Waiting for you to log in...")
        print()
        input("Press ENTER after you've logged in successfully: ")

        try:
            await scraper.page.wait_for_selector('[data-testid="primaryColumn"]', timeout=10000)
        except Exception:
            print("Could not verify login. Saving session anyway...")

        await scraper.context.storage_state(path=str(session_file))
        print()
        print(f"Session saved to: {session_file}")
        print()
        print("To deploy to your server, run:")
        print(f"  scp {session_file} <user>@<server>:~/HFI/data/session/storage_state.json")
        print()
    finally:
        await scraper.close()


if __name__ == "__main__":
    asyncio.run(main())
```

**Step 2: Test it runs without error (syntax check)**

Run: `python -c "import ast; ast.parse(open('tools/refresh_session.py').read()); print('OK')"`
Expected: `OK`

**Step 3: Commit**

```bash
git add tools/refresh_session.py
git commit -m "feat(tools): add refresh_session.py for local X session management"
```

---

### Task 13: Fix video media capture in scraper

**Files:**
- Modify: `src/scraper/scraper.py` (`fetch_raw_thread` method — merge `video_streams` into tweets)

**Step 1: Write the test**

```python
class TestVideoStreamMerge:
    @pytest.fixture(autouse=True)
    def scraper(self):
        with patch("scraper.scraper.UserAgent") as mock_ua:
            mock_ua.return_value.random = "Mozilla/5.0"
            self.scraper = TwitterScraper(headless=True)

    def test_video_streams_merged_into_tweets(self):
        """Video URLs captured by response listener should be merged into tweet media."""
        tweets = [
            {
                "tweet_id": "123",
                "text": "Check this video",
                "media": [{"type": "video", "src": "", "alt": ""}],
                "permalink": "https://x.com/user/status/123",
                "timestamp": "2026-01-01T00:00:00Z",
                "author_handle": "@user",
            }
        ]
        self.scraper.video_streams = {
            "123": "https://video.twimg.com/ext_tw_video/123/pu/vid/1280x720/abc.mp4"
        }

        merged = self.scraper._merge_video_streams(tweets)
        video_media = [m for m in merged[0]["media"] if m["type"] == "video"]
        assert video_media[0]["src"] == "https://video.twimg.com/ext_tw_video/123/pu/vid/1280x720/abc.mp4"
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_scraper.py::TestVideoStreamMerge -v`
Expected: FAIL — `_merge_video_streams` doesn't exist yet

**Step 3: Add `_merge_video_streams` method and call it in `fetch_raw_thread`**

Add to `src/scraper/scraper.py`:

```python
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
```

In `fetch_raw_thread`, call it before returning (after `filter_author_tweets_only`):

```python
tweets_to_return = self._merge_video_streams(tweets_to_return)
```

**Step 4: Run tests**

Run: `pytest tests/test_scraper.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/scraper/scraper.py tests/test_scraper.py
git commit -m "fix(scraper): merge captured video stream URLs into tweet media data"
```

---

### Task 14: Run full test suite and fix regressions

**Files:**
- Potentially any files modified in Tasks 1-13

**Step 1: Run the full test suite**

Run: `pytest tests/ -v --tb=short`
Expected: All 468+ tests pass (existing + new)

**Step 2: Fix any regressions**

If any existing tests break due to:
- Changed `_resolve_x_url` signature (now uses `fetch_raw_thread` instead of `get_tweet_content`) — update mocks in existing tests
- Changed `search_posts` error behavior (now raises 404 instead of auto-creating accounts) — update existing tests
- Any import changes — fix as needed

**Step 3: Run full suite again to confirm**

Run: `pytest tests/ -v --tb=short`
Expected: ALL PASS

**Step 4: Commit any regression fixes**

```bash
git add -u
git commit -m "fix: resolve test regressions from thread/inspiration stabilization"
```

---

### Task 15: Final integration verification

**Step 1: Verify Docker build**

Run: `docker-compose build --no-cache api frontend`
Expected: Build succeeds

**Step 2: Verify the new health endpoint responds**

Run: `docker-compose up -d api && sleep 5 && curl -s http://localhost:8000/health/scraper-session | python -m json.tool`
Expected: `{"status": "missing", "file_exists": false, ...}`

**Step 3: Commit any final adjustments**

```bash
git add -u
git commit -m "chore: final integration verification for thread/inspiration stabilization"
```

---

---

### Task 16: Switch from Firefox to Chromium (env-configurable)

**Files:**
- Modify: `src/scraper/scraper.py:40-70` (constructor), `src/scraper/scraper.py:77-123` (`_init_browser`)
- Test: `tests/test_scraper.py` (add browser selection test)

**Step 1: Write the failing test**

```python
class TestBrowserSelection:
    def test_default_browser_is_chromium(self):
        with patch("scraper.scraper.UserAgent") as mock_ua:
            mock_ua.return_value.random = "Mozilla/5.0"
            scraper = TwitterScraper(headless=True)
        assert scraper.browser_type == "chromium"

    def test_browser_type_from_env(self):
        with patch("scraper.scraper.UserAgent") as mock_ua, \
             patch.dict("os.environ", {"SCRAPER_BROWSER": "firefox"}):
            mock_ua.return_value.random = "Mozilla/5.0"
            scraper = TwitterScraper(headless=True)
        assert scraper.browser_type == "firefox"

    def test_invalid_browser_falls_back_to_chromium(self):
        with patch("scraper.scraper.UserAgent") as mock_ua, \
             patch.dict("os.environ", {"SCRAPER_BROWSER": "safari"}):
            mock_ua.return_value.random = "Mozilla/5.0"
            scraper = TwitterScraper(headless=True)
        assert scraper.browser_type == "chromium"
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_scraper.py::TestBrowserSelection -v`
Expected: FAIL — `scraper.browser_type` doesn't exist

**Step 3: Implement**

In `src/scraper/scraper.py` `__init__` (line ~48), add:

```python
import os
# ...
_VALID_BROWSERS = {"chromium", "firefox", "webkit"}

class TwitterScraper:
    def __init__(self, headless: bool = True, max_interactions: int = 50):
        # ... existing code ...
        self.browser_type = os.environ.get("SCRAPER_BROWSER", "chromium").lower()
        if self.browser_type not in _VALID_BROWSERS:
            self.browser_type = "chromium"
```

In `_init_browser` (line ~82), replace:

```python
self.browser = await self.playwright.firefox.launch(headless=self.headless)
```

With:

```python
launcher = getattr(self.playwright, self.browser_type)
self.browser = await launcher.launch(headless=self.headless)
```

Update the stealth script in `_init_browser` to only set `window.chrome` for chromium:

```python
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
```

**Step 4: Run tests**

Run: `pytest tests/test_scraper.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/scraper/scraper.py tests/test_scraper.py
git commit -m "feat(scraper): switch default browser to Chromium, env-configurable"
```

---

### Task 17: Add rate-limit detection and page-load validation

**Files:**
- Modify: `src/scraper/scraper.py` (add `_validate_page_loaded` method, call it after navigation)
- Test: `tests/test_scraper.py`

**Step 1: Write the failing test**

```python
class TestPageValidation:
    @pytest.fixture(autouse=True)
    def scraper(self):
        with patch("scraper.scraper.UserAgent") as mock_ua:
            mock_ua.return_value.random = "Mozilla/5.0"
            self.scraper = TwitterScraper(headless=True)

    def test_detect_rate_limit_page(self):
        """Should raise when X shows rate limit / error page."""
        mock_page = AsyncMock()
        mock_page.url = "https://x.com/search"
        mock_page.title = AsyncMock(return_value="Rate limit exceeded")
        mock_page.query_selector = AsyncMock(return_value=None)
        self.scraper.page = mock_page

        with pytest.raises(Exception, match="rate.limit"):
            asyncio.run(self.scraper._validate_page_loaded())

    def test_detect_login_redirect(self):
        """Should raise SessionExpiredError when redirected to login."""
        from scraper.errors import SessionExpiredError

        mock_page = AsyncMock()
        mock_page.url = "https://x.com/i/flow/login"
        self.scraper.page = mock_page

        with pytest.raises(SessionExpiredError):
            asyncio.run(self.scraper._validate_page_loaded())

    def test_valid_page_passes(self):
        """Should not raise on normal X page."""
        mock_page = AsyncMock()
        mock_page.url = "https://x.com/user/status/123"
        mock_page.title = AsyncMock(return_value="User on X")
        mock_page.query_selector = AsyncMock(return_value=True)  # primaryColumn exists
        self.scraper.page = mock_page

        # Should not raise
        asyncio.run(self.scraper._validate_page_loaded())
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_scraper.py::TestPageValidation -v`
Expected: FAIL — `_validate_page_loaded` doesn't exist

**Step 3: Implement `_validate_page_loaded`**

Add to `src/scraper/scraper.py`:

```python
async def _validate_page_loaded(self):
    """Check if the page loaded correctly (not rate-limited, not redirected to login)."""
    url = self.page.url.lower()

    if "login" in url or "signin" in url or "/flow/login" in url:
        raise SessionExpiredError("Redirected to login page — session expired.")

    title = await self.page.title()
    title_lower = (title or "").lower()
    if "rate limit" in title_lower or "rate_limit" in url:
        raise Exception("X rate limit detected. Wait before retrying.")

    # Check for error pages (X shows minimal page with no primary column)
    has_content = await self.page.query_selector('[data-testid="primaryColumn"]')
    if not has_content:
        # Give it one more second and retry
        await asyncio.sleep(1)
        has_content = await self.page.query_selector('[data-testid="primaryColumn"]')
        if not has_content:
            logger.warning("Page loaded but primaryColumn not found — possible X error page")
```

Call `_validate_page_loaded()` after `page.goto()` in both `fetch_raw_thread` and `search_by_user_engagement`, replacing the inline login redirect checks.

**Step 4: Run tests**

Run: `pytest tests/test_scraper.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/scraper/scraper.py tests/test_scraper.py
git commit -m "feat(scraper): add page validation with rate-limit and login redirect detection"
```

---

### Task 18: Fix thread author filtering to handle quoted tweets

**Files:**
- Modify: `src/scraper/scraper.py:975-1016` (`filter_author_tweets_only`)
- Test: `tests/test_scraper.py`

**Step 1: Write the failing test**

```python
class TestFilterAuthorQuotedTweets:
    @pytest.fixture(autouse=True)
    def scraper(self):
        with patch("scraper.scraper.UserAgent") as mock_ua:
            mock_ua.return_value.random = "Mozilla/5.0"
            self.scraper = TwitterScraper(headless=True)

    def test_quoted_tweet_does_not_break_thread(self):
        """A quoted tweet (different author) between thread tweets should not stop collection."""
        tweets = [
            {"tweet_id": "1", "author_handle": "@alice", "text": "Thread start", "timestamp": "2026-01-01T00:00:00Z"},
            {"tweet_id": "2", "author_handle": "@bob", "text": "Quoted/reply", "timestamp": "2026-01-01T00:00:30Z"},
            {"tweet_id": "3", "author_handle": "@alice", "text": "Thread continues", "timestamp": "2026-01-01T00:01:00Z"},
            {"tweet_id": "4", "author_handle": "@alice", "text": "Thread end", "timestamp": "2026-01-01T00:02:00Z"},
        ]
        result = self.scraper.filter_author_tweets_only(tweets, "@alice")
        # Current behavior: stops at tweet 2, returns only tweet 1
        # Expected behavior: skips tweet 2 (quoted), returns tweets 1, 3, 4
        assert len(result) == 3
        assert [t["tweet_id"] for t in result] == ["1", "3", "4"]

    def test_genuine_end_of_thread(self):
        """Multiple consecutive non-author tweets should still end collection."""
        tweets = [
            {"tweet_id": "1", "author_handle": "@alice", "text": "Thread 1", "timestamp": "2026-01-01T00:00:00Z"},
            {"tweet_id": "2", "author_handle": "@alice", "text": "Thread 2", "timestamp": "2026-01-01T00:01:00Z"},
            {"tweet_id": "3", "author_handle": "@bob", "text": "Reply 1", "timestamp": "2026-01-01T00:02:00Z"},
            {"tweet_id": "4", "author_handle": "@charlie", "text": "Reply 2", "timestamp": "2026-01-01T00:03:00Z"},
            {"tweet_id": "5", "author_handle": "@alice", "text": "Separate tweet", "timestamp": "2026-01-01T00:10:00Z"},
        ]
        result = self.scraper.filter_author_tweets_only(tweets, "@alice")
        # 2+ consecutive non-author tweets = end of thread
        assert len(result) == 2
        assert [t["tweet_id"] for t in result] == ["1", "2"]
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_scraper.py::TestFilterAuthorQuotedTweets -v`
Expected: FAIL — `test_quoted_tweet_does_not_break_thread` returns 1 tweet instead of 3

**Step 3: Fix `filter_author_tweets_only`**

Replace the current method (lines 975-1016):

```python
def filter_author_tweets_only(self, tweets: List[Dict], target_handle: str) -> List[Dict]:
    """
    Filter collected tweets to only include the target author's thread tweets.
    Tolerates single interspersed non-author tweets (quoted tweets, UI artifacts)
    but stops at 2+ consecutive non-author tweets (end of thread).
    """
    if not tweets or not target_handle:
        return tweets

    target = target_handle.lower().lstrip('@')
    sorted_tweets = sorted(tweets, key=lambda t: t.get('timestamp') or '')

    # Find root tweet (first by target author)
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
                break  # 2+ consecutive non-author = end of thread

    return result
```

**Step 4: Run tests**

Run: `pytest tests/test_scraper.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/scraper/scraper.py tests/test_scraper.py
git commit -m "fix(scraper): handle quoted tweets in thread author filtering"
```

---

### Task 19: Deprecate `fetch_thread`, keep only `fetch_raw_thread`

**Files:**
- Modify: `src/scraper/scraper.py:712-769` (mark deprecated, delegate to `fetch_raw_thread`)
- Test: `tests/test_scraper.py`

**Step 1: Write the test**

```python
import warnings

class TestFetchThreadDeprecation:
    @pytest.fixture(autouse=True)
    def scraper(self):
        with patch("scraper.scraper.UserAgent") as mock_ua:
            mock_ua.return_value.random = "Mozilla/5.0"
            self.scraper = TwitterScraper(headless=True)

    def test_fetch_thread_emits_deprecation_warning(self):
        """fetch_thread should emit DeprecationWarning."""
        self.scraper.fetch_raw_thread = AsyncMock(return_value={
            "tweets": [{"text": "hi", "tweet_id": "1"}],
            "author_handle": "@user",
        })
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            result = asyncio.run(self.scraper.fetch_thread("https://x.com/user/status/1"))
            assert len(w) == 1
            assert issubclass(w[0].category, DeprecationWarning)
            assert "fetch_raw_thread" in str(w[0].message)

    def test_fetch_thread_delegates_to_raw(self):
        """fetch_thread should delegate to fetch_raw_thread and return tweets list."""
        thread_data = {
            "tweets": [
                {"text": "tweet 1", "tweet_id": "1"},
                {"text": "tweet 2", "tweet_id": "2"},
            ],
            "author_handle": "@user",
        }
        self.scraper.fetch_raw_thread = AsyncMock(return_value=thread_data)
        with warnings.catch_warnings(record=True):
            warnings.simplefilter("always")
            result = asyncio.run(self.scraper.fetch_thread("https://x.com/user/status/1"))
        assert isinstance(result, list)
        assert len(result) == 2
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_scraper.py::TestFetchThreadDeprecation -v`
Expected: FAIL — no deprecation warning emitted

**Step 3: Replace `fetch_thread` with a thin deprecated wrapper**

Replace the entire `fetch_thread` method (lines 712-769):

```python
async def fetch_thread(self, thread_url: str, max_scroll_attempts: int = 50) -> List[Dict]:
    """
    DEPRECATED: Use fetch_raw_thread() instead.
    This method is kept for backward compatibility and delegates to fetch_raw_thread.
    Returns List[Dict] (just the tweets) for backward compatibility.
    """
    import warnings
    warnings.warn(
        "fetch_thread() is deprecated. Use fetch_raw_thread() instead.",
        DeprecationWarning,
        stacklevel=2,
    )
    result = await self.fetch_raw_thread(thread_url, max_scroll_attempts=max_scroll_attempts, author_only=True)
    return result.get("tweets", [])
```

This removes ~50 lines of duplicated scroll/collect logic and the orphaned `_scroll_and_collect` method can also be removed if nothing else calls it.

**Step 4: Run tests**

Run: `pytest tests/test_scraper.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/scraper/scraper.py tests/test_scraper.py
git commit -m "refactor(scraper): deprecate fetch_thread, delegate to fetch_raw_thread"
```

---

## Execution Order Summary

| Phase | Tasks | Focus |
|-------|-------|-------|
| **Foundation** | 1, 2, 3, 4, 16 | Scraper core: errors, URLs, selectors, browser, session handling |
| **Scraper Quality** | 13, 17, 18, 19 | Video streams, rate-limit detection, quoted tweets, deprecation |
| **API Layer** | 5, 6, 7, 8 | Health endpoint, timeouts, session checks, thread resolution |
| **Frontend** | 9, 10, 11 | PostCard provenance, error states, session indicator |
| **Tooling** | 12 | Session refresh script |
| **Verification** | 14, 15 | Full test suite, Docker build |
