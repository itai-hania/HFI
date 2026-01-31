# HFI Project AI Rules

## Context Usage Tracking

**On EVERY session start (first message):**
1. Reset the context file with fresh values starting from 0% usage
2. Update the session_id with current date/time

---

## Other Project Rules

- Follow rules in `.agent/` directory if they exist
- Avoid unnecessary comments in code
- Every feature should be tested
- Don't create .md files unless explicitly asked
