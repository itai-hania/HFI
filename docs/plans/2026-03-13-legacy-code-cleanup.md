# Legacy Code Cleanup — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Remove all unused, deprecated, and dead code identified by a full codebase audit — reducing maintenance burden and confusion.

**Architecture:** Methodical removal in dependency order: archive first (zero risk), then dead functions/imports, then deprecated services + infra, then stale docs. Each task is independently commitable and testable.

**Tech Stack:** Python, pytest, git

---

## Audit Summary

The scan found **5 categories** of legacy code totaling ~50+ files and ~4,000+ lines:

| Category | Items | Risk |
|----------|-------|------|
| A. Archive directory | 22 files, entire `archive/dashboard-v1/` | Zero — no imports |
| B. Dead code in `src/` | 17 dead functions/imports/schemas across 6 files | Low — unused code paths |
| C. Misplaced/fake test scripts | 3 files in wrong locations | Low — not collected by pytest |
| D. Deprecated infra & scripts | `k8s/` (12 files), `docker-build.sh`, `docker-validate.sh`, stale `tools/` scripts | Medium — referenced by `start_services.py` |
| E. Stale documentation | 7 completed/dead plan docs | Zero — no code impact |

---

## Task 1: Delete the `archive/` directory

**Why:** 22 files, zero imports from anywhere in the codebase. It's a frozen snapshot of `src/dashboard/` before the v2 refactor. The `DEPRECATED.md` note inside `src/dashboard/` already documents its status.

**Files:**
- Delete: `archive/dashboard-v1/` (entire directory tree — 22 files)

**Step 1: Verify zero imports from archive**

Run: `grep -r "from archive" src/ tests/ tools/ --include="*.py" | head -5`
Expected: No output (zero matches)

Run: `grep -r "import archive" src/ tests/ tools/ --include="*.py" | head -5`
Expected: No output (zero matches)

**Step 2: Delete the directory**

```bash
rm -rf archive/
```

**Step 3: Run tests to confirm no breakage**

Run: `pytest tests/ -x -q`
Expected: All 468 tests pass

**Step 4: Commit**

```bash
git add -A archive/
git commit -m "chore: remove archive/dashboard-v1 — zero imports, pure dead snapshot"
```

---

## Task 2: Remove dead functions from `src/common/models.py`

**Why:** Three query helper functions (`get_tweets_by_status`, `get_recent_trends`, `update_tweet_status`) are never called in production code. They are only referenced by tests written specifically to cover them. The application does all DB operations inline via ORM.

**Files:**
- Modify: `src/common/models.py` — remove `get_tweets_by_status()`, `get_recent_trends()`, `update_tweet_status()`
- Modify: `src/common/__init__.py` — remove these from re-exports
- Modify: `tests/test_models.py` — remove tests for the deleted functions
- Modify: `tests/test_dashboard.py` — remove any calls to `update_tweet_status()`

**Step 1: Identify exact locations**

Search for the three function definitions in `src/common/models.py` and their test usages.

Run: `grep -n "def get_tweets_by_status\|def get_recent_trends\|def update_tweet_status" src/common/models.py`

Run: `grep -rn "get_tweets_by_status\|get_recent_trends\|update_tweet_status" tests/ src/ --include="*.py"`

**Step 2: Remove the functions from `models.py`**

Delete `get_tweets_by_status()`, `get_recent_trends()`, and `update_tweet_status()` from `src/common/models.py`.

**Step 3: Remove from `__init__.py` re-exports**

Remove the three names from `src/common/__init__.py`'s import and `__all__` list.

**Step 4: Remove corresponding tests**

Remove test functions that call the deleted helpers from `tests/test_models.py` and `tests/test_dashboard.py`.

**Step 5: Run tests**

Run: `pytest tests/ -x -q`
Expected: Pass count drops by the number of removed tests; zero failures.

**Step 6: Commit**

```bash
git add src/common/models.py src/common/__init__.py tests/test_models.py tests/test_dashboard.py
git commit -m "chore: remove dead query helpers — get_tweets_by_status, get_recent_trends, update_tweet_status"
```

