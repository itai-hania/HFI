# News & Content Pipeline Improvement Design

> **Date:** 2026-03-13
> **Status:** Approved
> **Scope:** News scraper relevance, Telegram bot UX, Dashboard news hub, X content pipeline API

---

## Goals

1. **Laser-focused news** — US markets (Wall Street, NASDAQ, Fed), Israel economy/tech, and major global fintech. Filter out noise (tariffs, EU regulation, politics).
2. **Rich Telegram briefs** — HTML formatting, story age, source count, relevance scores, clickable links. Actually useful on mobile.
3. **Dashboard as news hub** — Expanded brief cards, alerts section, refresh button, full context passed to content creation.
4. **X content pipeline in v2** — Thread scraping, inspiration accounts, and trend discovery accessible from the Next.js frontend and Telegram bot via proper API endpoints.

## Non-Goals

- Auto-publishing to X (explicitly deferred)
- Post-publish engagement analytics
- AI-powered relevance gating (keyword filtering is sufficient)

---

## Section 1: News Scraper — Relevance & Sources

### 1.1 Add Israeli News Sources

Add to `FEEDS` dict in `src/scraper/news_scraper.py`:

| Source | RSS URL | Category |
|--------|---------|----------|
| Calcalist Tech | `https://www.calcalistech.com/ctechnews/rss` | Israel |
| Globes English | `https://en.globes.co.il/en/rss` | Israel |
| Times of Israel Business | `https://www.timesofisrael.com/feed/business/` | Israel |

New constant:
```python
ISRAEL_SOURCES = ["Calcalist", "Globes", "Times of Israel"]
```

### 1.2 Relevance Keyword Scoring

Replace the simple keyword overlap + Wall Street boost with a proper relevance filter.

**MUST_INCLUDE keywords** (any hit = relevant, +10 per keyword):
```
wall street, nasdaq, s&p 500, dow jones, nyse, ipo, earnings, fed, fomc,
treasury, sec, fintech, neobank, crypto, bitcoin, ethereum, defi, payments,
startup, funding, series a, series b, series c, valuation, acquisition,
israel, tel aviv, tase, check point, wix, monday.com, fiverr, ironource,
cybersecurity, saas, b2b, venture capital
```

**EXCLUDE keywords** (story demoted, -20 per keyword):
```
tariff, trade war, eu regulation, brexit, china sanctions, senate vote,
congress bill, political, election, campaign, diplomatic, military,
climate policy, carbon tax, immigration
```

Stories scoring below a configurable threshold (default: 15) are dropped entirely.

### 1.3 Three-Bucket Source Weighting

Replace `finance_weight=0.7` with:

| Bucket | Weight | Sources |
|--------|--------|---------|
| Finance | 50% | Yahoo Finance, WSJ, Bloomberg, MarketWatch |
| Tech/FinTech | 25% | TechCrunch |
| Israel | 25% | Calcalist, Globes, Times of Israel |

At least 1 Israel story always included if available. The `get_latest_news()` and `get_brief_news()` both use this 3-bucket system.

---

## Section 2: Telegram Bot — Rich Briefs & Better UX

### 2.1 Rich HTML Brief Formatting

Switch to `parse_mode="HTML"` for all brief and alert messages.

**Brief format:**
```html
📊 <b>Morning Brief</b> · 8 stories · 09:15 IST

<b>1.</b> <b>Fed Signals Rate Cut Pause</b>
Powell says committee needs more confidence before acting.
⏱ 2h ago · 📡 3 sources · 🎯 87
<a href="https://...">Bloomberg</a> · <a href="https://...">WSJ</a>

<b>2.</b> <b>Wix Reports Record Revenue</b>
Israeli tech company beats Q4 estimates by 12%.
⏱ 45m ago · 📡 2 sources · 🔵 Israel
<a href="https://...">Calcalist</a> · <a href="https://...">Globes</a>

/write 1 to create · /story 1 for details
```

Key metadata per story:
- **Story age** ("2h ago", "45m ago") from `published_at`
- **Source count** ("3 sources")
- **Relevance score** (🎯 87) or Israel badge (🔵)
- **Clickable source links** (all sources, HTML `<a>` tags)
- **Brief generation timestamp** with IST timezone

### 2.2 Alert Threshold & Format

Lower `min_sources` from 3 to 2. With 8 sources, 2-source crossover is meaningful.

