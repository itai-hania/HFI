# HFI Project Guide for Claude AI

> This document helps Claude AI understand the HFI project structure, current status, and how to assist effectively.
> Root agent entrypoint: `AGENTS.md` points here.

---

## Project Overview

**Name:** Hebrew FinTech Informant (HFI)
**Type:** Automated content creation pipeline
**Tech Stack:** Python, FastAPI, Next.js, Playwright, OpenAI GPT-4o, SQLite, Telegram Bot API, Docker, RSS Feed Parsing
**Purpose:** Scrape English FinTech content from X (Twitter) + news sources, rank by relevance, translate/generate Hebrew content, manage content in a Next.js studio, and deliver briefs/alerts through Telegram

---

## Current Status (as of 2026-03-08)

### Completion: ~95% (Beta Phase)

**Working Components:**
- ✅ X Scraper service (Playwright-based X scraper with thread support)
- ✅ News Scraper service (Multi-source RSS feeds with parallel fetching + smart ranking)
- ✅ Processor service (GPT-4o translation + media downloads + content generation)
- ✅ API v2 (JWT auth, content CRUD, generation, inspiration, settings, notifications)
- ✅ Frontend v2 (Next.js Content Studio with RTL UX and full content workflow)
- ✅ Telegram bot service (briefs, alerts, commands + scheduler)
- ✅ Database models (SQLAlchemy + SQLite)
- ✅ Docker containers + Compose file
- ✅ Comprehensive testing (100% pass rate)
- ✅ Code quality refactor (7 phases — prompt extraction, perf, security, packaging, dashboard split, tests)
- ✅ Security hardening (auth, rate limiting, input validation, XSS, CORS)
- ✅ Performance optimization (query consolidation, parallel feeds, caching, N+1 fixes)

**Pending:**
- ⏳ Publisher service (auto-posting to X)
- ⏳ Analytics dashboard
- ⏳ Additional news sources (Financial Times, CoinDesk)

---

## Architecture

### Services

```
┌───────────────────────┐        ┌────────────────────────┐
│ Next.js Frontend      │        │ Telegram Bot           │
│ (frontend/)           │        │ (src/telegram_bot/)    │
└───────────┬───────────┘        └───────────┬────────────┘
            │ REST (JWT)                      │ REST (JWT)
            └───────────────────┬─────────────┘
                                ▼
                    ┌────────────────────────┐
                    │ FastAPI API (src/api/) │
                    └───────────┬────────────┘
                                ▼
                         ┌────────────┐
                         │ SQLite DB  │
                         └──────┬─────┘
                                ▼
                    ┌────────────────────────┐
                    │ Scraper + Processor    │
                    └────────────────────────┘
```

### Directory Structure

```
HFI/
├── src/
│   ├── common/              # Shared models
│   │   ├── models.py        # SQLAlchemy (Tweet, Trend, Thread)
│   │   └── __init__.py
│   ├── scraper/             # X scraper + News scraper
│   │   ├── scraper.py       # TwitterScraper class (Playwright)
│   │   ├── news_scraper.py  # NewsScraper class (RSS feeds + ranking)
│   │   ├── main.py
│   │   └── Dockerfile
│   ├── processor/           # Translation + downloads + generation
│   │   ├── processor.py     # ContentProcessor + TranslationService
│   │   ├── content_generator.py  # ContentGenerator (post/thread generation)
│   │   ├── prompt_builder.py     # Shared prompt utilities
│   │   ├── style_manager.py      # Style example management
│   │   ├── main.py
│   │   └── Dockerfile
│   ├── api/                 # FastAPI routes/schemas/dependencies
│   ├── telegram_bot/        # Bot commands + scheduler
│   └── dashboard/           # Legacy Streamlit UI (deprecated)
│       ├── app.py           # ~63 lines — thin router
│       ├── styles.py        # CSS constant
│       ├── db_helpers.py    # DB helper functions
│       ├── auth.py          # Authentication gate
│       ├── lazy_loaders.py  # Lazy import helpers
│       ├── navigation.py    # Sidebar/navigation
│       ├── helpers.py       # Pure helper functions
│       ├── views/           # Page modules (NOT pages/ — avoids Streamlit multipage)
│       │   ├── home.py      # Home page
│       │   ├── content.py   # Content page (Acquire, Queue, Translation, Generate)
│       │   └── settings.py  # Settings page
│       └── Dockerfile
├── frontend/                # Next.js Content Studio
├── config/
│   ├── glossary.json        # EN→HE term translations
│   └── style.txt            # Hebrew tweet examples
├── data/                    # Gitignored
│   ├── hfi.db              # SQLite database
│   ├── media/              # Downloaded media
│   └── session/            # Browser session cookies
├── docs/                    # Documentation, plans, PDFs
│   └── archive/            # Completed plan documents
├── tests/                   # ALL test files (pytest)
├── tools/                   # Utility / one-off scripts
│   ├── init_db.py           # Database initializer
│   └── verify_setup.py      # Pre-flight dependency checker
├── docker-compose.yml
├── start_services.py        # App entrypoint
├── .env                     # Environment configuration (not in git)
├── CLAUDE.md
└── README.md
```

