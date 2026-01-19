# HFI - Hebrew FinTech Informant

> 🤖 AI-powered automated content creation pipeline for Hebrew FinTech content on X (Twitter)

## Project Status

🚀 **Current Version:** 0.9.0 (Beta - Integration Phase)  
📊 **Test Coverage:** 100% (49/49 tests passing)  
🏗️ **Deployment Ready:** Docker + K8s manifests complete

### Component Status

| Component | Status | Grade | Notes |
|-----------|--------|-------|-------|
| **Scraper** | ✅ Production Ready | A- (91/100) | Playwright-based X scraper with session persistence |
| **Processor** | ✅ Production Ready | A (95/100) | OpenAI GPT-4o translation + media downloads |
| **Dashboard** | ✅ Production Ready | B+ (85/100) | Streamlit human-in-loop review interface |
| **Models** | ✅ Production Ready | A- | SQLAlchemy models with full status tracking |

---

## What is HFI?

HFI automates the discovery, translation, and curation of FinTech content from English to Hebrew. It combines:

1. **Smart Scraping** - Monitors X (Twitter) trending topics and tweets
2. **AI Translation** - GPT-4o translates with style matching and financial terminology
3. **Human Review** - Dashboard for content approval and editing
4. **Automated Publishing** - (Planned) Schedule posts to X

---

## Architecture

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

Data Flow: Scrape → Translate → Review → Approve → Publish
```

---

## Quick Start

### Prerequisites

- Python 3.9+
- OpenAI API key
- X (Twitter) account (burner recommended)
- Docker (optional, for containerized deployment)

### 1. Clone and Setup

```bash
git clone <repository_url>
cd HFI

# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Copy environment template
cp .env.example .env
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

### 3. Install Dependencies

```bash
# Core dependencies
pip install -r requirements.txt

# Scraper dependencies  
pip install -r src/scraper/requirements.txt
playwright install chromium

# Dashboard dependencies
pip install -r src/dashboard/requirements.txt

# Processor dependencies
pip install -r src/processor/requirements.txt
```

### 4. Initialize Database

```bash
python init_db.py
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

**Terminal 1 - Scraper (manual/on-demand):**
```bash
cd src/scraper
export SCRAPER_HEADLESS=true
python main.py
```

**Terminal 2 - Processor (continuous):**
```bash
cd src/processor
python main.py
```

**Terminal 3 - Dashboard:**
```bash
cd src/dashboard
streamlit run app.py
# Access at http://localhost:8501
```

---

## Docker Deployment

### Local Development with Docker Compose

```bash
# Build and start all services
docker-compose up -d

# View logs
docker-compose logs -f processor
docker-compose logs -f dashboard

# Run scraper manually when needed
docker-compose exec scraper python main.py

# Access dashboard
open http://localhost:8501

# Stop services
docker-compose down
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
│   ├── scraper/             # X (Twitter) scraper
│   │   ├── scraper.py       # TwitterScraper class (Playwright)
│   │   ├── main.py          # Entry point
│   │   ├── requirements.txt
│   │   └── Dockerfile
│   ├── processor/           # Translation + media processing
│   │   ├── processor.py     # ContentProcessor, TranslationService
│   │   ├── main.py          # Polling loop
│   │   ├── requirements.txt
│   │   └── Dockerfile
│   └── dashboard/           # Streamlit web UI
│       ├── app.py           # Dashboard application
│       ├── requirements.txt
│       └── Dockerfile
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
├── .env.example            # Environment template
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
| `SCRAPER_HEADLESS` | Run browser headless | No | `true` |
| `SCRAPER_MAX_TRENDS` | Max trends to scrape | No | `5` |
| `PROCESSOR_POLL_INTERVAL` | Seconds between polls | No | `30` |

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
1. SCRAPE
   ├─ Fetch trending topics (X Explore page)
   ├─ Search tweets related to trends
   ├─ Extract tweet text + media URLs
   └─ Save to database (status: pending)

2. PROCESS
   ├─ Poll for pending tweets
   ├─ Translate to Hebrew (GPT-4o + glossary + style)
   ├─ Download media (yt-dlp for videos, requests for images)
   └─ Update DB (status: processed, store hebrew_draft + media_path)

3. REVIEW
   ├─ Human opens dashboard (Streamlit)
   ├─ Reviews Hebrew translation
   ├─ Edits if needed
   └─ Approves (status: approved)

4. PUBLISH (Coming Soon)
   └─ Auto-post to X on schedule
```

---

## Features

### Scraper
- ✅ Playwright-based browser automation
- ✅ Session persistence (login once, reuse forever)
- ✅ Anti-detection (stealth mode, random delays, user-agent spoofing)
- ✅ Trending topic discovery
- ✅ Tweet thread scraping
- ✅ Video URL interception (.m3u8 HLS streams)

### Processor
- ✅ OpenAI GPT-4o translation
- ✅ Style matching (learns from examples)
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

**Test Results:** 49/49 tests passing (100%)

---

## Troubleshooting

| Issue | Solution |
|-------|----------|
| **Session expired** | Delete `data/session/storage_state.json`, run scraper with `SCRAPER_HEADLESS=false` |
| **Browser stuck on login** | Ensure `viewport=None` in scraper.py, disable active network interception |
| **Database locked** | Only one processor instance allowed. Check `ps aux \| grep processor` |
| **No tweets found** | Run scraper first: `cd src/scraper && python main.py` |
| **yt-dlp fails** | Install ffmpeg: `brew install ffmpeg` (Mac) or `apt install ffmpeg` (Linux) |
| **Dashboard blank** | Ensure database exists: `ls -la data/hfi.db`, run `python init_db.py` |

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
- [x] Scraper service with session persistence
- [x] Processor service with GPT-4o translation
- [x] Dashboard UI with approval workflow
- [x] Docker containerization
- [x] Kubernetes manifests
- [x] Comprehensive testing (100% pass rate)
- [x] Thread scraping functionality

### Planned 🚧
- [ ] Publisher service (auto-posting to X)
- [ ] Multi-source scraping (Reuters, TechCrunch, Bloomberg)
- [ ] Analytics dashboard (views, engagement tracking)
- [ ] Scheduled posting with optimal timing
- [ ] Content calendar view
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
