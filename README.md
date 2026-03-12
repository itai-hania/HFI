# HFI - Hebrew FinTech Informant

> 🤖 AI-powered automated content creation pipeline for Hebrew FinTech content on X (Twitter)

**Latest Updates (v2):**
- Next.js 14+ Content Studio frontend (`frontend/`) with RTL-first Hebrew UX
- Expanded FastAPI API (`src/api/`) with JWT auth, content CRUD, generation, inspiration, settings, notifications
- Telegram bot + APScheduler service (`src/telegram_bot/`) for briefs, alerts, and commands
- Alert detector + inspiration engagement search integrated into the existing scraper/processor engine
- Streamlit dashboard archived at `archive/dashboard-v1/` (source retained for reference)

## Project Status

🚀 **Current Version:** 1.0.0 (Production Ready)
📊 **Test Coverage:** 100% (468/468 tests passing)
🏗️ **Deployment Ready:** Docker + K8s manifests complete
🔒 **Security:** Auth, rate limiting, input validation, XSS hardening, CORS
⚡ **Performance:** Optimized queries, parallel RSS feeds, caching, N+1 fixes

### Component Status (v2)

| Component | Status | Grade | Notes |
|-----------|--------|-------|-------|
| **Scraper** | ✅ Production Ready | A- (91/100) | Playwright-based X scraper + parallel RSS feeds with timeout |
| **Processor** | ✅ Production Ready | A (95/100) | OpenAI GPT-4o translation + content generation + media downloads |
| **Frontend** | ✅ Production Ready | A- | Next.js content studio with RTL, queue, inspiration, settings |
| **Dashboard (v1)** | 📦 Archived | N/A | Streamlit dashboard moved to `archive/dashboard-v1/` |
| **Models** | ✅ Production Ready | A- | SQLAlchemy models with consolidated queries |
| **Security** | ✅ Hardened | A (95/100) | Auth, rate limiting, input validation, XSS, CORS |
| **API** | ✅ Production Ready | A- | FastAPI with auth, optimized endpoints, singleton services |

---

## What is HFI?

HFI automates discovery, translation, generation, and curation of FinTech content from English to Hebrew. It combines:

1. **Multi-Source Scraping** - Monitors X (Twitter) + RSS feeds (Yahoo Finance, WSJ, TechCrunch Fintech, Bloomberg)
2. **Smart Ranking** - Ranks articles by cross-source keyword overlap to surface trending topics
3. **AI Translation** - GPT-4o translates with style matching and financial terminology
4. **Human Review** - Web Content Studio (Next.js) for content approval, editing, and scheduling
5. **Automated Publishing** - (Planned) Schedule posts to X

---

## Architecture

```
┌──────────────────────────────┐        ┌──────────────────────────────┐
│ Next.js Content Studio       │        │ Telegram Bot + Scheduler     │
│ (frontend/)                  │        │ (src/telegram_bot/)          │
└───────────────┬──────────────┘        └───────────────┬──────────────┘
                │ REST (JWT)                             │ REST (JWT)
                └───────────────┬────────────────────────┘
                                ▼
                    ┌──────────────────────────────┐
                    │ FastAPI API (src/api/)       │
                    │ Auth, Content, Gen, Settings │
                    └───────────────┬──────────────┘
                                    │ SQLAlchemy
                                    ▼
                    ┌──────────────────────────────┐
                    │ SQLite (data/hfi.db)         │
                    └───────────────┬──────────────┘
                                    │
                    ┌───────────────┴──────────────┐
                    │ Existing Engine Services      │
                    │ scraper/, processor/          │
                    └──────────────────────────────┘
```

---

## Quick Start

### Prerequisites

- Python 3.9+
- OpenAI API key
- X (Twitter) account (burner recommended)
- Docker (optional, for containerized deployment)

**Platform Support:** ✅ macOS, ✅ Windows, ✅ Linux

### 1. Clone and Setup

```bash
git clone <repository_url>
cd HFI

# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Create .env file with your credentials
```