---

## 🗂️ Project Structure Rules

**NEVER drop files at the repository root.** The root is reserved exclusively for:
- Project config/meta: `README.md`, `CLAUDE.md`, `AGENTS.md`, `.env`, `.gitignore`, `.dockerignore`, `pyproject.toml`
- Docker: `docker-compose.yml`
- App entrypoint: `start_services.py`

### Where each file type belongs

| File type | Correct location |
|-----------|------------------|
| `test_*.py` — pytest test files | `tests/` |
| `verify_*.py`, `init_*.py`, ad-hoc scripts | `tools/` |
| Scraper/processor/dashboard logic | `src/<service>/` |
| `.md` plans, specs, PDFs, reference docs | `docs/` |
| Glossary, style guide, config JSONs | `config/` |
| DB file, media downloads, session cookies | `data/` (gitignored) |

### Rules
1. **No new `.py` files at root** — they belong in `src/`, `tests/`, or `tools/`.
2. **No new `.md` files at root** — they belong in `docs/` (exceptions: `README.md`, `CLAUDE.md`, and `AGENTS.md`).
3. **No PDF / reference documents at root** — they belong in `docs/`.
4. **Stale one-off scripts must live in `tools/`**, not scattered anywhere else.
5. When in doubt, ask: *which concern does this serve?* → put it in the matching folder.

---

## Key Files to Reference

### When Helping with X Scraper Issues
- **`src/scraper/scraper.py`** - Main Playwright logic
- **`src/scraper/main.py`** - Entry point
- **Key Methods:**
  - `ensure_logged_in()` - Handles X authentication
  - `get_trending_topics()` - Scrapes X Explore page
  - `get_tweet_content(url)` - Fetches individual tweet
  - `fetch_raw_thread(url, author_only)` - Raw thread data extraction

### When Helping with News Scraper
- **`src/scraper/news_scraper.py`** - RSS feed aggregation + ranking
- **Key Classes:**
  - `NewsScraper` - Fetches from multiple RSS sources
- **Key Methods:**
  - `get_latest_news(limit_per_source, total_limit)` - Fetches and ranks articles
  - `get_brief_news(total_limit, max_age_hours, limit_per_source)` - Strict-fresh brief pipeline with source health gating + clustering
  - `_fetch_single_feed_for_brief(source_name, limit_per_source, max_age_hours, now_utc)` - Per-source freshness diagnostics and article extraction
  - `_cluster_brief_articles(articles)` / `_score_brief_cluster(cluster)` - Multi-source grouping + relevance scoring used by `/api/notifications/brief`
  - `_rank_articles(articles)` - Scores by cross-source keyword overlap
  - `_extract_keywords(title)` - Extracts significant words for ranking
- **News Sources:**
  - Yahoo Finance: `https://finance.yahoo.com/news/rssindex`
  - WSJ Markets: `https://feeds.a.dj.com/rss/RSSMarketsMain.xml`
  - TechCrunch Fintech: `https://techcrunch.com/category/fintech/feed/`
  - Bloomberg Markets: `https://feeds.bloomberg.com/markets/news.rss`
- **Ranking Algorithm:**
  - Extracts keywords from article titles (removes stopwords, keeps words >2 chars)
  - Builds keyword → sources map
  - Scores each article: keywords in 2+ sources = +10 per source, else +1
  - Returns top N articles by score

