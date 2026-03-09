"""Configuration for Telegram bot service."""

import os

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")
API_PASSWORD = os.getenv("DASHBOARD_PASSWORD", "")
BRIEF_TIMES = ["08:00", "19:00"]
ALERT_CHECK_INTERVAL_MINUTES = int(os.getenv("ALERT_CHECK_INTERVAL_MINUTES", "15"))
