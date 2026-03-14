# Clean Up Stale WSJ/Calcalist/Globes/Times of Israel References

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Remove all stale references to dead RSS feed sources (WSJ, Calcalist, Globes, Times of Israel) and add missing mappings for the replacement sources (CNBC, Seeking Alpha, Investing.com, Google News Israel) across docs, dashboard, API, and frontend.

**Architecture:** Pure find-and-replace cleanup across 6 files. No functional logic changes — only documentation text, badge mappings, source maps, and a hardcoded constant in the frontend. The `TrendSource` enum in `models.py` is NOT touched (backward compat with existing DB rows).

**Tech Stack:** Python, TypeScript/React, Markdown

---

### Task 1: Update README.md — replace stale source lists

**Files:**
- Modify: `README.md` (lines 38, 415, 453, 540)

**Step 1: Replace line 38 source list**

Replace:
```
1. **Multi-Source Scraping** - Monitors X (Twitter) + RSS feeds (Yahoo Finance, WSJ, TechCrunch Fintech, Bloomberg)
```
With:
```
1. **Multi-Source Scraping** - Monitors X (Twitter) + RSS feeds (Yahoo Finance, CNBC, Bloomberg, MarketWatch, Seeking Alpha, TechCrunch Fintech, Investing.com, Google News Israel)
```

**Step 2: Replace line 415 workflow diagram**

Replace:
```
   ├─ News Scraper: Fetch from RSS feeds (Yahoo Finance, WSJ, TechCrunch, Bloomberg)
```
With:
```
   ├─ News Scraper: Fetch from RSS feeds (Yahoo Finance, CNBC, Bloomberg, MarketWatch, Seeking Alpha, TechCrunch, Investing.com, Google News Israel)
```

**Step 3: Replace line 453 features list**

Replace:
```
- ✅ Multi-source RSS feed aggregation (Yahoo Finance, WSJ, TechCrunch Fintech, Bloomberg, MarketWatch)
```
With:
```
- ✅ Multi-source RSS feed aggregation (Yahoo Finance, CNBC, Bloomberg, MarketWatch, Seeking Alpha, TechCrunch Fintech, Investing.com, Google News Israel)
```

**Step 4: Replace line 540 roadmap**

Replace:
```
- [x] News scraper with multi-source parallel RSS feeds (Yahoo Finance, WSJ, TechCrunch, Bloomberg, MarketWatch)
```
With:
```
- [x] News scraper with multi-source parallel RSS feeds (Yahoo Finance, CNBC, Bloomberg, MarketWatch, Seeking Alpha, TechCrunch, Investing.com, Google News Israel)
```

**Step 5: Commit**

```bash
git add README.md
git commit -m "docs: update README source lists to match current RSS feeds"
```

---

### Task 2: Update dashboard helpers.py — badge map for new sources

**Files:**
- Modify: `src/dashboard/helpers.py` (lines 14-25)
- Modify: `tests/test_dashboard_helpers.py` (lines 21-28)

**Step 1: Update the test to expect the new source mappings**

In `tests/test_dashboard_helpers.py`, replace the parametrize list in `TestGetSourceBadgeClass`:

```python
    @pytest.mark.parametrize("source,expected", [
        ("Yahoo Finance", "source-yahoo-finance"),
        ("CNBC", "source-cnbc"),
        ("TechCrunch", "source-techcrunch"),
        ("Bloomberg", "source-bloomberg"),
        ("MarketWatch", "source-marketwatch"),
        ("Seeking Alpha", "source-seeking-alpha"),
        ("Investing.com", "source-investingcom"),
        ("Google News Israel", "source-google-news-israel"),
        ("Manual", "source-manual"),
        ("X", "source-x"),
        # Legacy sources still in map for DB backward compat
        ("WSJ", "source-wsj"),
        ("Calcalist", "source-calcalist"),
        ("Globes", "source-globes"),
        ("Times of Israel", "source-times-of-israel"),
    ])
```

**Step 2: Run the test to verify it fails**

Run: `pytest tests/test_dashboard_helpers.py::TestGetSourceBadgeClass -v`
Expected: FAIL — new sources (CNBC, Seeking Alpha, etc.) not in `_SOURCE_BADGE_MAP` yet

**Step 3: Update `_SOURCE_BADGE_MAP` in helpers.py**

Replace the existing `_SOURCE_BADGE_MAP` dict (lines 14-25) with:

```python
_SOURCE_BADGE_MAP = {
    'Yahoo Finance': 'source-yahoo-finance',
    'CNBC': 'source-cnbc',
    'TechCrunch': 'source-techcrunch',
    'Bloomberg': 'source-bloomberg',
    'MarketWatch': 'source-marketwatch',
    'Seeking Alpha': 'source-seeking-alpha',
    'Investing.com': 'source-investingcom',
    'Google News Israel': 'source-google-news-israel',
    'Manual': 'source-manual',
    'X': 'source-x',
    # Legacy sources kept for backward compatibility with existing DB rows
    'WSJ': 'source-wsj',
    'Calcalist': 'source-calcalist',
    'Globes': 'source-globes',
    'Times of Israel': 'source-times-of-israel',
}
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_dashboard_helpers.py::TestGetSourceBadgeClass -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/dashboard/helpers.py tests/test_dashboard_helpers.py
git commit -m "feat(dashboard): add badge mappings for new RSS feed sources"
```

---

### Task 3: Update dashboard styles.py — CSS classes for new sources

**Files:**
- Modify: `src/dashboard/styles.py` (after line 354)

**Step 1: Add CSS classes for the 4 new sources**

After the existing `.source-x` line (line 355), add CSS for the new sources. Insert these lines between `.source-times-of-israel` and `.source-manual`:

Replace the full source badge CSS block (lines 346-355):
```css
    .source-yahoo-finance { background: rgba(34, 197, 94, 0.15); color: #4ADE80; border: 1px solid rgba(34, 197, 94, 0.3); }
    .source-wsj { background: rgba(59, 130, 246, 0.15); color: #60A5FA; border: 1px solid rgba(59, 130, 246, 0.3); }
    .source-techcrunch { background: rgba(34, 197, 94, 0.15); color: #4ADE80; border: 1px solid rgba(34, 197, 94, 0.3); }
    .source-bloomberg { background: rgba(59, 130, 246, 0.15); color: #60A5FA; border: 1px solid rgba(59, 130, 246, 0.3); }
    .source-marketwatch { background: rgba(255, 193, 7, 0.15); color: #FFC107; border: 1px solid rgba(255, 193, 7, 0.3); }
    .source-calcalist { background: rgba(6, 182, 212, 0.15); color: #22D3EE; border: 1px solid rgba(6, 182, 212, 0.3); }
    .source-globes { background: rgba(20, 184, 166, 0.15); color: #2DD4BF; border: 1px solid rgba(20, 184, 166, 0.3); }
    .source-times-of-israel { background: rgba(56, 189, 248, 0.15); color: #38BDF8; border: 1px solid rgba(56, 189, 248, 0.3); }
    .source-manual { background: rgba(155, 163, 174, 0.15); color: #9BA3AE; border: 1px solid rgba(155, 163, 174, 0.3); }
    .source-x { background: rgba(255, 255, 255, 0.1); color: #E4E6EA; border: 1px solid rgba(255, 255, 255, 0.2); }
```

With (adds 4 new, keeps all existing for backward compat):
```css
    .source-yahoo-finance { background: rgba(34, 197, 94, 0.15); color: #4ADE80; border: 1px solid rgba(34, 197, 94, 0.3); }
    .source-cnbc { background: rgba(0, 133, 204, 0.15); color: #33AAFF; border: 1px solid rgba(0, 133, 204, 0.3); }
    .source-techcrunch { background: rgba(34, 197, 94, 0.15); color: #4ADE80; border: 1px solid rgba(34, 197, 94, 0.3); }
    .source-bloomberg { background: rgba(59, 130, 246, 0.15); color: #60A5FA; border: 1px solid rgba(59, 130, 246, 0.3); }
    .source-marketwatch { background: rgba(255, 193, 7, 0.15); color: #FFC107; border: 1px solid rgba(255, 193, 7, 0.3); }
    .source-seeking-alpha { background: rgba(255, 120, 0, 0.15); color: #FF9F43; border: 1px solid rgba(255, 120, 0, 0.3); }
    .source-investingcom { background: rgba(220, 53, 69, 0.15); color: #FF6B7A; border: 1px solid rgba(220, 53, 69, 0.3); }
    .source-google-news-israel { background: rgba(66, 133, 244, 0.15); color: #69A5FF; border: 1px solid rgba(66, 133, 244, 0.3); }
    .source-manual { background: rgba(155, 163, 174, 0.15); color: #9BA3AE; border: 1px solid rgba(155, 163, 174, 0.3); }
    .source-x { background: rgba(255, 255, 255, 0.1); color: #E4E6EA; border: 1px solid rgba(255, 255, 255, 0.2); }
    /* Legacy sources — kept for existing DB rows */
    .source-wsj { background: rgba(59, 130, 246, 0.15); color: #60A5FA; border: 1px solid rgba(59, 130, 246, 0.3); }
    .source-calcalist { background: rgba(6, 182, 212, 0.15); color: #22D3EE; border: 1px solid rgba(6, 182, 212, 0.3); }
    .source-globes { background: rgba(20, 184, 166, 0.15); color: #2DD4BF; border: 1px solid rgba(20, 184, 166, 0.3); }
    .source-times-of-israel { background: rgba(56, 189, 248, 0.15); color: #38BDF8; border: 1px solid rgba(56, 189, 248, 0.3); }
```

