"""Telegram bot implementation for HFI content workflows."""

from __future__ import annotations

import hashlib
import html
import logging
from dataclasses import dataclass
from typing import Any, Callable, Dict, List
from urllib.parse import urlparse
from uuid import uuid4

import httpx

from common.logging_utils import log_event
from common.stopwords import STOPWORDS
from common.url_validation import URLValidationError, X_HOSTS, validate_article_url, validate_x_status_url
from telegram_bot.command_catalog import render_help_text, render_start_text

try:
    from telegram import Update
    from telegram.error import BadRequest, Conflict
    from telegram.ext import Application, CommandHandler, ContextTypes
except Exception:  # pragma: no cover - type/runtime fallback for non-bot test environments
    Update = Any  # type: ignore
    BadRequest = RuntimeError  # type: ignore
    Conflict = RuntimeError  # type: ignore

    class _DummyUpdater:  # pragma: no cover
        async def start_polling(self):
            return None

        async def stop(self):
            return None

    class _DummyBot:  # pragma: no cover
        async def send_message(self, *_, **__):
            return None

    class _DummyApp:  # pragma: no cover
        def __init__(self):
            self.bot = _DummyBot()
            self.updater = _DummyUpdater()

        def add_handler(self, *_args, **_kwargs):
            return None

        async def initialize(self):
            return None

        async def start(self):
            return None

        async def stop(self):
            return None

        async def shutdown(self):
            return None

    class _DummyBuilder:  # pragma: no cover
        def token(self, _token: str):
            return self

        def build(self):
            return _DummyApp()

    class Application:  # pragma: no cover
        @staticmethod
        def builder():
            return _DummyBuilder()

    class CommandHandler:  # pragma: no cover
        def __init__(self, *_args, **_kwargs):
            pass

    class _DummyContext:  # pragma: no cover
        DEFAULT_TYPE = Any

    ContextTypes = _DummyContext()  # type: ignore


logger = logging.getLogger(__name__)
_MAX_TELEGRAM_MESSAGE_CHARS = 3500


@dataclass
class WriteSession:
    session_id: str
    source_type: str
    original_text: str
    preview_text: str
    title: str | None
    canonical_url: str | None
    source_domain: str | None
    variants: list[dict[str, Any]]


@dataclass
class ChatState:
    last_brief: list[dict[str, Any]] | None = None
    last_write_session: WriteSession | None = None


def _collapse_whitespace(value: str) -> str:
    return " ".join((value or "").split())


def _safe_preview(value: str, max_chars: int = 240) -> str:
    text = _collapse_whitespace(value)
    if len(text) <= max_chars:
        return text
    return f"{text[: max_chars - 1].rstrip()}…"


def _safe_text(value: str) -> str:
    return html.escape(_collapse_whitespace(value), quote=False)


def _first_safe_source_link(story: dict[str, Any]) -> str | None:
    urls = story.get("source_urls") or []
    if not isinstance(urls, list):
        return None
    for url in urls:
        text = str(url or "").strip()
        if not text:
            continue
        parsed = urlparse(text)
        if parsed.scheme == "https" and parsed.netloc and not (parsed.username or parsed.password):
            return text
    return None


def _chunk_text(text: str, max_chars: int = _MAX_TELEGRAM_MESSAGE_CHARS) -> list[str]:
    if len(text) <= max_chars:
        return [text]

    chunks: list[str] = []
    current = ""
    for line in text.splitlines(keepends=True):
        if len(current) + len(line) <= max_chars:
            current += line
            continue

        if current:
            chunks.append(current.rstrip())
            current = ""

        while len(line) > max_chars:
            chunks.append(line[:max_chars].rstrip())
            line = line[max_chars:]
        current = line

    if current.strip():
        chunks.append(current.rstrip())
    return chunks


