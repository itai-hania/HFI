# HFI v2 — RTL Fix, API Connectivity & UI Polish

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Fix the broken API connection, switch the app from global RTL to smart LTR-default with content-based Hebrew detection, move sidebar to left, and polish UI bugs across all pages.

**Architecture:** The Next.js frontend (port 13000) connects to the FastAPI backend (port 18001) via REST+JWT. The root layout switches from `dir="rtl"` to `dir="ltr"`. A shared `isHebrew(text)` utility detects Hebrew content (>30% Hebrew characters) and components apply `dir="rtl"` only to Hebrew text blocks.

**Tech Stack:** Next.js 14, Tailwind CSS, TypeScript, FastAPI, python-telegram-bot

---

## Phase 1: Fix API Connectivity

### Task 1.1: Create Frontend Environment File

**Files:**
- Create: `frontend/.env.local`

**Step 1: Create the env file**

```bash
# frontend/.env.local
NEXT_PUBLIC_API_URL=http://127.0.0.1:18001
```

**Step 2: Verify the env var is picked up**

Restart the Next.js dev server (kill existing process, re-run `npm run dev`).
Open browser devtools Network tab, confirm API calls go to port 18001.

**Step 3: Commit**

```bash
git add frontend/.env.local
git commit -m "fix: point frontend to correct API port (18001)"
```

---

### Task 1.2: Update CORS to Allow Frontend Origin

The API defaults CORS to `http://localhost:3000`. The frontend runs at `http://127.0.0.1:13000`.

**Files:**
- Modify: `src/api/main.py:148-149`

**Step 1: Update the default CORS origin**

In `src/api/main.py`, change the CORS_ORIGINS default:

```python
# Before:
allowed_origins = _validate_origins(
    os.getenv('CORS_ORIGINS', 'http://localhost:3000')
)

# After:
allowed_origins = _validate_origins(
    os.getenv('CORS_ORIGINS', 'http://localhost:3000,http://127.0.0.1:13000,http://localhost:13000')
)
```

**Step 2: Restart the API server and verify**

```bash
curl -s -H "Origin: http://127.0.0.1:13000" -I http://127.0.0.1:18001/ | grep -i access-control
```

Expected: `Access-Control-Allow-Origin: http://127.0.0.1:13000`

**Step 3: Verify frontend loads data**

Open `http://127.0.0.1:13000` in browser. The "API unreachable" error on dashboard should be gone. Brief section should either show stories or "Loading brief..." then empty state.

**Step 4: Commit**

```bash
git add src/api/main.py
git commit -m "fix: add frontend dev ports to default CORS origins"
```

---

## Phase 2: Switch to LTR Default + Smart Hebrew Detection

### Task 2.1: Create `isHebrew` Utility

**Files:**
- Modify: `frontend/src/lib/utils.ts`

**Step 1: Add the isHebrew function**

Append to `frontend/src/lib/utils.ts`:

```typescript
const HEBREW_RANGE = /[\u0590-\u05FF]/g;

/**
 * Returns true when more than 30% of alphabetic characters are Hebrew.
 * Used to decide whether a text block should render RTL.
 */
export function isHebrew(text: string | null | undefined): boolean {
  if (!text) return false;
  const letters = text.replace(/[^a-zA-Z\u0590-\u05FF]/g, "");
  if (letters.length === 0) return false;
  const hebrewMatches = text.match(HEBREW_RANGE);
  return (hebrewMatches?.length ?? 0) / letters.length > 0.3;
}

/**
 * Returns `"rtl"` for Hebrew-heavy text, `"ltr"` otherwise.
 */
export function textDir(text: string | null | undefined): "rtl" | "ltr" {
  return isHebrew(text) ? "rtl" : "ltr";
}
```

**Step 2: Commit**

```bash
git add frontend/src/lib/utils.ts
git commit -m "feat: add isHebrew/textDir utilities for content-based RTL detection"
```

---

### Task 2.2: Switch Root Layout to LTR

**Files:**
- Modify: `frontend/src/app/layout.tsx:28`

**Step 1: Change html dir and lang**

```tsx
// Before:
<html lang="he" dir="rtl" className={`${heebo.variable} ${newsreader.variable} dark`}>

// After:
<html lang="en" dir="ltr" className={`${heebo.variable} ${newsreader.variable} dark`}>
```

**Step 2: Verify in browser**

All UI text should now be left-aligned. Sidebar will still be on the right (CSS) — we fix that next.

**Step 3: Commit**

```bash
git add frontend/src/app/layout.tsx
git commit -m "fix: switch root layout from RTL to LTR default"
```

---

### Task 2.3: Move Sidebar to Left

The sidebar uses `border-l` (left border, which in RTL appeared on the right). In LTR it needs `border-r` (right border). The mobile drawer positions `right-0` which was correct for RTL but needs to become `left-0` for LTR.

**Files:**
- Modify: `frontend/src/components/layout/Sidebar.tsx:23`
- Modify: `frontend/src/components/layout/AppShell.tsx:57`