### 2. Configure Environment

Edit `.env` with your credentials:

```bash
# X (Twitter) Credentials
X_USERNAME=your_email@example.com
X_PASSWORD=your_password

# OpenAI API
OPENAI_API_KEY=sk-proj-...

# Database
DATABASE_URL=sqlite:///data/hfi.db
```

For worktree-safe local development, create shared env files once and symlink each worktree to them:

```bash
python3 tools/bootstrap_worktree_env.py
python3 tools/check_env.py
```

This keeps the canonical local files in `~/.config/hfi/root.env` and `~/.config/hfi/frontend.env.local`, then links `.env` and `frontend/.env.local` from each worktree.

### 3. Install Dependencies

```bash
# Core dependencies
pip install -r requirements.txt

# Scraper dependencies  
pip install -r src/scraper/requirements.txt
playwright install chromium

# API dependencies
pip install -r src/api/requirements.txt

# Processor dependencies
pip install -r src/processor/requirements.txt

# Telegram bot dependencies (optional)
pip install -r src/telegram_bot/requirements.txt
```

### 4. Initialize Database

```bash
python tools/init_db.py
```

### 5. First Run - Login to X

The scraper requires manual login on first run:

```bash
cd src/scraper
export SCRAPER_HEADLESS=false
python main.py

# A browser window will open
# 1. Log in to X manually
# 2. Complete any 2FA
# 3. Wait for home feed to load
# 4. Press ENTER in terminal

# Session will be saved for future runs
```

### 6. Run Services

Use this as the canonical local path for bot + studio development:

**Terminal 1 - API (required):**
```bash
cd src/api
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

**Terminal 2 - Frontend (required):**
```bash
cd frontend
npm install
npm run dev
# http://localhost:3000
```

**Terminal 3 - Telegram Bot (required for bot workflow):**
```bash
# One-time (recommended): install package so module imports work cleanly
pip install -e .

# Then run the bot
python -m telegram_bot.main
```

Run exactly one bot poller process for a token. Do not run local polling and Docker polling at the same time.

**Optional Terminal 4 - Processor:**
```bash
cd src/processor
python main.py
```

### Cross-Platform Launcher

For a simpler experience, use the cross-platform Python launcher:

```bash
# Works on Windows, macOS, and Linux
python start_services.py
```

This provides an interactive menu to start services without platform-specific commands.

### Telegram Setup

1. Create a bot with BotFather and copy `TELEGRAM_BOT_TOKEN`.
2. Get your chat ID and set `TELEGRAM_CHAT_ID`.
3. Ensure `DASHBOARD_PASSWORD`, `API_BASE_URL`, `JWT_SECRET`, and `FRONTEND_BASE_URL` are set.
4. Optional: set `BRIEF_TIMES=08:00,19:00` and `ALERT_CHECK_INTERVAL_MINUTES=15`.
5. Start API + frontend + bot with the steps above (one bot process only).
6. In Telegram, verify commands in this order:
   - `/start`
   - `/brief`
   - `/story 1`
   - `/write 1`

If `/write 1` reports no cached brief, run `/brief` again and retry `/write 1`.

### Using Content Studio

1. Login from `/login` (password -> JWT).
2. View brief + queue stats on Dashboard.
3. Generate variants in `/create`, edit Hebrew draft, copy/save/schedule.
4. Manage queue/library/inspiration/settings from dedicated pages.

---

## Docker Deployment

### Local Development with Docker Compose

Docker bot polling is secondary to local polling. Never run Docker and local bot pollers simultaneously with the same `TELEGRAM_BOT_TOKEN`.

```bash
# Build and start all services (frontend + api + processor + scraper + telegram bot)
docker-compose up -d

# View logs
docker-compose logs -f processor
docker-compose logs -f api
docker-compose logs -f frontend

# Run scraper manually when needed
docker-compose exec scraper python main.py

# Access app
open http://localhost:3000

