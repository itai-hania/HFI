# HFI Dashboard - Phase 2 Specification

**Version:** 2.0
**Date:** 2026-02-03
**Status:** Ready for Implementation

---

## Executive Summary

This specification outlines the next set of improvements for the HFI dashboard, focusing on **style-based translation** and **UX refinements**. The goal is to enable high-quality Hebrew rewrites that match the user's personal writing style.

**Key Priorities (in order):**

1. **Style Guide Overhaul** - Import Hebrew examples, few-shot prompting for style-matched translations
2. **Trend Management** - Delete/remove unwanted trends before processing
3. **UX Polish** - Auto-navigation and auto-scroll improvements

---

## Progress Summary

| Phase | Status | Completion |
|-------|--------|------------|
| Phase 1: UX Quick Wins | ✅ Complete | 100% (1.1 done, 1.2 removed) |
| Phase 2: Trend Management | ✅ Complete | 100% |
| Phase 3: Style Learning System | ✅ Complete | 100% |

---

## Phase 1: UX Quick Wins

**Goal:** Small improvements that make the dashboard more comfortable to use.

### 1.1 Auto-Navigate to Home After Fetch

**Current behavior:** After clicking "Fetch Trends", user stays on current tab and must manually navigate to Home to see results.

**Target behavior:** After fetch completes successfully, automatically switch to Home tab.

**Implementation:**
- [ ] Add `st.session_state` flag to track fetch completion
- [ ] After fetch completes, set navigation state to Home tab
- [ ] Use `st.rerun()` to trigger navigation

**Files to modify:**
- `src/dashboard/app.py`

### 1.2 Settings Danger Zone Auto-Scroll

**Status:** ❌ REMOVED - Streamlit's iframe isolation prevents reliable parent window scrolling.

**Original goal:** Auto-scroll to Danger Zone content when expander opens.

**Why removed:** `st.components.v1.html()` runs in an isolated iframe that cannot reliably scroll the parent Streamlit window. The complexity outweighs the minor UX benefit.

---

## Phase 2: Trend Management

**Goal:** Allow users to curate fetched trends by removing irrelevant articles.

### 2.1 Delete Trend Feature

**Current behavior:** All fetched trends remain visible; no way to remove unwanted ones.

**Target behavior:** Each trend card has a delete button that permanently removes it from the database.

**User flow:**
1. View trends on Home page
2. Click delete (trash icon) on unwanted trend
3. Trend is permanently removed from database
4. UI updates immediately (no page refresh needed)

**Implementation:**
- [ ] Add delete button to each trend card (trash icon, right-aligned)
- [ ] Create `delete_trend(trend_id)` function in database operations
- [ ] Immediate deletion (no confirmation dialog - faster workflow)
- [ ] Handle UI state update after deletion

**Database changes:**
- No schema changes needed (using existing DELETE operation)

**Files to modify:**
- `src/dashboard/app.py` (Home tab, trend card rendering)

### 2.2 Bulk Delete (Optional Enhancement)

**Potential future feature:**
- [ ] Select multiple trends with checkboxes
- [ ] "Delete Selected" button for bulk removal
- [ ] "Select All / Deselect All" toggle

---

## Phase 3: Style Learning System

**Goal:** Enable high-quality Hebrew translations that match the user's personal writing style.

### 3.1 Overview

**Current state:**
- `config/style.txt` contains mixed Hebrew/English text
- Translation uses generic style guidance
- Results don't consistently match user's voice

**Target state:**
- Import user's actual Hebrew content (X threads + local files)
- Store examples in structured format
- Use few-shot prompting with relevant examples
- Produce translations that are 100% Hebrew, 100% user's style

### 3.2 Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    Style Learning System                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────────┐     ┌──────────────┐     ┌──────────────┐    │
│  │  X Thread    │     │  Local File  │     │   Manual     │    │
│  │  Importer    │     │  Uploader    │     │   Entry      │    │
│  └──────┬───────┘     └──────┬───────┘     └──────┬───────┘    │
│         │                    │                    │             │
│         └────────────────────┼────────────────────┘             │
│                              ▼                                   │
│                    ┌──────────────────┐                         │
│                    │  Style Examples  │                         │
│                    │    Database      │                         │
│                    │  (SQLite table)  │                         │
│                    └────────┬─────────┘                         │
│                             │                                    │
│                             ▼                                    │
│                    ┌──────────────────┐                         │
│                    │   Translation    │                         │
│                    │    Service       │                         │
│                    │  (Few-shot GPT)  │                         │
│                    └──────────────────┘                         │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### 3.3 Data Model

**New table: `style_examples`**

