# HFI Security Hardening Plan

> Generated: 2026-02-14
> Context: Preparing app for limited public access
> Status: TODO — implement in order

---

## Phase 1: Authentication Hardening

### 1.1 Fix password comparison (CRITICAL)
- **File:** `src/dashboard/auth.py`
- **Change:** Replace `==` with `secrets.compare_digest()` to prevent timing attacks
- **Change:** Make `DASHBOARD_PASSWORD` **required** — refuse to start if unset
- Add clear error message when password is missing

### 1.2 Add brute force protection (CRITICAL)
- **File:** `src/dashboard/auth.py`
- Track failed attempts in `st.session_state` with timestamps
- Max 5 attempts per 2-minute window
- Show cooldown timer when locked out
- Log failed attempts with timestamp

### 1.3 Add session expiry (HIGH)
- **File:** `src/dashboard/auth.py`
- Store `authenticated_at` timestamp in session state
- Check on every request — expire after 4 hours
- Show re-login prompt on expiry

### 1.4 Add audit logging for auth events (MEDIUM)
- Log successful logins, failed attempts, session expiries
- Include timestamp and IP if available from Streamlit headers

---

## Phase 2: Input Validation & Sanitization

### 2.1 URL validation for scraper inputs (HIGH)
- **Files:** `src/dashboard/views/content.py`, `src/dashboard/views/settings.py`
- Create `src/dashboard/validators.py` with:
  - `validate_x_url(url) -> bool` — whitelist `x.com` and `twitter.com` domains only
  - `validate_url_length(url, max_len=500) -> bool`
- Apply to all URL text inputs before passing to scraper
- Reject non-HTTPS URLs

### 2.2 Input size limits on text fields (HIGH)
- **Files:** `src/dashboard/views/content.py`, `settings.py`
- Add `max_chars=500` to URL inputs
- Add `max_chars=10000` to text areas (source content, glossary, style examples)
- Add `max_chars=50000` to glossary editor

### 2.3 Glossary editor safety (HIGH)
- **File:** `src/dashboard/views/settings.py`
- Add max file size check (1MB) before writing
- Create backup of current glossary before overwrite (`glossary.json.bak`)
- Validate JSON structure (must be `dict[str, str]`)

### 2.4 URL validation in markdown links (MEDIUM)
- **File:** `src/dashboard/views/home.py`
- Validate `trend.article_url` starts with `https://` before rendering as link
- Reject `javascript:`, `data:`, `vbscript:` URLs

### 2.5 yt-dlp URL domain whitelist (HIGH)
- **File:** `src/processor/processor.py`
- Before passing URL to subprocess, validate domain is one of:
  `twimg.com`, `twitter.com`, `x.com`, `video.twimg.com`, `pbs.twimg.com`
- Reject all other domains

---

## Phase 3: Rate Limiting & Cost Protection

### 3.1 OpenAI API rate limiting (HIGH)
- **File:** `src/common/openai_client.py` or new `src/common/rate_limiter.py`
- Track calls per hour in module-level counter
- Default limit: 100 calls/hour (configurable via `OPENAI_RATE_LIMIT` env var)
- Raise clear error when limit reached
- Log usage stats

### 3.2 Scraper cooldown (HIGH)
- **File:** `src/dashboard/views/content.py`
- Track last scrape timestamp in `st.session_state`
- Enforce 30-second minimum between scraper invocations
- Enforce 60-second minimum between "Fetch All Trends" clicks

### 3.3 Batch translation limits (MEDIUM)
- **File:** `src/dashboard/views/content.py` (`run_batch_translate`)
- Max 20 tweets per batch translation
- Show warning if more are pending

---

## Phase 4: XSS Fixes & Error Handling

### 4.1 Fix remaining XSS gaps (MEDIUM)
- **File:** `src/dashboard/views/content.py:1298-1303`
  - Add `html.escape()` to `tweet.trend_topic` in editor header
- **File:** `src/dashboard/views/home.py:129`
  - Validate `trend.article_url` before using in markdown link

### 4.2 Generic error messages (MEDIUM)
- **Files:** All dashboard views
- Replace `st.error(f"Failed: {str(e)[:150]}")` pattern with:
  - Log full error server-side: `logger.error(f"...: {e}")`
  - Show generic message to user: `st.error("Operation failed. Check server logs for details.")`
- Apply to all user-facing error displays (~15 locations)

---

## Phase 5: CORS & API Security

