# HFI Dashboard Improvements - Technical Specification

**Version:** 2.2
**Date:** 2026-02-01
**Status:** Phase 1 Complete, Phase 2 In Progress

---

## Executive Summary

This specification outlines improvements to the Hebrew FinTech Informant (HFI) dashboard. The goal is to make the existing Streamlit dashboard **smoother and more comfortable to use** without a complete redesign.

**Key Priorities (in order):**

1. **AI Article Summaries** - Auto-generate summaries to quickly understand what each article is about
2. **UX Polish** - Smoother interactions, better visual feedback, more comfortable workflow
3. **Thread Translation** - Full Hebrew rewrite of threads in your style (RTL display)
4. **Keyboard Shortcuts** - (Low priority) Quick actions for power users

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
| Phase 3: Thread Translation RTL | 🔄 Next | 0% |
| Phase 4: Keyboard Shortcuts | ⏳ Pending | 0% |

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

## Phase 3: Thread Translation (Hebrew RTL)

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

### Phase 3 Testing Plan

**Unit Tests:**
- [ ] Translation service produces Hebrew output
- [ ] Thread structure preserved in translation
- [ ] Glossary terms applied correctly

**Browser Tests (MCP Chrome):**
- [ ] Paste thread URL - verify fetch works
- [ ] Click translate - verify Hebrew appears
- [ ] Hebrew text displays RTL correctly
- [ ] Side-by-side view renders properly

---

## Phase 4: Keyboard Shortcuts (Low Priority)

**Goal:** Quick actions for power users.

**Proposed Shortcuts:**
- `A` - Approve current article
- `R` - Reject current article
- `↑/↓` or `J/K` - Navigate between articles
- `Enter` - Open article details
- `/` - Focus search

**Note:** Streamlit has limited keyboard support. May require custom JavaScript injection or accepting limitations.

### Phase 4 Testing Plan

**Browser Tests (MCP Chrome):**
- [ ] Press `A` on focused item - verify approval
- [ ] Press arrow keys - verify navigation
- [ ] Visual feedback when action taken

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

**Document Version:** 2.3
**Last Updated:** 2026-02-01
**Status:** Phase 1 & 2 Complete, Phase 3 Next