# Stop services
docker-compose down
```

### Production - Azure VM (Private via Tailscale)

Production now has a dedicated private deployment path (single VM, Docker Compose, no public ingress):

- Canonical prod Compose: `deploy/docker-compose.prod.yml`
- Deployment scripts: `deploy/scripts/`
- CI/CD workflow: `.github/workflows/deploy-prod.yml`
- Full runbook: `docs/deploy/azure-private-production-runbook.md`

Typical VM deploy command:

```bash
ENV_FILE=/opt/hfi/app/.env.prod deploy/scripts/deploy.sh
```

Manual scraper run in production:

```bash
ENV_FILE=/opt/hfi/app/.env.prod deploy/scripts/run_scraper_manual.sh
```

### Production - Kubernetes (K3s)

Full K8s deployment available. See `k8s/README.md` for:
- Automated deployment scripts
- CronJob for scheduled scraping
- Persistent storage configuration
- Service exposure and ingress

Quick deploy:
```bash
cd k8s
./deploy.sh
```

---

## Project Structure

```
HFI/
├── src/
│   ├── common/              # Shared components
│   │   ├── models.py        # SQLAlchemy models (Tweet, Trend)
│   │   └── __init__.py
│   ├── scraper/             # X (Twitter) + News scraper
│   │   ├── scraper.py       # TwitterScraper class (Playwright)
│   │   ├── news_scraper.py  # NewsScraper class (RSS feeds + ranking)
│   │   ├── main.py          # Entry point
│   │   ├── requirements.txt
│   │   └── Dockerfile
│   ├── processor/           # Translation + media processing
│   │   ├── processor.py     # ContentProcessor, TranslationService
│   │   ├── style_manager.py # Style example management (DB-backed, cached)
│   │   ├── main.py          # Polling loop
│   │   ├── requirements.txt
│   │   └── Dockerfile
│   ├── api/                 # FastAPI REST API for frontend + bot
│   │   ├── routes/
│   │   ├── schemas/
│   │   └── main.py
│   ├── telegram_bot/        # Telegram commands + scheduler
│   │   ├── bot.py
│   │   ├── scheduler.py
│   │   └── main.py
│   └── dashboard/           # Legacy Streamlit v1 (deprecated)
│       ├── app.py
│       ├── requirements.txt
│       └── Dockerfile
├── frontend/                # Next.js Content Studio (v2)
│   ├── src/app/
│   ├── src/components/
│   └── Dockerfile
├── archive/
│   └── dashboard-v1/        # Frozen Streamlit reference snapshot
├── config/
│   ├── glossary.json        # Financial term translations (EN→HE)
│   └── style.txt            # Hebrew tweet style examples
├── data/                    # Persistent data (gitignored)
│   ├── hfi.db              # SQLite database
│   ├── media/              # Downloaded media files
│   └── session/            # Browser session state
├── k8s/                     # Kubernetes manifests
│   ├── deploy.sh           # Automated deployment
│   ├── README.md           # K8s deployment guide
│   └── *.yaml              # Manifests
├── tests/                   # Unit tests
├── docker-compose.yml       # Local development
├── .env                     # Environment configuration (not in git)
├── IMPLEMENTATION_PLAN.md  # Detailed implementation guide
└── README.md               # This file
```

---

## Configuration

### Environment Variables

| Variable | Description | Required | Default |
|----------|-------------|----------|---------|
| `X_USERNAME` | X/Twitter email | Yes | - |
| `X_PASSWORD` | X/Twitter password | Yes | - |
| `OPENAI_API_KEY` | OpenAI API key | Yes | - |
| `DATABASE_URL` | SQLite database path | No | `sqlite:///data/hfi.db` |
| `DASHBOARD_PASSWORD` | Password used by `/api/auth/login` | Yes | - |
| `JWT_SECRET` | JWT signing secret | Yes (prod) | dev fallback |
| `NEXT_PUBLIC_API_URL` | Frontend API base URL | No | `http://localhost:8000` |
| `TELEGRAM_BOT_TOKEN` | Telegram bot token | No | - |
| `TELEGRAM_CHAT_ID` | Telegram chat id | No | - |
| `FRONTEND_BASE_URL` | Frontend URL used by Telegram draft links | No | `http://localhost:3000` |
| `BRIEF_TIMES` | Comma-separated brief times in HH:MM UTC | No | `08:00,19:00` |
| `ALERT_CHECK_INTERVAL_MINUTES` | Alert polling interval in minutes | No | `15` |
| `SCRAPER_HEADLESS` | Run browser headless | No | `true` |
| `SCRAPER_MAX_TRENDS` | Max trends to scrape | No | `5` |
| `PROCESSOR_POLL_INTERVAL` | Seconds between polls | No | `30` |

