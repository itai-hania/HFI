# HFI Mobile Web Support Plan

**Version:** 1.0  
**Date:** 2026-02-28  
**Status:** Proposed

## Objective

Make the existing Streamlit dashboard usable and comfortable from a mobile browser (iPhone/Android) without building native iOS or Android apps.

## Non-Goals

- No migration away from Streamlit.
- No native app development.
- No major feature redesign unrelated to mobile usability.
- No backend architecture changes unless needed for mobile stability/performance.

## Current Baseline (Code-Aware)

1. Dashboard entrypoint uses desktop defaults (`layout="wide"`, expanded sidebar):  
   `src/dashboard/app.py`
2. Global CSS is desktop-first with fixed sidebar width (`260px`) and large paddings:  
   `src/dashboard/styles.py`
3. Heavy use of multi-column layouts across views, which will compress badly on phone widths:  
   `src/dashboard/views/home.py`, `src/dashboard/views/content.py`, `src/dashboard/views/settings.py`, `src/dashboard/navigation.py`
4. Local launch scripts bind to localhost by default, which blocks direct phone access over LAN:  
   `start_services.py`, `start_services.sh`

## Success Criteria (Definition of Done)

1. Dashboard is reachable from phone browser on same Wi-Fi via `http://<LAN-IP>:8501`.
2. No forced horizontal page scrolling at `360px` viewport width (except optional code/preformatted blocks).
3. All primary actions are tap-friendly (target size ~44px minimum).
4. Key workflows are fully usable on phone:
   - Home overview and quick actions
   - Content acquisition and queue management
   - Thread translation review/action flow
   - Settings save/export flows
5. UI remains readable and stable on Safari (iOS) and Chrome (Android).
6. README includes mobile access/run instructions and troubleshooting.

## Scope

- Runtime/network access for phone testing and daily usage.
- Responsive CSS foundations and mobile breakpoints.
- Navigation behavior for smaller viewports.
- Targeted refactors in Home, Content, and Settings views.
- Mobile-focused QA checklist and release criteria.

## Execution Plan

### Phase 0: Baseline Snapshot (Short)

1. Capture before-state screenshots on desktop + phone viewport simulation.
2. Record current pain points by flow (overflow, tiny actions, clipped content, tab crowding).
3. Freeze a baseline checklist to compare after each phase.

**Output:** Baseline issue list attached to this plan or PR description.

### Phase 1: Mobile Reachability & Runtime Defaults

**Goal:** Make app reachable from phone browser in local/dev setup.

1. Update launch commands to bind Streamlit on all interfaces:
   - `start_services.py` (`run_dashboard`)
   - `start_services.sh` (Dashboard options)
2. Add optional env-configurable host/port:
   - `HFI_DASHBOARD_HOST` (default `0.0.0.0`)
   - `HFI_DASHBOARD_PORT` (default `8501`)
3. Update docs:
   - Add LAN access steps in `README.md`
   - Add quick firewall/trusted-network note

**Acceptance:** Phone can open dashboard using LAN IP while services run locally.

### Phase 2: Global Responsive Foundation (CSS)

**Goal:** Establish responsive behavior without rewriting all components first.

1. Add mobile breakpoints in `src/dashboard/styles.py`:
   - `<=1024px` tablet adjustments
   - `<=768px` phone adjustments
   - `<=480px` compact phone adjustments
2. Core responsive changes:
   - Reduce main container paddings on smaller screens.
   - Collapse fixed-width sidebar behavior on narrow screens.
   - Make Streamlit column groups stack cleanly on phone.
   - Make tabs horizontally scrollable and easier to tap.
   - Reduce oversized typography/cards where needed.
3. Touch and accessibility improvements:
   - Increase tap target heights.
   - Ensure focus-visible states remain clear.
   - Reduce hover-dependent effects for touch contexts.

**Acceptance:** Base layout is readable and usable on `360px–430px` widths.

### Phase 3: Navigation and Information Hierarchy for Mobile

