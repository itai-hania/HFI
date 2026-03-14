# HFI Project Guide for Claude AI

> Root agent entrypoint: `AGENTS.md` points here.

## Project Overview

**Name:** Hebrew FinTech Informant (HFI)
**Tech Stack:** Python 3.9+, FastAPI, Next.js 16, React 19, TypeScript, Playwright, OpenAI GPT-4o, SQLite, Telegram Bot API, Docker, RSS Feed Parsing
**Purpose:** Scrape English FinTech content from X (Twitter) + news sources, rank by relevance, translate/generate Hebrew content, manage content in a Next.js studio, and deliver briefs/alerts through Telegram

---

## Architecture

```
┌──────────────────────┐        ┌────────────────────────┐
│ Next.js Frontend     │        │ Telegram Bot           │
│ (frontend/)          │        │ (src/telegram_bot/)    │
└──────────┬───────────┘        └───────────┬────────────┘
           │ REST (JWT)                      │ REST (JWT)
           └──────────────────┬──────────────┘
                              ▼
                  ┌────────────────────────┐
                  │ FastAPI API (src/api/) │
                  └──────────┬─────────────┘
                             ▼
                       ┌──────────┐
                       │ SQLite   │
                       └────┬─────┘
                            ▼
                  ┌────────────────────────┐
                  │ Scraper + Processor    │
                  └────────────────────────┘
```

**Docker services:** `redis`, `api`, `frontend`, `processor`, `scraper`, `telegram-bot`

### Directory Structure

```
HFI/
├── src/
│   ├── common/           # Shared models (SQLAlchemy), stopwords
│   ├── scraper/          # X scraper (Playwright) + News scraper (RSS)
│   ├── processor/        # Translation, content generation, style management
│   ├── api/              # FastAPI routes, schemas, dependencies
│   └── telegram_bot/     # Bot commands + scheduler
├── frontend/             # Next.js Content Studio (the active UI)
├── config/               # glossary.json, style.txt
├── data/                 # Gitignored: hfi.db, media/, session/
├── docs/                 # Plans, specs, runbooks
├── tests/                # ALL pytest test files
├── tools/                # Utility scripts (init_db.py, verify_setup.py)
├── docker-compose.yml
├── start_services.py     # CLI entrypoint (scraper, docker, setup)
└── pyproject.toml
```

### Frontend Pages (Next.js)

| Route | Purpose |
|-------|---------|
| `/login` | JWT auth (single password) |
| `/` | Dashboard — stats, today's brief, alerts, schedule timeline |
| `/acquire` | Scrape X threads → auto-translate → edit in studio |
| `/create` | Paste source → pick angle → generate Hebrew variants → save |
| `/queue` | Drafts / Scheduled / Published tabs with search |
| `/library` | Full content archive with filters |
| `/inspiration` | Track X accounts, search by engagement |
| `/settings` | Glossary, style examples, Telegram config, preferences |

### Database Tables

`tweets`, `threads`, `trends`, `style_examples`, `inspiration_accounts`, `inspiration_posts`, `notifications`, `user_preferences`, `tweet_engagements`

**Key enums:** `TweetStatus` (PENDING → PROCESSED → APPROVED → PUBLISHED | FAILED), `TrendSource` (X_TWITTER, YAHOO_FINANCE, CNBC, TECHCRUNCH, BLOOMBERG, MARKETWATCH, SEEKING_ALPHA, INVESTING_COM, GOOGLE_NEWS_ISRAEL, MANUAL, etc.)

---

## Project Structure Rules

**NEVER drop files at the repository root.** The root is reserved for config/meta files only.

| File type | Location |
|-----------|----------|
| Test files (`test_*.py`) | `tests/` |
| Utility scripts | `tools/` |
| Service logic | `src/<service>/` |
| Plans, specs, docs | `docs/` |
| Config JSONs | `config/` |
| DB, media, sessions | `data/` (gitignored) |

**Rules:**
1. No new `.py` files at root — use `src/`, `tests/`, or `tools/`
2. No new `.md` files at root — use `docs/` (exceptions: README.md, CLAUDE.md, AGENTS.md)
3. No PDFs at root — use `docs/`

---

## Code Conventions

- **Async/await** for all Playwright (scraper) operations
- **Minimal comments** — only for complex sections
- **Error handling:** Scraper retries + logs warnings. Processor sets `status='failed'` + stores `error_message`. Frontend shows toast errors via Sonner.
- **Logging:** Use `logging.getLogger(__name__)` with emoji indicators (✅ ⚠️ ❌)
- **Database access:**
  ```python
  from common.models import SessionLocal, Tweet
  db = SessionLocal()
  try:
      tweets = db.query(Tweet).filter_by(status='pending').all()
      db.commit()
  finally:
      db.close()
  ```

---

## Environment Variables

Required in `.env` (see `.env.example` for full list):

```bash
X_USERNAME=...                # X/Twitter credentials
X_PASSWORD=...
OPENAI_API_KEY=sk-proj-...    # OpenAI
DATABASE_URL=sqlite:///data/hfi.db
DASHBOARD_PASSWORD=...        # JWT auth for frontend
JWT_SECRET=...                # 32+ chars
CORS_ORIGINS=...              # Comma-separated (production)
# Optional: TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, REDIS_URL
```

---

## Testing

```bash
pytest tests/ -v              # All tests
pytest tests/test_api_content.py -v   # Specific file
pytest --cov=src tests/       # With coverage
```

For frontend changes, also test in the browser:
```bash
cd frontend && npm run dev    # Start Next.js dev server
# Navigate to http://localhost:3000
```

---

## Key Files Reference

| Area | Files |
|------|-------|
| X Scraper | `src/scraper/scraper.py` (Playwright login, trending, threads) |
| News Scraper | `src/scraper/news_scraper.py` (RSS feeds, ranking, clustering) |
| Translation | `src/processor/processor.py` (TranslationService, ContentProcessor) |
| Content Gen | `src/processor/content_generator.py` (Hebrew post/thread generation) |
| Prompts | `src/processor/prompt_builder.py` (shared prompt utilities) |
| Style | `src/processor/style_manager.py` (DB-backed style examples) |
| API | `src/api/main.py` + `src/api/routes/*.py` |
| Models | `src/common/models.py` (all SQLAlchemy models + enums) |
| Frontend | `frontend/src/app/(app)/` (Next.js App Router pages) |

---

## Deployment

**Local:** `docker-compose up -d`
**Production:** Azure VM + Caddy auto-HTTPS — see `docs/deploy/azure-private-production-runbook.md`
**CI/CD:** Push to `main` → GitHub Actions self-hosted runner auto-deploys

---

## Common Debugging

| Problem | Check |
|---------|-------|
| Scraper can't login | `data/session/storage_state.json` exists? `SCRAPER_HEADLESS` set? |
| No news trends | RSS feeds accessible? `feedparser` installed? Check logs for bozo_exception |
| Bad translations | `config/glossary.json` terms? `config/style.txt` examples? API key valid? |
| DB locked | Only one processor instance allowed |
| Frontend errors | `cd frontend && npm run dev`, check browser console, verify API is running |
| DB reset | `rm data/hfi.db && python tools/init_db.py` |

---

**Last Updated:** 2026-03-14 | **Version:** 2.0