**Step 2: Commit**

```bash
git add src/dashboard/styles.py
git commit -m "style(dashboard): add CSS badge classes for new RSS feed sources"
```

---

### Task 4: Update dashboard content.py — source_map in Fetch All Trends

**Files:**
- Modify: `src/dashboard/views/content.py` (lines 518-527)

**Step 1: Replace the `source_map` dict**

Replace:
```python
                    source_map = {
                        'Yahoo Finance': TrendSource.YAHOO_FINANCE,
                        'WSJ': TrendSource.WSJ,
                        'TechCrunch': TrendSource.TECHCRUNCH,
                        'Bloomberg': TrendSource.BLOOMBERG,
                        'MarketWatch': TrendSource.MARKETWATCH,
                        'Calcalist': TrendSource.CALCALIST,
                        'Globes': TrendSource.GLOBES,
                        'Times of Israel': TrendSource.TIMES_OF_ISRAEL,
                    }
```

With:
```python
                    source_map = {
                        'Yahoo Finance': TrendSource.YAHOO_FINANCE,
                        'CNBC': TrendSource.CNBC,
                        'TechCrunch': TrendSource.TECHCRUNCH,
                        'Bloomberg': TrendSource.BLOOMBERG,
                        'MarketWatch': TrendSource.MARKETWATCH,
                        'Seeking Alpha': TrendSource.SEEKING_ALPHA,
                        'Investing.com': TrendSource.INVESTING_COM,
                        'Google News Israel': TrendSource.GOOGLE_NEWS_ISRAEL,
                    }
```

**Step 2: Commit**

```bash
git add src/dashboard/views/content.py
git commit -m "fix(dashboard): update source_map to match current RSS feed sources"
```

---

### Task 5: Update API schemas and routes — remove WSJ from examples

**Files:**
- Modify: `src/api/schemas/trend.py` (line 20)
- Modify: `src/api/routes/trends.py` (line 25)

**Step 1: Update schema docstring**

In `src/api/schemas/trend.py`, replace:
```python
    source: str = Field(..., description="Source platform (Yahoo Finance, WSJ, etc.)")
```
With:
```python
    source: str = Field(..., description="Source platform (Yahoo Finance, CNBC, Bloomberg, etc.)")
```

**Step 2: Update route docstring**

In `src/api/routes/trends.py`, replace:
```python
    source: Optional[str] = Query(None, description="Filter by source (Yahoo Finance, WSJ, etc.)"),
```
With:
```python
    source: Optional[str] = Query(None, description="Filter by source (Yahoo Finance, CNBC, Bloomberg, etc.)"),
```

**Step 3: Commit**

```bash
git add src/api/schemas/trend.py src/api/routes/trends.py
git commit -m "docs(api): update source examples in API schemas and routes"
```

---

### Task 6: Update frontend BriefCard.tsx — fix ISRAEL_SOURCES constant

**Files:**
- Modify: `frontend/src/components/dashboard/BriefCard.tsx` (line 13)

**Step 1: Replace the hardcoded ISRAEL_SOURCES array**

Replace:
```typescript
const ISRAEL_SOURCES = ["Calcalist", "Globes", "Times of Israel"];
```
With:
```typescript
const ISRAEL_SOURCES = ["Investing.com", "Google News Israel"];
```

**Step 2: Commit**

```bash
git add frontend/src/components/dashboard/BriefCard.tsx
git commit -m "fix(frontend): update ISRAEL_SOURCES to match current feed sources"
```

---

### Task 7: Run full test suite to verify nothing is broken

**Step 1: Run all tests**

Run: `pytest tests/ -v`
Expected: All tests pass (no regressions)

**Step 2: Squash or verify all commits**

Verify `git log --oneline` shows all 6 commits from this plan.
