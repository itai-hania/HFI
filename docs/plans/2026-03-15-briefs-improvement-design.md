# Briefs Improvement — Design

**Date:** 2026-03-15
**Status:** Approved

---

## Problem

1. **Briefs feel raw** — currently a flat list of ranked headlines with no narrative structure or insight. Users scan 8 disconnected stories with no context about what matters or why.
2. **Too much friction to act** — tapping "Write" navigates away to `/create`, breaking flow. The Telegram `/write` + `/save` two-step is clunky.
3. **No learning** — briefs never adapt to the user's interests. Irrelevant stories keep appearing.

## Design

Three improvements, mirrored on both Telegram and Dashboard:

### 1. AI-Powered Themed Sections

After `NewsScraper.get_brief_news()` returns the flat scored story list, a new `BriefThemer` passes stories to GPT-4o to group them into 2-4 themes with AI-generated names and one-line takeaways.

**New module:** `src/processor/brief_themer.py`

```python
class BriefThemer:
    async def generate_themes(self, stories: List[dict]) -> List[dict]:
        """
        Takes flat scored stories, returns themed groups with
        AI-generated theme names and takeaways.
        """
```

**GPT-4o prompt strategy:**

- Input: story titles + summaries + sources (~500 tokens)
- Output: structured JSON via `response_format={"type": "json_object"}`

```json
{
  "themes": [
    {
      "name": "Chip War Heats Up",
      "emoji": "🤖",
      "takeaway": "NVIDIA's blowout earnings signal AI spending is accelerating",
      "story_indices": [0, 3]
    }
  ]
}
```

**Fallback:** If the API call fails or times out (5s), fall back to rule-based grouping by source category (Finance/Tech/Israel) with the top story's title as the takeaway.

**Cost:** ~$0.005 per brief, ~$0.50/month.

### 2. Inline One-Tap Drafts

Clicking "Write" on a story generates a Hebrew draft inline — no navigation.

**Dashboard:** An expandable panel slides open below the story card with an editable textarea containing the generated Hebrew draft, plus Save Draft / Queue / Close buttons.

- **Save Draft** — `POST /api/content` with `status=PROCESSED`
- **Queue** — `POST /api/content` with `status=APPROVED`
- **Close** — discard unsaved edits

Generates 1 variant (not 2) for speed. Uses existing `POST /api/generation/source/resolve` + `POST /api/generation/post`.

**New hook:** `useInlineDraft()` — manages generate/edit/save lifecycle. Only one panel open at a time.

**Telegram:** After `/write N`, bot replies with Hebrew text + inline keyboard buttons: `[Save]` `[Queue]` `[Edit]`. Replaces the current `/write` + `/save` two-step flow.

### 3. Feedback & Personalization

Each story gets a thumbs-down button. Tapping it stores feedback and adjusts future brief scoring.

**Dashboard:** Story card fades, shows "Noted — we'll show less like this".

**Telegram:** `/skip N` command (alias `👎 N`), bot replies "Got it, less stories like this".

**Backend flow:**

1. `POST /api/notifications/brief/feedback` receives `{story_title, feedback_type, keywords[]}`
2. Keywords extracted from title (split + lowercase + remove stopwords)
3. Stored in `brief_feedback` table
4. On next brief generation, keywords with >= 3 "not_relevant" votes are dynamically added to `EXCLUDE_KEYWORDS` (-20 relevance penalty each)

**Settings:** New section in `/settings` showing learned keyword adjustments with a Reset button.

---

## Data Model Changes

### New table: `brief_feedback`

| Column | Type | Purpose |
|---|---|---|
| `id` | Integer PK | Auto-increment |
| `story_title` | String(500) | The story that received feedback |
| `feedback_type` | String(20) | `"not_relevant"` (only type in v1) |
| `keywords` | JSON | Extracted keywords from the story |
| `source` | String(50) | `"telegram"` or `"dashboard"` |
| `created_at` | DateTime(tz) | When feedback was given |

### Updated schemas (`src/api/schemas/notification.py`)

```python
class BriefStory(BaseModel):
    title: str
    summary: str
    sources: List[str]
    source_urls: List[str]
    source_count: int
    published_at: datetime | None
    relevance_score: int = 0

class BriefTheme(BaseModel):
    name: str                          # "Chip War Heats Up"
    emoji: str                         # "🤖"
    takeaway: str                      # One-line insight
    stories: List[BriefStory]

class BriefResponse(BaseModel):
    themes: List[BriefTheme]           # Grouped view
    stories: List[BriefStory]          # Flat list for backward compat (/story N, /write N)
    generated_at: datetime
```

### New API endpoints

- `POST /api/notifications/brief/feedback` — store feedback
- `GET /api/notifications/brief/feedback/weights` — view learned keyword adjustments

---

## Telegram Format

```
📊 Morning Brief · 6 stories · 10:00 IST

🤖 Chip War Heats Up
   NVIDIA's blowout earnings signal AI spending is accelerating

1. NVIDIA beats earnings expectations...
   ⏱ 2h ago · 📡 4 sources
   Bloomberg · CNBC · Yahoo Finance

2. OpenAI launches enterprise agents...
   ⏱ 3h ago · 📡 2 sources
   TechCrunch · Bloomberg

💰 Fed Holds Steady
   Markets rally as rate cut expectations firm up for Q2

3. Treasury yields drop after Fed decision...
   ⏱ 4h ago · 📡 3 sources
   CNBC · MarketWatch

4. S&P 500 hits record on rate hopes...
   ⏱ 5h ago · 📡 2 sources
   Yahoo Finance · Bloomberg

🇮🇱 Israeli FinTech Funding Surge
   Startup investment hits Q1 high, led by payments and crypto

5. Israeli FinTech raises $50M Series C...
   ⏱ 3h ago · 📡 3 sources
   Investing.com · Google News Israel

6. TASE hits new high on tech rally...
   ⏱ 6h ago · 📡 2 sources
   Calcalist · Globes

/write N · /story N · /skip N
```

Stories numbered continuously across themes for simple `/write N` and `/story N` indexing.

---

## Files Changed

**New files:**
- `src/processor/brief_themer.py` — AI theming pipeline
- `frontend/src/hooks/useInlineDraft.ts` — inline draft lifecycle

**Modified files:**

| File | Change |
|------|--------|
| `src/common/models.py` | Add `BriefFeedback` model |
| `src/api/schemas/notification.py` | Add `BriefTheme`, update `BriefResponse` |
| `src/api/routes/notifications.py` | Theming integration, feedback endpoints |
| `src/scraper/news_scraper.py` | Dynamic keyword weight adjustments from feedback |
| `frontend/src/components/dashboard/BriefCard.tsx` | Themed layout, inline draft panel, thumbs-down button |
| `frontend/src/app/(app)/page.tsx` | Render themes instead of flat story list |
| `frontend/src/hooks/useBrief.ts` | Add feedback mutation, update types |
| `src/telegram_bot/bot.py` | Themed format, inline keyboard buttons, `/skip` command |
| `frontend/src/app/(app)/settings/page.tsx` | Feedback weights section with reset |

---

## Decisions

| Decision | Choice | Rationale |
|---|---|---|
| Theming approach | AI (GPT-4o) over rule-based | Contextual theme names and insightful takeaways are the difference between raw and curated |
| Draft variants | 1 per write (not 2) | Speed over choice in inline context |
| Feedback v1 | Thumbs-down only, no boost | Keep simple; boost can come later |
| Story numbering | Continuous across themes | Keeps `/write N` and `/story N` indexing simple |
| Flat `stories` in response | Kept alongside `themes` | Backward compat for Telegram commands that index by number |
