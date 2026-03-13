# Cloud Readiness Plan: Performance + Security

Generated: 2026-02-15
Scope: HFI application (API, dashboard, processor, scraper, DB layer)

## Objectives
- Prevent production fail-open security behavior before cloud exposure.
- Remove immediate cloud migration blockers (especially DB backend assumptions).
- Reduce high-cost/high-latency query and processing paths.
- Keep changes low-risk and test-backed.

## Findings (Deep Analysis)

### Critical Security Findings
1. Production auth fail-open behavior
- Dashboard auth allows access when `DASHBOARD_PASSWORD` is unset.
- API key dependency skips auth when `API_SECRET_KEY` is unset.
- Impact: accidental unauthenticated exposure in cloud if env secrets are misconfigured.

2. Unsafe link rendering paths in dashboard content views
- Some URLs are rendered into HTML anchors without scheme validation in `unsafe_allow_html=True` flows.
- Impact: possible `javascript:`/unsafe scheme injection in rendered links from external content.

3. Inconsistent URL policy (HTTPS not strictly enforced)
- URL validators accept non-HTTPS schemes in some paths.
- Impact: weaker transport guarantees and inconsistent input hardening.

### High Performance Findings
1. DB layer is SQLite-specific and not cloud DB-safe
- `create_engine` uses SQLite-only `connect_args` unconditionally.
- SQLite PRAGMA handler is attached for all backends.
- Impact: Postgres/MySQL migration can fail at startup; cloud rollout blocker.

2. Summary generator uses full-table scans in core methods
- `calculate_source_count()` queries all trends.
- Backfill paths repeatedly process with broad scans.
- Impact: O(n^2)-like growth, high latency/cost as data grows.

3. Processor batch path loads all pending tweets at once
- `process_pending_tweets()` currently loads all pending items into memory.
- Impact: memory spikes and long processing windows with large queues.

4. Dashboard query hot paths include avoidable broad scans
- Style example tag filtering falls back to Python-side filtering after fetching many rows.
- Home view prefetches all queued trend titles instead of only those on screen.
- Impact: unnecessary DB load and slower UI under larger datasets.

### Additional Security/Resource Findings
1. Video download size cap not enforced by downloader command
- `MAX_VIDEO_SIZE` constant exists but yt-dlp execution does not enforce it.
- Impact: risk of oversized downloads, disk exhaustion, and noisy neighbor behavior in cloud.

2. Failed-processing internals surfaced directly in editor UI
- Raw `tweet.error_message` shown to user.
- Impact: potential information disclosure of internals/secrets from exception strings.

## Remediation Plan (Execution Order)

### Phase 1: Cloud Blockers + Fail-Closed Auth
1. Make DB engine setup backend-aware (SQLite vs non-SQLite).
2. Restrict SQLite PRAGMAs to SQLite connections only.
3. Make production dashboard auth fail closed if password missing.
4. Make production API auth fail closed if API key secret missing.

### Phase 2: Input/Link Hardening + Media Guardrails
5. Enforce HTTPS in URL validators.
6. Apply safe URL validation in all dashboard link-rendering hot paths.
7. Enforce yt-dlp max file size and tighten media URL checks.
8. Reduce user-facing error leakage in UI.

### Phase 3: Performance Scaling Fixes
9. Optimize summary generator queries (time-windowed candidate set, avoid full scans).
10. Batch processor pending tweet processing with configurable chunk size.
11. Optimize dashboard queries for tag filtering and queued-title lookup.

### Phase 4: Validation
12. Add/adjust tests for new security and performance behavior.
13. Run focused test suites (`security`, `summary`, `api`, `processor`) and fix regressions.

## Status Tracker
- [x] Plan document created
- [x] Phase 1 complete
- [x] Phase 2 complete
- [x] Phase 3 complete
- [x] Phase 4 complete

## Execution Notes (Completed 2026-02-15)
- Implemented production fail-closed behavior for dashboard and API auth misconfiguration.
- Implemented backend-aware DB engine setup for cloud DB compatibility.
- Hardened URL/link handling with strict HTTPS validation and safer render paths.
- Enforced media download controls including yt-dlp max file size and response cleanup.
- Reduced hot-path load in summary processing, processor batching, and dashboard queries.
- Validation: `python3 -m pytest -q` passed (`472 passed`).
