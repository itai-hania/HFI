"""Telegram bot implementation for HFI content workflows."""

from __future__ import annotations

import html
import logging
from typing import Any, List

import httpx

try:
    from telegram import Update
    from telegram.ext import Application, CommandHandler, ContextTypes
except Exception:  # pragma: no cover - type/runtime fallback for non-bot test environments
    Update = Any  # type: ignore
    Application = Any  # type: ignore
    CommandHandler = Any  # type: ignore

    class _DummyContext:  # pragma: no cover
        DEFAULT_TYPE = Any

    ContextTypes = _DummyContext()  # type: ignore


logger = logging.getLogger(__name__)


def _esc(value: Any) -> str:
    return html.escape(str(value), quote=False)


class HFIBot:
    """Telegram bot facade around HFI API endpoints."""

    def __init__(self, token: str, chat_id: str, api_url: str, api_password: str):
        self.chat_id = chat_id
        self.api_url = api_url.rstrip("/")
        self.api_password = api_password
        self.app = Application.builder().token(token).build()
        self.http = httpx.AsyncClient(base_url=self.api_url, timeout=30.0)
        self.jwt_token: str | None = None
        self._register_handlers()

    def _register_handlers(self):
        self.app.add_handler(CommandHandler("start", self.cmd_start))
        self.app.add_handler(CommandHandler("status", self.cmd_status))
        self.app.add_handler(CommandHandler("brief", self.cmd_brief))
        self.app.add_handler(CommandHandler("schedule", self.cmd_schedule))
        self.app.add_handler(CommandHandler("write", self.cmd_write))

    async def _ensure_auth(self) -> dict[str, str]:
        if not self.jwt_token:
            response = await self.http.post("/api/auth/login", json={"password": self.api_password})
            response.raise_for_status()
            self.jwt_token = response.json()["access_token"]
        return {"Authorization": f"Bearer {self.jwt_token}"}

    async def _request(self, method: str, path: str, **kwargs):
        headers = kwargs.pop("headers", {})
        auth_headers = await self._ensure_auth()
        auth_headers.update(headers)
        response = await self.http.request(method, path, headers=auth_headers, **kwargs)

        if response.status_code == 401:
            # Token expired, re-auth once.
            self.jwt_token = None
            auth_headers = await self._ensure_auth()
            auth_headers.update(headers)
            response = await self.http.request(method, path, headers=auth_headers, **kwargs)

        response.raise_for_status()
        return response

    async def cmd_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text("HFI Content Studio Bot. Use /brief for latest topics.")

    async def cmd_brief(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        response = await self._request("POST", "/api/notifications/brief")
        stories = response.json().get("stories", [])
        msg = format_brief_message(stories, "on-demand")
        await update.message.reply_text(msg, parse_mode="HTML")

    async def cmd_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        drafts = await self._request("GET", "/api/content/drafts?status=pending")
        scheduled = await self._request("GET", "/api/content/scheduled")
        published = await self._request("GET", "/api/content/published")

        msg = (
            f"Drafts: {drafts.json().get('total', 0)}\n"
            f"Scheduled: {scheduled.json().get('total', 0)}\n"
            f"Published: {published.json().get('total', 0)}"
        )
        await update.message.reply_text(msg)

    async def cmd_schedule(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text("Brief schedule: 08:00 and 19:00. Alerts checked every 15 minutes.")

    async def cmd_write(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        source_text = " ".join(context.args) if getattr(context, "args", None) else ""
        if not source_text:
            await update.message.reply_text("Usage: /write <source text or URL>")
            return

        response = await self._request(
            "POST",
            "/api/generation/post",
            json={"source_text": source_text, "num_variants": 2},
        )

        variants = response.json().get("variants", [])
        for variant in variants:
            await update.message.reply_text(
                (
                    f"<b>{_esc(variant.get('label', 'Variant'))}</b>\n\n"
                    f"{_esc(variant.get('content', ''))}\n\n"
                    f"({variant.get('char_count', 0)} chars)"
                ),
                parse_mode="HTML",
            )

    async def send_scheduled_brief(self):
        response = await self._request("POST", "/api/notifications/brief")
        stories = response.json().get("stories", [])
        if not stories:
            return

        msg = format_brief_message(stories, "scheduled")
        await self.app.bot.send_message(chat_id=self.chat_id, text=msg, parse_mode="HTML")

    async def check_alerts(self):
        # Generate new alerts first, then deliver pending.
        await self._request("POST", "/api/notifications/alerts/check")
        response = await self._request("GET", "/api/notifications/alerts?delivered=false")

        alerts = response.json().get("alerts", [])
        for alert in alerts:
            content = alert.get("content", {})
            msg = format_alert_message(content)
            await self.app.bot.send_message(chat_id=self.chat_id, text=msg, parse_mode="HTML")
            await self._request("PATCH", f"/api/notifications/{alert['id']}/delivered")

    async def close(self):
        await self.http.aclose()



def format_brief_message(stories: List[dict], brief_type: str) -> str:
    """Render stories as Telegram-friendly HTML message."""
    if brief_type == "morning":
        header = "Morning Brief"
    elif brief_type == "evening":
        header = "Evening Brief"
    else:
        header = "Brief"

    lines = [f"<b>{header} - {len(stories)} hot topics</b>\n"]
    for index, story in enumerate(stories, 1):
        title = _esc(story.get("title", "Untitled"))
        sources = ", ".join(_esc(item) for item in story.get("sources", []))
        summary = _esc(story.get("summary", ""))
        lines.append(f"{index}. <b>{title}</b>")
        if sources:
            lines.append(f"   Sources: {sources}")
        if summary:
            lines.append(f"   {summary}")
        lines.append(f"   /write_{index}  /skip_{index}\n")

    return "\n".join(lines)



def format_alert_message(alert: dict) -> str:
    """Render a single alert payload for Telegram."""
    sources = ", ".join(_esc(item) for item in alert.get("sources", []))
    summary = _esc(alert.get("summary", ""))
    title = _esc(alert.get("title", "Breaking alert"))
    lines = [f"<b>Breaking:</b> {title}"]
    if sources:
        lines.append(f"Sources: {sources}")
    if summary:
        lines.append(summary)
    lines.append("\n/write  /translate  /skip")
    return "\n".join(lines)
