# Twitter/X Scraper Overhaul — Surgical Fix Design

**Date:** 2026-03-13
**Approach:** Surgical Fix — fix critical bugs and reliability issues with minimal restructuring
**Primary use case:** Paste X thread/tweet URLs in the Next.js dashboard → get scraped content
**Environment:** Production (Azure VM Docker) primary, local dev secondary

---

## Context

The Twitter/X scraper is currently non-functional. The primary issues are:
- Dockerfile installs Chromium but code uses Firefox
- Session management blocks on `input()` in Docker (hangs forever)
- No session health monitoring — failures are silent
- Selectors may be stale (X changes DOM frequently)
- Thread scraping breaks on quoted tweets
- Video quality selection is broken
- No retry logic or rate-limit detection
- `main.py` uses wrong enum value for trend source

---

## Section 1: Fix Docker & Browser Engine

**Problem:** Dockerfile installs Chromium, Python code calls `playwright.firefox.launch()`.

**Changes:**
- `scraper.py` `_init_browser()`: switch from Firefox to Chromium as default
- Add `SCRAPER_BROWSER` env var (values: `chromium`, `firefox`; default: `chromium`)
- Update stealth script for Chromium (Chromium already has `window.chrome`, so don't need to fake it; still patch `navigator.webdriver`)
- Dockerfile: no changes needed (already installs Chromium)

**Files:** `src/scraper/scraper.py`

---

## Section 2: Fix Session & Auth Management

**Problem:** `ensure_logged_in()` calls `input()` which blocks forever in Docker. Session expiry is silent.

**Changes:**
1. Remove `input()` blocking call. If no valid session exists, raise a descriptive error:
   `"No valid X session found. Run locally with SCRAPER_HEADLESS=false to create one, then copy data/session/storage_state.json to the server."`
2. Add `check_session_health()` method — navigates to a lightweight X page, verifies no redirect to `/login`
3. Add session age tracking — write `last_verified_at` timestamp to a sidecar JSON file next to `storage_state.json`. Skip re-verification if verified within 30 minutes
4. Return structured error dicts (not exceptions) from public methods when session is invalid, so dashboard can display clear messages

**Files:** `src/scraper/scraper.py`

---

## Section 3: Fix Selectors & Extraction Reliability

**Problem:** Selectors may be stale. No fallbacks. Extraction failures are silent.

**Changes:**
1. Add page-load validation after every navigation — check for `[data-testid="primaryColumn"]` or `article`. If missing, detect failure state (login redirect, rate limit, error page) and return specific error
2. Define fallback selector lists for critical extractions:
   - Text: `['[data-testid="tweetText"]', 'div[lang]']`
   - Author: `['[data-testid="User-Name"] a', 'a[role="link"][href*="/"]']`
   - Timestamp: `['time[datetime]', 'time']`
3. Validate extraction results — require minimum `text` + `tweet_id`. Log warnings for missing fields
4. Verify and update all current selectors against March 2026 X DOM

**Files:** `src/scraper/scraper.py`

---

## Section 4: Fix Thread Scraping

**Problem:** Author filtering breaks on quoted tweets. Scroll stop is too aggressive. Legacy duplication.

**Changes:**
1. Fix `filter_author_tweets_only()` — collect ALL tweets by target author regardless of position (don't stop at first non-author tweet). Handles quoted tweets and "Show more" elements inserted between author tweets
2. Fix `_should_stop_at_other_author()` — only stop scrolling after 3+ consecutive non-author tweets following the last author tweet
3. Attach `self.video_streams` data to tweet media arrays (match by tweet position/context)
4. Make `fetch_thread()` a thin wrapper calling `fetch_raw_thread()`, add deprecation warning

**Files:** `src/scraper/scraper.py`

---

## Section 5: Fix Trending Pipeline & Enum Mismatch

**Problem:** `main.py` uses `source='X'` instead of `TrendSource.X_TWITTER`. No retries.

**Changes:**
1. Change `source='X'` to `source=TrendSource.X_TWITTER` in `main.py`
2. Wrap `get_tweet_content()` and `search_tweets_by_topic()` with 2-attempt retry (catch timeout, wait 5s, retry)
3. Adaptive delay — if scrape returns empty or times out, increase inter-tweet delay from 2s to 5s for remaining tweets in that trend

**Files:** `src/scraper/main.py`

---

## Section 6: Alerts & Error Reporting

**Problem:** Failures are silent. No way to know when scraper breaks until content is missing.

**Changes:**
1. New `src/scraper/alerts.py` module with `send_alert(level, message)`:
   - Always logs to standard logger
   - Sends Telegram message if `TELEGRAM_ALERT_CHAT_ID` env var is set (uses existing bot API)
2. Alert triggers:
   - Session expired / login needed
   - Selector failure (page loaded but key elements missing)
   - Rate limit detected
   - Scrape returned 0 results unexpectedly
3. Dashboard error display — `fetch_raw_thread()` returns structured error dict on failure so dashboard shows specific error messages
4. New `GET /api/scraper/health` endpoint — checks session age and last successful scrape timestamp

**Files:** `src/scraper/alerts.py` (new), `src/scraper/scraper.py`, `src/api/routes/` (new health route)

---

## Section 7: Media Handling Fixes

**Problem:** Video quality selection sorts URLs alphabetically. Intercepted video streams are captured but never used.

**Changes:**
1. Fix video quality selection — parse `.m3u8` URLs for resolution hints (X URLs contain patterns like `/pl/720x1280/` or `/vid/avc1/720/`). Sort by extracted resolution, pick highest
2. Prefer network-intercepted video URLs over DOM-scraped ones — merge `self.intercepted_media_urls` and `self.video_streams` into tweet output
3. Keep existing media domain allowlist (twimg.com variants, x.com, twitter.com)

**Files:** `src/scraper/scraper.py`

---

## What Stays Unchanged

- Dashboard code (except handling new error types from scraper)
- Processor/translation pipeline
- Database models and schema
- All existing tests (new tests will be added)
- News scraper (RSS feeds)
- Frontend (Next.js)

---

## Testing Strategy

- Update existing `tests/test_scraper.py` with new test cases for:
  - Chromium browser initialization
  - Session health check logic
  - Fallback selector behavior
  - Improved author filtering (with quoted tweet scenarios)
  - Retry logic in main.py
  - Alert module
  - Video quality parsing
- Update `tests/test_scraper_page.py` mock tests for changed extraction logic
- Manual browser testing after deployment (verify session works in Docker)

---

## Risks

- **X DOM selectors may change again** — fallback selectors reduce but don't eliminate this risk
- **Chromium may behave differently than Firefox** for anti-detection — Playwright's Chromium is well-tested for scraping
- **Telegram alert integration** depends on bot being configured with correct chat ID
