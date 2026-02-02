# HFI Dashboard Improvements - Technical Specification

**Version:** 3.0
**Date:** 2026-02-02
**Status:** Phase 1-3 Complete, Phase 4 In Planning

---

## Executive Summary

This specification outlines improvements to the Hebrew FinTech Informant (HFI) dashboard. The goal is to make the existing Streamlit dashboard **smoother and more comfortable to use** without a complete redesign.

**Key Priorities (in order):**

1. **AI Article Summaries** - Auto-generate summaries to quickly understand what each article is about
2. **UX Polish** - Smoother interactions, better visual feedback, more comfortable workflow
3. **Thread Translation** - Full Hebrew rewrite of threads in your style (RTL display)
4. **Home Page Layout** - Collapsible sections for better content organization

**What we're NOT doing:**
- ❌ Migrating away from Streamlit
- ❌ Dark/Light mode toggle (staying dark)
- ❌ RTL for the entire interface (content is English)
- ❌ Complete visual redesign

---

## Progress Summary

| Phase | Status | Completion |
|-------|--------|------------|
| Phase 1: AI Summaries | ✅ Complete | 100% |
| Phase 2: UX Polish | ✅ Complete | 100% |
| Phase 3: Thread Translation RTL | ✅ Complete | 100% |
| Phase 4: Home Page Layout | 📋 Planning | 0% |

---

## Phase 1: AI Article Summaries ✅ COMPLETE

**Goal:** Quickly understand what each article is about without reading the full content.

### Completed Tasks

- [x] **Database Models** - Added `summary`, `keywords`, `source_count`, `related_trend_ids` fields to Trend model
- [x] **Summary Generator** - Created `src/processor/summary_generator.py` with OpenAI GPT-4o integration
- [x] **Dashboard Integration** - Wired summary display into Streamlit trends list
- [x] **Generate Summaries Button** - Added "Generate Summaries" button + auto-generate on fetch
- [x] **Keywords Display** - Show extracted keywords as small tags below each trend
- [x] **Source Count Indicator** - Show "N sources" badge for trends found in multiple sources
- [x] **HTML Rendering Bug Fix** - Fixed multiline HTML template issue causing raw tags to display

### Technical Details

**Bug Fix Applied:** Streamlit's markdown renderer had issues with multiline HTML templates. Fixed by:
1. Adding `import html` for escaping user content from RSS feeds
2. Converting multiline HTML templates to single-line strings
3. Applying `html.escape()` to all user-provided content (titles, descriptions, summaries, keywords)

### Phase 1 Testing ✅

**Unit Tests:**
- [x] Summary generator produces valid summaries
- [x] Keywords extraction works correctly
- [x] Database fields save and retrieve properly

**Browser Tests (MCP Chrome):**
- [x] Home page loads without errors
- [x] Trends display with summaries, keywords, and source badges
- [x] No raw HTML tags visible
- [x] All 5 test trends render correctly
- [x] Content page loads and shows trends

---

## Phase 2: UX Polish ✅ COMPLETE

**Goal:** Make the dashboard feel smooth and comfortable for daily use.

### 2.1 Reduce Information Overload
- [x] Cleaner layout with less visual noise
- [x] Show only essential info in list view (title, source, status, summary)
- [x] Hide details until user clicks to expand (Details expander)
- [x] Group related items logically

### 2.2 Clear Status Indicators
- [x] Visual badges/colors for status: `Pending` | `Approved` | `Published`
- [x] At-a-glance understanding of what needs attention (Stat cards on Home)
- [x] Filter by status easily (Filter dropdown in Queue)

### 2.3 Fewer Clicks for Common Actions
- [x] **View details:** Inline expansion using Streamlit expanders
- [x] **Quick Actions:** "Add to Queue" button on each trend
- [x] **In Queue indicator:** Shows "✓ In Queue" for already-queued items

### 2.4 Default to Trends List
- [x] Dashboard opens directly to latest trends (Home page shows Discovered Trends)
- [x] No extra clicks to get to main content

### Phase 2 Implementation Tasks

| Task | Priority | Status |
|------|----------|--------|
| Add inline "Add to Queue" button on trend cards | High | ✅ Complete |
| Add expandable details for each trend | Medium | ✅ Complete |
| Improve visual hierarchy (larger titles, clearer sections) | Medium | ✅ Complete |
| Add quick status filter buttons (not just dropdown) | Low | ⏳ Deferred |

### Phase 2 Testing Plan

**Unit Tests:**
- [x] Add to Queue button creates Tweet record
- [x] Expandable details show full content

**Browser Tests (MCP Chrome):**
- [x] Click "Add to Queue" button - verify tweet created (INBOX count increased 0→1)
- [x] Queue tab shows added item with PENDING status
- [x] "✓ In Queue" indicator replaces button for queued items
- [x] Expand trend details - verify content visible (Source link, Full Summary, Keywords, Discovery date)
- [x] Details expander collapses/expands smoothly
- [x] All interactions feel smooth (no page jumps)

