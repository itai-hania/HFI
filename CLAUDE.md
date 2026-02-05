# HFI Project Guide for Claude AI

> This document helps Claude AI understand the HFI project structure, current status, and how to assist effectively.

---

## Project Overview

**Name:** Hebrew FinTech Informant (HFI)
**Type:** Automated content creation pipeline
**Tech Stack:** Python, Playwright, OpenAI GPT-4o, Streamlit, SQLite, Docker, Kubernetes, RSS Feed Parsing
**Purpose:** Scrape English FinTech content from X (Twitter) + news sources (Yahoo Finance, WSJ, TechCrunch Fintech, Bloomberg), rank by relevance, translate to Hebrew with style matching, enable human review, and (future) auto-publish

---

## Current Status (as of 2026-01-27)

### Completion: ~92% (Beta Phase)

**Working Components:**
- ✅ X Scraper service (Playwright-based X scraper with thread support)
- ✅ News Scraper service (Multi-source RSS feeds with smart ranking)
- ✅ Processor service (GPT-4o translation + media downloads)
- ✅ Dashboard (Streamlit human review interface with trend discovery UI)
- ✅ Database models (SQLAlchemy + SQLite)
- ✅ Docker containers + Compose file
- ✅ Kubernetes manifests (ready for deployment)
- ✅ Comprehensive testing (100% pass rate - 202/202 tests)

**Pending:**
- ⏳ Publisher service (auto-posting to X)
- ⏳ Analytics dashboard
- ⏳ Additional news sources (Financial Times, CoinDesk)

---

## Architecture

### Services

```
┌─────────────┐      ┌────────────┐      ┌──────────────┐
│  X Scraper  │─────▶│  Database  │◀─────│  Dashboard   │
│ (Playwright)│      │  (SQLite)  │      │ (Streamlit)  │
└─────────────┘      └────────────┘      └──────────────┘
                           ▲                    │
┌─────────────┐            │                    │
│ News Scraper│────────────┤                    │
│ (RSS + Rank)│            │                    │
└─────────────┘            │                    │
                           │                    │
                    ┌──────────────┐            │
                    │  Processor   │◀───────────┘
                    │ (OpenAI GPT) │
                    └──────────────┘
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
│   ├── processor/           # Translation + downloads
│   │   ├── processor.py     # ContentProcessor
│   │   ├── main.py
│   │   └── Dockerfile
│   └── dashboard/           # Streamlit UI
│       ├── app.py
│       └── Dockerfile
├── config/
│   ├── glossary.json        # EN→HE term translations
│   └── style.txt            # Hebrew tweet examples
├── data/                    # Gitignored
│   ├── hfi.db              # SQLite database
│   ├── media/              # Downloaded media
│   └── session/            # Browser session cookies
├── k8s/                     # K8s manifests
├── tests/                   # Unit tests
├── docker-compose.yml
├── .env                     # Environment configuration (not in git)
├── IMPLEMENTATION_PLAN.md  # Detailed implementation guide
└── README.md
```

---

## Key Files to Reference

### When Helping with X Scraper Issues
- **`src/scraper/scraper.py`** - Main Playwright logic
- **`src/scraper/main.py`** - Entry point
- **Key Methods:**
  - `ensure_logged_in()` - Handles X authentication
  - `get_trending_topics()` - Scrapes X Explore page
  - `get_tweet_content(url)` - Fetches individual tweet
  - `fetch_thread(url)` - Scrapes full thread with replies
  - `fetch_raw_thread(url, author_only)` - Raw thread data extraction
  - `_scroll_and_collect()` - Scrolls page and collects tweets

### When Helping with News Scraper
- **`src/scraper/news_scraper.py`** - RSS feed aggregation + ranking
- **Key Classes:**
  - `NewsScraper` - Fetches from multiple RSS sources
- **Key Methods:**
  - `get_latest_news(limit_per_source, total_limit)` - Fetches and ranks articles
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
- **`src/processor/style_manager.py`** - Style example management (DB-backed, cached)
- **Key Classes:**
  - `TranslationService` - GPT-4o API wrapper with style matching
  - `ContentProcessor` - Orchestrates translation + downloads
  - `StyleManager` - Manages style examples from DB with topic tag matching
