# HFI Project Guide for Claude AI

> This document helps Claude AI understand the HFI project structure, current status, and how to assist effectively.

---

## Project Overview

**Name:** Hebrew FinTech Informant (HFI)  
**Type:** Automated content creation pipeline  
**Tech Stack:** Python, Playwright, OpenAI GPT-4o, Streamlit, SQLite, Docker, Kubernetes  
**Purpose:** Scrape English FinTech content from X (Twitter), translate to Hebrew with style matching, enable human review, and (future) auto-publish

---

## Current Status (as of 2026-01-19)

### Completion: ~90% (Beta Phase)

**Working Components:**
- ✅ Scraper service (Playwright-based X scraper)
- ✅ Processor service (GPT-4o translation + media downloads)
- ✅ Dashboard (Streamlit human review interface)
- ✅ Database models (SQLAlchemy + SQLite)
- ✅ Docker containers + Compose file
- ✅ Kubernetes manifests (ready for deployment)
- ✅ Comprehensive testing (100% pass rate)

**Pending:**
- ⏳ Publisher service (auto-posting to X)
- ⏳ Multi-source scraping (beyond X)
- ⏳ Analytics dashboard

---

## Architecture

### Services

```
┌─────────────┐      ┌────────────┐      ┌──────────────┐
│   Scraper   │─────▶│  Database  │◀─────│  Dashboard   │
│ (Playwright)│      │  (SQLite)  │      │ (Streamlit)  │
└─────────────┘      └────────────┘      └──────────────┘
       │                   ▲                    │
       │                   │                    │
       └───────────────────┼────────────────────┘
                           │
                    ┌──────────────┐
                    │  Processor   │
                    │ (OpenAI GPT) │
                    └──────────────┘
```

### Directory Structure

```
HFI/
├── src/
│   ├── common/              # Shared models
│   │   ├── models.py        # SQLAlchemy (Tweet, Trend)
│   │   └── __init__.py
│   ├── scraper/             # X scraper (Playwright)
│   │   ├── scraper.py       # TwitterScraper class
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
├── .env.example
├── IMPLEMENTATION_PLAN.md  # Detailed implementation guide
└── README.md
```

---

## Key Files to Reference

### When Helping with Scraper Issues
- **`src/scraper/scraper.py`** - Main Playwright logic
- **`src/scraper/main.py`** - Entry point
- **Key Methods:**
  - `ensure_logged_in()` - Handles X authentication
  - `get_trending_topics()` - Scrapes X Explore page
  - `get_tweet_content(url)` - Fetches individual tweet
  - `fetch_thread(url)` - NEW: Scrapes full thread with replies
  - `_scroll_and_collect()` - Scrolls page and collects tweets

### When Helping with Translation/Processing
- **`src/processor/processor.py`** - Translation + media download
- **Key Classes:**
  - `TranslationService` - GPT-4o API wrapper with style matching
  - `ContentProcessor` - Orchestrates translation + downloads
- **Dependencies:** openai, yt-dlp, requests

### When Helping with Dashboard
- **`src/dashboard/app.py`** - Streamlit interface
- **Features:** Tweet review, inline editing, approval workflow

### When Helping with Database/Models
- **`src/common/models.py`** - SQLAlchemy models
- **Tables:**
  - `tweets` - Main content table (status workflow: pending → processed → approved → published)
  - `trends` - Trending topics discovered
- **Important:** Database schema includes `error_message` field and `failed` status for error tracking

---

## Common Tasks & How to Help

### 1. Debugging Scraper Issues

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

### 2. Translation Quality Issues

**Check:**
- `config/glossary.json` - Add missing financial terms
- `config/style.txt` - Needs 5-10 good Hebrew tweet examples
- OpenAI API key valid and has credits
- System prompt in `processor.py` > `TranslationService`

### 3. Database Errors

**Common Issues:**
- Database locked → Only one processor instance allowed
- Missing fields → Check if models.py matches database schema
- Status enum mismatch → Verify TweetStatus includes: pending, processed, approved, published, failed

**Reset Database:**
```bash
rm data/hfi.db
python init_db.py
```

### 4. Docker/K8s Deployment

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
- Scraper uses async Playwright API
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

**Run Tests:**
```bash
pytest tests/ -v                    # All tests
pytest tests/test_scraper.py -v    # Specific component
pytest --cov=src tests/             # With coverage
```

**Current Status:** 49/49 tests passing (100%)

**Test Files:**
- `tests/test_models.py` - Database models
- `tests/test_scraper.py` - Scraper functionality
- `tests/test_processor.py` - Translation + downloads
- Dashboard tested manually (Streamlit apps)

---

## Recent Updates & Changes

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

### Scraper
- X changes DOM selectors frequently → Requires periodic updates
- Rate limiting possible if run too frequently (30-60 min intervals recommended)
- 2FA during login must be handled manually on first run

### Processor
- OpenAI API costs can add up → Monitor usage
- yt-dlp occasionally fails on certain video formats → Fallback to error status

### Dashboard
- No authentication → Should not be exposed publicly without adding auth
- Auto-refresh can be slow with large datasets → Pagination planned

---

## How to Extend

### Add New Source (e.g., Reuters)
1. Create `src/scraper/reuters_scraper.py`
2. Implement similar interface to `TwitterScraper`
3. Add to `main.py` orchestration
4. Update `Trend.source` field

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

### Scraper
```bash
cd src/scraper
export SCRAPER_HEADLESS=false  # For manual login
python main.py
```

### Processor
```bash
cd src/processor
python main.py  # Runs continuously
```

### Dashboard
```bash
cd src/dashboard
streamlit run app.py  # Access at http://localhost:8501
```

### Database Inspection
```bash
sqlite3 data/hfi.db
.tables
SELECT * FROM tweets LIMIT 5;
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
5. Update documentation

---

## Priority Order for Fixes

1. **CRITICAL** - Scraper can't login / Session expired
2. **HIGH** - Processor crashes / Translation fails
3. **MEDIUM** - Dashboard bugs / UI issues
4. **LOW** - Code cleanup / Optimization

---

## Project Goals

**Primary:** Enable one person to monitor FinTech trends and publish Hebrew content efficiently  
**Secondary:** Learn AI automation, practice DevOps (Docker/K8s), experiment with LLMs

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

**User Preferences:**
- Minimal comments in code (only complex sections)
- Test all features
- Check `.agent` directory for task-specific rules
- Update context usage tracking after each response

---

**Last Updated:** 2026-01-19  
**Version:** 1.0  
**Maintained by:** HFI Project Team
