# Thread Scraping & Inspiration Stabilization

**Date:** 2026-03-13
**Scope:** Fix & stabilize (no new features)
**Target UI:** Next.js Content Studio only

## Problem

Both thread scraping and inspiration search depend on Playwright-based X scraping. Neither feature works reliably because:

1. No session file exists on the production VM — scraper can't authenticate
2. Session expiry causes the API to hang forever (`input()` deadlock)
3. `twitter.com` URLs silently produce 0 results (regex only matches `x.com`)
4. Author handle extraction in JS is fragile and breaks when X changes DOM
5. No timeouts, no error messages — failures are silent
6. Thread URL resolution only fetches the first tweet, not the full thread
7. Inspiration "Use as Source" drops the `post_url`, losing provenance

## Design

### Section 1: Scraper Foundation Fixes

**1a. Handle `twitter.com` URLs**

`_extract_handle_from_url()` regex changes from `r'x\.com/([^/]+)/status'` to `r'(?:x\.com|twitter\.com)/([^/]+)/status'`.

**1b. Robust author handle extraction in JS**

`_collect_tweets_from_page()` JS adds a fallback chain:
1. Current: `@`-prefixed span in `User-Name` div
2. Fallback: extract handle from tweet permalink URL (`/user/status/...` -> `@user`)
3. Fallback: extract from User-Name div's link `href`

**1c. Session expiry handling**

Replace `input("Press ENTER...")` with a `SessionExpiredError` exception. Callers catch this and return a clear error. Never call `input()` in headless mode.

**1d. `ensure_logged_in()` timeout**

Wrap login-check navigation in a 15-second timeout. If it fails, raise `SessionExpiredError`.

### Section 2: Inspiration Feature Fixes

**2a. Timeout on scraper calls**

Wrap `scraper.search_by_user_engagement()` in `asyncio.wait_for(timeout=90)`. Return 504 on timeout.

**2b. Session check before scraping**

Before launching Playwright, check session file validity. Return 503 with `{"detail": "X session expired", "action": "refresh_session"}` if invalid.

**2c. Pass `post_url` to Create page**

`PostCard` changes from `/create?text={content}` to `/create?text={content}&url={post_url}`. Create page reads `url` and pre-fills `source_url`.

**2d. Error surfacing in frontend**

- 503 (session expired) -> warning banner with refresh instructions
- 504 (timeout) -> "Search timed out, try again"
- Empty results, no error -> "No posts found matching your criteria"

**2e. No phantom accounts**

Remove auto-create of `InspirationAccount` on search. Require explicit account adding first (UI already supports this).

### Section 3: Thread Scraping Fixes

**3a. Source resolver supports threads**

Modify `_resolve_x_url()` in `source_resolver.py` to detect thread URLs and use `fetch_raw_thread()`. Returns full consolidated thread text as source material for generation.

**3b. Timeout + error handling**

Wrap thread scraping in `asyncio.wait_for(timeout=120)`. Session check before attempting. Clear error messages on failure.

**3c. Fix video media capture**

Merge video URLs from response listener `video_streams` dict into tweet data after collection, instead of relying on empty `video.src` from DOM.

**3d. `twitter.com` URL support**

Covered by fix 1a.

### Section 4: Session Management & Tooling

**4a. `tools/refresh_session.py`**

Local script: opens visible browser -> user logs in -> saves `storage_state.json` -> prints SCP command for VM transfer.

**4b. `GET /api/health/scraper-session`**

Returns session status without launching a browser:
```json
{
  "status": "valid|expired|missing",
  "file_exists": true,
  "age_hours": 48.5,
  "last_checked": "2026-03-13T..."
}
```

**4c. Frontend session status indicator**

Shown on Inspiration page and Create page source resolution:
- Green: session valid
- Yellow: session >5 days old, may expire soon
- Red: session expired/missing, with refresh instructions

**4d. Graceful degradation**

All scraper-dependent features check session health first. Clear error messages instead of infinite loading.

## Files Affected

### Modified
- `src/scraper/scraper.py` — handle extraction, JS selectors, session handling, video merge
- `src/common/source_resolver.py` — thread-aware X URL resolution
- `src/api/routes/inspiration.py` — timeout, session check, no auto-create accounts
- `src/api/routes/generation.py` — timeout, session check on source resolve
- `frontend/src/app/(app)/inspiration/page.tsx` — error states, session indicator
- `frontend/src/app/(app)/create/page.tsx` — read `url` param, session indicator
- `frontend/src/components/PostCard.tsx` — pass `post_url` in link

### New
- `tools/refresh_session.py` — local session refresh script
- `src/api/routes/health.py` (or extend existing health endpoint) — session health check
- `src/scraper/errors.py` — `SessionExpiredError` exception class
- `frontend/src/components/SessionStatus.tsx` — reusable session status indicator

### Tests
- `tests/test_scraper.py` — new tests for `twitter.com` URL handling, fallback handle extraction
- `tests/test_inspiration.py` — timeout behavior, session check, no auto-create
- `tests/test_source_resolver.py` — thread URL resolution
- `tests/test_session_health.py` — health endpoint responses