---

## Phase 3: Thread Translation (Hebrew RTL) ✅ COMPLETE

**Goal:** Translate fetched threads to Hebrew in your writing style.

**Workflow:**

1. **Paste URL** - User pastes X/Twitter thread URL
2. **Auto-fetch** - System scrapes all tweets in thread
3. **Translate** - Click "Translate" → GPT-4o rewrites in Hebrew
   - Uses your style from `config/style.txt`
   - Uses glossary from `config/glossary.json`
   - Maintains thread structure (numbered tweets)

**Display: Side-by-Side**
```
┌─────────────────────────────────┬─────────────────────────────────┐
│  English (LTR)                  │  Hebrew (RTL)                   │
│                                 │                                 │
│  1. Original tweet text...      │  ...טקסט התרגום הראשון .1       │
│  2. Second tweet...             │  ...טקסט התרגום השני .2         │
│  3. Third tweet...              │  ...טקסט התרגום השלישי .3       │
└─────────────────────────────────┴─────────────────────────────────┘
```

**Existing Code:** Translation logic in `src/processor/processor.py` (TranslationService)

### Completed Tasks

- [x] **Thread Translation Tab** - Added new "Thread Translation" tab in Content view
- [x] **URL Input & Fetch** - Paste thread URL and click "Fetch Thread" to scrape
- [x] **Side-by-Side Display** - English (LTR) left, Hebrew (RTL) right
- [x] **Translation Modes** - Consolidated (single flowing post) or Separate (preserve thread structure)
- [x] **RTL CSS Support** - Added CSS for proper Hebrew RTL text direction
- [x] **Hebrew Font Loading** - Added Heebo Google Font for better Hebrew rendering
- [x] **Numbered Tweets** - Display tweet numbers with RTL-aware positioning
- [x] **Action Buttons** - Add to Queue, Download Hebrew, Re-translate, Clear Thread

### Technical Details

**CSS Additions:**
- `.rtl-container` - Direction: RTL, text-align: right
- `.translation-panel-header` - Styled headers for English/Hebrew columns
- `.thread-tweet-item` - Individual tweet cards with hover effects
- `.thread-tweet-number` - Circular numbered badges
- Hebrew font: Heebo from Google Fonts

**TranslationService Methods:**
- `translate_thread_consolidated()` - Combines thread into one flowing Hebrew post
- `translate_thread_separate()` - Translates each tweet with context awareness
- `is_hebrew()` - Detects if text is already Hebrew (skip re-translation)
- `validate_hebrew_output()` - Ensures output is ≥50% Hebrew characters

### Phase 3 Testing ✅

**Unit Tests (26 passed):**
- [x] Hebrew detection (`is_hebrew()`) works correctly
- [x] Hebrew output validation catches invalid translations
- [x] URL/mention/hashtag extraction preserves content
- [x] Consolidated thread translation produces Hebrew output
- [x] Separate thread translation preserves order
- [x] Already-Hebrew content is not re-translated
- [x] RTL structure and numbers preserved

**Browser Tests (MCP Chrome):**
- [x] Thread Translation tab renders correctly
- [x] URL input field displays with placeholder
- [x] "Fetch Thread" button is functional
- [x] Empty state shows instructions
- [x] Side-by-side columns display properly

---

## Phase 4: Home Page Layout & Content Organization

**Goal:** Make Home page more comfortable to browse by changing from 2-column to collapsible row-based layout.

### User Requirements (Q&A Summary)

| Question | Answer |
|----------|--------|
| What to do with trends? | **Option B**: Scan quickly, expand interesting ones, translate & publish tweets |
| Keep Queue as separate tab? | Yes, keep it as a separate tab |
| Layout preference | 2 **rows** instead of 2 columns, with collapsible/dropdown sections |
| Processed Threads preview | Show first 10-15 words as intro, click to see full thread |
| Trend details on expand | Summary + source link + all existing functions |

### Current Layout (Problem)

```
┌─────────────────────────┬─────────────────────────┐
│  Processed Content      │  Discovered Trends      │
│  (narrow column)        │  (narrow column)        │
│                         │                         │
│  Hard to read when      │  Hard to read when      │
│  details expanded       │  details expanded       │
└─────────────────────────┴─────────────────────────┘
```

**Problem:** When expanding trend details, content is cramped in a narrow column.

### Target Layout (Solution)

```
┌───────────────────────────────────────────────────┐
│ ▼ Discovered Trends (10)                    [▲▼]  │
├───────────────────────────────────────────────────┤
│  #1 Article Title...                    [SOURCE]  │
│      Summary text here...                         │
│      keywords: tag1, tag2, tag3                   │
│      [▶ Details] [+ Add to Queue]                 │
├───────────────────────────────────────────────────┤
│  #2 Article Title...                    [SOURCE]  │
│      ...                                          │
└───────────────────────────────────────────────────┘

┌───────────────────────────────────────────────────┐
│ ▼ Processed Threads (3)                     [▲▼]  │
├───────────────────────────────────────────────────┤
│  "First 10-15 words of the original thread..."    │
│      Status: PENDING | Source: @username          │
│      [▶ View Full Thread]                         │
├───────────────────────────────────────────────────┤
│  "Another thread preview text here..."            │
│      Status: TRANSLATED | Source: @another        │
│      [▶ View Full Thread]                         │
└───────────────────────────────────────────────────┘
```

