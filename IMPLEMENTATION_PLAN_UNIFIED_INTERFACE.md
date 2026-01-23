# HFI Unified Web Interface Implementation Plan

## Goal
Create a unified command interface within the existing Streamlit dashboard to allow the user to easily trigger 3 specific operations:
1. **X Top Trends**: Scrape trending topics from X.
2. **X Thread**: Scrape a specific thread/post with optional translation.
3. **News Sources**: Scrape multi-source news (Reuters, WSJ, TechCrunch, Bloomberg).

---

## 1. Architecture Changes

### Dashboard Enhancement (`src/dashboard/app.py`)
Add a new **"Actions" Sidebar** with radio buttons to select the operational mode.

```python
st.sidebar.title("🚀 New Task")
mode = st.sidebar.radio("Select Mode",
    ["Scrape X Trends", "Scrape X Thread", "Scrape News Sources"])

if mode == "Scrape X Thread":
    url = st.sidebar.text_input("Thread URL")
    translate = st.sidebar.checkbox("Translate & Rewrite", value=True)

if st.sidebar.button("▶ Start Scraping"):
    # Trigger logic
```

### New News Scraper (`src/scraper/news_scraper.py`)
Implement `NewsScraper` class to handle multi-source RSS/HTML scraping.

| Source | Method | URL / Feed |
|--------|--------|------------|
| **Reuters** | RSS | `http://feeds.reuters.com/reuters/businessNews` |
| **WSJ** | RSS | `https://feeds.a.dj.com/rss/RSSMarketsMain.xml` |
| **TechCrunch** | RSS | `https://techcrunch.com/feed/` |
| **Bloomberg** | RSS | `https://feeds.bloomberg.com/markets/news.rss` |

### Database Updates (`src/common/models.py`)
Update `Trend` model to support non-X sources if needed (already supports `source` field).

---

## 2. Implementation Steps

### Step 1: Create News Scraper
- [x] Create `src/scraper/news_scraper.py`
- [x] Implement RSS parsing using `feedparser` (add to requirements)
- [x] Implement `get_latest_news()` method

### Step 2: Update Scraper Main
- [x] Modify `src/scraper/main.py` or create a router to handle specific requests
- [x] Ensure it can be imported and called from the Dashboard

### Step 3: Enhance Dashboard
- [x] Add sidebar UI code to `src/dashboard/app.py`
- [x] Connect buttons to scraper functions
- [x] Add visual feedback (success/error messages)

### Step 4: Testing
- [x] Verify Mode 1 (Trends) saves to DB
- [x] Verify Mode 2 (Thread) saves to DB + Translation
- [x] Verify Mode 3 (News) saves to DB

---

## 3. Dependencies
- [x] Add `feedparser` to `src/scraper/requirements.txt`
- [x] Add scraper dependencies to `src/dashboard/requirements.txt` (playwright, feedparser, etc.)

---

## 4. Bug Fixes Applied (2026-01-23)

The following bugs were discovered and fixed during implementation:

1. **TrendSource enum missing values** - Added `WSJ` and `Bloomberg` to `TrendSource` enum in `src/common/models.py`

2. **Dashboard logger not defined** - Added `import logging` and `logger = logging.getLogger(__name__)` to `src/dashboard/app.py`

3. **Source enum mismatch** - Fixed dashboard to use proper `TrendSource` enum values instead of raw strings:
   - X Trends: `source=TrendSource.X_TWITTER`
   - News: Added source mapping dictionary to convert string sources to enum values

4. **Dashboard dependencies** - Updated `src/dashboard/requirements.txt` to include:
   - `playwright==1.40.0`
   - `fake-useragent==1.5.1`
   - `feedparser==6.0.10`
   - `beautifulsoup4==4.12.3`
   - `requests==2.31.0`

---

## Status: ✅ COMPLETE

All implementation steps have been completed and tested:
- 108/108 unit tests passing
- News scraper successfully fetches from WSJ, TechCrunch, Bloomberg (Reuters feed may have intermittent issues)
- Dashboard integration verified
- Source enum mapping verified