**Alert format:**
```html
🚨 <b>Breaking:</b> NASDAQ Drops 3% on Rate Fears
Markets react to unexpected inflation data.
📡 4 sources · ⏱ 12m ago
<a href="...">Bloomberg</a> · <a href="...">WSJ</a> · <a href="...">Yahoo</a>

/write alert to create content
```

### 2.3 `/brief` Accepts Any Number

Change from hardcoded `[3, 4, 5]` to accept 1-8. Default stays 5.

### 2.4 New Commands

| Command | Purpose |
|---------|---------|
| `/scrape <x_url>` | Scrape X thread, translate consolidated, show preview, offer /save |
| `/xtrends` | Show top 10 X trending topics with /write shortcuts |

---

## Section 3: Frontend Dashboard — News Hub

### 3.1 Homepage Overhaul

**Stats bar additions:**
- "Brief generated Xm ago" indicator
- Alert count ("2 unread alerts")
- Keep existing pipeline stats (Drafts, Scheduled, Published)

**Brief section changes:**
- **Cards expanded by default** — summary visible without clicking
- **"Refresh Brief" button** — calls `POST /api/notifications/brief?force_refresh=true`
- **Relevance score** visible per story (star + number)
- **Israel badge** on Israeli-source stories
- **Story age** ("2h ago") on each card
- **All source names** shown as clickable links
- **"Write" button passes full context** — title + summary + source URLs

**New Alerts section:**
- Fetch from `GET /api/notifications/alerts?delivered=false`
- Show unread alerts with source count, age, dismiss action
- "Write" action for each alert

### 3.2 "Write" Button Context Fix

Currently: `?text={title}` (loses summary and URLs).
Change to: `?text={title}\n\n{summary}&sources={url1,url2,...}`

The Create page reads `sources` param and includes them in generation context.

### 3.3 useBrief GET/POST Split

- **Page load:** `GET /api/notifications/brief/latest` (reads cache, no generation)
- **Refresh button:** `POST /api/notifications/brief?force_refresh=true` (generates fresh)
- **Auto-refresh interval:** keep 5 minutes but use GET

---

## Section 4: X Content Pipeline — API + Frontend

### 4.1 New API Endpoints

| Endpoint | Method | Body | Returns |
|----------|--------|------|---------|
| `POST /api/scrape/thread` | POST | `{url: string}` | Thread data (tweets, author, count) |
| `POST /api/scrape/tweet` | POST | `{url: string}` | Single tweet data |
| `POST /api/scrape/trends` | POST | `{limit?: number}` | List of X trending topics |
| `POST /api/content/from-thread` | POST | `{url, mode, auto_translate, download_media}` | Created content item(s) |

All endpoints require JWT auth. The scraper endpoints use a shared `TwitterScraper` instance with session management.

`POST /api/content/from-thread` is the "one-click" endpoint: scrape → translate → save to queue. The `mode` field accepts `"consolidated"` or `"separate"`.

### 4.2 Frontend Acquire Page

New page at `/acquire` (or tab within existing layout) with:

1. **URL input** — paste X thread/tweet URL
2. **Mode selector** — Consolidated vs Separate radio
3. **Options** — Auto-translate checkbox, Download media checkbox
4. **"Scrape & Process" button** — calls `POST /api/content/from-thread`
5. **Side-by-side results** — English (LTR) left, Hebrew (RTL) right
6. **Actions** — Edit, Approve, Save to queue

### 4.3 Inspiration Accounts

The existing `AccountManager` and `SearchForm` components are already built. They need:
- A sidebar link to make them discoverable (currently hidden)
- Integration into the Acquire page or a dedicated `/inspiration` route

### 4.4 X Trend Discovery

- **Dashboard:** "Discover X Trends" button on the Acquire page → calls `POST /api/scrape/trends`
- **Telegram:** `/xtrends` command → shows top 10 trending topics with `/write` shortcuts

---

## Implementation Order

1. **Slice 1: News Scraper** — Israeli sources, relevance scoring, 3-bucket weighting
2. **Slice 2: Telegram Bot** — Rich HTML formatting, lower alert threshold, /brief improvements
3. **Slice 3: Dashboard** — Homepage overhaul, alerts section, write context fix, GET/POST split
4. **Slice 4: X Pipeline** — Scrape API endpoints, Acquire page, /scrape and /xtrends commands

Each slice is independently deployable and testable.