def _extract_story_keywords(title: str) -> list[str]:
    """Extract meaningful keywords from a story title for feedback."""
    words = title.lower().split()
    return [w.strip(".,!?:;\"'()") for w in words if w.strip(".,!?:;\"'()") not in STOPWORDS and len(w) > 2]


def _format_story_lines(story: dict, index: int, now, israel_sources: set) -> list[str]:
    """Format a single story as HTML lines."""
    from datetime import datetime as _dt

    title = html.escape(str(story.get("title", "Untitled")))
    summary = html.escape(_safe_preview(str(story.get("summary", "")), max_chars=280))
    source_count = story.get("source_count", len(story.get("sources", [])))
    relevance = story.get("relevance_score", 0)
    sources = story.get("sources", [])
    source_urls = story.get("source_urls", [])

    age_str = ""
    published = story.get("published_at")
    if published:
        if isinstance(published, str):
            try:
                pub_dt = _dt.fromisoformat(published.replace("Z", "+00:00"))
                age_hours = (now - pub_dt).total_seconds() / 3600
                if age_hours < 1:
                    age_str = f"{int(age_hours * 60)}m ago"
                elif age_hours < 24:
                    age_str = f"{int(age_hours)}h ago"
                else:
                    age_str = f"{int(age_hours / 24)}d ago"
            except (ValueError, TypeError):
                pass

    is_israel = any(s.lower() in israel_sources for s in sources)
    badge = "\U0001f535 Israel" if is_israel else f"\U0001f3af {relevance}"

    source_names = [html.escape(s) for s in sources]

    lines = [f"<b>{index}.</b> <b>{title}</b>"]
    if summary:
        lines.append(f"   {summary}")
    meta_parts = []
    if age_str:
        meta_parts.append(f"\u23f1 {age_str}")
    meta_parts.append(f"\U0001f4e1 {source_count} sources")
    meta_parts.append(badge)
    lines.append("   " + " \u00b7 ".join(meta_parts))
    if source_names:
        lines.append("   " + " \u00b7 ".join(source_names))
    lines.append("")
    return lines


def format_brief_message(stories: list[dict], brief_type: str, themes: list[dict] | None = None) -> str:
    """Render stories as rich HTML for Telegram — themed if themes provided."""
    from datetime import datetime, timezone, timedelta

    if brief_type == "morning":
        header = "Morning Brief"
    elif brief_type == "evening":
        header = "Evening Brief"
    else:
        header = "Brief"

    now = datetime.now(timezone.utc)
    ist_now = now + timedelta(hours=2)
    timestamp = ist_now.strftime("%H:%M")

    lines = [f"\U0001f4ca <b>{header}</b> \u00b7 {len(stories)} stories \u00b7 {timestamp} IST", ""]

    israel_sources = {"calcalist", "globes", "times of israel"}

    if themes:
        story_index = 1
        for theme in themes:
            lines.append(f"{theme.get('emoji', '\U0001f4ca')} <b>{html.escape(theme.get('name', 'News'))}</b>")
            takeaway = theme.get("takeaway", "")
            if takeaway:
                lines.append(f"   {html.escape(takeaway)}")
            lines.append("")

            for story in theme.get("stories", []):
                lines.extend(_format_story_lines(story, story_index, now, israel_sources))
                story_index += 1
    else:
        for index, story in enumerate(stories, 1):
            lines.extend(_format_story_lines(story, index, now, israel_sources))

    lines.append("/write N \u00b7 /story N \u00b7 /skip N")
    return "\n".join(lines).strip()


