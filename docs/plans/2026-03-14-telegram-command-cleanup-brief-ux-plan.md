# Telegram Command Cleanup & Brief UX — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Slim the Telegram bot from 15 to 10 commands, make `/brief` always fetch fresh content, and register commands with Telegram for autocomplete.

**Architecture:** Remove 5 unused command handlers and catalog entries, simplify the brief input parser to always force-refresh, and add a `set_my_commands` call at bot startup. All changes are in `src/telegram_bot/` with corresponding test updates.

**Tech Stack:** Python, python-telegram-bot, httpx, pytest

---

### Task 1: Update command catalog — remove 5 dropped commands

**Files:**
- Modify: `src/telegram_bot/command_catalog.py:22-107`

**Step 1: Remove dropped commands from COMMAND_CATALOG**

Replace the entire `COMMAND_CATALOG` tuple with:

```python
COMMAND_CATALOG: tuple[CommandSpec, ...] = (
    CommandSpec(
        name="brief",
        syntax="/brief [1-8]",
        summary="Fetch a fresh brief, optionally limit the number of stories.",
        example="/brief 3",
    ),
    CommandSpec(
        name="story",
        syntax="/story <n>",
        summary="Show the source links and fuller context for story n from the latest brief.",
        example="/story 1",
    ),
    CommandSpec(
        name="write",
        syntax="/write <n|x_url|https_url|text>",
        summary="Turn a brief item, X post, article URL, or pasted text into Hebrew draft variants.",
        example="/write https://x.com/user/status/123",
    ),
    CommandSpec(
        name="save",
        syntax="/save <variant_index>",
        summary="Save one variant from your last /write session as a draft in the queue.",
        example="/save 1",
    ),
    CommandSpec(
        name="schedule",
        syntax="/schedule",
        summary="Show the configured brief and alert automation times.",
        example="/schedule",
    ),
    CommandSpec(
        name="scrape",
        syntax="/scrape <url>",
        summary="Scrape an X thread, translate it, and save as a draft.",
        example="/scrape https://x.com/user/status/123",
    ),
    CommandSpec(
        name="xtrends",
        syntax="/xtrends",
        summary="Show the top trending topics on X.",
        example="/xtrends",
    ),
    CommandSpec(
        name="health",
        syntax="/health",
        summary="Check API and database health.",
        example="/health",
    ),
    CommandSpec(
        name="help",
        syntax="/help",
        summary="Show examples and supported input formats.",
        example="/help",
    ),
)
```

Removed: `lastbrief`, `queue`, `draft`, `approve`, `status`.
Changed: `brief` syntax from `/brief [1-8|refresh]` to `/brief [1-8]`, updated summary.

**Step 2: Run tests to see what breaks**

Run: `pytest tests/test_telegram_bot.py -v`
Expected: `test_start_output_contract` and `test_brief_input_accepts_1_to_8` will FAIL (they reference old commands/refresh arg).

**Step 3: Commit**

```bash
git add src/telegram_bot/command_catalog.py
git commit -m "refactor(telegram): remove 5 dropped commands from catalog"
```

---

### Task 2: Remove 5 command handlers from bot.py

**Files:**
- Modify: `src/telegram_bot/bot.py:281-296` (handler registration)
- Modify: `src/telegram_bot/bot.py` (remove handler methods)

**Step 1: Remove handler registrations**

In `_register_handlers()`, remove these 5 lines:
```python
self.app.add_handler(CommandHandler("lastbrief", self.cmd_lastbrief))
self.app.add_handler(CommandHandler("queue", self.cmd_queue))
self.app.add_handler(CommandHandler("draft", self.cmd_draft))
self.app.add_handler(CommandHandler("approve", self.cmd_approve))
self.app.add_handler(CommandHandler("status", self.cmd_status))
```

Keep these 10:
```python
def _register_handlers(self):
    self.app.add_handler(CommandHandler("start", self.cmd_start))
    self.app.add_handler(CommandHandler("help", self.cmd_help))
    self.app.add_handler(CommandHandler("health", self.cmd_health))
    self.app.add_handler(CommandHandler("brief", self.cmd_brief))
    self.app.add_handler(CommandHandler("story", self.cmd_story))
    self.app.add_handler(CommandHandler("write", self.cmd_write))
    self.app.add_handler(CommandHandler("save", self.cmd_save))
    self.app.add_handler(CommandHandler("schedule", self.cmd_schedule))
    self.app.add_handler(CommandHandler("scrape", self.cmd_scrape))
    self.app.add_handler(CommandHandler("xtrends", self.cmd_xtrends))
```

**Step 2: Delete the 5 handler methods**

