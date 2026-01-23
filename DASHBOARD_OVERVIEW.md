# HFI Dashboard - Visual Overview

## Dashboard Layout

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  📊 Hebrew FinTech Informant (HFI) Dashboard                                │
│  Human-in-the-loop content approval and editing interface                   │
├───────────────┬─────────────────────────────────────────────────────────────┤
│               │                                                             │
│  SIDEBAR      │  MAIN CONTENT AREA                                          │
│               │                                                             │
│ 🎛️ Dashboard  │  ═══════════════════════════════════════════════════════   │
│    Controls   │                                                             │
│               │  Showing 12 tweet(s)                                        │
│ 📊 Statistics │                                                             │
│  Total: 24    │  ┌─────────────────────────────────────────────────────┐  │
│  Pending: 5   │  │ 🟢 FinTech Innovation - 2026-01-23 15:30           │  │
│  Processed:12 │  │                                                     │  │
│  Approved: 6  │  │  📝 Original (English)  │  🔄 Hebrew Translation  │  │
│  Published: 1 │  │  ─────────────────────  │  ───────────────────── │  │
│               │  │  Breaking: Major AI     │  חדשות חמות: מימון     │  │
│ 🔍 Filters    │  │  funding round for...   │  משמעותי לסטארטאפ...   │  │
│  Status: All ▼│  │                         │                         │  │
│               │  │  Source: x.com/...      │  🎬 Media               │  │
│ 🔄 Refresh    │  │  Status: processed      │  [Video Preview]        │  │
│  □ Auto (30s) │  │  Created: 2026-01-23    │                         │  │
│  [🔄 Now]     │  │                         │                         │  │
│               │  │  ─────────────────────────────────────────────    │  │
│ ⚡ Bulk       │  │  [💾 Save] [✅ Approve] [⏮️ Reset] [🔄] [🗑️]    │  │
│  [Approve ✅] │  └─────────────────────────────────────────────────────┘  │
│  [Delete 🗑️] │                                                             │
│               │  ┌─────────────────────────────────────────────────────┐  │
│ ─────────────│  │ 🟠 Crypto News - 2026-01-23 14:20                  │  │
│               │  │ ...                                                 │  │
│ 🚀 New Task   │  └─────────────────────────────────────────────────────┘  │
│               │                                                             │
│ ○ Scrape X    │  ┌─────────────────────────────────────────────────────┐  │
│   Trends      │  │ 🟣 Banking Tech - 2026-01-23 13:15                 │  │
│ ● Scrape X    │  │ ...                                                 │  │
│   Thread      │  └─────────────────────────────────────────────────────┘  │
│ ○ Scrape News │                                                             │
│               │  ... (more tweet cards)                                     │
│ Thread URL:   │                                                             │
│ [___________] │                                                             │
│               │                                                             │
│ ☑ Translate & │  ─────────────────────────────────────────────────────── │
│   Rewrite     │  HFI Dashboard v1.0 - Built with Streamlit                  │
│               │                                                             │
│ [▶ Start]     │                                                             │
│               │                                                             │
└───────────────┴─────────────────────────────────────────────────────────────┘
```

---

## Component Breakdown

### 1. Statistics Panel
```
┌──────────────────┐
│ 📊 Statistics    │
│ Total Tweets: 24 │
│                  │
│ Pending     5    │
│ Processed  12    │
│ Approved    6    │
│ Published   1    │
└──────────────────┘
```
Shows real-time counts of tweets in each status.

---

### 2. New Task Panel (3 Modes)

#### Mode 1: X Trends
```
┌────────────────────────┐
│ 🚀 New Task            │
│                        │
│ ● Scrape X Trends      │
│ ○ Scrape X Thread      │
│ ○ Scrape News Sources  │
│                        │
│ [▶ Start Scraping]     │
└────────────────────────┘
```
Discovers 5 trending topics on X/Twitter and saves them to database.

#### Mode 2: X Thread
```
┌────────────────────────┐
│ 🚀 New Task            │
│                        │
│ ○ Scrape X Trends      │
│ ● Scrape X Thread      │
│ ○ Scrape News Sources  │
│                        │
│ Thread URL:            │
│ [https://x.com/...]    │
│                        │
│ ☑ Translate & Rewrite  │
│                        │
│ [▶ Start Scraping]     │
└────────────────────────┘
```
Scrapes a specific tweet or full thread. Option to auto-translate.

#### Mode 3: News Sources
```
┌────────────────────────┐
│ 🚀 New Task            │
│                        │
│ ○ Scrape X Trends      │
│ ○ Scrape X Thread      │
│ ● Scrape News Sources  │
│                        │
│ [▶ Start Scraping]     │
└────────────────────────┘
```
Fetches latest articles from Reuters, WSJ, TechCrunch, Bloomberg RSS feeds.

---

### 3. Tweet Card Structure

```
┌─────────────────────────────────────────────────────────────────────┐
│ 🟢 Status Indicator + Topic - Date/Time                             │
│                                                                      │
│  ┌─────────────────────────────┬─────────────────────────────────┐ │
│  │ 📝 Original (English)       │ 🔄 Hebrew Translation           │ │
│  │ ─────────────────────────── │ ─────────────────────────────── │ │
│  │ Breaking news: Major funding│ חדשות חמות: מימון משמעותי     │ │
│  │ round announced for AI      │ לסטארטאפ בינה מלאכותית.       │ │
│  │ startup focused on fintech  │ הסטארטאפ מתמקד בפתרונות        │ │
│  │ solutions. This could...    │ פינטק חדשניים...               │ │
│  │                             │                                 │ │
│  │                             │ [Editable text area]            │ │
│  │ Source: x.com/user/123...   │                                 │ │
│  │ Status: processed           │                                 │ │
│  │ Created: 2026-01-23 15:30   │                                 │ │
│  │                             │                                 │ │
│  │                             │ 🎬 Media                         │ │
│  │                             │ [Video/Image Preview]           │ │
│  └─────────────────────────────┴─────────────────────────────────┘ │
│                                                                      │
│  ─────────────────────────────────────────────────────────────────  │
│  [💾 Save Edits] [✅ Approve] [⏮️ Reset] [🔄 Reprocess] [🗑️ Delete]│
└─────────────────────────────────────────────────────────────────────┘
```

**Status Indicators:**
- 🟠 Pending (orange) - Just scraped, needs translation
- 🟢 Processed (green) - Translated, ready for review
- 🟣 Approved (purple) - Human-approved, ready to publish
- 🔵 Published (blue) - Already posted to X

---

## User Interaction Flow

### Typical Session Flow:

```
                    START DASHBOARD
                          ↓
         ┌────────────────┴────────────────┐
         │                                  │
    [VIEW STATS]                     [NEW TASK]
         │                                  │
         ↓                                  ↓
   Filter by Status              Choose Scraping Mode
   (all/pending/                 (Trends/Thread/News)
    processed/etc)                        ↓
         ↓                          Enter URL (if Thread)
   View Tweet Cards                       ↓
         ↓                         Click "Start Scraping"
   ┌────┴────┐                            ↓
   │         │                    Wait for completion
 [EDIT]  [APPROVE]                        ↓
   │         │                      Status message
   ↓         │                            ↓
Save Edits   │                    New tweets appear
   ↓         │                            │
Mark as      │                            │
Approved ────┴────────────────────────────┘
   ↓                                      │
Ready to Publish                          │
   ↓                                      │
(Manual or Auto-Publisher)                │
                                          │
         ┌────────────────────────────────┘
         │
         ↓
   [REFRESH] to see updates
```

---

## Color Coding

**Status Colors:**
- **Orange** (`pending`) - Needs translation
- **Green** (`processed`) - Needs human review
- **Purple** (`approved`) - Ready to publish
- **Blue** (`published`) - Already published

**UI Elements:**
- **Blue borders** - Default card style
- **Red buttons** - Destructive actions (Delete)
- **Green buttons** - Positive actions (Approve, Save)
- **Gray buttons** - Neutral actions (Reset, Reprocess)

---

## Keyboard Shortcuts (Streamlit Default)

- `R` - Rerun the app
- `C` - Clear cache
- `?` - Show keyboard shortcuts

---

## Real-Time Features

1. **Auto-refresh** (optional, 30s interval)
   - Polls database for new tweets
   - Updates statistics
   - Shows newly processed content

2. **Instant feedback**
   - Success/error messages on all actions
   - Status updates immediately visible
   - Media previews load on demand

3. **Background processing**
   - Processor service runs independently
   - Dashboard shows results as they're ready
   - No manual refresh needed with auto-refresh enabled

---

## Technical Details

**Built with:**
- Streamlit 1.30.0 (Python web framework)
- SQLAlchemy 2.0.25 (ORM)
- Pillow 10.2.0 (Image display)

**Performance:**
- Handles 100+ tweets efficiently
- Media lazy-loaded
- Database queries optimized with indexes
- Responsive on standard hardware

**Browser Compatibility:**
- Chrome ✅
- Firefox ✅
- Safari ✅
- Edge ✅

---

See `QUICK_START_GUIDE.md` for usage instructions.
