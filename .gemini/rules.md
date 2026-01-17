# HFI Project AI Rules

## Context Usage Tracking

**On EVERY session start (first message):**
1. Reset the context file with fresh values starting from 0% usage
2. Update the session_id with current date/time

**After EVERY response:**
Update `/Users/itayy16/CursorProjects/HFI/tools/token-counter/context-usage.json` with:

```json
{
  "session_id": "[YYYY-MM-DD_HH:MM]",
  "last_updated": "[current ISO timestamp]",
  "tokens_remaining": [value from system ctx_window],
  "tokens_used": [183000 - tokens_remaining],
  "total_context": 183000,
  "usage_percent": [((183000 - tokens_remaining) / 183000) * 100],
  "status": "🟢 Healthy (<60%)" or "🟡 Warning (60-80%)" or "🔴 Critical (>80%)"
}
```

The user monitors this file with `watch-context.sh` in a terminal.

---

## Other Project Rules

- Follow rules in `.agent/` directory if they exist
- Avoid unnecessary comments in code
- Every feature should be tested
- Don't create .md files unless explicitly asked
