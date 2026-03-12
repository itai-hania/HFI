# Telegram Bot Hardening, URL Routing, and Draft Workflow Plan

## Summary

- Goal: harden the Telegram bot runtime, make `/write` correctly route X URLs versus generic HTTPS article URLs, turn generated variants into an explicit draft workflow, and make `/start` a reliable command index.
- Primary runtime: local polling.
- Persistence model: explicit save only; `/write` generates chat variants and `/save <variant_index>` persists one variant as a draft.
- Content scheduling from Telegram is out of scope for this iteration; `/schedule` remains informational for bot brief and alert timings only.
- This document is the implementation source of truth for the Telegram bot improvement work.

## Deliverables

- Shared Telegram command catalog module, proposed path: `src/telegram_bot/command_catalog.py`.
- Updated bot startup and runtime behavior in `src/telegram_bot/main.py`, `src/telegram_bot/config.py`, and `src/telegram_bot/bot.py`.
- Shared source resolution and URL validation for both bot and frontend-backed generation flows.
- New and updated API endpoints in `src/api/routes/generation.py`, `src/api/routes/content.py`, and `src/api/routes/notifications.py`.
- Updated local setup documentation in `README.md`.

## Telegram Command Surface

- `/start`
  Shows the bot status plus the full public command list, one sentence per command, in plain text.
- `/help`
  Shows detailed syntax and examples, generated from the same command catalog as `/start`.
- `/health`
  Checks API and database reachability.
- `/brief [3|4|5|refresh]`
  Fetches the latest brief, limits result count, or forces a refresh.
- `/story <n>`
  Shows fuller context and source links for story `n` from the latest brief.
- `/lastbrief`
  Re-opens the most recently cached brief without regenerating it.
- `/write <n|x_url|https_url|text>`
  Turns a brief item, X post, article URL, or pasted text into Hebrew draft variants.
- `/save <variant_index>`
  Saves one variant from the latest `/write` session as a draft in the queue.
- `/queue`
  Shows queue counts plus the newest review-ready drafts.
- `/draft <id>`
  Shows the status, preview, and frontend edit link for a saved draft.
- `/approve <id>`
  Marks a saved draft as approved for the publishing workflow.
- `/status`
  Shows quick counts for drafts, scheduled items, and published items.
- `/schedule`
  Shows configured brief and alert automation times.

## Exact `/start` Output Contract

- Render `/start` in plain text, not HTML, to avoid entity parsing issues.
- The output format is fixed:

```text
HFI Content Studio Bot is online.

Commands:
/brief [3|4|5|refresh] - Fetch the latest brief, limit the number of stories, or force a refresh.
/story <n> - Show the source links and fuller context for story n from the latest brief.
/lastbrief - Re-open the most recent brief without regenerating it.
/write <n|x_url|https_url|text> - Turn a brief item, X post, article URL, or pasted text into Hebrew draft variants.
/save <variant_index> - Save one variant from your last /write session as a draft in the queue.
/queue - Show queue counts and the newest review-ready draft IDs.
/draft <id> - Show the status, preview, and studio link for a saved draft.
/approve <id> - Mark a saved draft as approved for the publishing workflow.
/status - Show quick counts for drafts, scheduled, and published content.
/schedule - Show the configured brief and alert automation times.
/health - Check API and database health.
/help - Show examples and supported input formats.
```

- `/help` must be generated from the same registry to prevent drift.
- Tests must assert that every visible command in the registry appears in `/start`.

## Important API, Interface, and Type Changes

- New env var: `FRONTEND_BASE_URL`, default `http://localhost:3000` in development; used to build links like `/create?edit={id}`.
- New bot command registry type:
  - `name`
  - `syntax`
  - `summary`
  - `example`
  - `visible_in_start`
  - `visible_in_help`
- New API endpoint: `GET /api/notifications/brief/latest`
  - Returns the latest stored brief or `404`.