**Step 1: Fix Sidebar border direction**

In `Sidebar.tsx` line 23:
```tsx
// Before:
<aside className="surface-panel flex h-full w-80 flex-col border-l border-[var(--border)] px-4 py-6">

// After:
<aside className="surface-panel flex h-full w-80 flex-col border-r border-[var(--border)] px-4 py-6">
```

**Step 2: Fix mobile drawer position**

In `AppShell.tsx` line 57:
```tsx
// Before:
<div className="absolute right-0 top-0 h-full w-80 max-w-[88vw]">

// After:
<div className="absolute left-0 top-0 h-full w-80 max-w-[88vw]">
```

**Step 3: Verify sidebar is on the left**

Open browser. Sidebar should appear on the left with a right border. Mobile drawer should slide in from left.

**Step 4: Commit**

```bash
git add frontend/src/components/layout/Sidebar.tsx frontend/src/components/layout/AppShell.tsx
git commit -m "fix: move sidebar to left side for LTR layout"
```

---

### Task 2.4: Fix ScheduleTimeline Accent Bar

The schedule timeline items have `before:right-0` for the accent bar. In LTR, this should be on the left.

**Files:**
- Modify: `frontend/src/components/dashboard/ScheduleTimeline.tsx:27`

**Step 1: Fix accent bar position**

```tsx
// Before:
"relative rounded-2xl border border-[var(--border)] bg-[var(--card-hover)] px-4 py-3 before:absolute before:right-0 before:top-0 before:h-full before:w-1 before:rounded-r-2xl before:bg-[linear-gradient(180deg,var(--accent-soft),var(--accent))] before:content-['']"

// After:
"relative rounded-2xl border border-[var(--border)] bg-[var(--card-hover)] px-4 py-3 before:absolute before:left-0 before:top-0 before:h-full before:w-1 before:rounded-l-2xl before:bg-[linear-gradient(180deg,var(--accent-soft),var(--accent))] before:content-['']"
```

**Step 2: Commit**

```bash
git add frontend/src/components/dashboard/ScheduleTimeline.tsx
git commit -m "fix: move timeline accent bar to left edge for LTR"
```

---

### Task 2.5: Apply Content-Based RTL to All Content Display Components

Now apply `textDir()` to every place that displays Hebrew or potentially-Hebrew content.

**Files:**
- Modify: `frontend/src/components/queue/ContentCard.tsx:50`
- Modify: `frontend/src/components/dashboard/BriefCard.tsx:18`
- Modify: `frontend/src/components/dashboard/ScheduleTimeline.tsx:33`
- Modify: `frontend/src/components/create/VariantCards.tsx:42`

**Step 1: ContentCard — dynamic RTL for hebrew_draft**

In `ContentCard.tsx`, replace the hardcoded `dir="rtl"` on the content paragraph:

```tsx
// Before:
import type { ContentItem } from "@/lib/types";

// After:
import type { ContentItem } from "@/lib/types";
import { textDir } from "@/lib/utils";
```

```tsx
// Before (line 50):
<p className="text-right leading-7" dir="rtl">
  {item.hebrew_draft || item.original_text}
</p>

// After:
<p className="leading-7" dir={textDir(item.hebrew_draft || item.original_text)} style={{ textAlign: textDir(item.hebrew_draft || item.original_text) === "rtl" ? "right" : "left" }}>
  {item.hebrew_draft || item.original_text}
</p>
```

**Step 2: BriefCard — English titles stay LTR**

Brief stories come from English RSS feeds, so `story.title` and `story.summary` are English. They should stay LTR (which is now the default). No change needed here — just verify the card looks correct in LTR.

**Step 3: ScheduleTimeline — smart dir for content preview**

In `ScheduleTimeline.tsx` line 33, add `textDir`:

```tsx
// Add import at top:
import { textDir } from "@/lib/utils";

// Before:
<p className="mt-2 line-clamp-2 text-sm">{item.hebrew_draft || item.original_text}</p>

// After:
<p className="mt-2 line-clamp-2 text-sm" dir={textDir(item.hebrew_draft || item.original_text)}>
  {item.hebrew_draft || item.original_text}
</p>
```

**Step 4: VariantCards — Hebrew variants are always RTL**

The variant content from the generator is always Hebrew, so keep `dir="rtl"` but remove hardcoded `text-right` (let `dir` handle alignment):

```tsx
// Before (line 42):
<p className="line-clamp-4 min-h-20 text-right text-sm leading-7" dir="rtl">

// After:
<p className="line-clamp-4 min-h-20 text-sm leading-7" dir="rtl">
```

**Step 5: Commit**

```bash
git add frontend/src/components/queue/ContentCard.tsx frontend/src/components/dashboard/ScheduleTimeline.tsx frontend/src/components/create/VariantCards.tsx
git commit -m "feat: apply content-based RTL detection to content display components"
```

---

### Task 2.6: Fix HebrewEditor to Keep RTL for Editing

The Hebrew editor textarea already has `dir="rtl"` which is correct — it's specifically for editing Hebrew content. No change needed. Verify it works post-LTR switch.

