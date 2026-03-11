"""Structured logging helpers for event-style key=value logs."""

from __future__ import annotations

import logging
from typing import Any


def _format_value(value: Any) -> str:
    text = str(value)
    if not text:
        return '""'
    if any(ch.isspace() for ch in text) or "=" in text or '"' in text:
        escaped = text.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}"'
    return text


def build_event_log(event: str, **fields: Any) -> str:
    """Build an event log line: event=<name> key=value ..."""
    parts = [f"event={_format_value(event)}"]
    for key in sorted(fields):
        value = fields[key]
        if value is None:
            continue
        parts.append(f"{key}={_format_value(value)}")
    return " ".join(parts)


def log_event(logger: logging.Logger, event: str, *, level: int = logging.INFO, **fields: Any) -> None:
    """Emit a structured event line through the provided logger."""
    logger.log(level, build_event_log(event, **fields))

