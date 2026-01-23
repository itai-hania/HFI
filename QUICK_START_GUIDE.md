# HFI Dashboard - Quick Start Guide

## Overview
The HFI Dashboard is a unified web interface for scraping FinTech content from X/Twitter and news sources, translating to Hebrew, and managing content workflow.

---

## Prerequisites

1. **Install Dependencies:**
   ```bash
   # Install dashboard requirements
   cd src/dashboard
   pip install -r requirements.txt

   # Install Playwright browsers (required for X scraping)
   playwright install chromium
   ```

2. **Configure Environment:**
   ```bash
   # Copy example env file
   cp .env.example .env

   # Edit .env with your credentials:
   # - X_USERNAME (your X/Twitter email)
   # - X_PASSWORD (your X/Twitter password)
   # - OPENAI_API_KEY (for Hebrew translation)
   ```

3. **Initialize Database:**
   ```bash
   python init_db.py
   ```

---

## Starting the Dashboard

```bash
cd src/dashboard
streamlit run app.py
```

The dashboard will open at: **http://localhost:8501**

---

## How to Use

### Main Interface

The dashboard has two main sections:

**Left Sidebar:**
- 📊 Statistics (total tweets, status breakdown)
- 🔍 Filters (view by status: all, pending, processed, approved, published)
- 🔄 Refresh controls
- ⚡ Bulk actions
- 🚀 New Task panel

**Main Area:**
- Tweet cards showing original English and Hebrew translation
- Action buttons for each tweet

---

### 3 Scraping Modes (New Task Panel)

#### Mode 1: Scrape X Trends
**What it does:** Discovers trending topics on X/Twitter

**Steps:**
1. Select "Scrape X Trends" in sidebar
2. Click "▶ Start Scraping"
3. Wait for completion (saves 5 trending topics to database)

**Use case:** Discover what's trending in FinTech/Tech

---

#### Mode 2: Scrape X Thread
**What it does:** Scrapes a specific tweet or thread from X/Twitter

**Steps:**
1. Select "Scrape X Thread" in sidebar
2. Enter thread URL (e.g., `https://x.com/user/status/1234567890`)
3. Check "Translate & Rewrite" if you want automatic Hebrew translation
4. Click "▶ Start Scraping"
5. Wait for completion (saves all tweets from thread)

**Use case:** Target specific high-quality content

---

#### Mode 3: Scrape News Sources
**What it does:** Fetches latest articles from Reuters, WSJ, TechCrunch, Bloomberg

**Steps:**
1. Select "Scrape News Sources" in sidebar
2. Click "▶ Start Scraping"
3. Wait for completion (saves articles as trends in database)

**Use case:** Monitor news from major financial sources

---

### Content Review Workflow

Once content is scraped, follow this workflow:

#### Status Flow:
```
pending → processed → approved → published
```

**1. Pending Tweets** (just scraped)
- Status: `pending`
- No Hebrew translation yet
- **Action needed:** Run processor service to translate

**2. Processed Tweets** (translated)
- Status: `processed`
- Hebrew translation complete
- **Action needed:** Human review and approval

**3. Approved Tweets** (ready to publish)
- Status: `approved`
- Translation reviewed and approved
- **Action needed:** Manual publish or wait for auto-publisher

**4. Published Tweets** (live on X)
- Status: `published`
- Already posted to X
- **Action needed:** None (archived)

---

### Tweet Card Actions

Each tweet card has 5 action buttons:

1. **💾 Save Edits** - Save manual changes to Hebrew translation
2. **✅ Approve** - Mark as ready for publishing (saves edits automatically)
3. **⏮️ Reset to Pending** - Send back to pending status
4. **🔄 Reprocess** - Clear translation and reprocess
5. **🗑️ Delete** - Remove from database

---

### Bulk Actions

**Approve All Processed:**
- Approves all tweets with status `processed`
- Only works for tweets with Hebrew translation

**Delete All Pending:**
- Removes all tweets with status `pending`
- Use to clear unwanted scraped content

---

## Background Services

For full automation, run these services alongside the dashboard:

### Processor Service (Translation)
```bash
cd src/processor
python main.py
```
- Polls database every 30 seconds
- Translates pending tweets to Hebrew
- Downloads media files
- Updates status to `processed`

### Scraper Service (Scheduled)
```bash
cd src/scraper
python main.py
```
- Runs trending topic scraper
- Saves tweets with status `pending`
- Usually run as a cron job (every 1-4 hours)

---

## Common Workflows

### Workflow 1: Monitor Trends
1. Run scraper: Mode 1 (X Trends)
2. Start processor service (background)
3. Wait for translations (auto-refresh dashboard)
4. Review and approve translated content
5. Publish manually or wait for auto-publisher

### Workflow 2: Curate Specific Content
1. Find interesting thread on X
2. Copy URL
3. Dashboard: Mode 2 (X Thread) with URL
4. Check "Translate & Rewrite"
5. Review translation when processed
6. Edit if needed, then approve

### Workflow 3: News Monitoring
1. Dashboard: Mode 3 (News Sources)
2. Browse saved articles in Trends table
3. Manually search for related tweets on X
4. Use Mode 2 to scrape specific tweets about the news

---

## Tips

- **Auto-refresh:** Enable for real-time updates (30s interval)
- **Edit Hebrew:** Click in the Hebrew text area to make manual corrections
- **Filter by status:** Use sidebar filter to focus on specific workflow stage
- **Media preview:** Images and videos display inline in tweet cards
- **First login:** If scraping X for first time, set `SCRAPER_HEADLESS=false` to manually log in

---

## Troubleshooting

**Problem: No tweets appearing**
- Check if scraper ran successfully
- Verify database file exists: `data/hfi.db`
- Check status filter isn't hiding tweets

**Problem: Translations not happening**
- Make sure processor service is running
- Check OpenAI API key is valid
- Look for error messages in tweet cards

**Problem: X scraper fails**
- Browser session may have expired
- Delete `data/session/storage_state.json`
- Run scraper with `SCRAPER_HEADLESS=false` for manual login
- Check X credentials in `.env`

**Problem: News scraper returns 0 articles**
- RSS feeds may be temporarily down (especially Reuters)
- Check internet connection
- Try again in a few minutes

---

## Files & Locations

- **Database:** `data/hfi.db`
- **Media files:** `data/media/`
- **Browser session:** `data/session/storage_state.json`
- **Configuration:** `config/glossary.json` and `config/style.txt`
- **Logs:** Service logs in respective directories

---

## Quick Reference

| Action | Command |
|--------|---------|
| Start dashboard | `cd src/dashboard && streamlit run app.py` |
| Run processor | `cd src/processor && python main.py` |
| Run scraper | `cd src/scraper && python main.py` |
| Run tests | `pytest tests/ -v` |
| Reset database | `rm data/hfi.db && python init_db.py` |

---

**Need help?** See `CLAUDE.md` for detailed technical documentation or `README.md` for project overview.
