"""Cross-source alert detection for breaking trend notifications."""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from difflib import SequenceMatcher
from typing import Any, Dict, List, Sequence

from sqlalchemy.orm import Session

from common.models import Notification

_STOPWORDS = {
    "the",
    "a",
    "an",
    "and",
    "or",
    "of",
    "to",
    "for",
    "in",
    "on",
    "with",
    "at",
    "from",
    "new",
    "says",
}


class AlertDetector:
    """Detects multi-source hot stories and stores undelivered alert notifications."""

    def __init__(self, news_scraper, db_session: Session):
        self.news_scraper = news_scraper
        self.db = db_session

    @staticmethod
    def _extract_keywords(title: str) -> set[str]:
        words = re.findall(r"[A-Za-z0-9']+", (title or "").lower())
        return {w for w in words if len(w) > 2 and w not in _STOPWORDS}

    @staticmethod
    def _similarity(a: str, b: str) -> float:
        return SequenceMatcher(None, (a or "").lower(), (b or "").lower()).ratio()

    @classmethod
    def _keyword_overlap(cls, a: str, b: str) -> float:
        left = cls._extract_keywords(a)
        right = cls._extract_keywords(b)
        if not left or not right:
            return 0.0
        return len(left & right) / len(left | right)

    def _load_recent_alert_fingerprints(self, hours: int = 24) -> List[tuple[str, set[str]]]:
        """Fetch recent alert titles + keywords once to avoid per-article DB scans."""
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
        rows = (
            self.db.query(Notification.content)
            .filter(Notification.type == "alert", Notification.created_at >= cutoff)
            .all()
        )
        titles: List[tuple[str, set[str]]] = []
        for (content,) in rows:
            if isinstance(content, dict):
                title = content.get("title") or ""
                if title:
                    normalized = str(title)
                    titles.append((normalized, self._extract_keywords(normalized)))
        return titles

    def _already_alerted_in_titles(
        self,
        title: str,
        title_keywords: set[str],
        existing_titles: Sequence[tuple[str, set[str]]],
    ) -> bool:
        """Deduplicate against an in-memory title list."""
        for existing_title, existing_keywords in existing_titles:
            if title_keywords and existing_keywords:
                intersection = len(title_keywords & existing_keywords)
                if intersection:
                    union = len(title_keywords | existing_keywords)
                    if union and (intersection / union) >= 0.6:
                        return True
                else:
                    # No shared keywords - skip expensive fuzzy ratio.
                    continue
            if self._similarity(existing_title, title) >= 0.85:
                return True
        return False

    def _build_source_count(self, article: Dict[str, Any], all_articles: List[Dict[str, Any]]) -> int:
        """Estimate source count by keyword overlap across unique sources."""
        this_title = article.get("title") or ""
        this_source = article.get("source")

        if article.get("source_count"):
            try:
                return int(article["source_count"])
            except (TypeError, ValueError):
                pass

        this_keywords = self._extract_keywords(this_title)
        related_sources = {this_source} if this_source else set()

        for other in all_articles:
            if other is article:
                continue
            other_source = other.get("source")
            if not other_source or other_source in related_sources:
                continue

            other_keywords = self._extract_keywords(other.get("title") or "")
            if not this_keywords or not other_keywords:
                continue

            overlap = len(this_keywords & other_keywords)
            union = len(this_keywords | other_keywords)
            if union and (overlap / union >= 0.5 or self._similarity(this_title, other.get("title") or "") >= 0.8):
                related_sources.add(other_source)

        return max(1, len(related_sources))

    def _create_notification(self, article: Dict[str, Any], source_count: int) -> Notification:
        content = {
            "title": article.get("title") or "",
            "summary": (article.get("description") or "")[:280],
            "sources": [article.get("source")] if article.get("source") else [],
            "source_count": source_count,
            "url": article.get("url") or article.get("article_url"),
        }

        row = Notification(type="alert", content=content, delivered=False)
        self.db.add(row)
        self.db.flush()
        return row

    def check_for_alerts(self, min_sources: int = 3) -> List[Dict[str, Any]]:
        """Fetch latest news, detect cross-source stories, and persist alerts."""
        articles = self.news_scraper.get_latest_news(limit_per_source=10, total_limit=20)
        created: List[Dict[str, Any]] = []
        existing_titles = self._load_recent_alert_fingerprints(hours=24)

        for article in articles:
            title = article.get("title") or ""
            if not title:
                continue
            title_keywords = self._extract_keywords(title)

            source_count = self._build_source_count(article, articles)
            if source_count < min_sources:
                continue

            if self._already_alerted_in_titles(title, title_keywords, existing_titles):
                continue

            notif = self._create_notification(article, source_count)
            created.append({"id": notif.id, "title": title, "source_count": source_count})
            existing_titles.append((title, title_keywords))

        if created:
            self.db.commit()

        return created