### When Helping with Translation/Processing
- **`src/processor/processor.py`** - Translation + media download
- **`src/processor/content_generator.py`** - Hebrew content generation from English sources
- **`src/processor/prompt_builder.py`** - Shared prompt utilities (glossary, style, validation)
- **`src/processor/style_manager.py`** - Style example management (DB-backed, cached)
- **Key Classes:**
  - `TranslationService` - GPT-4o API wrapper with style matching
  - `ContentProcessor` - Orchestrates translation + downloads
  - `ContentGenerator` - Generates Hebrew posts/threads from source material
  - `StyleManager` - Manages style examples from DB with topic tag matching
- **Dependencies:** openai, yt-dlp, requests

### When Helping with Dashboard
- **`src/dashboard/app.py`** - Thin router (~63 lines): page config, CSS, auth, navigation, page routing
- **`src/dashboard/views/`** - Page modules (named `views/` not `pages/` to avoid Streamlit multipage auto-detection)
  - `home.py` - Home page (stats, trends, threads overview)
  - `content.py` - Content page (Acquire, Queue, Thread Translation, Generate tabs)
  - `settings.py` - Settings page (glossary, style learning, danger zone)
- **`src/dashboard/db_helpers.py`** - DB helper functions (get_db, get_stats, CRUD)
- **`src/dashboard/helpers.py`** - Pure helper functions (badge classes, media parsing)
- **`src/dashboard/styles.py`** - CSS constant
- **`src/dashboard/navigation.py`** - Sidebar navigation
- **Features:**
  - Tweet review, inline editing, approval workflow
  - One-click trend discovery (Fetch All Trends button)
  - Thread scraping UI (paste URL → scrape → consolidate/separate)
  - Content generation (paste source → pick mode/angle → generate variants)
  - Ranked article display (numbered #1-#10 with source badges)
  - Style learning system (DB-backed examples with topic tags)
  - Status filtering (pending/processed/approved/published/failed)

### When Helping with Database/Models
- **`src/common/models.py`** - SQLAlchemy models
- **Tables:**
  - `tweets` - Main content table (status workflow: pending → processed → approved → published)
  - `trends` - Trending topics discovered (supports TrendSource enum)
  - `threads` - Full thread data stored as JSON
  - `style_examples` - Hebrew style examples with topic tags (is_active Boolean)
- **Important Enums:**
  - `TweetStatus`: PENDING, PROCESSED, APPROVED, PUBLISHED, FAILED
  - `TrendSource`: X_TWITTER, YAHOO_FINANCE, WSJ, TECHCRUNCH, BLOOMBERG, MANUAL
- **Important:** Database schema includes `error_message` field and `failed` status for error tracking

---

## Common Tasks & How to Help

### 1. Debugging X Scraper Issues

**Symptoms:**
- Browser hangs on login
- Session expires
- No tweets found

**Check:**
- `data/session/storage_state.json` exists and valid
- `SCRAPER_HEADLESS` environment variable
- Playwright selectors still match X's DOM (they change often!)
- Network interception not blocking requests

**Key Selectors (X DOM - as of 2026-01):**
```javascript
article[data-testid="tweet"]         // Tweet container
div[data-testid="tweetText"]         // Tweet text
div[data-testid="User-Name"]         // Author section
time[datetime]                       // Timestamp
[data-testid="tweetPhoto"]          // Image
[data-testid="videoPlayer"]         // Video
```

### 2. Debugging News Scraper Issues

**Symptoms:**
- No trends fetched
- Error: `total_limit` not recognized
- Empty results

**Check:**
- RSS feeds are accessible: `curl -I https://finance.yahoo.com/news/rssindex`
- `feedparser` dependency installed: `pip install feedparser`
- Check logs for feed parsing errors (bozo_exception)

**Common Fixes:**
- **Feed changes**: RSS URLs may change; verify each feed individually
- **Network issues**: Some feeds may be temporarily unavailable

### 3. Translation Quality Issues

**Check:**
- `config/glossary.json` - Add missing financial terms
- `config/style.txt` - Needs 5-10 good Hebrew tweet examples
- OpenAI API key valid and has credits
- System prompt in `processor.py` > `TranslationService`

### 4. Database Errors

**Common Issues:**
- Database locked → Only one processor instance allowed
- Missing fields → Check if models.py matches database schema
- Status enum mismatch → Verify TweetStatus includes: pending, processed, approved, published, failed
- Enum value mismatch → Ensure `TrendSource.YAHOO_FINANCE` (not REUTERS)

**Reset Database:**
```bash
rm data/hfi.db
python tools/init_db.py
```

### 5. Deployment

**Local (Docker Compose):**
```bash
docker-compose up -d          # Start all services
docker-compose logs -f        # View logs
docker-compose down           # Stop
```

**Production (Azure VM + Caddy auto-HTTPS):**
- See `docs/deploy/azure-private-production-runbook.md` for full guide
- URL: `https://hfi-prod.israelcentral.cloudapp.azure.com`
- Caddy handles Let's Encrypt TLS automatically
- CI/CD: push to `main` → GitHub Actions self-hosted runner auto-deploys

---

## Code Patterns & Conventions

### Async/Await
- X Scraper uses async Playwright API
- Use `await` for all browser operations
- Pattern: `async def method_name():`

### Database Access
```python
from common.models import SessionLocal, Tweet

db = SessionLocal()
try:
    tweets = db.query(Tweet).filter_by(status='pending').all()
    # ... work with tweets ...
    db.commit()
finally:
    db.close()
```

### Error Handling
- Scraper: Retry on failures, log warnings
- Processor: Set `status='failed'` and store `error_message`
- Dashboard: Display errors to user with emoji indicators

### Logging
```python
import logging
logger = logging.getLogger(__name__)

logger.info("✅ Success message")
logger.warning("⚠️ Warning message")
logger.error("❌ Error message")
```

---

## Environment Variables

Required in `.env`:
```bash
# X Credentials
X_USERNAME=email@example.com
X_PASSWORD=password

# OpenAI
OPENAI_API_KEY=sk-proj-...

# Database
DATABASE_URL=sqlite:///data/hfi.db

# Optional
SCRAPER_HEADLESS=true
SCRAPER_MAX_TRENDS=5
```

---

## Testing

### Running Tests

```bash
# All tests
pytest tests/ -v

# Specific component
pytest tests/test_scraper.py -v
pytest tests/test_processor_comprehensive.py -v
pytest tests/test_models.py -v
pytest tests/test_dashboard.py -v

# With coverage
pytest --cov=src tests/
```

**Current Status:** All tests passing (100%)

**Test Files:**
- `tests/test_models.py` - Database models
- `tests/test_scraper.py` - X scraper functionality
- `tests/test_scraper_page.py` - Scraper page mock tests
- `tests/test_processor_comprehensive.py` - Processor config, translation, batch processing
- `tests/test_content_generator.py` - Content generation engine
- `tests/test_prompt_builder.py` - Shared prompt builder utilities
- `tests/test_dashboard.py` - Dashboard database operations
- `tests/test_dashboard_helpers.py` - Pure dashboard helper functions
- `tests/test_api_endpoints.py` - FastAPI trend/summary endpoints
- `tests/test_summary_generator.py` - Summary generation logic
- `tests/test_thread_media.py` - Thread media downloads
- `tests/test_thread_translation.py` - Thread translation logic (parameterized)

---

## 🚨 CRITICAL: Testing Changes via Web Browser (MCP)

### When You MUST Test in Browser

**ALWAYS test in the browser using MCP tools when:**

1. **UI/Dashboard Changes:**
   - Any modification to `src/dashboard/app.py`
   - CSS/styling changes
   - Button behavior changes
   - Form input changes
   - Display logic changes

2. **Integration Points:**
   - Changes to scraper that affect dashboard display
   - Database schema changes that impact UI
   - New features with user-facing components
   - API parameter changes (e.g., adding `total_limit`)

3. **Significant Feature Additions:**
   - New scraper sources
   - New ranking algorithms
   - New data processing pipelines
   - Workflow modifications

### Testing Workflow

When you make changes that require browser testing:

```python
# 1. Ensure Streamlit is running
# Check for existing process
pgrep -f "streamlit"

# Kill old process if exists
kill <process_id>

# Start fresh Streamlit server
cd src/dashboard
python3 -m streamlit run app.py --server.port 8501 &

# 2. Use MCP browser automation tools
# Get tab context
mcp__claude-in-chrome__tabs_context_mcp(createIfEmpty=true)

# Navigate to dashboard
mcp__claude-in-chrome__navigate(url="http://localhost:8501", tabId=<tab_id>)

# Take screenshot to verify load
mcp__claude-in-chrome__computer(action="screenshot", tabId=<tab_id>)

# 3. Interact with the feature
# Example: Click "Fetch All Trends" button
mcp__claude-in-chrome__computer(action="left_click", coordinate=[x, y], tabId=<tab_id>)

# Wait for processing
mcp__claude-in-chrome__computer(action="wait", duration=10, tabId=<tab_id>)

# Take screenshot of results
mcp__claude-in-chrome__computer(action="screenshot", tabId=<tab_id>)

# 4. Verify results visually
# Check for:
# - Error messages
# - Expected data displayed
# - UI elements render correctly
# - Interactions work as expected
```

### Why This Is Critical

**❌ Unit tests alone are NOT enough because:**
- Streamlit caches imported modules (old code may run)
- UI rendering issues won't be caught
- Integration bugs between components
- Real-world interaction patterns differ from tests

**✅ Browser testing catches:**
- Module caching issues (stale imports)
- UI rendering bugs
- JavaScript errors
- Network request failures
- CSS styling issues
- User interaction bugs

### Example: Recent Bug Caught by Browser Testing

**Issue:** User reported `total_limit` error after implementing news scraper ranking.
- ✅ Unit tests passed (new code was correct)
- ❌ Browser showed error: "get_latest_news() got an unexpected keyword argument 'total_limit'"
- **Root cause:** Streamlit cached old `news_scraper.py` module without `total_limit` parameter
- **Solution:** Restart Streamlit server to clear module cache

**Lesson:** Always restart Streamlit and test in browser after significant changes.

### Testing Checklist for Dashboard Changes

Before declaring a dashboard feature complete:

- [ ] Run unit tests: `pytest tests/ -v`
- [ ] Restart Streamlit: `pkill -f streamlit && python3 -m streamlit run app.py`
- [ ] Navigate to dashboard via MCP
- [ ] Take screenshot of initial state
- [ ] Interact with changed feature (click buttons, enter data)
- [ ] Take screenshot of results
- [ ] Verify no error messages displayed
- [ ] Verify data displays correctly
- [ ] Verify UI elements render properly

---

## Recent Updates & Changes

### 2026-03-13 (Latest)
- ✅ **Legacy code cleanup** — full codebase audit and removal
  - Deleted `archive/dashboard-v1/` (22 files, zero imports)
  - Removed dead query helpers from `models.py` (get_tweets_by_status, get_recent_trends, update_tweet_status)
  - Removed dead scraper methods (fetch_thread, _scroll_and_collect, main demo)
  - Cleaned processor dead code (dead imports, unreachable returns, unused methods)
  - Removed dead API schemas (TrendCreate, TrendUpdate) and unused route helper
  - Moved misplaced test scripts from `tests/` to `tools/`
  - Deleted stale tools (verify_changes.py, scrape_hebrew_threads.py)
  - Deleted superseded `k8s/` directory (12 files, ~2,669 lines)
  - Deleted stale Docker scripts (docker-build.sh, docker-validate.sh)
  - Cleaned `start_services.py` — removed deprecated dashboard menu options, fixed tool paths
  - Removed misleading root `requirements.txt`
  - Consolidated duplicate STOPWORDS into `src/common/stopwords.py`
  - Archived completed plan documents to `docs/archive/`

### 2026-02-15
- ✅ **Performance optimization for public deployment** (468/468 tests)
  - Database: Collapsed `get_stats()` from 6 queries to 1 (GROUP BY + conditional aggregation) with 5s TTL cache
  - Database: Gated `create_tables()` behind session flag (was running 12 ALTER TABLE attempts per rerun)
  - Database: Fixed N+1 queries in home page trends loop, ranked articles, auto_pipeline (pre-fetch into sets/dicts)
  - Database: `health_check()` consolidated from 7 queries to 2
  - Database: API trends stats replaced per-source loop with single GROUP BY
  - Network: RSS feeds fetched in parallel via ThreadPoolExecutor with 10s timeout
  - Network: Deduplication pre-computes keyword sets (was O(n^2) re-extraction)
  - Network: HTML regex compiled once as class attribute
  - Dashboard: Removed 20+ unnecessary `time.sleep()` calls before `st.rerun()`
  - Dashboard: Lazy loaders now cache singleton instances
  - Dashboard: Batch translate commits every 5 tweets instead of every 1
  - Dashboard: X threads filtered in SQL (LIKE) instead of loading 50 + Python filter
  - Dashboard: Settings duplicate count queries eliminated
  - API: SummaryGenerator cached as singleton

### 2026-02-14
- ✅ **Security hardening** (48 new tests in test_security.py)

### 2026-02-09
- ✅ **Code quality refactor — all 7 phases complete** (338/338 tests)
  - Phase 1: Quick fixes (log paths, float index, subprocess, 22 exception handlers)
  - Phase 2: Performance (shared OpenAI client, TTL cache, yield_per pagination)
  - Phase 3: Security (XSS hardening, dashboard auth gate)
  - Phase 4: PromptBuilder extraction (`src/processor/prompt_builder.py`) — shared utilities for TranslationService + ContentGenerator
  - Phase 5: Python packaging (`pyproject.toml` + `pip install -e .`, removed all sys.path hacks)
  - Phase 6: Dashboard split (app.py 3004→63 lines, modular `views/` structure)
  - Phase 7: Test improvements (parameterized tests, mock pages, dashboard helpers extraction)

### 2026-02-06
- ✅ **Content Generation Engine** (`src/processor/content_generator.py`)
  - ContentGenerator class with generate_post() and generate_thread()
  - Tweet model: added `content_type` + `generation_metadata` columns
  - Dashboard "Generate" tab (paste source → pick mode/angle → generate variants → approve/save)
  - Auto-style learning: approved tweets auto-added to style_examples DB

### 2026-02-05
- ✅ **Implemented Style Learning (SPEC v2)** (`src/processor/style_manager.py`)
  - DB-backed style examples with `style_examples` table
  - Topic tag extraction and matching for context-aware translation
  - Style cache with refresh support
  - 5 examples + 800 char truncation per prompt
  - Hebrew content threshold (50%) validation
- ✅ **Dashboard style management UI**
  - Add/edit/delete style examples
  - Topic tag editing with visual chips
  - Tag-based filtering
  - X thread preview for style examples
  - "Load More" pagination

### 2026-01-27
- ✅ **Added multi-source news scraper** (`src/scraper/news_scraper.py`)
  - Yahoo Finance, WSJ, TechCrunch Fintech, Bloomberg
  - Cross-source keyword overlap ranking algorithm
  - Returns top 10 most relevant articles
- ✅ **Updated dashboard UI**
  - One-click "Fetch All Trends" button
  - Ranked article display (#1-#10 with source badges)
  - Updated source mapping (REUTERS → YAHOO_FINANCE)
  - Removed old client-side ranking (now in scraper)
- ✅ **Database model update**
  - Renamed `TrendSource.REUTERS` → `TrendSource.YAHOO_FINANCE`
- ✅ **Updated all tests** (106/108 passing, 98%)
- ✅ **Updated README.md and CLAUDE.md**
- ⚠️ **Important lesson:** Always test dashboard changes in browser (module caching)

### 2026-01-19
- ✅ Implemented thread scraping (`fetch_thread` method)
- ✅ Fixed browser viewport conflicts
- ✅ Switched from active network interception to passive listeners
- ✅ Cleaned up unnecessary .md files
- ✅ Updated README with current status

### 2026-01-18
- ✅ Completed comprehensive testing (49 tests)
- ✅ Fixed processor blockers (FAILED status, error_message field)
- ✅ Added yt-dlp dependency
- ✅ Fixed scraper memory leaks (event handler cleanup)

---

## Known Issues & Limitations

### X Scraper
- X changes DOM selectors frequently → Requires periodic updates
- Rate limiting possible if run too frequently (30-60 min intervals recommended)
- 2FA during login must be handled manually on first run

### News Scraper
- RSS feeds may change URLs or become unavailable
- Some feeds may be rate-limited
- TechCrunch Fintech feed is narrower than main feed (by design)
- Ranking algorithm prioritizes cross-source topics (may miss single-source stories)

### Processor
- OpenAI API costs can add up → Monitor usage
- yt-dlp occasionally fails on certain video formats → Fallback to error status

### Dashboard
- Optional auth gate via `DASHBOARD_PASSWORD` env var (added in Phase 3)
- Auto-refresh can be slow with large datasets → Pagination planned
- **Module caching:** Streamlit caches imports; restart required after code changes
- Session state can persist old data; use browser refresh if issues occur

---

## How to Extend

### Add New News Source (e.g., Financial Times)
1. Open `src/scraper/news_scraper.py`
2. Add to `FEEDS` dict:
   ```python
   "Financial Times": "https://www.ft.com/rss/markets"
   ```
3. Update `src/dashboard/views/content.py`:
   - Add to `source_map` with appropriate `TrendSource` enum
   - Update `src/dashboard/helpers.py` `get_source_badge_class()` mapping
   - Add CSS badge class in `src/dashboard/styles.py`
4. Update `src/common/models.py`:
   - Add `FINANCIAL_TIMES = "Financial Times"` to `TrendSource` enum
5. Test in browser using MCP tools

### Add Auto-Publishing
1. Create `src/publisher/publisher.py`
2. Use tweepy or X API v2
3. Query for `status='approved'` tweets
4. Post to X, update `status='published'`

### Add Analytics
1. Extend `Tweet` model with engagement fields (views, likes, retweets)
2. Create `src/analytics/tracker.py`
3. Add analytics page to Next.js frontend

---

## Helpful Commands Reference

### X Scraper
```bash
cd src/scraper
export SCRAPER_HEADLESS=false  # For manual login
python main.py
```

### News Scraper (integrated in dashboard)
- Use dashboard "Fetch All Trends" button
- Or call directly:
```python
from scraper.news_scraper import NewsScraper
scraper = NewsScraper()
articles = scraper.get_latest_news(limit_per_source=5, total_limit=10)
brief_stories = scraper.get_brief_news(total_limit=8, max_age_hours=48)
```

### Processor
```bash
cd src/processor
python main.py  # Runs continuously
```

### Database Inspection
```bash
sqlite3 data/hfi.db
.tables
SELECT * FROM tweets LIMIT 5;
SELECT * FROM trends ORDER BY discovered_at DESC LIMIT 10;
.schema tweets
.exit
```

---

## When User Asks About...

### "Why isn't the scraper working?"
1. Check if session exists: `ls data/session/storage_state.json`
2. Check if headless mode is correct for the task
3. Review recent X DOM structure changes
4. Check logs for Playwright errors

### "News scraper not fetching trends"
1. Check RSS feed connectivity: `curl -I https://finance.yahoo.com/news/rssindex`
2. Verify `feedparser` installed: `pip show feedparser`
3. Check API logs for parsing errors
4. Verify news scraper module is importable

### "Frontend shows error after code change"
1. Check browser console for JavaScript errors
2. Restart Next.js dev server (`cd frontend && npm run dev`)
3. Verify database schema matches models
4. Test in browser using MCP tools

### "Translations are bad"
1. Review `config/style.txt` - needs quality examples
2. Check `config/glossary.json` - add missing terms
3. Verify OpenAI model is gpt-4o (not older models)
4. Check system prompt in `TranslationService`

### "How do I deploy this?"
1. Local: `docker-compose up -d`
2. Production: Azure VM with Caddy auto-HTTPS (see `docs/deploy/azure-private-production-runbook.md`)
3. Ensure `.env.prod` is configured on the VM (see `deploy/.env.prod.example`)
4. Push to `main` to trigger auto-deploy via GitHub Actions

### "I want to add [feature]"
1. Check `IMPLEMENTATION_PLAN.md` for architecture
2. Determine which service it belongs to
3. Follow existing code patterns
4. Add tests in `tests/` directory
5. **If dashboard changes: TEST IN BROWSER using MCP**
6. Update documentation (README.md, CLAUDE.md)

---

## Priority Order for Fixes

1. **CRITICAL** - Scraper can't login / Session expired
2. **HIGH** - Processor crashes / Translation fails / News scraper broken
3. **MEDIUM** - Dashboard bugs / UI issues
4. **LOW** - Code cleanup / Optimization

---

## Project Goals

**Primary:** Enable one person to monitor FinTech trends from multiple sources and publish Hebrew content efficiently
**Secondary:** Learn AI automation, practice DevOps (Docker), experiment with LLMs and RSS aggregation

**Non-Goals:**
- Not trying to replace human creativity (hence human-in-loop dashboard)
- Not trying to spam or automate engagement (ethical content creation)
- Not trying to build a SaaS product (personal tool)

---

## Contact & Collaboration

When helping:
- Be proactive with suggestions
- Prioritize user's time (simplify complex tasks)
- Assume user is technical but busy
- Provide copy-pasteable code when possible
- Link to relevant files with line numbers
- **CRITICAL:** Always test dashboard changes in browser using MCP

**User Preferences:**
- Minimal comments in code (only complex sections)
- Test all features (unit tests + browser tests)
- Check `.agent` directory for task-specific rules
- Update documentation after changes

---

**Last Updated:** 2026-03-13
**Version:** 1.8
**Maintained by:** HFI Project Team