---

## Task 3: Remove dead code from `src/scraper/scraper.py`

**Why:** `fetch_thread()` was superseded by `fetch_raw_thread()`. Its only helper `_scroll_and_collect()` is transitively dead. The `async def main()` demo block at the bottom is a dev stub with no callers.

**Files:**
- Modify: `src/scraper/scraper.py` — remove `fetch_thread()`, `_scroll_and_collect()`, and the standalone `async def main()` block at the bottom

**Step 1: Verify no production callers for `fetch_thread()`**

Run: `grep -rn "fetch_thread\b" src/ tests/ --include="*.py" | grep -v "fetch_raw_thread" | grep -v "def fetch_thread"`

Expected: Only internal self-references within `scraper.py` itself (inside `main()` demo block). No external callers.

**Step 2: Verify `_scroll_and_collect()` is only called from `fetch_thread()`**

Run: `grep -rn "_scroll_and_collect\b" src/ tests/ --include="*.py" | grep -v "_scroll_and_collect_all"`

Expected: Only references within `scraper.py` — inside `fetch_thread()` and its own definition.

**Step 3: Remove the three dead blocks**

1. Remove the `fetch_thread()` method
2. Remove the `_scroll_and_collect()` method
3. Remove the standalone `async def main()` block and its `if __name__ == "__main__"` guard at the end of the file

**Step 4: Run tests**

Run: `pytest tests/test_scraper.py tests/test_scraper_page.py -x -q`
Expected: All scraper tests pass

Run: `pytest tests/ -x -q`
Expected: Full suite passes

**Step 5: Commit**

```bash
git add src/scraper/scraper.py
git commit -m "chore: remove dead fetch_thread, _scroll_and_collect, and main() demo from scraper"
```

---

## Task 4: Clean dead code from `src/processor/`

**Why:** Multiple dead imports, unreachable code paths, and unused methods.

**Files:**
- Modify: `src/processor/processor.py` — fix dead imports, remove unreachable code, remove unused methods
- Modify: `src/processor/alert_detector.py` — remove dead `_already_alerted()` method
- Delete: `src/processor/test_processor.py` — misplaced legacy manual test script

**Step 1: Fix dead imports in `processor.py`**

Remove `build_glossary_section` and `StyleExample` from the import lines — they are imported but never used in this file.

**Step 2: Remove unreachable fallback returns in `processor.py`**

Remove:
- The `return text  # Fallback to original` line after the `except` block in `translate_and_rewrite()` (line ~348)
- The `return combined_text  # Fallback` line after the `except` block in `translate_thread_consolidated()` (line ~494)

These lines come after `except` blocks that always `raise`, making them unreachable.

**Step 3: Remove unused method `translate_long_text()` from `TranslationService`**

Verify zero callers:
Run: `grep -rn "translate_long_text" src/ tests/ --include="*.py"`
Expected: Only its own definition (zero external callers)

Delete the method.

**Step 4: Remove unused method `validate_hebrew_output()` from `TranslationService`**

This is a thin wrapper (`return validate_hebrew_output(text)`) that is never called — all callers use the `prompt_builder.validate_hebrew_output()` directly.

Verify zero callers:
Run: `grep -rn "\.validate_hebrew_output\b" src/ tests/ --include="*.py"`
Expected: Only its own definition

Delete the method.

**Step 5: Remove dead `_already_alerted()` from `alert_detector.py`**

This was superseded by `_already_alerted_in_titles()` and `_load_recent_alert_fingerprints()`.

Verify zero callers:
Run: `grep -rn "_already_alerted\b" src/ --include="*.py" | grep -v "_already_alerted_in_titles" | grep -v "_load_recent_alert_fingerprints"`
Expected: Only its own definition

Delete the method.

**Step 6: Delete misplaced `src/processor/test_processor.py`**