**Goal:** Keep navigation fast and predictable on phone.

1. Preserve sidebar for desktop/tablet.
2. Introduce mobile-friendly top navigation (Home, Content, Settings) in main area for narrow screens.
3. Move non-critical sidebar details (extra stats/visual noise) behind collapse or secondary placement on mobile.

**Acceptance:** User can switch sections quickly on phone without opening a cramped sidebar repeatedly.

### Phase 4: Home View Mobile Refactor

**File:** `src/dashboard/views/home.py`

1. Convert dense multi-action rows to vertical or two-step action groups on small screens.
2. Ensure stat cards render as 2x2 or stacked cards without clipping.
3. Keep trend/thread cards readable:
   - Title and badges first
   - Actions beneath content
   - Expanders remain usable without overflow

**Acceptance:** Home page can be fully scanned and acted on with one-thumb interaction on phone.

### Phase 5: Content View Mobile Refactor

**File:** `src/dashboard/views/content.py`

1. Refactor crowded action rows (`st.columns` with 3-5 controls) into stacked groups on small screens.
2. Ensure `Acquire`, `Queue`, `Thread Translation`, `Generate` tab content does not overflow.
3. Thread translation:
   - Desktop keeps side-by-side English/Hebrew
   - Mobile switches to stacked panel flow
4. Keep primary CTA buttons visible and easy to hit.

**Acceptance:** All content workflows are executable on phone without accidental taps or horizontal scrolling.

### Phase 6: Settings View Mobile Refactor

**File:** `src/dashboard/views/settings.py`

1. Convert two-column sections to single-column flow on phone.
2. Keep long text areas editable with predictable heights.
3. Ensure import/export and destructive actions are separated and readable.

**Acceptance:** Settings can be safely edited from mobile browser without layout breakage.

### Phase 7: Validation, QA, and Documentation

1. Run existing tests to avoid regressions:
   - `pytest tests/test_dashboard.py`
   - `pytest tests/test_dashboard_helpers.py`
2. Execute manual mobile QA matrix:
   - iPhone Safari (390x844 and 430x932)
   - Android Chrome (360x800 and 412x915)
3. Validate key flows:
   - Auth/login
   - Home quick actions
   - Fetch/scrape actions
   - Queue edit/approve
   - Settings save/export
4. Update `README.md` with:
   - Mobile run/access instructions
   - Known limitations
   - Troubleshooting for LAN access/firewall

**Acceptance:** All key flows pass QA matrix; documentation is updated and usable.

## Work Breakdown and Priority

1. **P0:** Phase 1 + Phase 2 (reachability + responsive foundation)
2. **P1:** Phase 3 + Phase 4 + Phase 5 (navigation and high-traffic views)
3. **P2:** Phase 6 + Phase 7 (settings polish, QA, docs completeness)

## Risks and Mitigations

1. **Risk:** Streamlit DOM/test-id changes can break CSS selectors.  
   **Mitigation:** Prefer stable selectors, keep overrides minimal, test on target versions.
2. **Risk:** No direct server-side viewport detection in Streamlit.  
   **Mitigation:** Use CSS-first responsiveness and avoid hard viewport branching in Python.
3. **Risk:** LAN access blocked by firewall/router isolation.  
   **Mitigation:** Add explicit troubleshooting and trusted-network guidance in README.
4. **Risk:** Large `content.py` complexity increases regression risk.  
   **Mitigation:** Incremental PRs by section and checklist-based manual verification each step.

## Out of Scope for This Plan

- PWA packaging/offline mode.
- Push notifications.
- Native mobile gestures/components.
- Full visual redesign of dashboard identity.

## Recommended PR Sequence

1. `PR-1`: Reachability + README mobile access instructions.
2. `PR-2`: Global responsive CSS foundation.
3. `PR-3`: Home + navigation mobile behavior.
4. `PR-4`: Content mobile behavior.
5. `PR-5`: Settings mobile behavior + final QA checklist results.