```python
class StyleExample(Base):
    __tablename__ = 'style_examples'

    id = Column(Integer, primary_key=True)
    content = Column(Text, nullable=False)          # Hebrew text
    source_type = Column(String(50))                # 'x_thread', 'local_file', 'manual'
    source_url = Column(String(500), nullable=True) # Original URL if from X
    topic_tags = Column(JSON, nullable=True)        # ['fintech', 'crypto', 'banking']
    word_count = Column(Integer)                    # For selection/filtering
    created_at = Column(DateTime, default=datetime.utcnow)
    is_active = Column(Boolean, default=True)       # Soft delete capability
```

### 3.4 Import Methods

#### 3.4.1 X Thread Importer

**User flow:**
1. Go to Settings > Style Guide
2. Click "Import from X"
3. Paste thread URL (e.g., `https://x.com/username/status/123456789`)
4. System scrapes thread content
5. Preview extracted Hebrew text
6. Confirm to add to style examples

**Implementation:**
- [ ] Add "Import from X" section in Settings
- [ ] URL input field with "Fetch" button
- [ ] Reuse existing `TwitterScraper.fetch_thread()` method
- [ ] Filter to keep only Hebrew content
- [ ] Preview modal before saving
- [ ] Save to `style_examples` table

#### 3.4.2 Local File Uploader

**User flow:**
1. Go to Settings > Style Guide
2. Click "Upload File"
3. Select `.txt` or `.md` file containing Hebrew content
4. System parses and previews content
5. Confirm to add to style examples

**Supported formats:**
- Plain text (`.txt`)
- Markdown (`.md`)
- Future: Word documents (`.docx`)

**Implementation:**
- [ ] Add file uploader widget (`st.file_uploader`)
- [ ] Parse uploaded content
- [ ] Validate Hebrew content (>50% Hebrew characters)
- [ ] Preview before saving
- [ ] Save to `style_examples` table

#### 3.4.3 Manual Entry (Optional)

**User flow:**
1. Go to Settings > Style Guide
2. Click "Add Manual Example"
3. Paste Hebrew text in textarea
4. Topic tags auto-extracted (can be edited)
5. Save to examples

#### 3.4.4 Auto Topic Tagging

**Behavior:** When importing any style example, the system automatically extracts topic tags using GPT-4o analysis of the Hebrew content.

**Implementation:**
- [ ] Create `extract_topic_tags(content: str) -> List[str]` function
- [ ] Call GPT-4o with prompt to identify 2-5 topic tags
- [ ] Predefined tag vocabulary: `fintech`, `crypto`, `banking`, `payments`, `investing`, `regulation`, `startups`, `AI`, `blockchain`, etc.
- [ ] User can edit/add/remove tags after auto-extraction

### 3.5 Style Examples Management UI

**Features:**
- [ ] View all stored examples (paginated list)
- [ ] Search/filter by topic tags
- [ ] Edit existing examples
- [ ] Delete examples (soft delete)
- [ ] View example statistics (count, total words, topics)
- [ ] Export all examples to JSON for backup
- [ ] Soft limit warning at 100+ examples (allow more, but show notice)

**UI Layout:**
```
┌─────────────────────────────────────────────────────────────┐
│ Style Guide                                    [+ Import ▼] │
├─────────────────────────────────────────────────────────────┤
│ Statistics: 47 examples | 12,450 words | Topics: 8         │
├─────────────────────────────────────────────────────────────┤
│ ┌─────────────────────────────────────────────────────────┐ │
│ │ Example #1                              [Edit] [Delete] │ │
│ │ Source: X Thread | Words: 280 | Tags: fintech, payments │ │
│ │ "הטכנולוגיה הפיננסית משנה את הדרך שבה אנחנו..."       │ │
│ └─────────────────────────────────────────────────────────┘ │
│ ┌─────────────────────────────────────────────────────────┐ │
│ │ Example #2                              [Edit] [Delete] │ │
│ │ Source: Local File | Words: 450 | Tags: crypto          │ │
│ │ "הביטקוין חצה את רף ה-100 אלף דולר..."                │ │
│ └─────────────────────────────────────────────────────────┘ │
│                        [Load More]                          │
└─────────────────────────────────────────────────────────────┘
```

### 3.6 Translation Integration

**Current translation flow:**
```
English Content → GPT-4o (generic prompt) → Hebrew Output
```

**New translation flow:**
```
English Content → Select 3-5 Examples → GPT-4o (few-shot prompt) → Hebrew Output
```

#### 3.6.1 Example Selection Strategy

**Phase 1 (Simple - Current Implementation):**
- Select 3-5 most recent examples
- Include diverse word counts (short + long examples)
- Prioritize examples with matching topic tags if available

**Phase 2 (RAG Upgrade - Future):**
- Embed all examples using OpenAI embeddings
- For each translation, embed source content
- Retrieve top 3-5 most semantically similar examples
- This provides contextually relevant style matching

#### 3.6.2 Few-Shot Prompt Structure