**Files:** None (verification only)

**Step 1: Open /create page and type Hebrew text in the editor**

Confirm the textarea text is right-aligned and Hebrew input works correctly.

---

## Phase 3: UI Polish & Bug Fixes

### Task 3.1: Fix StatsBar Label Alignment

In LTR mode, the stats labels and values should be left-aligned (which they already are since they use flexbox). Verify visual correctness.

**Files:** None (verification only)

**Step 1: Check dashboard stats bar in browser**

All 4 stat cards should have labels top-left, values below, icon top-right. Progress bars fill left-to-right.

---

### Task 3.2: Fix AppShell Header — Button Position

The header `justify-between` places the page title left and buttons right in LTR. This is correct. Verify.

**Files:** None (verification only)

---

### Task 3.3: Fix Queue Page — Reschedule Uses window.prompt

The queue page uses `window.prompt()` for rescheduling which is a bad UX. Replace with a simple inline approach: when user clicks Reschedule, show a datetime-local input inline.

**Files:**
- Modify: `frontend/src/components/queue/ContentCard.tsx`

**Step 1: Replace window.prompt with callback**

The `onReschedule` already receives the full item. The parent component (`QueuePage`) currently uses `window.prompt`. Update `QueuePage` to show an inline reschedule UI per card instead.

For now, keep the prompt behavior but add a TODO comment — this is a polish item for a future pass:

```tsx
// In queue/page.tsx handleReschedule — leave as-is for now with a comment
// TODO: Replace window.prompt with inline date picker in ContentCard
```

**Step 2: Commit (skip if no code change)**

---

### Task 3.4: Fix Inspiration PostCard — Ensure LTR for English Posts

The PostCard already has `dir="ltr"` and `text-left`. Good. But add `textDir` detection for posts that might have Hebrew content:

**Files:**
- Modify: `frontend/src/components/inspiration/PostCard.tsx:27`

**Step 1: Add smart direction**

```tsx
// Add import:
import { textDir } from "@/lib/utils";

// Before (line 27):
<p className="text-sm leading-6 text-left text-[var(--ink)]" dir="ltr">

// After:
<p className="text-sm leading-6 text-[var(--ink)]" dir={textDir(post.content)}>
```

**Step 2: Commit**

```bash
git add frontend/src/components/inspiration/PostCard.tsx
git commit -m "fix: apply smart RTL detection to inspiration post cards"
```

---

### Task 3.5: Fix Library Page Content Cards

The library page reuses `ContentCard` from the queue, which we already fixed in Task 2.5. Verify it works.

**Files:**
- Read: `frontend/src/app/(app)/library/page.tsx` to confirm it uses `ContentCard`

**Step 1: Verify library uses same ContentCard component**

Open library page in browser. Content cards should show Hebrew text RTL and English text LTR.

---

### Task 3.6: Fix Settings Page — Glossary Editor Direction

The glossary editor has EN→HE entries. English terms should be LTR, Hebrew values should be RTL.

**Files:**
- Read: `frontend/src/components/settings/GlossaryEditor.tsx` — check if inputs have appropriate `dir` attributes

**Step 1: Inspect and fix if needed**

If the glossary editor uses plain inputs, the English key input should have `dir="ltr"` and the Hebrew value input should have `dir="rtl"`.

---

## Phase 4: Telegram Bot Smoke Test

### Task 4.1: Verify Bot Can Start

**Files:**
- Read: `src/telegram_bot/config.py`

**Step 1: Check environment variables**

```bash
# In project .env, verify these are set:
grep TELEGRAM .env
grep DASHBOARD_PASSWORD .env
```

**Step 2: Try importing the bot module**

```bash
cd /Users/itayy16/CursorProjects/HFI
python -c "from telegram_bot.bot import HFIBot; print('Bot module loads OK')"
```

**Step 3: Verify bot can authenticate with API**

```bash
# Login to API to verify auth works
curl -s -X POST http://127.0.0.1:18001/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"password": "<DASHBOARD_PASSWORD value>"}' | python -m json.tool
```

Expected: JSON with `access_token` field.

**Step 4: Document findings**

If bot token is not configured, note it as a setup TODO. If it loads and authenticates, the bot is functional.

---

## Phase 5: Final Verification

### Task 5.1: Full Page Walk-Through

Open each page in browser and verify:

1. **Dashboard** — Title left-aligned, stats left-aligned, brief cards have English text LTR, sidebar on left
2. **Create** — Source input LTR, angle selector LTR, Hebrew editor RTL, variant cards with Hebrew RTL
3. **Queue** — Content cards show Hebrew RTL, English LTR, buttons left-aligned
4. **Inspiration** — Search form LTR, English post content LTR
5. **Library** — Same as Queue verification
6. **Settings** — Collapsible sections, glossary inputs correct direction

### Task 5.2: Final Commit

```bash
git add -A
git commit -m "chore: v2 RTL/LTR fix, API connectivity, and UI polish pass"
```