def format_alert_message(alert: dict) -> str:
    """Render a single alert as rich HTML for Telegram."""
    title = html.escape(str(alert.get("title", "Breaking alert")))
    summary = html.escape(_safe_preview(str(alert.get("summary", "")), max_chars=280))
    source_count = alert.get("source_count", 0)
    sources = alert.get("sources", [])
    source_urls = alert.get("source_urls", [])

    source_links = []
    for i, src in enumerate(sources):
        url = source_urls[i] if i < len(source_urls) else ""
        if url:
            source_links.append(f'<a href="{url}">{html.escape(src)}</a>')
        else:
            source_links.append(html.escape(src))

    lines = [f"🚨 <b>Breaking:</b> {title}"]
    if summary:
        lines.append(summary)
    lines.append(f"📡 {source_count} sources")
    if source_links:
        lines.append(" · ".join(source_links))
    lines.append("")
    lines.append("/write alert to create content")
    return "\n".join(lines)


class HFIBot:
    """Telegram bot facade around HFI API endpoints."""

    def __init__(
        self,
        token: str,
        chat_id: str,
        api_url: str,
        api_password: str,
        brief_times: List[str] | None = None,
        alert_interval_minutes: int = 15,
        frontend_base_url: str = "http://localhost:3000",
    ):
        self.chat_id = chat_id
        self.api_url = api_url.rstrip("/")
        self.api_password = api_password
        self.brief_times = list(brief_times or ["08:00", "19:00"])
        self.alert_interval_minutes = max(1, int(alert_interval_minutes))
        self.frontend_base_url = frontend_base_url.rstrip("/")
        self.app = Application.builder().token(token).build()
        self.http = httpx.AsyncClient(base_url=self.api_url, timeout=30.0)
        self.jwt_token: str | None = None
        self._chat_states: dict[str, ChatState] = {}
        self._register_handlers()

    def _register_handlers(self):
        self.app.add_handler(CommandHandler("start", self.cmd_start))
        self.app.add_handler(CommandHandler("help", self.cmd_help))
        self.app.add_handler(CommandHandler("health", self.cmd_health))
        self.app.add_handler(CommandHandler("brief", self.cmd_brief))
        self.app.add_handler(CommandHandler("story", self.cmd_story))
        self.app.add_handler(CommandHandler("write", self.cmd_write))
        self.app.add_handler(CommandHandler("save", self.cmd_save))
        self.app.add_handler(CommandHandler("schedule", self.cmd_schedule))
        self.app.add_handler(CommandHandler("skip", self.cmd_skip))
        self.app.add_handler(CommandHandler("scrape", self.cmd_scrape))
        self.app.add_handler(CommandHandler("xtrends", self.cmd_xtrends))

    def _chat_key(self, update: Update) -> str:
        chat_id = getattr(getattr(update, "effective_chat", None), "id", None)
        return str(chat_id) if chat_id is not None else str(self.chat_id)

    def _state_for(self, update: Update) -> ChatState:
        key = self._chat_key(update)
        return self._state_for_chat_key(key)

    def _state_for_chat_key(self, key: str) -> ChatState:
        if key not in self._chat_states:
            self._chat_states[key] = ChatState()
        return self._chat_states[key]

    def _is_authorized_chat(self, update: Update) -> bool:
        """Allow command handling only from the configured chat."""
        chat_id = getattr(getattr(update, "effective_chat", None), "id", None)
        if chat_id is None:
            return False
        return str(chat_id) == str(self.chat_id)

    async def _ensure_auth(self) -> dict[str, str]:
        if not self.jwt_token:
            response = await self.http.post("/api/auth/login", json={"password": self.api_password})
            if response.status_code >= 400:
                log_event(logger, "auth_failed", level=logging.ERROR, status=response.status_code)
            response.raise_for_status()
            self.jwt_token = response.json()["access_token"]
        return {"Authorization": f"Bearer {self.jwt_token}"}

    async def _request(self, method: str, path: str, **kwargs) -> httpx.Response:
        headers = kwargs.pop("headers", {})
        auth_headers = await self._ensure_auth()
        auth_headers.update(headers)
        response = await self.http.request(method, path, headers=auth_headers, **kwargs)

        if response.status_code == 401:
            self.jwt_token = None
            auth_headers = await self._ensure_auth()
            auth_headers.update(headers)
            response = await self.http.request(method, path, headers=auth_headers, **kwargs)

        response.raise_for_status()
        return response

    @staticmethod
    def _extract_http_error_detail(error: httpx.HTTPStatusError) -> str:
        try:
            payload = error.response.json()
        except ValueError:
            return f"API returned HTTP {error.response.status_code}."
        if isinstance(payload, dict):
            detail = payload.get("detail")
            if isinstance(detail, str) and detail.strip():
                return detail
        return f"API returned HTTP {error.response.status_code}."

    async def _reply_text(self, update: Update, text: str, parse_mode: str | None = None):
        message = getattr(update, "message", None)
        if message is None:
            return
        try:
            await message.reply_text(text, parse_mode=parse_mode)
        except BadRequest as err:
            log_event(logger, "telegram_rejected_message", level=logging.WARNING, error=str(err))
            raise

    async def _send_chunked_reply(self, update: Update, text: str, parse_mode: str | None = None):
        for chunk in _chunk_text(text, max_chars=_MAX_TELEGRAM_MESSAGE_CHARS):
            await self._reply_text(update, chunk, parse_mode=parse_mode)

    async def _reply_error(self, update: Update, err: Exception):
        logger.exception("Telegram command failed: %s", err)
        if isinstance(err, Conflict):
            detail = "Another Telegram polling session is already running for this bot."
        elif isinstance(err, BadRequest):
            detail = "Telegram rejected the message payload. Try shorter plain text."
        elif isinstance(err, httpx.ConnectError):
            detail = "Cannot reach API service right now."
        elif isinstance(err, httpx.HTTPStatusError):
            status = err.response.status_code
            if status in {401, 403}:
                detail = "API authentication failed."
            elif status == 404:
                detail = "Requested item was not found."
            elif status == 409:
                detail = "Item already exists."
            elif status >= 500:
                detail = "API returned an internal error."
            else:
                detail = self._extract_http_error_detail(err)
        else:
            detail = "Unexpected command failure."
        await self._reply_text(update, f"Command failed. {detail}")

    async def _reject_if_unauthorized(self, update: Update, command_name: str) -> bool:
        if self._is_authorized_chat(update):
            return False
        log_event(
            logger,
            "telegram_rejected_message",
            level=logging.WARNING,
            command=command_name,
            reason="unauthorized_chat",
        )
        return True

    async def run_startup_self_checks(self):
        """Validate API, auth, and queue endpoints before polling."""
        try:
            response = await self.http.get("/health")
            response.raise_for_status()
            payload = response.json()
            log_event(
                logger,
                "bot_startup_check",
                check="health",
                status=payload.get("status", "unknown"),
                db_status=(payload.get("database") or {}).get("status", "unknown"),
            )
        except httpx.ConnectError as exc:
            log_event(logger, "api_unreachable", level=logging.ERROR, check="health", error=str(exc))
            raise

        try:
            login_response = await self.http.post("/api/auth/login", json={"password": self.api_password})
            login_response.raise_for_status()
            self.jwt_token = login_response.json().get("access_token")
            if not self.jwt_token:
                raise RuntimeError("Auth response did not include access_token")
            log_event(logger, "bot_startup_check", check="auth", status="ok")
        except httpx.HTTPStatusError as exc:
            log_event(
                logger,
                "auth_failed",
                level=logging.ERROR,
                check="auth",
                status=exc.response.status_code,
                detail=self._extract_http_error_detail(exc),
            )
            raise

        try:
            response = await self._request("GET", "/api/content/queue/summary")
            log_event(
                logger,
                "bot_startup_check",
                check="queue_summary",
                status="ok",
                pending=response.json().get("pending", 0),
            )
        except httpx.ConnectError as exc:
            log_event(logger, "api_unreachable", level=logging.ERROR, check="queue_summary", error=str(exc))
            raise

    async def cmd_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if await self._reject_if_unauthorized(update, "start"):
            return
        await self._reply_text(update, render_start_text())

    async def cmd_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if await self._reject_if_unauthorized(update, "help"):
            return
        await self._reply_text(update, render_help_text())

    async def cmd_health(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if await self._reject_if_unauthorized(update, "health"):
            return
        try:
            response = await self.http.get("/health")
            response.raise_for_status()
            payload = response.json()
            await self._reply_text(
                update,
                (
                    "API health: "
                    f"{payload.get('status', 'unknown')} | "
                    f"DB: {(payload.get('database') or {}).get('status', 'unknown')}"
                ),
            )
        except Exception as err:  # pragma: no cover - exercised in integration
            await self._reply_error(update, err)

    async def _fetch_latest_brief(self) -> list[dict[str, Any]]:
        response = await self._request("GET", "/api/notifications/brief/latest")
        return response.json().get("stories", [])

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

    async def cmd_brief(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if await self._reject_if_unauthorized(update, "brief"):
            return

        try:
            count = self._brief_input(getattr(context, "args", []) or [])
            response = await self._request("POST", "/api/notifications/brief?force_refresh=true")
            data = response.json()
            stories = data.get("stories", [])[:count]
            themes = data.get("themes", [])
            self._state_for(update).last_brief = stories

            msg = format_brief_message(stories, "on-demand", themes=themes)
            await self._send_chunked_reply(update, msg, parse_mode="HTML")
            log_event(logger, "brief_sent", mode="on_demand", count=len(stories))
        except ValueError as err:
            await self._reply_text(update, str(err))
        except Exception as err:  # pragma: no cover - exercised in integration
            await self._reply_error(update, err)

    async def _load_brief_for_chat(self, update: Update) -> list[dict[str, Any]] | None:
        state = self._state_for(update)
        if state.last_brief:
            return state.last_brief
        try:
            stories = await self._fetch_latest_brief()
        except httpx.HTTPStatusError as err:
            if err.response.status_code == 404:
                return None
            raise
        state.last_brief = stories
        return stories

    async def cmd_story(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if await self._reject_if_unauthorized(update, "story"):
            return

        arg = (getattr(context, "args", []) or [None])[0]
        if arg is None or not str(arg).isdigit():
            await self._reply_text(update, "Usage: /story <n>")
            return
        index = int(arg)
        if index <= 0:
            await self._reply_text(update, "Story index must be >= 1.")
            return

        try:
            stories = await self._load_brief_for_chat(update)
            if not stories:
                await self._reply_text(update, "No cached brief found. Run /brief first.")
                return
            if index > len(stories):
                await self._reply_text(update, f"Story {index} is not available in the cached brief.")
                return

            story = stories[index - 1]
            lines = [
                f"Story {index}",
                f"Title: {_collapse_whitespace(str(story.get('title', 'Untitled')))}",
                f"Summary: {_collapse_whitespace(str(story.get('summary', '')))}",
            ]
            source_urls = story.get("source_urls") or []
            if isinstance(source_urls, list) and source_urls:
                lines.append("Sources:")
                for item in source_urls:
                    lines.append(f"- {item}")

            await self._send_chunked_reply(update, "\n".join(lines))
        except Exception as err:
            await self._reply_error(update, err)

    @staticmethod
    def _story_to_source_text(story: dict[str, Any]) -> str:
        title = _collapse_whitespace(str(story.get("title", "")))
        summary = _collapse_whitespace(str(story.get("summary", "")))
        links = [str(item) for item in (story.get("source_urls") or []) if item]
        lines = [line for line in [title, summary] if line]
        if links:
            lines.append("Sources: " + ", ".join(links))
        return "\n".join(lines).strip()

    async def _resolve_source(self, payload: dict[str, Any]) -> dict[str, Any]:
        response = await self._request("POST", "/api/generation/source/resolve", json=payload)
        resolved = response.json()
        log_event(
            logger,
            "source_resolved",
            source_type=resolved.get("source_type"),
            source_domain=resolved.get("source_domain"),
        )
        return resolved

    def _classify_write_input(
        self,
        source_input: str,
        brief_stories: list[dict[str, Any]] | None,
    ) -> tuple[dict[str, Any] | None, str | None]:
        raw = source_input.strip()
        if not raw:
            return None, "Usage: /write <n|x_url|https_url|text>"

        if raw.isdigit():
            if not brief_stories:
                return None, "No cached brief found. Run /brief first."
            index = int(raw)
            if index <= 0 or index > len(brief_stories):
                return None, f"Story {index} is not available in the cached brief."
            story = brief_stories[index - 1]
            text_payload = self._story_to_source_text(story)
            return {"text": text_payload}, None

        looks_like_url = raw.startswith("https://") or "://" in raw
        if looks_like_url:
            parsed = urlparse(raw)
            host = (parsed.hostname or "").lower()
            try:
                if host in X_HOSTS:
                    return {"url": validate_x_status_url(raw)}, None
                if not raw.startswith("https://"):
                    return None, "Only https URLs are accepted."
                return {"url": validate_article_url(raw)}, None
            except URLValidationError as exc:
                if host in X_HOSTS:
                    return None, str(exc)
                return None, "Unsafe or unsupported HTTPS URL."

        return {"text": raw}, None

    async def cmd_write(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if await self._reject_if_unauthorized(update, "write"):
            return

        source_input = " ".join(context.args) if getattr(context, "args", None) else ""
        state = self._state_for(update)

        payload, error_text = self._classify_write_input(source_input, state.last_brief)
        if error_text:
            await self._reply_text(update, error_text)
            return
        if payload is None:
            await self._reply_text(update, "Usage: /write <n|x_url|https_url|text>")
            return

        try:
            resolved = await self._resolve_source(payload)
        except httpx.HTTPStatusError as err:
            detail = self._extract_http_error_detail(err)
            await self._reply_text(update, detail)
            return
        except Exception as err:
            await self._reply_error(update, err)
            return

        preview_lines = [
            "Source resolved.",
            f"Type: {resolved.get('source_type', 'unknown')}",
        ]
        if resolved.get("title"):
            preview_lines.append(f"Title: {resolved['title']}")
        if resolved.get("canonical_url"):
            preview_lines.append(f"URL: {resolved['canonical_url']}")
        preview_lines.append(f"Preview: {resolved.get('preview_text', '')}")
        await self._send_chunked_reply(update, "\n".join(preview_lines))

        try:
            response = await self._request(
                "POST",
                "/api/generation/post",
                json={"source_text": resolved.get("original_text", ""), "num_variants": 2},
            )
            variants = response.json().get("variants", [])
            if not variants:
                await self._reply_text(update, "No variants returned.")
                return

            session = WriteSession(
                session_id=uuid4().hex,
                source_type=str(resolved.get("source_type") or "text"),
                original_text=str(resolved.get("original_text") or ""),
                preview_text=str(resolved.get("preview_text") or ""),
                title=(str(resolved.get("title")) if resolved.get("title") else None),
                canonical_url=(str(resolved.get("canonical_url")) if resolved.get("canonical_url") else None),
                source_domain=(str(resolved.get("source_domain")) if resolved.get("source_domain") else None),
                variants=variants,
            )
            state.last_write_session = session

            for idx, variant in enumerate(variants, start=1):
                msg = (
                    f"Variant {idx}: {variant.get('label', 'Variant')}\n\n"
                    f"{variant.get('content', '')}\n\n"
                    f"Chars: {variant.get('char_count', 0)} | "
                    f"Quality: {variant.get('quality_score', 0)}\n"
                    f"Use /save {idx} to persist this draft."
                )
                await self._send_chunked_reply(update, msg)
        except Exception as err:  # pragma: no cover - exercised in integration
            await self._reply_error(update, err)

    @staticmethod
    def _manual_source_url(source_text: str) -> str:
        digest = hashlib.sha256(source_text.encode("utf-8")).hexdigest()[:16]
        return f"https://manual.local/content/{digest}"

    def _frontend_edit_link(self, content_id: int) -> str:
        return f"{self.frontend_base_url}/create?edit={content_id}"

    async def cmd_save(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if await self._reject_if_unauthorized(update, "save"):
            return
        arg = (getattr(context, "args", []) or [None])[0]
        if arg is None or not str(arg).isdigit():
            await self._reply_text(update, "Usage: /save <variant_index>")
            return
        variant_index = int(arg)
        if variant_index <= 0:
            await self._reply_text(update, "variant_index must be >= 1.")
            return

        state = self._state_for(update)
        session = state.last_write_session
        if session is None:
            await self._reply_text(update, "No /write session found. Run /write first.")
            return
        if variant_index > len(session.variants):
            await self._reply_text(update, f"Variant {variant_index} is not available.")
            return

        variant = session.variants[variant_index - 1]
        source_url = session.canonical_url or self._manual_source_url(session.original_text)

        payload = {
            "source_url": source_url,
            "original_text": session.original_text,
            "hebrew_draft": variant.get("content", ""),
            "content_type": "generation",
            "status": "processed",
            "generation_metadata": {
                "origin": "telegram",
                "source_type": session.source_type,
                "canonical_source_url": session.canonical_url,
                "source_title": session.title,
                "variant_index": variant_index,
                "label": variant.get("label"),
                "quality_score": variant.get("quality_score"),
                "write_session_id": session.session_id,
            },
        }

        try:
            response = await self._request("POST", "/api/content", json=payload)
            content = response.json()
            content_id = int(content["id"])
            link = self._frontend_edit_link(content_id)
            log_event(
                logger,
                "draft_saved",
                content_id=content_id,
                source_type=session.source_type,
                variant_index=variant_index,
            )
            await self._reply_text(
                update,
                (
                    f"Draft saved as #{content_id}.\n"
                    f"Status: {content.get('status', 'processed')}\n"
                    f"Edit: {link}"
                ),
            )
        except httpx.HTTPStatusError as err:
            if err.response.status_code == 409:
                data = err.response.json()
                existing_id = data.get("existing_id")
                if existing_id is not None:
                    link = self._frontend_edit_link(int(existing_id))
                    await self._reply_text(
                        update,
                        (
                            f"Draft already exists as #{existing_id}.\n"
                            f"Edit: {link}"
                        ),
                    )
                    return
            await self._reply_error(update, err)
        except Exception as err:
            await self._reply_error(update, err)

    async def cmd_schedule(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if await self._reject_if_unauthorized(update, "schedule"):
            return
        brief_schedule = ", ".join(self.brief_times) if self.brief_times else "none configured"
        await self._reply_text(
            update,
            (
                f"Brief schedule (UTC): {brief_schedule}\n"
                f"Alert checks every {self.alert_interval_minutes} minutes."
            ),
        )

    async def cmd_scrape(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if await self._reject_if_unauthorized(update, "scrape"):
            return

        args = getattr(context, "args", []) or []
        if not args:
            await self._reply_text(update, "Usage: /scrape &lt;x_thread_url&gt;", parse_mode="HTML")
            return

        url = args[0]
        try:
            validated = validate_x_status_url(url)
        except (URLValidationError, ValueError):
            await self._reply_text(update, "Invalid X URL. Use: /scrape https://x.com/user/status/...")
            return

        await self._reply_text(update, "🔄 Scraping thread...")

        try:
            response = await self._request("POST", "/api/content/from-thread", json={
                "url": validated, "mode": "consolidated", "auto_translate": True,
            })
            data = response.json()
            first = data.get("saved_items", [{}])[0] if data.get("saved_items") else {}
            preview = _safe_preview(first.get("hebrew_draft") or first.get("original_text") or "", max_chars=500)
            draft_id = first.get("id", "?")
            msg = (
                f"<b>Thread scraped</b>\n\n"
                f"{html.escape(preview)}\n\n"
                f"Draft #{draft_id} · Edit: {self._frontend_edit_link(int(draft_id)) if str(draft_id).isdigit() else ''}"
            )
            await self._send_chunked_reply(update, msg, parse_mode="HTML")
        except Exception as err:
            await self._reply_error(update, err)

    async def cmd_xtrends(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if await self._reject_if_unauthorized(update, "xtrends"):
            return

        await self._reply_text(update, "🔄 Fetching X trends...")

        try:
            response = await self._request("POST", "/api/scrape/trends", json={"limit": 10})
            data = response.json()
            trends = data.get("trends", [])

            if not trends:
                await self._reply_text(update, "No trending topics found.")
                return

            lines = ["<b>📈 X Trending Topics</b>", ""]
            for i, trend in enumerate(trends, 1):
                title = html.escape(str(trend.get("title", "")))
                lines.append(f"<b>{i}.</b> {title}")
            lines.append("")
            lines.append("/write &lt;topic&gt; to create content")

            await self._send_chunked_reply(update, "\n".join(lines), parse_mode="HTML")
        except Exception as err:
            await self._reply_error(update, err)

    async def cmd_skip(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Mark a brief story as not relevant — /skip N."""
        if await self._reject_if_unauthorized(update, "skip"):
            return

        args = context.args or []
        if not args or not args[0].isdigit():
            await self._reply_text(update, "Usage: /skip N (story number from last brief)")
            return

        index = int(args[0]) - 1
        state = self._state_for(update)
        stories = state.last_brief or []

        if index < 0 or index >= len(stories):
            await self._reply_text(update, f"Invalid story number. Last brief had {len(stories)} stories.")
            return

        story = stories[index]
        title = story.get("title", "")
        keywords = _extract_story_keywords(title)

        try:
            await self._request("POST", "/api/notifications/brief/feedback", json={
                "story_title": title,
                "feedback_type": "not_relevant",
                "keywords": keywords,
                "source": "telegram",
            })
            await self._reply_text(update, f"Got it, less stories like \"{title[:50]}...\"")
        except Exception as err:
            await self._reply_error(update, err)

    async def send_scheduled_brief(self):
        response = await self._request("POST", "/api/notifications/brief")
        data = response.json()
        stories = data.get("stories", [])
        themes = data.get("themes", [])
        if not stories:
            return

        self._state_for_chat_key(str(self.chat_id)).last_brief = stories
        msg = format_brief_message(stories, "scheduled", themes=themes)
        try:
            await self.app.bot.send_message(chat_id=self.chat_id, text=msg, parse_mode="HTML")
            log_event(logger, "brief_sent", mode="scheduled", count=len(stories))
        except BadRequest as err:
            log_event(logger, "telegram_rejected_message", level=logging.WARNING, error=str(err))
            raise

    async def check_alerts(self):
        # Generate new alerts first, then deliver pending.
        await self._request("POST", "/api/notifications/alerts/check")
        response = await self._request("GET", "/api/notifications/alerts?delivered=false")

        alerts = response.json().get("alerts", [])
        for alert in alerts:
            content = alert.get("content", {})
            msg = format_alert_message(content)
            try:
                await self.app.bot.send_message(chat_id=self.chat_id, text=msg, parse_mode="HTML")
                await self._request("PATCH", f"/api/notifications/{alert['id']}/delivered")
            except BadRequest as err:
                log_event(logger, "telegram_rejected_message", level=logging.WARNING, error=str(err))
            except Exception as err:  # pragma: no cover - exercised in integration
                logger.exception("Failed delivering alert id=%s: %s", alert.get("id"), err)

    async def close(self):
        await self.http.aclose()
