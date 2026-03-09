# HFI v2 — Content Studio Design

**Date:** 2026-03-08
**Status:** Approved
**Goal:** Transform HFI from a clunky Streamlit admin panel into a polished content creator tool with a Next.js web app + Telegram bot for push updates.

---

## 1. Problem Statement

The current HFI app is ~30% of what's needed for a daily Hebrew fintech content creator workflow:
- **UI feels generic** — looks like an admin panel, not a content tool
- **Too many clicks** — scattered tabs and multi-step workflows
- **Streamlit is clunky** — slow reruns, janky interactions
- **No push notifications** — user must actively check for trending topics
- **No RTL support** — Hebrew content is hard to read/edit
- **No inspiration feed** — user manually searches X for high-performing posts from top accounts
- **Content not browsable** — DB-stored content is uncomfortable to read in the current UI

## 2. User Profile

- Solo Hebrew fintech content creator on X
- Publishes 3-5 posts/day (mix of short posts, threads, articles)
- Monitors ~10 top English fintech accounts for inspiration
- Needs morning + evening content planning sessions (~15 min each)
- Wants real-time alerts for breaking stories
- Copies final Hebrew text to X manually (no auto-publish needed)

## 3. Architecture

### Components

```
┌─────────────────┐     ┌──────────────┐
│  Next.js Web UI │────>│              │
│  (React, TW CSS)│     │  FastAPI API  │──> SQLite
└─────────────────┘     │              │
                        │  Python      │──> OpenAI GPT-4o
┌─────────────────┐     │  Backend     │
│  Telegram Bot   │────>│              │──> X Scraper (Playwright)
│  (python-telegram│     │              │──> RSS Feeds
│   -bot)         │     └──────────────┘
└─────────────────┘
```

### What We Keep (working well)
- X Scraper (Playwright) — thread scraping, session management
- News Scraper (RSS + cross-source ranking) — parallel feed fetching
- Translation engine (GPT-4o + glossary + style matching)
- Content Generator (multi-angle Hebrew generation)
- Database models (SQLAlchemy ORM, migrate to API-only access)
- Security layer (rate limiting, input validation, auth)

### What We Replace
- Streamlit dashboard → Next.js web app
- Direct DB access from UI → REST API layer
- No notifications → Telegram bot with scheduled briefs + real-time alerts

### What We Add
- Inspiration feed (scrape top accounts by engagement)
- Proper RTL support throughout
- Copy-optimized content cards
- Content library with search
- Scheduled briefs (8am + 7pm) + breaking alerts

## 4. Web App — Pages & UX

### 4.1 Dashboard (Home)

The first screen. Designed for a 15-minute session.

**Layout:**
- **Today's Brief** — top 5-7 stories ranked by cross-source overlap + recency, one-line Hebrew summary each
- **Quick Actions per story**: "Write about this" | "Translate" | "Skip"
- **Pipeline Stats** — drafts count, scheduled today, published today
- **Scheduled Timeline** — horizontal bar showing today's posts with visible gaps

**Behavior:**
- Auto-fetches fresh trends on page load (with cache, not on every render)
- Stories marked as "skipped" disappear from brief
- "Write about this" navigates to Create page with source pre-filled

### 4.2 Create

Unified content creation — replaces the old Acquire/Queue/Translate/Generate tabs.

**Source Input (flexible):**
- Paste a URL (auto-detects: tweet, thread, article)
- Pick a trend from the dashboard brief
- Start from scratch (blank editor)

**Generation Flow:**
1. Source detected and displayed
2. Angle selector: News / Educational / Opinion (remembers last choice)
3. Click "Generate" → 2-3 Hebrew variants appear side-by-side in RTL cards
4. Pick a variant → opens in RTL editor for polishing
5. Actions: Copy to clipboard (one click) | Save as draft | Schedule