- New API endpoint: `POST /api/generation/source/resolve`
  - Request: `{ text?: string, url?: string }`
  - Response: `{ source_type: "text"|"x_url"|"article_url", original_text: string, title?: string, canonical_url?: string, source_domain?: string, preview_text: string }`
- Updated API behavior: `POST /api/generation/translate` must use the shared resolver so frontend translation of URLs supports both X URLs and HTTPS article URLs.
- New API endpoint: `GET /api/content/queue/summary`
  - Returns counts for `pending`, `processed`, `approved`, `scheduled`, `published`, and `failed`.
- New API endpoint: `POST /api/content/{id}/approve`
  - Validates `hebrew_draft` exists and sets status to `approved`.
- Updated content schemas in `src/api/schemas/content.py`:
  - Expose optional `generation_metadata` in create, update, and response models.
- Updated duplicate-create behavior for `POST /api/content`:
  - On unique `source_url` conflict return `409` with `{ detail, existing_id }`.

## `/write` Input Routing Contract

- Input precedence is fixed:
  1. If the input is a bare integer and a last brief exists, treat it as a story index.
  2. Else if the input is a valid X or Twitter status URL, treat it as `x_url`.
  3. Else if the input is a valid safe HTTPS URL, treat it as `article_url`.
  4. Else treat it as free text.
- Failure behavior is fixed:
  - Integer with no cached brief: return `No cached brief found. Run /brief first.`
  - Invalid X or Twitter URL: return a URL validation error.
  - Unsafe or unsupported HTTPS URL: return a safe extraction error.
  - Article extraction failure: return `Couldn't extract article text from this URL. Paste the text instead.`
- Validation rules:
  - Only `https` URLs are accepted.
  - Reject URLs with embedded credentials.
  - Reject dangerous schemes.
  - Reject loopback, private-network, and link-local targets for article extraction.
  - Reject response bodies over 2 MB.
  - Reject redirect chains over 5 hops.
  - Reject non-HTML content types for article extraction.

## Phase 1: Runtime and Config Stabilization

- Add shared env helpers in `src/common/env_utils.py`.
- Add structured logging helpers in `src/common/logging_utils.py`.
- Add duplicate `.env` key detection before startup and abort with clear key names and line numbers.
- Fail fast if bot-required env vars are missing:
  - `TELEGRAM_BOT_TOKEN`
  - `TELEGRAM_CHAT_ID`
  - `API_BASE_URL`
  - `DASHBOARD_PASSWORD`
  - `JWT_SECRET`
- Fail fast if API-required env vars are missing:
  - `DASHBOARD_PASSWORD`
  - `JWT_SECRET`
- Add bot startup self-checks before polling:
  - `GET /health`
  - `POST /api/auth/login`
  - `GET /api/content/queue/summary`
- Add a local single-instance lock file at `data/runtime/telegram-bot.lock`; if the lock cannot be acquired, exit immediately.
- Explicitly handle:
  - `telegram.error.Conflict`
  - `telegram.error.BadRequest`
  - `httpx.ConnectError`
- Replace generic `Unexpected error` user messages with categorized messages based on error class.
- Add tests in:
  - `tests/test_telegram_bot.py`
  - `tests/test_telegram_bot_startup.py`
  - `tests/test_env_utils.py`

## Phase 2: Command Catalog, `/start`, Brief UX, and Unified Source Resolution

- Create `src/telegram_bot/command_catalog.py` and move command definitions there.
- Update `/start` to render the exact command index contract above in plain text.
- Update `/help` to render richer syntax and examples from the same catalog.
- Keep `/brief` short by default:
  - Default count is 5.
  - Explicit supported counts are 3, 4, and 5.
  - Each item shows title, one concise summary line, and at most one safe source link.
- Add per-chat state caches:
  - `last_brief`
  - `last_write_session`
