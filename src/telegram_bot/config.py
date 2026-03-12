"""Configuration loading for Telegram bot service."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import List

from common.env_utils import load_dotenv_checked, require_env_vars

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_DOTENV_PATH = _PROJECT_ROOT / ".env"

BOT_REQUIRED_ENV_VARS = (
    "TELEGRAM_BOT_TOKEN",
    "TELEGRAM_CHAT_ID",
    "API_BASE_URL",
    "DASHBOARD_PASSWORD",
    "JWT_SECRET",
)


def _parse_brief_times(raw_value: str) -> List[str]:
    """Parse comma-separated HH:MM brief times with safe fallback."""
    values = [item.strip() for item in raw_value.split(",") if item.strip()]
    parsed: List[str] = []

    for value in values:
        parts = value.split(":", maxsplit=1)
        if len(parts) != 2:
            continue
        hour_text, minute_text = parts
        if not (hour_text.isdigit() and minute_text.isdigit()):
            continue
        hour = int(hour_text)
        minute = int(minute_text)
        if 0 <= hour <= 23 and 0 <= minute <= 59:
            parsed.append(f"{hour:02d}:{minute:02d}")

    if not parsed:
        return ["08:00", "19:00"]
    return parsed


def _parse_int(raw_value: str, default: int) -> int:
    try:
        return int(raw_value)
    except (TypeError, ValueError):
        return default


@dataclass(frozen=True)
class BotConfig:
    token: str
    chat_id: str
    api_base_url: str
    api_password: str
    brief_times: List[str]
    alert_interval_minutes: int
    frontend_base_url: str


def load_bot_config() -> BotConfig:
    """Load env values with duplicate-key and required-var checks."""
    load_dotenv_checked(_DOTENV_PATH)
    values = require_env_vars(BOT_REQUIRED_ENV_VARS, scope="telegram bot")

    brief_times = _parse_brief_times(os.getenv("BRIEF_TIMES", "08:00,19:00"))
    alert_interval_minutes = max(1, _parse_int(os.getenv("ALERT_CHECK_INTERVAL_MINUTES", "15"), 15))
    frontend_base_url = os.getenv("FRONTEND_BASE_URL", "http://localhost:3000").strip() or "http://localhost:3000"

    return BotConfig(
        token=values["TELEGRAM_BOT_TOKEN"],
        chat_id=values["TELEGRAM_CHAT_ID"],
        api_base_url=values["API_BASE_URL"],
        api_password=values["DASHBOARD_PASSWORD"],
        brief_times=brief_times,
        alert_interval_minutes=alert_interval_minutes,
        frontend_base_url=frontend_base_url.rstrip("/"),
    )