```
You are a Hebrew content writer. Your task is to translate English fintech content
into Hebrew while matching a specific writing style.

## Style Examples (learn from these):

Example 1:
{example_1_content}

Example 2:
{example_2_content}

Example 3:
{example_3_content}

## Glossary (use these translations for financial terms):
{glossary_json}

## Instructions:
1. Translate the following English content to Hebrew
2. Match the tone, sentence structure, and vocabulary from the style examples
3. Use the glossary for financial/technical terms
4. Output MUST be 100% Hebrew (no English words except brand names)
5. Maintain the same level of formality as the examples

## Content to translate:
{english_content}

## Hebrew translation:
```

### 3.7 Implementation Tasks

| Task | Priority | Phase | Status |
|------|----------|-------|--------|
| Create `style_examples` database table | High | 3 | ✅ Complete |
| Build X Thread importer UI | High | 3 | ✅ Complete |
| Build local file uploader | High | 3 | ✅ Complete |
| Create style examples list/management UI | Medium | 3 | ✅ Complete |
| Integrate few-shot prompting in TranslationService | High | 3 | ✅ Complete |
| Add example selection logic | High | 3 | ✅ Complete |
| Update translation prompt template | High | 3 | ✅ Complete |
| Add auto topic tag extraction (GPT-4o) | High | 3 | ✅ Complete |
| Add statistics dashboard for style examples | Low | 3 | ✅ Complete |
| Add export to JSON feature | Medium | 3 | ✅ Complete |
| Add soft limit warning (100+ examples) | Low | 3 | ✅ Complete |

### 3.8 Future: RAG Upgrade Path

When ready to upgrade from few-shot to RAG:

**Additional components needed:**
1. **Vector database** - ChromaDB or Pinecone for embeddings storage
2. **Embedding generation** - OpenAI `text-embedding-3-small` for style examples
3. **Retrieval logic** - Query similar examples based on source content
4. **Caching** - Cache embeddings to reduce API calls

**Migration path:**
1. Keep `style_examples` table as-is
2. Add `embedding` column (BLOB or store in separate vector DB)
3. Create embedding generation script for existing examples
4. Update `TranslationService` to use retrieval instead of random selection
5. A/B test results vs. few-shot approach

**Estimated additional complexity:**
- New dependency: `chromadb` or similar
- Embedding generation on example import
- Retrieval query on each translation
- ~500 lines of additional code

---

## Technical Notes

### Files to Create

```
src/
  common/
    models.py          # Add StyleExample model
  processor/
    style_manager.py   # NEW: Style example CRUD operations
  dashboard/
    app.py             # Update Settings tab
```

### Dependencies

**Current (no changes needed for Phase 1-2):**
- streamlit
- openai
- sqlalchemy

**Phase 3 additions:**
- None for few-shot approach

**Future RAG additions:**
- chromadb (or alternative vector DB)
- numpy (for embedding operations)

---

## Testing Plan

### Phase 1: UX Quick Wins

**Manual tests:**
- [ ] Fetch trends → verify auto-navigation to Home
- [ ] Open Danger Zone expander → verify auto-scroll

### Phase 2: Trend Management

**Unit tests:**
- [ ] `delete_trend()` removes trend from database
- [ ] Verify cascade behavior (if any related records)

**Manual tests:**
- [ ] Delete trend → verify removal from UI
- [ ] Delete trend → verify database record gone

### Phase 3: Style Learning

**Unit tests:**
- [ ] Style example CRUD operations
- [ ] Hebrew content validation
- [ ] Few-shot prompt generation
- [ ] Example selection logic
- [ ] Auto topic tag extraction
- [ ] Export to JSON format

**Manual tests (Browser - MCP):**
- [ ] Import X thread → verify content extracted
- [ ] Upload local file → verify content saved
- [ ] Verify topic tags auto-extracted on import
- [ ] View style examples list
- [ ] Delete style example
- [ ] Export examples → verify JSON file downloads
- [ ] Translate with style examples → verify output quality
- [ ] Verify soft limit warning appears at 100+ examples

**Quality tests:**
- [ ] Compare translations with/without style examples
- [ ] Verify output is 100% Hebrew
- [ ] Verify style matches examples (subjective evaluation)

---

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Trend deletion | Immediate (no confirmation) | Faster workflow, user can re-fetch if needed |
| Topic tagging | Auto-extract from content | GPT-4o analyzes Hebrew text and suggests tags automatically |
| Example limits | Soft limit at 100+ | Show warning but allow unlimited storage |
| Backup/Export | Yes, export to JSON | Enable backup and portability of style examples |

---

## Document History

| Version | Date | Changes |
|---------|------|---------|
| 2.0 | 2026-02-03 | Initial specification |
| 2.1 | 2026-02-03 | Added design decisions (immediate delete, auto-tagging, soft limits, export) |
| 2.2 | 2026-02-04 | Phase 3 implementation complete (style learning system) |

---

**Last Updated:** 2026-02-04
**Status:** All Phases Complete