This is a standalone manual test script (uses `print()`, `sys.exit()`, `if __name__`), not a pytest file, not collected by pytest, not imported anywhere.

```bash
rm src/processor/test_processor.py
```

**Step 7: Run tests**

Run: `pytest tests/ -x -q`
Expected: All tests pass (count should stay the same — we didn't remove any pytest tests)

**Step 8: Commit**

```bash
git add src/processor/processor.py src/processor/alert_detector.py
git rm src/processor/test_processor.py
git commit -m "chore: remove dead imports, unreachable code, unused methods from processor"
```

---

## Task 5: Remove dead API schemas and dead route helper

**Why:** `TrendCreate` and `TrendUpdate` schemas are defined but no API endpoint uses them (no POST/PUT trend endpoints exist). `_backfill_summaries_task()` in summaries routes is defined but never called.

**Files:**
- Modify: `src/api/schemas/trend.py` — remove `TrendCreate`, `TrendUpdate` classes
- Modify: `src/api/schemas/__init__.py` — remove from re-exports
- Modify: `src/api/routes/summaries.py` — remove `_backfill_summaries_task()`

**Step 1: Verify zero usage of dead schemas**

Run: `grep -rn "TrendCreate\|TrendUpdate" src/ tests/ --include="*.py"`
Expected: Only definition and re-export lines (no route or service usage)

**Step 2: Verify zero callers of `_backfill_summaries_task`**

Run: `grep -rn "_backfill_summaries_task" src/ tests/ --include="*.py"`
Expected: Only its own definition

**Step 3: Remove dead schemas from `trend.py`**

Delete the `TrendCreate` and `TrendUpdate` class definitions.

**Step 4: Remove from `schemas/__init__.py`**

Remove `TrendCreate` and `TrendUpdate` from the import and `__all__` list.

**Step 5: Remove `_backfill_summaries_task()` from `summaries.py`**

Delete the function.

**Step 6: Run tests**

Run: `pytest tests/ -x -q`
Expected: All tests pass

**Step 7: Commit**

```bash
git add src/api/schemas/trend.py src/api/schemas/__init__.py src/api/routes/summaries.py
git commit -m "chore: remove dead TrendCreate/TrendUpdate schemas and unused _backfill_summaries_task"
```

---

## Task 6: Move misplaced test scripts to `tools/`

**Why:** `tests/test_news_live.py` and `tests/test_thread_media_download.py` are NOT pytest tests — they contain no `def test_*` functions, use `sys.exit()` and `main()`, and require live infrastructure. They belong in `tools/` per project conventions.

**Files:**
- Move: `tests/test_news_live.py` → `tools/test_news_live.py`
- Move: `tests/test_thread_media_download.py` → `tools/test_thread_media_download.py`

**Step 1: Verify these are not collected by pytest**

Run: `pytest tests/test_news_live.py --collect-only 2>&1 | head -5`
Expected: "no tests ran" or collection warning (no `test_` functions)

Run: `pytest tests/test_thread_media_download.py --collect-only 2>&1 | head -5`
Expected: Same — no tests collected

**Step 2: Move to tools/**

```bash
git mv tests/test_news_live.py tools/test_news_live.py
git mv tests/test_thread_media_download.py tools/test_thread_media_download.py
```

**Step 3: Run tests to confirm no impact**

Run: `pytest tests/ -x -q`
Expected: Same pass count (these files contributed 0 tests)

**Step 4: Commit**

```bash
git commit -m "chore: move non-pytest scripts from tests/ to tools/"
```

---

## Task 7: Clean up stale `tools/` scripts

**Why:** `verify_changes.py` is a one-off debugging script that syntax-checks the deprecated dashboard and doesn't know about v2 services. `scrape_hebrew_threads.py` has a hardcoded dead output path from a different machine and its purpose is superseded by the DB-backed `style_examples` system.

**Files:**
- Delete: `tools/verify_changes.py` — stale one-off
- Delete: `tools/scrape_hebrew_threads.py` — one-off with dead hardcoded path, superseded by StyleManager

**Step 1: Verify zero imports**

Run: `grep -rn "verify_changes\|scrape_hebrew_threads" src/ tests/ --include="*.py"`
Expected: No imports from any production or test code

**Step 2: Delete the scripts**

```bash
git rm tools/verify_changes.py
git rm tools/scrape_hebrew_threads.py
```

**Step 3: Run tests**

Run: `pytest tests/ -x -q`
Expected: All pass (no code depended on these scripts)

**Step 4: Commit**

```bash
git commit -m "chore: remove stale one-off scripts — verify_changes.py, scrape_hebrew_threads.py"
```

---

## Task 8: Delete superseded `k8s/` directory

**Why:** CLAUDE.md explicitly states "Legacy K8s manifests in k8s/ (superseded)". Production uses Azure VM + Caddy + GitHub Actions CI/CD. The k8s manifests are frozen at a pre-v2 snapshot — they deploy the deprecated Streamlit dashboard and don't know about `api`, `frontend`, or `telegram-bot` services. 12 files, ~2,669 lines.

**Files:**
- Delete: `k8s/` (entire directory — 12 files)

**Step 1: Verify no runtime dependency on k8s/**

Run: `grep -rn "k8s/" src/ tests/ tools/ docker-compose.yml start_services.py --include="*.py" --include="*.yml" --include="*.sh"`
Expected: Only documentation references (CLAUDE.md, README.md) — no runtime imports

**Step 2: Delete the directory**

```bash
rm -rf k8s/
```

**Step 3: Run tests**

Run: `pytest tests/ -x -q`
Expected: All pass

**Step 4: Commit**

```bash
git add -A k8s/
git commit -m "chore: remove superseded k8s/ manifests — production uses Azure VM + Caddy"
```

---

## Task 9: Delete stale Docker build/validate scripts

**Why:** `docker-build.sh` and `docker-validate.sh` were written for the pre-v2 three-service architecture (scraper, processor, dashboard). They build the deprecated Streamlit dashboard image, health-check port 8501, and know nothing about the actual v2 services (api, frontend, telegram-bot). They would not correctly build or validate the current stack if run. ~529 lines of misleading code.

**Files:**
- Delete: `docker-build.sh`
- Delete: `docker-validate.sh`

**Step 1: Verify no active CI/CD dependency**

Run: `grep -rn "docker-build.sh\|docker-validate.sh" .github/ docker-compose.yml start_services.py Makefile 2>/dev/null`
Expected: No matches in CI configs. `start_services.py` may reference `docker-build.sh` — that reference is part of the stale launcher (addressed in Task 10).

**Step 2: Delete the scripts**

```bash
git rm docker-build.sh
git rm docker-validate.sh
```

**Step 3: Run tests**

Run: `pytest tests/ -x -q`
Expected: All pass

**Step 4: Commit**

```bash
git commit -m "chore: remove stale docker-build.sh and docker-validate.sh — don't cover v2 services"
```

---

## Task 10: Clean up `start_services.py` — remove deprecated menu options

**Why:** `start_services.py` has 3 bugs and 4 stale menu options:
- Menu option 3 (`Run Dashboard`) launches the deprecated Streamlit dashboard
- Menu option 4 (`Stop Streamlit`) kills Streamlit processes
- Menu option 6 (`Docker dashboard`) runs `docker-compose up -d dashboard` — the `dashboard` service no longer exists in `docker-compose.yml`, so this **always silently fails**
- Menu option 7 (`Verify setup`) calls `project_root / "verify_setup.py"` — **wrong path** (should be `tools/verify_setup.py`)
- `check_database()` calls `project_root / "init_db.py"` — **wrong path** (should be `tools/init_db.py`)

**Files:**
- Modify: `start_services.py` — remove Streamlit/dashboard menu options (3, 4, 6); fix paths for init_db.py and verify_setup.py

**Step 1: Read `start_services.py` to identify exact line ranges**

Read the file and identify:
- `run_dashboard()` function
- `get_dashboard_bind()` function
- Menu option 3 (run dashboard)
- Menu option 4 (stop streamlit)
- Menu option 6 (docker dashboard)
- `init_db.py` path reference
- `verify_setup.py` path reference

**Step 2: Remove dashboard-related functions and menu options**

- Delete `run_dashboard()` function
- Delete `get_dashboard_bind()` function
- Remove menu options 3 (Run Dashboard), 4 (Stop Streamlit), and 6 (Docker dashboard)
- Renumber remaining menu options

**Step 3: Fix broken paths**

- Change `project_root / "init_db.py"` → `project_root / "tools" / "init_db.py"`
- Change `project_root / "verify_setup.py"` → `project_root / "tools" / "verify_setup.py"`

**Step 4: Run tests**

Run: `pytest tests/ -x -q`
Expected: All pass

**Step 5: Commit**

```bash
git add start_services.py
git commit -m "chore: remove deprecated dashboard menu options from start_services.py, fix tool paths"
```

---

## Task 11: Remove stale root-level `requirements.txt`

**Why:** The root `requirements.txt` contains only 7 packages (`sqlalchemy`, `python-dotenv`, `pytest`, `pytest-cov`, `pytest-asyncio`, `PyJWT`, `beautifulsoup4`). The real per-service requirements live in `src/api/requirements.txt`, `src/scraper/requirements.txt`, etc. The `pyproject.toml` supersedes it for packaging. This file is misleading — it implies these are all the project's dependencies.

**Files:**
- Delete: `requirements.txt` (root)

**Step 1: Verify `pyproject.toml` covers all dependencies**

Run: `cat pyproject.toml | head -30`
Confirm it lists project dependencies.

**Step 2: Verify no CI/CD or Docker references to root `requirements.txt`**

Run: `grep -rn "requirements.txt" docker-compose.yml .github/ Makefile 2>/dev/null | grep -v "src/"`
Expected: No active references to the root file (only per-service `src/*/requirements.txt`)

**Step 3: Delete the file**

```bash
git rm requirements.txt
```

**Step 4: Run tests**

Run: `pytest tests/ -x -q`
Expected: All pass

**Step 5: Commit**

```bash
git commit -m "chore: remove misleading root requirements.txt — pyproject.toml and per-service files are canonical"
```

---

## Task 12: Consolidate duplicate STOPWORDS

**Why:** The same English stopword set is independently defined in 3 places: `src/scraper/news_scraper.py`, `src/processor/alert_detector.py`, and `src/processor/summary_generator.py`. (`auto_pipeline.py` already imports from `news_scraper`.) This duplication makes maintenance error-prone.

**Files:**
- Create: `src/common/stopwords.py` — single canonical `STOPWORDS` set
- Modify: `src/scraper/news_scraper.py` — import from `common.stopwords`
- Modify: `src/processor/alert_detector.py` — import from `common.stopwords`
- Modify: `src/processor/summary_generator.py` — import from `common.stopwords`
- Modify: `src/processor/auto_pipeline.py` — import from `common.stopwords` (instead of `news_scraper`)

**Step 1: Create the shared module**

Create `src/common/stopwords.py` containing the union of all three STOPWORDS sets.

```python
STOPWORDS: set[str] = {
    "the", "a", "an", "and", "or", "but", "in", "on", "at", "to",
    "for", "of", "with", "by", "from", "is", "are", "was", "were",
    "be", "been", "being", "have", "has", "had", "do", "does", "did",
    "will", "would", "could", "should", "may", "might", "can", "shall",
    "it", "its", "this", "that", "these", "those", "i", "we", "you",
    "he", "she", "they", "me", "him", "her", "us", "them", "my",
    "your", "his", "our", "their", "what", "which", "who", "whom",
    "how", "not", "no", "nor", "as", "if", "then", "than", "too",
    "very", "just", "about", "above", "after", "again", "all", "also",
    "any", "because", "before", "between", "both", "each", "few",
    "more", "most", "other", "over", "same", "so", "some", "such",
    "into", "up", "out", "new", "now", "says", "said",
}
```

Note: Merge the actual sets from the three files before finalizing — ensure the union covers all words.

**Step 2: Update imports in all four files**

Replace the local `STOPWORDS` definition in each file with:
```python
from common.stopwords import STOPWORDS
```

**Step 3: Run tests**

Run: `pytest tests/ -x -q`
Expected: All pass

**Step 4: Commit**

```bash
git add src/common/stopwords.py src/scraper/news_scraper.py src/processor/alert_detector.py src/processor/summary_generator.py src/processor/auto_pipeline.py
git commit -m "refactor: consolidate duplicate STOPWORDS into src/common/stopwords.py"
```

---

## Task 13: Archive completed plan documents

**Why:** 7 plan/spec documents in `docs/` are fully completed, stale, or target the deprecated Streamlit dashboard. They clutter the docs directory and can mislead developers.

**Files:**
- Move: `docs/REFACTOR_PLAN.md` → `docs/archive/REFACTOR_PLAN.md`
- Move: `docs/SECURITY_HARDENING_PLAN.md` → `docs/archive/SECURITY_HARDENING_PLAN.md`
- Move: `docs/SPEC_v1_dashboard_improvements.md` → `docs/archive/SPEC_v1_dashboard_improvements.md`
- Move: `docs/SPEC_v2_style_learning.md` → `docs/archive/SPEC_v2_style_learning.md`
- Move: `docs/thread_scraping_improvement.md` → `docs/archive/thread_scraping_improvement.md`
- Move: `docs/CLOUD_READINESS_PERF_SECURITY_PLAN.md` → `docs/archive/CLOUD_READINESS_PERF_SECURITY_PLAN.md`
- Delete: `docs/MOBILE_WEB_SUPPORT_PLAN.md` — targets deprecated Streamlit, contradicts current architecture
- Delete: `docs/UX_E2E_CHECKLIST.md` — Streamlit-specific checklist, entire UI has been replaced

**Step 1: Create archive directory**

```bash
mkdir -p docs/archive
```

**Step 2: Move completed plans**

```bash
git mv docs/REFACTOR_PLAN.md docs/archive/
git mv docs/SECURITY_HARDENING_PLAN.md docs/archive/
git mv docs/SPEC_v1_dashboard_improvements.md docs/archive/
git mv docs/SPEC_v2_style_learning.md docs/archive/
git mv docs/thread_scraping_improvement.md docs/archive/
git mv docs/CLOUD_READINESS_PERF_SECURITY_PLAN.md docs/archive/
```

**Step 3: Delete dead plans**

```bash
git rm docs/MOBILE_WEB_SUPPORT_PLAN.md
git rm docs/UX_E2E_CHECKLIST.md
```

**Step 4: Commit**

```bash
git commit -m "chore: archive completed plan docs, delete Streamlit-specific plans"
```

---

## Task 14: Update `CLAUDE.md` to reflect cleanup

**Why:** After all the removals, CLAUDE.md has stale references — the `archive/` directory section, `k8s/` references, test file listings that no longer exist, etc.

**Files:**
- Modify: `CLAUDE.md`

**Step 1: Update the following sections**

1. **Directory Structure** — remove `archive/` entry, remove `k8s/` entry, update test file list
2. **Testing section** — remove reference to `tests/test_processor.py` (file doesn't exist; actual file is `tests/test_processor_comprehensive.py`)
3. **Known Issues** — remove k8s deployment references
4. **Deployment section** — remove "Legacy K8s manifests in `k8s/` (superseded)" note
5. **Recent Updates** — add a new entry for this cleanup
6. **Where each file type belongs** — remove `K8s YAML manifests | k8s/` row
7. **Helpful Commands Reference** — remove Streamlit dashboard commands, keep only API/frontend

**Step 2: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: update CLAUDE.md to reflect legacy code cleanup"
```

---

## Task 15: Run full test suite + final verification

**Why:** Final sanity check that nothing was broken across all 14 cleanup tasks.

**Step 1: Full pytest run**

Run: `pytest tests/ -v --tb=short`
Expected: All tests pass (count will be lower due to removed dead-helper tests from Task 2)

**Step 2: Verify no broken imports**

Run: `python -c "from common.models import *; from scraper.scraper import TwitterScraper; from processor.processor import TranslationService; from api.main import app; print('All imports OK')"`
Expected: `All imports OK`

**Step 3: Verify clean file structure**

Run:
```bash
echo "=== Root .py files ===" && ls *.py
echo "=== No archive/ ===" && ls archive/ 2>&1
echo "=== No k8s/ ===" && ls k8s/ 2>&1
echo "=== tools/ contents ===" && ls tools/
echo "=== docs/ contents ===" && ls docs/
```

Expected:
- Root: only `start_services.py`
- `archive/`: "No such file or directory"
- `k8s/`: "No such file or directory"
- `tools/`: `init_db.py`, `verify_setup.py`, `bootstrap_worktree_env.py`, `check_env.py`, `test_news_live.py`, `test_thread_media_download.py`
- `docs/`: `archive/`, `deploy/`, `plans/`, PDFs — no stale plans at top level

**Step 4: Final commit (if any stragglers)**

```bash
git status
# If clean, no action needed
```

---

## Excluded from This Plan (Requires Separate Decision)

These items were identified but are **not safe to remove without a broader migration decision**:

| Item | Why Excluded |
|------|-------------|
| `src/dashboard/` (entire deprecated Streamlit UI) | Still launched by `start_services.py`, tested by 3 test files, has `DEPRECATED.md`. Removing it requires deleting associated tests (`test_dashboard.py`, `test_dashboard_helpers.py`, `test_dashboard_ux_contract.py`, `test_security.py`). **Decision needed:** Are these tests still valuable? |
| `src/dashboard/Dockerfile` | Tied to `src/dashboard/` removal decision |
| `docker-compose.yml` redis service | Redis is wired up but no Python code imports it. **Decision needed:** Was this planned for future caching? |
| `config/style.txt` | Still used as DB fallback in `TranslationService`. Could be removed once style_examples DB is fully populated, but requires confirming the DB has enough examples. |
| `tools/verify_setup.py` | Stale (checks for Streamlit, doesn't know about v2 services) but `start_services.py` menu still calls it. Fixed path in Task 10, but the script content itself needs a rewrite for v2. |
| Auth inconsistency (`require_api_key` vs `require_jwt`) | `trends.py` and `summaries.py` use X-API-Key while everything else uses JWT. Legacy artifact but changing it is a behavior change, not dead code removal. |

---

## Execution Summary

| Task | Description | Files Affected | Lines Removed (est.) |
|------|-------------|----------------|---------------------|
| 1 | Delete `archive/` | 22 files deleted | ~800 |
| 2 | Remove dead model helpers | 4 files modified | ~100 |
| 3 | Remove dead scraper methods | 1 file modified | ~150 |
| 4 | Clean processor dead code | 3 files modified/deleted | ~300 |
| 5 | Remove dead API schemas | 3 files modified | ~30 |
| 6 | Move fake test scripts | 2 files moved | 0 (moved) |
| 7 | Delete stale tools | 2 files deleted | ~200 |
| 8 | Delete `k8s/` | 12 files deleted | ~2,669 |
| 9 | Delete stale Docker scripts | 2 files deleted | ~529 |
| 10 | Clean `start_services.py` | 1 file modified | ~80 |
| 11 | Delete root `requirements.txt` | 1 file deleted | ~10 |
| 12 | Consolidate STOPWORDS | 5 files modified | ~40 net (new shared module) |
| 13 | Archive stale docs | 8 files moved/deleted | 0 (moved) |
| 14 | Update CLAUDE.md | 1 file modified | ~20 (net change) |
| 15 | Final verification | 0 | 0 |
| **Total** | | **~65 files** | **~4,900 lines** |