### 5.1 Lock down CORS (HIGH)
- **File:** `src/api/main.py`
- Change `allow_methods=["*"]` to `allow_methods=["GET", "POST"]`
- Change `allow_headers=["*"]` to `allow_headers=["Content-Type", "Authorization"]`
- Review if `allow_credentials=True` is needed

### 5.2 Add API key authentication (HIGH)
- **File:** `src/api/main.py` + `src/api/dependencies.py`
- Add `X-API-Key` header check using FastAPI dependency
- Key stored in `API_SECRET_KEY` env var
- Return 401 for missing/invalid key

### 5.3 Disable docs in production (MEDIUM)
- **File:** `src/api/main.py`
- Set `docs_url=None, redoc_url=None, openapi_url=None` when `ENVIRONMENT=production`

---

## Phase 6: Infrastructure & Logging

### 6.1 Remove DB URL from logs (CRITICAL)
- **File:** `src/common/models.py:63`
- Replace `logger.info(f"Database configured: {DATABASE_URL}")` with:
  `logger.info(f"Database configured: {DATABASE_URL.split('://')[0]}://***")`

### 6.2 HTTPS documentation (MEDIUM)
- Add `nginx.conf` example for TLS termination with Let's Encrypt
- Add to `docker-compose.yml` as optional nginx service
- Document in README

### 6.3 Update dependencies (MEDIUM)
- Update `requests` (CVE-2024-35195)
- Update `pillow` (security patches)
- Update `streamlit`, `sqlalchemy`, `openai` to latest stable
- Run `pip-audit` and document results

### 6.4 File download size limits (MEDIUM)
- **File:** `src/processor/processor.py`
- Add 10MB max size for image downloads (check Content-Length header)
- Add 100MB max size for video downloads
- Add allowed extension whitelist for images: `jpg, jpeg, png, gif, webp`

---

## Phase 7: Tests for Security Features

### 7.1 Auth tests
- Test brute force lockout triggers after 5 attempts
- Test session expiry after configured timeout
- Test `secrets.compare_digest` is used (mock and verify)
- Test app refuses to start without `DASHBOARD_PASSWORD`

### 7.2 Validation tests
- Test URL validator rejects non-X URLs
- Test URL validator rejects `javascript:` URLs
- Test input size limits are enforced
- Test glossary max size enforcement

### 7.3 Rate limiting tests
- Test OpenAI rate limiter blocks after limit
- Test scraper cooldown enforced

---

## Implementation Order

| Step | Phase | Effort | Description |
|------|-------|--------|-------------|
| 1 | 6.1 | 5 min | Remove DB URL from logs |
| 2 | 1.1 | 15 min | Fix password comparison + require password |
| 3 | 1.2 | 30 min | Brute force protection |
| 4 | 1.3 | 20 min | Session expiry |
| 5 | 2.1 | 30 min | URL validator + apply to scraper inputs |
| 6 | 2.5 | 15 min | yt-dlp domain whitelist |
| 7 | 2.2 | 20 min | Input size limits |
| 8 | 2.3 | 15 min | Glossary editor safety |
| 9 | 3.1 | 30 min | OpenAI rate limiting |
| 10 | 3.2 | 15 min | Scraper cooldown |
| 11 | 4.1 | 10 min | Fix XSS gaps |
| 12 | 4.2 | 20 min | Generic error messages |
| 13 | 5.1 | 10 min | CORS lockdown |
| 14 | 5.2 | 20 min | API key auth |
| 15 | 5.3 | 5 min | Disable docs in prod |
| 16 | 6.3 | 15 min | Update dependencies |
| 17 | 6.4 | 15 min | File download limits |
| 18 | 2.4 | 10 min | URL validation in markdown |
| 19 | 3.3 | 10 min | Batch translation limits |
| 20 | 7.* | 60 min | Security tests |

**Total estimated: ~6 hours**

---

## Files to Create
- `src/dashboard/validators.py` — URL validation, input sanitization
- `src/common/rate_limiter.py` — OpenAI call rate limiter

## Files to Modify
- `src/dashboard/auth.py` — major rewrite (phases 1.1-1.4)
- `src/common/models.py` — line 63 (phase 6.1)
- `src/dashboard/views/content.py` — validation, rate limits, error handling
- `src/dashboard/views/settings.py` — glossary safety, input limits
- `src/dashboard/views/home.py` — URL validation in links
- `src/processor/processor.py` — yt-dlp whitelist, download limits
- `src/api/main.py` — CORS, API auth, docs toggle
- `src/api/dependencies.py` — API key dependency
- `src/common/openai_client.py` — rate limit integration
- Various `requirements.txt` — dependency updates
