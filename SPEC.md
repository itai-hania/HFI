# HFI Dashboard Improvements - Technical Specification

**Version:** 2.1
**Date:** 2026-02-01
**Status:** Ready for Implementation

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

## Problem Statement

The current HFI dashboard works but doesn't feel smooth or comfortable enough for regular use.

**User's Main Workflows:**
1. Finding trends (discover what's trending in FinTech)
2. Thread translation (fetch and translate X threads to Hebrew)

**Specific Pain Points Identified:**

### Layout Issues
- ❌ **Too much on screen** - Information overload, hard to focus
- ❌ **Status unclear** - Can't easily see what's pending/done/approved

### Too Many Clicks Required For
- ❌ **Translating threads** - The fetch → translate → review flow is clunky
- ❌ **Approving/rejecting** - Acting on individual articles
- ❌ **Viewing details** - Expanding to see full article content

**Default View:** Dashboard should open to **Trends list** (latest FinTech trends)

---

## Priority 1: AI Article Summaries

**Goal:** Quickly understand what each article is about without reading the full content.

**Implementation:**

1. **Summary Generation**
   - Use OpenAI GPT-4o to generate 1-2 sentence summaries
   - Generate in background (not blocking UI)
   - Store in database (`Trend.summary` field) - ✅ Already added to models.py

2. **Display in Dashboard**
   - Show summary below article title in the trends list
   - Truncate to 1-2 lines with "..." if too long
   - Show "Generating summary..." placeholder while processing

3. **Keywords & Context**
   - Extract keywords from article title
   - Show source count if article appears in multiple sources
   - Fields already added: `keywords`, `source_count`, `related_trend_ids`

**Backend Status:** ✅ Models updated, ✅ summary_generator.py created, ✅ API endpoints ready

**Remaining Work:**
- [ ] Integrate summary display into Streamlit dashboard
- [ ] Add "Generate Summaries" button or auto-generate on fetch
- [ ] Show keywords/context in UI

---

## Priority 2: UX Polish

**Goal:** Make the dashboard feel smooth and comfortable for daily use.

### 2.1 Reduce Information Overload
- Cleaner layout with less visual noise
- Show only essential info in list view (title, source, status, summary)
- Hide details until user clicks to expand
- Group related items logically

### 2.2 Clear Status Indicators
- Visual badges/colors for status: `Pending` | `Approved` | `Published`
- At-a-glance understanding of what needs attention
- Filter by status easily

### 2.3 Fewer Clicks for Common Actions
- **Approve/Reject:** Single click buttons visible on each item
- **View details:** Inline expansion (not separate page)
- **Thread translation:** Streamlined flow (paste URL → auto-fetch → translate button)

### 2.4 Default to Trends List
- Dashboard opens directly to latest trends
- No extra clicks to get to main content

---

## Priority 3: Thread Translation (Hebrew RTL)

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

- English column: LTR alignment (left)
- Hebrew column: RTL alignment (right)
- Easy to compare and verify translation quality

**Existing Code:** Translation logic in `src/processor/processor.py` (TranslationService)

---

## Priority 4: Keyboard Shortcuts (Low Priority)

**Goal:** Quick actions for power users.

**Proposed Shortcuts:**
- `A` - Approve current article
- `R` - Reject current article
- `↑/↓` or `J/K` - Navigate between articles
- `Enter` - Open article details
- `/` - Focus search

**Note:** Streamlit has limited keyboard support. May require custom JavaScript injection or accepting limitations.

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

## Implementation Plan

### Phase 1: AI Summaries (Current Focus)
- [ ] Wire up summary_generator.py to Streamlit
- [ ] Add summary display to trends list
- [ ] Test summary generation flow

### Phase 2: UX Polish
- [ ] Identify specific pain points (user feedback needed)
- [ ] Implement improvements iteratively
- [ ] Test for smoothness

### Phase 3: Thread Translation RTL
- [ ] Update translation display to use RTL for Hebrew
- [ ] Test with real threads
- [ ] Refine style matching

### Phase 4: Keyboard Shortcuts (If Time Permits)
- [ ] Research Streamlit keyboard support
- [ ] Implement what's feasible

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

**Document Version:** 2.1
**Last Updated:** 2026-02-01
**Status:** Ready for Implementation