Delete these methods entirely:
- `cmd_lastbrief` (lines 573-583)
- `cmd_queue` (lines 801-822)
- `cmd_draft` (lines 824-849)
- `cmd_approve` (lines 851-864)
- `cmd_status` (lines 866-879)

**Step 3: Run tests**

Run: `pytest tests/test_telegram_bot.py -v`
Expected: Some tests may reference removed commands — we'll fix those in Task 4.

**Step 4: Commit**

```bash
git add src/telegram_bot/bot.py
git commit -m "refactor(telegram): remove 5 unused command handlers"
```

---

### Task 3: Make /brief always fresh — simplify _brief_input

**Files:**
- Modify: `src/telegram_bot/bot.py:484-521` (`_brief_input` + `cmd_brief`)

**Step 1: Write the failing test**

In `tests/test_telegram_bot.py`, replace the `test_brief_input_accepts_1_to_8` test:

```python
def test_brief_input_accepts_1_to_8(self):
    """_brief_input should accept 1-8 and default to 5. No 'refresh' arg."""
    from telegram_bot.bot import HFIBot

    assert HFIBot._brief_input(["1"]) == 1
    assert HFIBot._brief_input(["6"]) == 6
    assert HFIBot._brief_input(["8"]) == 8
    assert HFIBot._brief_input([]) == 5

    with pytest.raises(ValueError):
        HFIBot._brief_input(["9"])
    with pytest.raises(ValueError):
        HFIBot._brief_input(["0"])
    with pytest.raises(ValueError):
        HFIBot._brief_input(["refresh"])
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_telegram_bot.py::TestTelegramBotFormatting::test_brief_input_accepts_1_to_8 -v`
Expected: FAIL — old `_brief_input` returns a tuple, not int.

**Step 3: Simplify `_brief_input` to return just count**

Replace the `_brief_input` method:

```python
@staticmethod
def _brief_input(args: list[str]) -> int:
    """Parse /brief args: optional count 1-8, default 5."""
    if not args:
        return 5
    token = args[0].strip()
    try:
        n = int(token)
    except ValueError:
        raise ValueError("Usage: /brief [1-8]")
    if 1 <= n <= 8:
        return n
    raise ValueError("Usage: /brief [1-8]")
```

**Step 4: Update `cmd_brief` to always force_refresh**

Replace `cmd_brief`:

```python
async def cmd_brief(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await self._reject_if_unauthorized(update, "brief"):
        return

    try:
        count = self._brief_input(getattr(context, "args", []) or [])
        response = await self._request("POST", "/api/notifications/brief?force_refresh=true")
        stories = response.json().get("stories", [])[:count]
        self._state_for(update).last_brief = stories

        msg = format_brief_message(stories, "on-demand")
        await self._send_chunked_reply(update, msg, parse_mode="HTML")
        log_event(logger, "brief_sent", mode="on_demand", count=len(stories))
    except ValueError as err:
        await self._reply_text(update, str(err))
    except Exception as err:  # pragma: no cover - exercised in integration
        await self._reply_error(update, err)
```

**Step 5: Run test to verify it passes**

Run: `pytest tests/test_telegram_bot.py::TestTelegramBotFormatting::test_brief_input_accepts_1_to_8 -v`
Expected: PASS

**Step 6: Commit**

```bash
git add src/telegram_bot/bot.py tests/test_telegram_bot.py
git commit -m "feat(telegram): /brief always fetches fresh content"
```

---

### Task 4: Add set_my_commands at bot startup

**Files:**
- Modify: `src/telegram_bot/main.py:40-50`
- Modify: `src/telegram_bot/command_catalog.py` (add helper function)

**Step 1: Write the failing test**

Add to `tests/test_telegram_bot.py`:

```python
def test_bot_commands_list():
    """Verify bot_commands() returns BotCommand-compatible tuples for set_my_commands."""
    from telegram_bot.command_catalog import bot_commands
    commands = bot_commands()
    assert len(commands) == 10
    names = [c[0] for c in commands]
    assert "brief" in names
    assert "start" in names
    assert "help" in names
    assert "lastbrief" not in names
    assert "queue" not in names
    assert "draft" not in names
    assert "approve" not in names
    assert "status" not in names
    for name, description in commands:
        assert isinstance(name, str)
        assert isinstance(description, str)
        assert len(description) <= 256
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_telegram_bot.py::test_bot_commands_list -v`
Expected: FAIL — `bot_commands` function doesn't exist yet.

**Step 3: Add `bot_commands()` helper to command_catalog.py**

Add after the `render_help_text` function at the bottom of `command_catalog.py`:

```python
def bot_commands() -> list[tuple[str, str]]:
    """Return (name, description) pairs for Telegram set_my_commands.

    Includes /start (always present in Telegram) plus all visible catalog commands.
    """
    pairs = [("start", "Start the bot and show available commands")]
    for item in visible_start_commands():
        pairs.append((item.name, item.summary[:256]))
    return pairs
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_telegram_bot.py::test_bot_commands_list -v`
Expected: PASS

**Step 5: Add `set_my_commands` call in main.py**

In `src/telegram_bot/main.py`, add import at top:

```python
from telegram_bot.command_catalog import bot_commands
```

In the `_run` function, after `await bot.app.initialize()` (line 41), add:

```python
        await bot.app.initialize()
        initialized = True

        try:
            from telegram import BotCommand
            cmds = [BotCommand(name, desc) for name, desc in bot_commands()]
            await bot.app.bot.set_my_commands(cmds)
            log_event(logger, "bot_commands_registered", count=len(cmds))
        except Exception as exc:
            log_event(logger, "bot_commands_registration_failed", level=logging.WARNING, error=str(exc))

        await bot.app.start()
```

The try/except ensures command registration failures don't prevent bot startup.

**Step 6: Commit**

```bash
git add src/telegram_bot/command_catalog.py src/telegram_bot/main.py tests/test_telegram_bot.py
git commit -m "feat(telegram): register commands with Telegram for autocomplete"
```

---

### Task 5: Update all tests to match new command set

**Files:**
- Modify: `tests/test_telegram_bot.py`

**Step 1: Update `test_start_output_contract`**

Replace the expected string:

```python
def test_start_output_contract(self):
    expected = (
        "HFI Content Studio Bot is online.\n\n"
        "Commands:\n"
        "/brief [1-8] - Fetch a fresh brief, optionally limit the number of stories.\n"
        "/story <n> - Show the source links and fuller context for story n from the latest brief.\n"
        "/write <n|x_url|https_url|text> - Turn a brief item, X post, article URL, or pasted text into Hebrew draft variants.\n"
        "/save <variant_index> - Save one variant from your last /write session as a draft in the queue.\n"
        "/schedule - Show the configured brief and alert automation times.\n"
        "/scrape <url> - Scrape an X thread, translate it, and save as a draft.\n"
        "/xtrends - Show the top trending topics on X.\n"
        "/health - Check API and database health.\n"
        "/help - Show examples and supported input formats."
    )
    assert render_start_text() == expected
```

**Step 2: Update `test_start_output_lists_all_visible_commands`**

No change needed — it dynamically checks `visible_start_commands()`.

**Step 3: Verify removed commands are NOT in start text**

Add a new test:

```python
def test_dropped_commands_not_in_start_text(self):
    text = render_start_text()
    assert "/lastbrief" not in text
    assert "/queue" not in text
    assert "/draft" not in text
    assert "/approve" not in text
    assert "/status" not in text
```

**Step 4: Run all telegram tests**

Run: `pytest tests/test_telegram_bot.py tests/test_telegram_bot_security.py tests/test_telegram_bot_startup.py tests/test_telegram_scheduler.py -v`
Expected: ALL PASS

**Step 5: Commit**

```bash
git add tests/test_telegram_bot.py
git commit -m "test(telegram): update tests for slimmed command set"
```

---

### Task 6: Run full test suite and verify

**Files:** None (verification only)

**Step 1: Run the full test suite**

Run: `pytest tests/ -v`
Expected: ALL PASS. No test should reference the removed commands except to assert their absence.

**Step 2: Check for any remaining references to dropped commands**

Search for stale references:
```bash
grep -rn "cmd_lastbrief\|cmd_queue\|cmd_draft\|cmd_approve\|cmd_status" src/telegram_bot/ tests/
```
Expected: Zero matches (no stale references).

```bash
grep -rn "lastbrief\|/queue\|/draft\|/approve\|/status" src/telegram_bot/
```
Expected: Zero matches in telegram bot source. (May appear in API routes, which is fine — those are separate.)

**Step 3: Verify the `/scrape` command footer**

Note: `cmd_scrape` at line 922 references `/approve {draft_id}`. Since `/approve` is removed, update this line to show a frontend edit link instead:

In `cmd_scrape`, change:
```python
f"Draft #{draft_id} · /approve {draft_id} to approve"
```
to:
```python
f"Draft #{draft_id} · Edit: {self._frontend_edit_link(draft_id) if isinstance(draft_id, int) else ''}"
```

**Step 4: Final full test run**

Run: `pytest tests/ -v`
Expected: ALL PASS

**Step 5: Commit**

```bash
git add src/telegram_bot/bot.py
git commit -m "fix(telegram): update /scrape footer to use frontend link instead of removed /approve"
```