**Editor:**
- RTL-aware rich text editor
- Inline glossary term suggestions
- Character count (X post limits)
- Preview mode (how it'll look on X)

### 4.3 Queue / Drafts

**Tabs:** Drafts | Scheduled | Published

**Each card shows:**
- Hebrew content in RTL layout
- Source reference (linked)
- Status badge
- Scheduled time (if scheduled)
- One-click copy button

**Actions:**
- Edit → opens in Create page
- Reschedule (date/time picker)
- Delete
- Bulk select + bulk actions

### 4.4 Inspiration Feed

Replaces manual `from:account min_faves:100` X searches.

**Search interface:**
- Account selector (from configured list of ~10)
- Min likes filter (slider or input)
- Date range
- Keyword search

**Results:**
- Browsable cards with post content + engagement stats (likes, retweets, views)
- Sorted by engagement by default
- "Use as source" button → jumps to Create page with content pre-filled

### 4.5 Content Library

All past content (yours), searchable.

**Features:**
- Full-text search across Hebrew content
- Filter by: topic tags, date range, status, content type
- Each card: Hebrew content (RTL), source, date, status
- "Reuse" button → opens in Create with content pre-filled for rework

### 4.6 Settings

- **Inspiration Accounts** — add/remove/edit the ~10 monitored accounts
- **Glossary** — EN→HE financial term editor (add, edit, delete terms)
- **Style Examples** — import/manage Hebrew style examples with topic tags
- **Telegram** — connect/disconnect bot, notification preferences (brief times, alert threshold)
- **Defaults** — preferred angle, posts-per-day target, default scheduling times

## 5. Telegram Bot

### 5.1 Scheduled Briefs (8:00 AM + 7:00 PM)

```
📊 Evening Brief — 3 hot topics

1. 🔥 SEC approves new Bitcoin ETF framework
   Trending across: Bloomberg, WSJ, Yahoo Finance
   → /write_1  /translate_1  /skip_1

2. 📈 Stripe acquires stablecoin startup
   Trending across: TechCrunch, Bloomberg
   → /write_2  /skip_2

3. 💰 JPMorgan Q1 earnings beat expectations
   Trending across: WSJ, Yahoo Finance
   → /write_3  /skip_3
```

### 5.2 Real-time Alerts

Triggered when a topic crosses 3+ sources within a short window.

```
🚨 Breaking: Major fintech story

"Federal Reserve announces CBDC pilot program"
Sources: Bloomberg, WSJ, Yahoo Finance, TechCrunch

→ /write  /translate  /skip
```

### 5.3 Commands

| Command | Action |
|---------|--------|
| `/write` or `/write_N` | Generate Hebrew post from alert/brief item N, sends back variants |
| `/translate <url>` | Translate a thread/post URL, sends Hebrew result |
| `/status` | "3 drafts, 2 scheduled today, 1 published" |
| `/schedule` | Shows today's scheduled posts |
| `/accounts` | List monitored inspiration accounts |
| `/brief` | Trigger an on-demand brief |

### 5.4 Content Delivery

- Bot sends generated content in RTL Hebrew
- User copies directly from Telegram to X
- Or replies `/save` to save as draft in web app

## 6. API Layer (FastAPI)

All UI interactions go through the API. No direct DB access from frontends.

### Trends & Discovery
```
GET    /api/trends/brief          — ranked stories for dashboard
POST   /api/trends/fetch          — trigger fresh trend fetch
GET    /api/trends/alerts         — undelivered alerts for Telegram
POST   /api/trends/{id}/skip     — mark trend as skipped
```

### Content Creation
```
POST   /api/content/generate      — source + angle → Hebrew variants
POST   /api/content/translate     — URL or text → Hebrew translation
GET    /api/content/drafts        — list drafts (filterable)
GET    /api/content/scheduled     — list scheduled posts
GET    /api/content/published     — list published posts
GET    /api/content/{id}          — single content item
POST   /api/content               — create new draft
PATCH  /api/content/{id}          — update text/status/schedule
DELETE /api/content/{id}          — delete content
POST   /api/content/{id}/copy    — increment copy count
```

### Inspiration
```
POST   /api/inspiration/search    — account + min_faves + keywords → results
GET    /api/inspiration/accounts  — list configured accounts
POST   /api/inspiration/accounts  — add account
DELETE /api/inspiration/accounts/{id} — remove account
```

### Settings
```
GET    /api/settings/glossary     — get glossary
PUT    /api/settings/glossary     — update glossary
GET    /api/settings/style-examples — list examples (filterable by tag)
POST   /api/settings/style-examples — add example
PUT    /api/settings/style-examples/{id} — update example
DELETE /api/settings/style-examples/{id} — delete example
GET    /api/settings/preferences  — get user preferences
PUT    /api/settings/preferences  — update preferences
```

### Auth
```
POST   /api/auth/login            — password → JWT token
POST   /api/auth/refresh          — refresh JWT
```

## 7. Tech Stack

| Layer | Technology | Rationale |
|-------|-----------|-----------|
| Web Frontend | Next.js 14+ (App Router) | Modern React, SSR, great DX |
| Styling | Tailwind CSS + shadcn/ui | Rapid UI development, dark mode, RTL support |
| RTL | Tailwind RTL plugin + `dir="rtl"` | Native RTL flipping for margins/padding |
| State/Caching | TanStack Query (React Query) | API caching, optimistic updates, refetch |
| Backend API | FastAPI | Already Python ecosystem, async, auto-docs |
| Telegram Bot | python-telegram-bot v20+ | Async, well-maintained, conversation handlers |
| Scheduler | APScheduler | Briefs at 8am/7pm, alert checks every 15min |
| Database | SQLite (same) | Works for single-user, already battle-tested |
| AI Engine | OpenAI GPT-4o | Existing translation + generation (unchanged) |
| Scraping | Playwright (X), feedparser (RSS) | Existing, working well |
| Font | Heebo (Google Fonts) | Clean Hebrew font, good readability |

## 8. Data Model Changes

### New Tables

**`inspiration_accounts`**
| Column | Type | Description |
|--------|------|-------------|
| id | Integer PK | |
| username | String | X handle (without @) |
| display_name | String | Display name |
| category | String | e.g., "fintech", "crypto", "banking" |
| is_active | Boolean | Whether to include in searches |
| created_at | DateTime | |

**`inspiration_posts`** (cached search results)
| Column | Type | Description |
|--------|------|-------------|
| id | Integer PK | |
| account_id | Integer FK | Reference to inspiration_accounts |
| x_post_id | String | X post ID (unique) |
| content | Text | Post text |
| likes | Integer | Favorite count |
| retweets | Integer | Retweet count |
| views | Integer | View count |
| posted_at | DateTime | Original post date |
| fetched_at | DateTime | When we scraped it |

**`notifications`**
| Column | Type | Description |
|--------|------|-------------|
| id | Integer PK | |
| type | String | "brief" or "alert" |
| content | JSON | Notification payload |
| delivered | Boolean | Whether sent to Telegram |
| delivered_at | DateTime | When sent |
| created_at | DateTime | |

**`user_preferences`**
| Column | Type | Description |
|--------|------|-------------|
| key | String PK | Preference key |
| value | JSON | Preference value |

### Modified Tables

**`tweets`** (existing)
- Keep all existing columns
- Add `copy_count` (Integer, default 0) — track clipboard copies

## 9. RTL Strategy

- All Hebrew content wrapped in `<div dir="rtl" class="font-heebo">`
- Tailwind CSS RTL plugin (`tailwindcss-rtl`) for automatic margin/padding flipping
- Editor component uses RTL-aware contenteditable or textarea
- Mixed content (English terms embedded in Hebrew) wrapped with `<bdi>` tags for correct bidirectional rendering
- Font stack: `'Heebo', 'Arial Hebrew', system-ui, sans-serif`
- Content cards: right-aligned text, left-aligned metadata/actions

## 10. Migration Strategy

### Phase approach — keep old app running until new one is ready

1. **Build API layer first** — wrap existing Python engine with FastAPI endpoints
2. **Build Next.js app** — page by page, starting with Dashboard + Create
3. **Build Telegram bot** — connect to same API
4. **Test end-to-end** — full workflow validation
5. **Switch over** — retire Streamlit dashboard

### Data migration
- Same SQLite database, same models
- New tables added via Alembic migrations
- No data loss — additive changes only

## 11. Non-Goals (Explicitly Out of Scope)

- Auto-publishing to X (user copies manually)
- Mobile native app (responsive web is sufficient)
- Multi-user support (single content creator)
- Engagement analytics from X API (future consideration)
- AI-powered scheduling optimization (manual scheduling)

## 12. Success Criteria

- Morning content session takes <15 minutes (currently ~30+)
- 3-5 posts created and ready per day with minimal friction
- Hebrew content is readable and editable in proper RTL layout
- Telegram alerts surface breaking stories within 15 minutes
- One-click copy from any content card
- Inspiration feed replaces manual X searches entirely
