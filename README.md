# Hebrew FinTech Informant (HFI)

An automated content creation pipeline for Hebrew FinTech content on X (Twitter). This system scrapes trending topics, translates content to Hebrew with style matching, and provides a human-in-the-loop dashboard for content approval.

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
```

## Features

- **Scraper**: Playwright-based X scraper with anti-detection, session persistence
- **Processor**: GPT-4o translation to Hebrew with style matching + media downloads
- **Dashboard**: Streamlit UI for content review, editing, and approval
- **Docker**: Full containerization with Docker Compose and K8s/K3s support

## Quick Start

### 1. Setup Environment

```bash
# Clone and navigate to project
cd /path/to/HFI

# Copy environment template
cp .env.example .env

# Edit with your credentials (X account, OpenAI API key)
nano .env
```

### 2. Install Dependencies

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

### 3. Initialize Database

```bash
python init_db.py
```

### 4. Run Services

**Scraper (first run - manual login):**
```bash
cd src/scraper
export SCRAPER_HEADLESS=false
python main.py
# Log in to X manually, then press Enter
```

**Scraper (subsequent runs):**
```bash
export SCRAPER_HEADLESS=true
python main.py
```

**Dashboard:**
```bash
cd src/dashboard
streamlit run app.py
# Access at http://localhost:8501
```

**Processor:**
```bash
cd src/processor
python main.py  # Runs continuously, polling for pending tweets
```

## Docker Deployment

### Using Docker Compose

```bash
# Build and start all services
docker-compose up -d

# Run scraper manually
docker-compose exec scraper python main.py

# Access dashboard at http://localhost:8501
```

### Using Kubernetes (K3s)

See `k8s/README.md` for detailed K3s deployment instructions.

## Project Structure

```
HFI/
├── src/
│   ├── common/          # Shared database models
│   │   └── models.py    # SQLAlchemy models (Tweet, Trend)
│   ├── scraper/         # X (Twitter) scraper
│   │   ├── scraper.py   # TwitterScraper class
│   │   └── main.py      # Entry point
│   ├── processor/       # Translation + media processing
│   │   ├── processor.py # ContentProcessor, TranslationService
│   │   └── main.py      # Polling loop
│   └── dashboard/       # Streamlit web UI
│       └── app.py       # Dashboard application
├── config/
│   ├── glossary.json    # Financial term translations (EN→HE)
│   └── style.txt        # Hebrew tweet style examples
├── data/                # Persistent data (gitignored)
│   ├── hfi.db          # SQLite database
│   ├── media/          # Downloaded media files
│   └── session/        # Browser session state
├── k8s/                 # Kubernetes manifests
├── tests/               # Unit tests
├── docker-compose.yml   # Local development
└── .env.example         # Environment template
```

## Configuration

### Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `X_USERNAME` | X/Twitter email | Yes (for scraper) |
| `X_PASSWORD` | X/Twitter password | Yes (for scraper) |
| `OPENAI_API_KEY` | OpenAI API key | Yes (for processor) |
| `DATABASE_URL` | SQLite path | No (defaults to `data/hfi.db`) |
| `SCRAPER_HEADLESS` | Run browser headless | No (default: `true`) |
| `SCRAPER_MAX_TRENDS` | Trends to scrape | No (default: `5`) |

### Customization

- **`config/glossary.json`**: Add financial term translations
- **`config/style.txt`**: Add example tweets for style matching

## Workflow

1. **Scrape** → Scraper fetches trending topics and tweets (status: `pending`)
2. **Process** → Processor translates to Hebrew and downloads media (status: `processed`)
3. **Review** → Human reviews in Dashboard, edits if needed (status: `approved`)
4. **Publish** → (Future) Auto-post to X (status: `published`)

## Testing

```bash
# Run all tests
pytest tests/ -v

# Run specific tests
pytest tests/test_models.py -v
```

## Troubleshooting

| Issue | Solution |
|-------|----------|
| Session expired | Delete `data/session/storage_state.json`, run scraper with `SCRAPER_HEADLESS=false` |
| Database locked | Ensure only one processor instance is running |
| No tweets found | Run scraper first, check database with `sqlite3 data/hfi.db "SELECT * FROM tweets;"` |

## Security Notes

- Never commit `.env` to version control
- Use a secondary/burner X account for scraping
- Keep `data/session/storage_state.json` secure (contains auth tokens)
- Rotate API keys regularly

## License

MIT License

## Roadmap

- [x] Scraper service
- [x] Processor service  
- [x] Dashboard UI
- [x] Docker containerization
- [x] Kubernetes manifests
- [ ] Publisher service (auto-posting)
- [ ] Multi-source scraping (Reuters, TechCrunch)
- [ ] Analytics dashboard