### Worktree-Safe Env Setup

Use `python3 tools/bootstrap_worktree_env.py` once per machine to create and maintain shared env files outside the repo:

- `~/.config/hfi/root.env` for the Python services and bot
- `~/.config/hfi/frontend.env.local` for the Next.js frontend

Then run `python3 tools/check_env.py` in any worktree to catch missing keys or API URL drift between `.env` and `frontend/.env.local`.

### Customization Files

**`config/glossary.json`** - Financial term translations:
```json
{
  "Short Squeeze": "סקוויז שורט",
  "Bear Market": "שוק דובי",
  "IPO": "הנפקה ראשונית",
  "Fintech": "פינטק"
}
```

**`config/style.txt`** - Example Hebrew tweets for style matching:
```
🚨 עדכון טק: OpenAI מכריזה על GPT-5
הדבר הבא בתעשייה כבר כאן, וזה משנה הכל.

[Add 5-10 of your best Hebrew tweets here]
```

---

## Workflow

```
1. DISCOVER
   ├─ X Scraper: Fetch trending topics (X Explore page)
   ├─ News Scraper: Fetch from RSS feeds (Yahoo Finance, WSJ, TechCrunch, Bloomberg)
   ├─ Rank articles by cross-source keyword overlap (top 10)
   └─ Save trends to database

2. SCRAPE
   ├─ Search X tweets related to discovered trends
   ├─ Extract tweet text + media URLs
   └─ Save to database (status: pending)

3. PROCESS
   ├─ Poll for pending tweets
   ├─ Translate to Hebrew (GPT-4o + glossary + style)
   ├─ Download media (yt-dlp for videos, requests for images)
   └─ Update DB (status: processed, store hebrew_draft + media_path)

4. REVIEW
   ├─ Human opens Content Studio (Next.js)
   ├─ Reviews Hebrew translation
   ├─ Edits if needed
   └─ Approves (status: approved)

5. PUBLISH (Coming Soon)
   └─ Auto-post to X on schedule
```

---

## Features

### X Scraper
- ✅ Playwright-based browser automation
- ✅ Session persistence (login once, reuse forever)
- ✅ Anti-detection (stealth mode, random delays, user-agent spoofing)
- ✅ Trending topic discovery
- ✅ Tweet thread scraping
- ✅ Video URL interception (.m3u8 HLS streams)

### News Scraper
- ✅ Multi-source RSS feed aggregation (Yahoo Finance, WSJ, TechCrunch Fintech, Bloomberg, MarketWatch)
- ✅ Parallel feed fetching with ThreadPoolExecutor and timeout protection
- ✅ Cross-source keyword overlap ranking with Wall Street focus
- ✅ Weighted sampling (70% finance / 30% tech)
- ✅ Automatic deduplication with Jaccard similarity
- ✅ Optimized keyword extraction (pre-computed, compiled regex)

### Processor
- ✅ OpenAI GPT-4o translation
- ✅ Style matching (learns from DB-backed examples with topic tags)
- ✅ Financial term glossary
- ✅ Media download (images + videos via yt-dlp)
- ✅ Error handling with retry logic
- ✅ Failed tweet tracking

### Dashboard
- ✅ Real-time tweet review
- ✅ Side-by-side EN/HE comparison
- ✅ Inline editing
- ✅ Media preview (images/videos)
- ✅ Status filtering (pending/processed/approved)
- ✅ Approval workflow
- ✅ Ranked article display (numbered list with source badges)
- ✅ One-click trend discovery from multiple sources
- ✅ Thread scraping UI