### 4.1 Collapsible Sections

- [ ] **Discovered Trends section** - Full-width, collapsible header
  - Click header to expand/collapse entire section
  - Show count in header: "Discovered Trends (10)"
  - When expanded: All trends displayed as rows (full width)

- [ ] **Processed Threads section** - Full-width, collapsible header
  - Click header to expand/collapse entire section
  - Show count in header: "Processed Threads (3)"
  - When expanded: All threads displayed as rows (full width)

### 4.2 Trend Row Display

Each trend row (full width) shows:
- [ ] Rank number (#1, #2, etc.)
- [ ] Title (clickable link to source)
- [ ] AI-generated summary
- [ ] Keywords as tags
- [ ] Source badge (right-aligned)
- [ ] Expandable "Details" section
- [ ] "Add to Queue" button

### 4.3 Thread Row Display (Preview Mode)

Each processed thread row shows:
- [ ] **Preview text**: First 10-15 words of the original thread
- [ ] **Status badge**: PENDING | TRANSLATED | APPROVED | PUBLISHED
- [ ] **Source**: @username who posted the thread
- [ ] **"View Full Thread" button**: Expands to show full content

### 4.4 Thread Expanded View

When "View Full Thread" is clicked:
- [ ] Original thread content (all tweets)
- [ ] Hebrew translation (if available)
- [ ] Side-by-side display (English LTR | Hebrew RTL)
- [ ] Action buttons: Translate, Edit, Approve, etc.

### Phase 4 Implementation Tasks

| Task | Priority | Status |
|------|----------|--------|
| Convert 2-column layout to 2-row layout | High | ⏳ Pending |
| Add collapsible section headers | High | ⏳ Pending |
| Implement trend rows (full width) | High | ⏳ Pending |
| Implement thread preview rows | High | ⏳ Pending |
| Add "View Full Thread" expansion | Medium | ⏳ Pending |
| Add section item counts in headers | Low | ⏳ Pending |
| Polish animations/transitions | Low | ⏳ Pending |

### Phase 4 Testing Plan

**Unit Tests:**
- [ ] Collapsible sections expand/collapse correctly
- [ ] Thread preview generates first 10-15 words
- [ ] Full thread expansion shows all content

**Browser Tests (MCP Chrome):**
- [ ] Home page loads with 2-row layout (not columns)
- [ ] Click "Discovered Trends" header - section expands/collapses
- [ ] Click "Processed Threads" header - section expands/collapses
- [ ] Trend rows display full-width with all elements
- [ ] Trend details expand comfortably (full width, not cramped)
- [ ] Thread preview shows first 10-15 words
- [ ] "View Full Thread" expands to show complete thread
- [ ] Hebrew translation visible in expanded thread view
- [ ] All interactions feel smooth (no page jumps)

---

## Future Considerations

### Keyboard Shortcuts (Deferred)

**Goal:** Quick actions for power users.

**Proposed Shortcuts (if implemented later):**
- `A` - Approve current article
- `R` - Reject current article
- `↑/↓` or `J/K` - Navigate between articles
- `Enter` - Open article details
- `/` - Focus search

**Note:** Streamlit has limited keyboard support. May require custom JavaScript injection.

---

## Technical Architecture

### Stack (Unchanged)
- **Frontend:** Streamlit (keeping current)
- **Backend:** Python + FastAPI API layer (new)
- **Database:** SQLite (unchanged)
- **AI:** OpenAI GPT-4o for summaries and translations

### New Components
```
src/
  api/                    # NEW: FastAPI for frontend-backend communication
    main.py
    routes/
      trends.py
  processor/
    summary_generator.py  # NEW: AI summary generation
```

### Database Changes (Already Applied)
```python
# Added to Trend model:
summary = Column(Text, nullable=True)           # AI-generated summary
keywords = Column(JSON, nullable=True)          # Extracted keywords
source_count = Column(Integer, default=1)       # Number of sources
related_trend_ids = Column(JSON, nullable=True) # Related articles
```

---

## Questions Resolved

| Question | Answer |
|----------|--------|
| Main pain points | Too much on screen, unclear status, too many clicks |
| Actions need fewer clicks | Thread translation, approve/reject, viewing details |
| Translation display | Side-by-side (English LTR, Hebrew RTL) |
| Default view | Trends list |
| Main workflows | Finding trends, thread translation |

---

**Document Version:** 3.0
**Last Updated:** 2026-02-02
**Status:** Phase 1, 2 & 3 Complete, Phase 4 In Planning