- **Dependencies:** openai, yt-dlp, requests

### When Helping with Dashboard
- **`src/dashboard/app.py`** - Streamlit interface
- **Features:**
  - Tweet review, inline editing, approval workflow
  - One-click trend discovery (Fetch All Trends button)
  - Thread scraping UI (paste URL → scrape → consolidate/separate)
  - Ranked article display (numbered #1-#10 with source badges)
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
- Streamlit server restarted (module caching issue): `pkill -f streamlit && python -m streamlit run app.py`
- Check logs for feed parsing errors (bozo_exception)

**Common Fixes:**
- **Module cache**: If dashboard shows old code, restart Streamlit completely
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
python init_db.py
```

### 5. Docker/K8s Deployment

**Docker Compose:**
```bash
docker-compose up -d          # Start all services
docker-compose logs -f        # View logs
docker-compose down           # Stop
```

**Kubernetes:**
- See `k8s/README.md` for full guide
- Quick deploy: `cd k8s && ./deploy.sh`
- All manifests validated and ready

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
pytest tests/test_processor.py -v
pytest tests/test_models.py -v
pytest tests/test_dashboard.py -v

# With coverage
pytest --cov=src tests/
```

**Current Status:** 202/202 tests passing (100%)

**Test Files:**
- `tests/test_models.py` - Database models
- `tests/test_scraper.py` - X scraper functionality
- `tests/test_processor.py` - Translation + downloads
- `tests/test_processor_comprehensive.py` - Processor config, translation, batch processing
- `tests/test_dashboard.py` - Dashboard database operations
- `tests/test_api_endpoints.py` - FastAPI trend/summary endpoints
- `tests/test_summary_generator.py` - Summary generation logic
- `tests/test_thread_media.py` - Thread media downloads
- `tests/test_thread_translation.py` - Thread translation logic
- Dashboard UI tested manually (Streamlit apps)

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

### 2026-02-05 (Latest)
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
- ✅ **Fixed all tests** (202/202 passing, 100%)
  - Fixed 22 pre-existing test failures across API, dashboard, and processor tests
  - Fixed module identity issues between `src.common.models` and `common.models`
  - Fixed ProcessorConfig, TranslationService, and batch processing test assertions

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
- No authentication → Should not be exposed publicly without adding auth
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
3. Update `src/dashboard/app.py`:
   - Add to `source_map` with appropriate `TrendSource` enum
   - Add CSS badge class
   - Update `get_source_badge_class()` mapping
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
3. Add analytics page to Streamlit dashboard

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
```

### Processor
```bash
cd src/processor
python main.py  # Runs continuously
```

### Dashboard
```bash
cd src/dashboard
python3 -m streamlit run app.py  # Access at http://localhost:8501

# Restart if code changed
pkill -f streamlit
python3 -m streamlit run app.py
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
3. Check dashboard logs for parsing errors
4. Restart Streamlit to clear module cache

### "Dashboard shows error after code change"
1. **FIRST:** Restart Streamlit (`pkill -f streamlit && python3 -m streamlit run app.py`)
2. Check browser console for JavaScript errors
3. Verify database schema matches models
4. Test in browser using MCP tools

### "Translations are bad"
1. Review `config/style.txt` - needs quality examples
2. Check `config/glossary.json` - add missing terms
3. Verify OpenAI model is gpt-4o (not older models)
4. Check system prompt in `TranslationService`

### "How do I deploy this?"
1. Local: `docker-compose up -d`
2. Production: K3s (see `k8s/README.md`)
3. Ensure `.env` is configured
4. Ensure secrets are created (for K8s)

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
**Secondary:** Learn AI automation, practice DevOps (Docker/K8s), experiment with LLMs and RSS aggregation

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
- Always restart Streamlit after code changes
- Check `.agent` directory for task-specific rules
- Update documentation after changes

---

**Last Updated:** 2026-02-05
**Version:** 1.3
**Maintained by:** HFI Project Team