---

## Testing

```bash
# Run all tests
pytest tests/ -v

# Run specific component
pytest tests/test_scraper.py -v
pytest tests/test_processor.py -v
pytest tests/test_models.py -v

# With coverage
pytest --cov=src tests/
```

**Test Results:** 468/468 tests passing (100%)

---

## Troubleshooting

| Issue | Solution |
|-------|----------|
| **Session expired** | Delete `data/session/storage_state.json`, run scraper with `SCRAPER_HEADLESS=false` |
| **Browser stuck on login** | Ensure `viewport=None` in scraper.py, disable active network interception |
| **Database locked** | Only one processor instance allowed. Check `ps aux \| grep processor` |
| **No tweets found** | Run scraper first: `cd src/scraper && python main.py` |
| **yt-dlp fails** | Install ffmpeg: `brew install ffmpeg` (Mac) or `apt install ffmpeg` (Linux) |
| **Dashboard blank** | Ensure database exists: `ls -la data/hfi.db`, run `python tools/init_db.py` |
| **News scraper fails** | Check RSS feed connectivity: `curl -I https://finance.yahoo.com/news/rssindex` |
| **total_limit error** | Restart Streamlit to clear module cache: `pkill -f streamlit && streamlit run app.py` (Mac/Linux) or use Task Manager (Windows) |

### Windows-Specific Issues

| Issue | Solution |
|-------|----------|
| **yt-dlp not found** | Install via pip: `pip install yt-dlp` or add to PATH |
| **Streamlit won't restart** | Use Task Manager to end Python processes, or `taskkill /F /IM python.exe` |
| **Path errors** | Ensure paths use forward slashes or raw strings (`r"C:\path"`) |
| **PowerShell script issues** | Use `python start_services.py` instead of bash scripts |

---

## Security Notes

⚠️ **Important Security Practices:**

- Never commit `.env` to version control
- Use a secondary/burner X account for scraping
- Keep `data/session/storage_state.json` private (contains auth tokens)
- Rotate OpenAI API keys regularly
- Limit scraper frequency to avoid rate limits (30-60 min intervals)

---

## Roadmap

### Completed ✅
- [x] X scraper service with session persistence
- [x] News scraper with multi-source parallel RSS feeds (Yahoo Finance, WSJ, TechCrunch, Bloomberg, MarketWatch)
- [x] Cross-source ranking algorithm with Wall Street focus and weighted sampling
- [x] Processor service with GPT-4o translation + content generation engine
- [x] Dashboard UI with approval workflow (modular architecture, optimized queries)
- [x] Thread scraping functionality
- [x] Docker containerization
- [x] Kubernetes manifests
- [x] Comprehensive testing (100% pass rate - 468 tests)
- [x] Style learning system (DB-backed examples with topic tags and engagement scoring)
- [x] Security hardening (auth, rate limiting, input validation, XSS, CORS)
- [x] Performance optimization (query consolidation, parallel feeds, caching, N+1 fixes)
- [x] Autopilot pipeline (two-phase trend-to-post workflow)
- [x] Content generation engine (multi-angle Hebrew post/thread creation)

### Planned 🚧
- [ ] Publisher service (auto-posting to X)
- [ ] Analytics dashboard (views, engagement tracking)
- [ ] Scheduled posting with optimal timing
- [ ] Content calendar view
- [ ] Additional news sources (Financial Times, CoinDesk, etc.)
- [ ] Multi-language support (beyond Hebrew)

---

## Contributing

Contributions welcome! Please:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

---

## License

MIT License - see LICENSE file for details

---

## Support

For issues, questions, or feature requests:
- Create an issue on GitHub
- Check `IMPLEMENTATION_PLAN.md` for detailed technical documentation
- Review `k8s/README.md` for deployment help

---

**Built with ❤️ for the Hebrew FinTech community**