- Add `GET /api/notifications/brief/latest` so `/lastbrief` works across restarts.
- Implement `src/common/url_validation.py` and make bot, API, and dashboard share it.
- Implement `src/common/source_resolver.py`:
  - X URLs use `TwitterScraper`.
  - HTTPS article URLs use `httpx` plus `BeautifulSoup`.
  - Extraction strategy:
    - prefer `og:title`, `twitter:title`, then `<title>`
    - prefer `article` or `main` containers
    - strip scripts, styles, nav, footer, aside, form, noscript
    - join paragraph-like blocks
    - require a minimum text threshold before accepting
- Update `POST /api/generation/translate` to call the shared resolver.
- Update `/write`:
  - Send a short source preview first.
  - Generate 2 variants by default.
  - Send one variant per message.
  - Chunk messages at 3500 characters max.

## Phase 3: Persisted Draft Workflow

- Keep explicit save as the only persistence path:
  - `/write` generates variants only.
  - `/save <variant_index>` persists one selected variant.
- Save flow:
  - call `POST /api/content`
  - set `content_type="generation"`
  - set `status="processed"`
  - set `hebrew_draft=<selected variant>`
  - include `generation_metadata` with:
    - `origin="telegram"`
    - `source_type`
    - `canonical_source_url`
    - `source_title`
    - `variant_index`
    - `label`
    - `quality_score`
    - `write_session_id`
- Duplicate handling:
  - keep one persisted draft per canonical `source_url`
  - if a duplicate source exists, return the existing id and link
- Synthetic source URL for free text:
  - `https://manual.local/content/{sha256(source_text)[:16]}`
- Add:
  - `/queue` using `GET /api/content/queue/summary` and `GET /api/content/drafts?status=processed&page=1&limit=5`
  - `/draft <id>` using `GET /api/content/{id}`
  - `/approve <id>` using `POST /api/content/{id}/approve`
- Draft links use:
  - `{FRONTEND_BASE_URL}/create?edit={id}`

## Phase 4: Operations and Documentation

- Keep local polling as the canonical supported runtime.
- Treat Docker polling as secondary and warn against running both local and Docker pollers with the same token.
- Standardize logs as `event=<name> key=value`.
- Required log events:
  - `bot_startup_check`
  - `api_unreachable`
  - `auth_failed`
  - `brief_sent`
  - `source_resolved`
  - `draft_saved`
  - `telegram_rejected_message`
  - `telegram_poll_conflict`
- Update `README.md`:
  - one exact local startup path
  - one bot process only
  - explicit `/start`, `/brief`, `/story 1`, `/write 1` verification steps

## Tests and Acceptance Criteria

- `/start` shows every public command with exactly one sentence per command.
- `/help` is generated from the same command catalog and includes syntax examples.
- Startup fails immediately on:
  - duplicate `.env` keys
  - missing required env vars
  - failed health check
  - failed login
  - lock acquisition failure
- `/brief`, `/brief refresh`, `/brief 3`, `/story 2`, and `/lastbrief` work with cached and uncached brief state.
- `/write` correctly distinguishes:
  - story number
  - X URL
  - HTTPS article URL
  - free text
- `/write` never emits Telegram-invalid formatting and never exceeds chunk limits.
- `/save 1` creates a processed draft with metadata and a valid edit link.
- Duplicate `/save` returns the existing draft id and link instead of creating a second row.
- `/queue`, `/draft <id>`, and `/approve <id>` return clear failures for missing ids, bad state, or empty Hebrew text.
- Frontend compatibility: URL translation in `frontend/src/hooks/useTranslate.ts` continues to work because it now uses the shared resolver.

## Assumptions and Defaults

- `/start` and `/help` remain English for this iteration; Hebrew localization is deferred.
- `/schedule` remains read-only and informational for bot timing only.
- Content scheduling from Telegram is deferred.
- Generic HTTPS article support is best-effort and not guaranteed for paywalled or JS-only pages.
- Default `/brief` count is 5.
- Default `/write` variant count is 2.
- `FRONTEND_BASE_URL` defaults to `http://localhost:3000` in local development.
