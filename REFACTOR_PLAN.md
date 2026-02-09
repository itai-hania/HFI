# HFI Codebase Refactor Plan

> Full code review conducted 2026-02-08. All decisions approved by user.

## Current Status (2026-02-08)

**Completed:** Phases 1, 2, 3, 4, 7
**Skipped:** Phases 5, 6 (high-risk, deferred by user)
**Tests:** 338/338 passing

## Phases

### Phase 1: Quick Fixes (Low Risk, High Value) ✅ DONE
*No structural changes. Fix bugs and bad patterns in-place.*

- [x] **1.1** Fix hardcoded log path in `src/processor/main.py:56` — use `LOG_DIR` env var
- [x] **1.2** Fix float index bug in `src/processor/processor.py:245-246` — integer division
- [x] **1.3** Fix float index bug in `src/processor/style_manager.py:172` — integer division
- [x] **1.4** Fix subprocess buffering in `src/processor/processor.py:936-943` — `stdout=DEVNULL`
- [x] **1.5** Fix all 22 bare/broad exception handlers across codebase — specific exceptions + logging

**Test gate:** `pytest tests/ -v` — all 246 tests pass ✅

---

### Phase 2: Performance Improvements (Low Risk) ✅ DONE
*Optimize hot paths without changing APIs.*

- [x] **2.1** Add `get_openai_client()` shared factory — module-level cached client
- [x] **2.2** Add TTL cache (5 min) for style examples in `TranslationService._load_db_style_examples()`
- [x] **2.3** Add pagination/streaming to heavy DB queries (export uses `yield_per(100)`)

**Test gate:** `pytest tests/ -v` — all 246 tests pass ✅

---

### Phase 3: XSS Hardening + Dashboard Auth (Low-Medium Risk) ✅ DONE
*Security improvements to the dashboard.*

- [x] **3.1** Audit all 48 `unsafe_allow_html=True` uses in `app.py`, add `html.escape()` to borderline cases
- [x] **3.2** Add comment convention `# SAFETY: value is escaped/controlled` to key `unsafe_allow_html` uses
- [x] **3.3** Add simple password gate — `DASHBOARD_PASSWORD` env var, gate wraps `main()`

**Test gate:** `pytest tests/ -v` — all tests pass + manual browser test of dashboard ✅

---

### Phase 4: Extract PromptBuilder (Medium Risk) ✅ DONE
*Refactor duplicated prompt logic into shared class.*

- [x] **4.1** Create `src/processor/prompt_builder.py` with:
  - `build_glossary_section(glossary: dict) -> str`
  - `build_style_section(source_text, db_examples) -> str`
  - `validate_hebrew_output(text: str) -> Tuple[bool, str]`
  - `get_completion_params(model, system_prompt, user_content, temperature) -> dict`
  - `call_with_retry(client, params, max_retries, validator_fn) -> str`
  - `extract_topic_keywords(text) -> List[str]`
  - `load_style_examples_from_db(limit, source_tags) -> List[str]`
  - `KEEP_ENGLISH` constant + `KEYWORD_MAP` constant
- [x] **4.2** Refactor `TranslationService` to use `PromptBuilder`
- [x] **4.3** Refactor `ContentGenerator` to use `PromptBuilder`
- [x] **4.4** Add tests for `PromptBuilder` (36 tests)

**Test gate:** `pytest tests/ -v` — all tests pass (existing + new) ✅

---

### Phase 5: Python Packaging (High Risk — touches all imports) ⏸️ DEFERRED
*Proper package structure. All imports change. Skipped by user — high risk.*

- [ ] **5.1** Create `pyproject.toml` with `[project]` and `[tool.setuptools.packages.find]`
- [ ] **5.2** Add `__init__.py` files to all packages under `src/`
- [ ] **5.3** Update all imports from `from common.models import ...` to `from hfi.common.models import ...` (or use relative imports within packages)
- [ ] **5.4** Remove all 12 `sys.path.append()` hacks
- [ ] **5.5** Update `conftest.py` to use the installed package
- [ ] **5.6** Update Docker files to `pip install -e .`
- [ ] **5.7** Run `pip install -e .` and verify

---

### Phase 6: Split Dashboard (High Risk — restructures UI) ⏸️ DEFERRED
*Break 3,003-line app.py into page modules. Skipped by user — high risk.*

- [ ] **6.1** Create directory structure
- [ ] **6.2** Extract CSS to `theme.py`
- [ ] **6.3** Extract page render functions to their modules
- [ ] **6.4** Extract reusable components
- [ ] **6.5** Thin `app.py` to router + auth gate
- [ ] **6.6** Update imports and session handling

---

### Phase 7: Test Improvements (Low Risk) ✅ DONE
*Strengthen existing tests + add missing coverage.*

- [x] **7.1** Strengthen all weak assertions across test files (~20 assertions improved)
- [x] **7.2** Add scraper mock Page unit tests — `test_scraper_page.py` (20 tests)
- [x] **7.3** Add parameterized OpenAI mock tests — `test_thread_translation.py` (12 new tests)
- [x] **7.4** Extract dashboard pure functions into `src/dashboard/helpers.py` + `test_dashboard_helpers.py` (24 tests)

**Test gate:** `pytest tests/ -v` — 338/338 tests pass ✅

---

## Files Created/Modified in This Refactor

### New files:
- `src/processor/prompt_builder.py` — shared prompt logic (Phase 4)
- `src/dashboard/helpers.py` — pure dashboard helpers (Phase 7)
- `tests/test_prompt_builder.py` — 36 tests (Phase 4)
- `tests/test_scraper_page.py` — 20 tests (Phase 7)
- `tests/test_dashboard_helpers.py` — 24 tests (Phase 7)

### Modified files:
- `src/processor/processor.py` — refactored to delegate to prompt_builder
- `src/processor/content_generator.py` — refactored to delegate to prompt_builder
- `src/processor/main.py` — log path fix
- `src/processor/style_manager.py` — float index fix
- `src/dashboard/app.py` — XSS hardening, auth gate, helpers extraction
- `tests/test_scraper.py` — strengthened assertions
- `tests/test_thread_translation.py` — strengthened + parameterized tests
- `tests/test_dashboard.py` — strengthened assertions
- `tests/test_processor_comprehensive.py` — strengthened assertions
- `tests/test_content_generator.py` — strengthened assertions
- `tests/test_summary_generator.py` — strengthened assertions
- `tests/test_api_endpoints.py` — strengthened assertions

## Risk Assessment

| Phase | Risk | Status |
|-------|------|--------|
| 1 | Low | ✅ Done |
| 2 | Low | ✅ Done |
| 3 | Low-Med | ✅ Done |
| 4 | Medium | ✅ Done |
| 5 | High | ⏸️ Deferred |
| 6 | High | ⏸️ Deferred |
| 7 | Low | ✅ Done |
