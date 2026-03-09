"""Lightweight UX event logging for dashboard interactions."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


def _events_path() -> Path:
    repo_root = Path(__file__).resolve().parent.parent.parent
    data_dir = repo_root / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir / "ui_events.jsonl"


def log_ux_event(
    action: str,
    view: str,
    success: bool = True,
    duration_ms: Optional[int] = None,
    error_code: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> None:
    """Append a structured UX event to data/ui_events.jsonl."""
    payload: Dict[str, Any] = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "action": action,
        "view": view,
        "success": bool(success),
    }
    if duration_ms is not None:
        payload["duration_ms"] = int(duration_ms)
    if error_code:
        payload["error_code"] = error_code
    if metadata:
        payload["metadata"] = metadata

    try:
        path = _events_path()
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(payload, ensure_ascii=False) + "\n")
    except OSError as exc:
        logger.warning("Failed to write UX event log: %s", exc)
