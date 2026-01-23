# HFI - First Time User Guidelines

## 🚀 Get Started in 5 Minutes

### Step 1: Setup (One-Time)
```bash
# 1. Install dependencies
cd src/dashboard
pip install -r requirements.txt
playwright install chromium

# 2. Configure credentials
cp .env.example .env
# Edit .env with your X_USERNAME, X_PASSWORD, and OPENAI_API_KEY

# 3. Initialize database
python init_db.py
```

### Step 2: Start the Dashboard
```bash
cd src/dashboard
streamlit run app.py
```
Open browser to: **http://localhost:8501**

---

## 🎯 What You Can Do

### 3 Scraping Modes (in Sidebar)

| Mode | What It Does | When to Use |
|------|-------------|-------------|
| **Scrape X Trends** | Gets trending topics from X/Twitter | Discover what's hot in FinTech |
| **Scrape X Thread** | Scrapes specific tweet/thread | Found good content, want to save it |
| **Scrape News** | Gets articles from Reuters, WSJ, etc. | Monitor financial news sources |

---

## 📋 Basic Workflow

```
1. SCRAPE CONTENT
   └─ Use "New Task" in sidebar
   └─ Choose mode, enter URL if needed
   └─ Click "Start Scraping"

2. TRANSLATE (Automatic)
   └─ Run processor in background:
      cd src/processor && python main.py
   └─ Or wait and translate later

3. REVIEW & EDIT
   └─ Check Hebrew translation
   └─ Edit if needed
   └─ Click "Save Edits"

4. APPROVE
   └─ Click "✅ Approve" button
   └─ Tweet is now ready to publish

5. PUBLISH (Manual for now)
   └─ Copy approved Hebrew text
   └─ Post to X manually
   └─ Mark as published in dashboard
```

---

## 🎨 Dashboard Overview

```
┌──────────────┬─────────────────────────────┐
│  SIDEBAR     │  MAIN AREA                  │
│              │                             │
│  📊 Stats    │  Tweet Cards:               │
│  🔍 Filter   │  ┌─────────────────────┐   │
│  🔄 Refresh  │  │ English | Hebrew    │   │
│  ⚡ Bulk     │  │ ─────────────────── │   │
│  🚀 New Task │  │ [💾][✅][⏮️][🔄][🗑️]│   │
│              │  └─────────────────────┘   │
└──────────────┴─────────────────────────────┘
```

---

## 🟢 Status Colors

- **🟠 Pending** - Just scraped, needs translation
- **🟢 Processed** - Translated, review it
- **🟣 Approved** - Ready to publish
- **🔵 Published** - Already posted

---

## ⚡ Quick Actions

**On Each Tweet Card:**
- **💾 Save Edits** - Save your manual changes
- **✅ Approve** - Mark ready for publishing
- **⏮️ Reset to Pending** - Send back for reprocessing
- **🔄 Reprocess** - Translate again from scratch
- **🗑️ Delete** - Remove completely

**Bulk Actions (Sidebar):**
- **Approve All Processed** - Approve all translated tweets at once
- **Delete All Pending** - Clear all unprocessed tweets

---

## 🔧 Common Tasks

### Task: Get Today's Trends
1. Select "Scrape X Trends"
2. Click "▶ Start Scraping"
3. Wait 10-30 seconds
4. View results in main area

### Task: Save a Specific Tweet
1. Copy tweet URL from X (e.g., `https://x.com/user/status/123...`)
2. Select "Scrape X Thread"
3. Paste URL
4. Check "Translate & Rewrite" box
5. Click "▶ Start Scraping"
6. Wait for translation (if processor is running)

### Task: Monitor Financial News
1. Select "Scrape News Sources"
2. Click "▶ Start Scraping"
3. Articles saved as Trends
4. Browse in dashboard or search X for related tweets

---

## ⚙️ Background Services

For full automation, run these in separate terminals:

**Processor** (translates pending tweets):
```bash
cd src/processor
python main.py
# Leave running, checks every 30s
```

**Scraper** (optional, for scheduled scraping):
```bash
cd src/scraper
python main.py
# Run manually or as cron job
```

---

## 🚨 First-Time Login to X

If scraping X for the first time:
```bash
# Set headless to false
export SCRAPER_HEADLESS=false

# Run scraper
cd src/scraper
python main.py

# Browser will open - log in manually
# Session saved to: data/session/storage_state.json
# Next time it will be automatic
```

---

## 💡 Pro Tips

1. **Enable Auto-refresh** in sidebar to see updates in real-time
2. **Filter by status** to focus on tweets that need action
3. **Edit Hebrew inline** - click in the text area to modify
4. **Use bulk approve** after reviewing multiple tweets
5. **Check media previews** before approving

---

## 🐛 Something Wrong?

**No tweets appearing?**
- Check filter isn't hiding them (set to "All")
- Run scraper to fetch content
- Check database exists: `data/hfi.db`

**Translation not working?**
- Start processor service: `cd src/processor && python main.py`
- Check OPENAI_API_KEY in `.env`
- Look for errors in processor logs

**X scraper fails?**
- Session expired - delete `data/session/storage_state.json`
- Run with `SCRAPER_HEADLESS=false` to login manually
- Check X credentials in `.env`

---

## 📚 More Help

- **Detailed Guide:** `QUICK_START_GUIDE.md`
- **Dashboard Layout:** `DASHBOARD_OVERVIEW.md`
- **Technical Docs:** `CLAUDE.md`
- **Project Overview:** `README.md`

---

## 🎯 Your First Session Checklist

- [ ] Installed dependencies
- [ ] Configured `.env` file
- [ ] Initialized database
- [ ] Started dashboard
- [ ] Tested one scraping mode
- [ ] Started processor service (optional)
- [ ] Reviewed a tweet card
- [ ] Approved first tweet

**You're ready to go! 🎉**

---

**Need Support?** Check documentation or review error messages in dashboard status containers.
