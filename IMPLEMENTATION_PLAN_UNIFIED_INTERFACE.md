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
- [ ] Create `src/scraper/news_scraper.py`
- [ ] Implement RSS parsing using `feedparser` (add to requirements)
- [ ] Implement `get_latest_news()` method

### Step 2: Update Scraper Main
- [ ] Modify `src/scraper/main.py` or create a router to handle specific requests
- [ ] Ensure it can be imported and called from the Dashboard

### Step 3: Enhance Dashboard
- [ ] Add sidebar UI code to `src/dashboard/app.py`
- [ ] Connect buttons to scraper functions
- [ ] Add visual feedback (success/error messages)

### Step 4: Testing
- [ ] Verify Mode 1 (Trends) saves to DB
- [ ] Verify Mode 2 (Thread) saves to DB + Translation
- [ ] Verify Mode 3 (News) saves to DB

---

## 3. Dependencies
Add `feedparser` to `src/scraper/requirements.txt`.
