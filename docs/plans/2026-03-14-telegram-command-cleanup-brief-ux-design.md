# Telegram Command Cleanup & Brief UX — Design

**Date:** 2026-03-14
**Status:** Approved

---

## Problem

1. **Brief UX is confusing** — `/brief refresh` exists but isn't discoverable. Users expect `/brief` to always give fresh content.
2. **Too many Telegram commands** — 15 commands overwhelm; many overlap with the frontend studio.
3. **No autocomplete** — bot never calls `set_my_commands`, so Telegram doesn't show slash-command suggestions.

## Design

### 1. Slim Command Set (15 → 10)

**Keep:**

| Command | Description |
|---------|------------|
| `/start` | Start the bot |
| `/help` | Show all commands |
| `/brief` | Get a fresh brief |
| `/story` | Story details from brief |
| `/write` | Generate Hebrew content |
| `/save` | Save a generated variant |
| `/schedule` | Show brief schedule |
| `/scrape` | Scrape & translate X thread |
| `/xtrends` | Top X trending topics |
| `/health` | Check API status |

**Drop:**

| Command | Reason |
|---------|--------|
| `/approve` | Use frontend studio |
| `/lastbrief` | `/brief` is always fresh now; `/story` covers drill-down |
| `/queue` | Use frontend studio |
| `/draft` | Use frontend studio |
| `/status` | Use frontend studio |

### 2. Brief — Always Fresh

- `/brief` always passes `force_refresh=true` to the API. No cache for on-demand calls.
- `/brief 3` = fresh brief, show only 3 stories.
- Remove the `refresh` argument parsing from `_brief_input()`.
- The API's 10-min cache (`_BRIEF_CACHE_TTL`) remains but only benefits the scheduler (prevents double-scrape).

### 3. Telegram Autocomplete

- Add `set_my_commands()` call during bot startup (after `app.initialize()`).
- Register only the 10 kept commands with one-line descriptions.
- Users will see autocomplete suggestions when typing `/` in the Telegram chat.

### 4. Frontend — No Changes

- The ↻ Refresh button already works (`POST /brief?force_refresh=true`).
- 5-minute polling via `GET /brief/latest` stays.
- No changes to the Next.js dashboard.

## Files Affected

- `src/telegram_bot/bot.py` — remove 5 handlers, simplify `_brief_input()`, always `force_refresh=true`
- `src/telegram_bot/command_catalog.py` — remove 5 dropped commands
- `src/telegram_bot/main.py` — add `set_my_commands()` at startup
- `src/telegram_bot/bot.py` — remove handler methods for dropped commands
- Tests — update any tests that reference dropped commands

## Non-Goals

- No changes to the brief API endpoint logic
- No changes to the scheduler
- No changes to the frontend
- No new features — this is cleanup + UX improvement only
