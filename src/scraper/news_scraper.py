"""
News Scraper Module for HFI

This module handles scraping news from various RSS feeds:
- Yahoo Finance (News)
- WSJ (Markets)
- TechCrunch (Fintech)
- Bloomberg (Markets)

It normalizes the data into a common format for the database,
then ranks articles by cross-source keyword overlap.
"""

import feedparser
import logging
import re
import time
from calendar import timegm
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError, as_completed
from datetime import datetime, timezone
from difflib import SequenceMatcher
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser
from io import StringIO
from typing import Any, List, Dict, Optional

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

STOPWORDS = {
    'the', 'a', 'an', 'in', 'on', 'at', 'for', 'of', 'to', 'is', 'are', 'was',
    'were', 'be', 'been', 'has', 'have', 'had', 'do', 'does', 'did', 'will',
    'would', 'could', 'should', 'may', 'might', 'can', 'shall', 'and', 'but',
    'or', 'nor', 'not', 'no', 'so', 'yet', 'both', 'either', 'neither',
    'each', 'every', 'all', 'any', 'few', 'more', 'most', 'other', 'some',
    'such', 'than', 'too', 'very', 'just', 'also', 'now', 'new', 'says',
    'said', 'its', 'it', 'this', 'that', 'these', 'those', 'what', 'which',
    'who', 'whom', 'how', 'why', 'when', 'where', 'with', 'from', 'by',
    'about', 'into', 'through', 'during', 'before', 'after', 'above', 'below',
    'up', 'down', 'out', 'off', 'over', 'under', 'again', 'further', 'then',
    'once', 'here', 'there', 'as', 'if', 'while', 'report', 'reports',
    'according', 'amid', 'among', 'like', 'between', 'against', 'despite',
}


class _HTMLStripper(HTMLParser):
    """Lightweight HTML tag stripper without regex (ReDoS-safe)."""

    def __init__(self):
        super().__init__()
        self.fed = []

    def handle_data(self, d):
        self.fed.append(d)

    def get_data(self):
        return ''.join(self.fed)


class NewsScraper:
    """
    Scraper for RSS news feeds from major financial/tech sources.
    Fetches articles, then ranks them by cross-source keyword overlap.
    Supports weighted sampling (default: 70% finance, 30% tech).
    """

    # Feed categories for weighted sampling
    # Focus on Wall Street, specific companies, and stock markets
    FEEDS = {
        "Yahoo Finance": "https://finance.yahoo.com/news/rssindex",
        "WSJ": "https://feeds.a.dj.com/rss/RSSMarketsMain.xml",
        "TechCrunch": "https://techcrunch.com/category/fintech/feed/",
        "Bloomberg": "https://feeds.bloomberg.com/markets/news.rss",
        "MarketWatch": "https://www.marketwatch.com/rss/topstories",
        "Calcalist": "https://www.calcalistech.com/ctechnews/rss",
        "Globes": "https://en.globes.co.il/en/rss",
        "Times of Israel": "https://www.timesofisrael.com/feed/business/",
    }

    FINANCE_SOURCES = ["Yahoo Finance", "WSJ", "Bloomberg", "MarketWatch"]
    TECH_SOURCES = ["TechCrunch"]
    ISRAEL_SOURCES = ["Calcalist", "Globes", "Times of Israel"]

    _HTML_RE = re.compile('<.*?>')
    _FEED_TIMEOUT = 10  # seconds per feed
    _URL_DATE_RE = re.compile(r"/(20\d{2})-(\d{2})-(\d{2})(?:/|$)")

    # Keywords that indicate Wall Street / stock market focus (boost these)
    WALL_STREET_KEYWORDS = {
        'stock', 'stocks', 'shares', 'trading', 'trader', 'investors', 'investment',
        'nasdaq', 'nyse', 's&p', 'dow', 'earnings', 'ipo', 'market', 'markets',
        'ticker', 'equity', 'equities', 'portfolio', 'hedge', 'fund', 'valuation',
        'buyback', 'dividend', 'rally', 'plunge', 'surge', 'analyst', 'rating',
        'upgrade', 'downgrade', 'target', 'price', 'wall', 'street', 'bullish',
        'bearish', 'volatility', 'gain', 'loss', 'index', 'etf', 'sec'
    }

    # Keywords that indicate general economy (penalize these for finance)
    GENERAL_ECONOMY_KEYWORDS = {
        'economy', 'gdp', 'unemployment', 'inflation', 'deflation', 'recession',
        'policy', 'tariff', 'tariffs', 'trade', 'deficit', 'budget', 'senate',
        'congress', 'government', 'federal', 'reserve', 'central', 'bank'
    }

    def __init__(self):
        """Initialize the news scraper."""
        pass

    def get_latest_news(self, limit_per_source: int = 10, total_limit: int = 10, finance_weight: float = 0.7) -> List[Dict]:
        """
        Fetch latest news from all configured sources and return
        the top articles ranked by Wall Street focus with weighted sampling.

        Args:
            limit_per_source: Max articles to fetch per source (increased to account for deduplication)
            total_limit: Max total articles to return after ranking
            finance_weight: Percentage of finance articles (0.0-1.0, default: 0.7 for 70% finance)

        Returns:
            List of ranked, deduplicated article dicts (top total_limit), each containing:
            - title
            - description (snippet)
            - source
            - url
            - discovered_at
            - score (ranking score)
            - category (Finance/Tech)
        """
        # Calculate target counts for each category (overfetch to account for deduplication)
        finance_count = int(total_limit * finance_weight) + 3  # +3 buffer for deduplication
        tech_count = total_limit - int(total_limit * finance_weight) + 2  # +2 buffer

        logger.info(f"Weighted sampling: targeting {int(total_limit * finance_weight)} finance + {total_limit - int(total_limit * finance_weight)} tech articles (with buffer)")

        # Fetch articles by category (fetch more per source to account for filtering)
        finance_articles = self._fetch_by_category(self.FINANCE_SOURCES, limit_per_source, "Finance")
        tech_articles = self._fetch_by_category(self.TECH_SOURCES, limit_per_source, "Tech")

        logger.info(f"Fetched {len(finance_articles)} finance, {len(tech_articles)} tech articles (before ranking/dedup)")

        # Rank within each category (includes deduplication)
        finance_ranked = self._rank_articles(finance_articles)[:finance_count]
        tech_ranked = self._rank_articles(tech_articles)[:tech_count]

        # Trim to exact target counts
        finance_final = finance_ranked[:int(total_limit * finance_weight)]
        tech_final = tech_ranked[:total_limit - int(total_limit * finance_weight)]

        # Combine and interleave for variety (finance, tech, finance, tech...)
        combined = []
        for i in range(max(len(finance_final), len(tech_final))):
            if i < len(finance_final):
                combined.append(finance_final[i])
            if i < len(tech_final):
                combined.append(tech_final[i])

        logger.info(f"Final mix: {len(finance_final)} finance + {len(tech_final)} tech = {len(combined)} total")
        return combined[:total_limit]

    def get_brief_news(self, total_limit: int = 8, max_age_hours: int = 48, limit_per_source: int = 20) -> List[Dict[str, Any]]:
        """
        Fetch and rank strict-fresh brief stories using clustered multi-source scoring.

        - Only stories with parseable publish timestamps are considered.
        - Stories older than max_age_hours are excluded.
        - Source health is validated per run; unhealthy sources are ignored.
        - Recency bonus applies only to <=24h stories; 24-48h stories can still rank via source breadth/health.
        """
        source_list = list(self.FEEDS.keys())
        now_utc = datetime.now(timezone.utc)

        diagnostics: Dict[str, Dict[str, Any]] = {}
        with ThreadPoolExecutor(max_workers=len(source_list)) as executor:
            futures = {
                executor.submit(
                    self._fetch_single_feed_for_brief,
                    source_name=source,
                    limit_per_source=limit_per_source,
                    max_age_hours=max_age_hours,
                    now_utc=now_utc,
                ): source
                for source in source_list
            }
            pending_sources = set(source_list)
            try:
                for future in as_completed(futures, timeout=self._FEED_TIMEOUT + 7):
                    source = futures[future]
                    pending_sources.discard(source)
                    try:
                        diagnostics[source] = future.result()
                    except Exception as exc:
                        diagnostics[source] = {
                            "source": source,
                            "fetch_ok": False,
                            "healthy": False,
                            "reason": f"fetch_exception:{exc}",
                            "health_score": 0.0,
                            "latest_age_hours": None,
                            "fresh_ratio_48h": 0.0,
                            "total_entries": 0,
                            "parseable_entries": 0,
                            "fresh_entries": 0,
                            "articles": [],
                        }
            except FuturesTimeoutError:
                logger.warning(
                    "⚠️ Brief fetch timed out after %ss; unfinished_sources=%s",
                    self._FEED_TIMEOUT + 7,
                    ",".join(sorted(pending_sources)) if pending_sources else "none",
                )
                for future, source in futures.items():
                    if source not in pending_sources:
                        continue
                    future.cancel()
                    diagnostics[source] = {
                        "source": source,
                        "fetch_ok": False,
                        "healthy": False,
                        "reason": "feed_timeout",
                        "health_score": 0.0,
                        "latest_age_hours": None,
                        "fresh_ratio_48h": 0.0,
                        "total_entries": 0,
                        "parseable_entries": 0,
                        "fresh_entries": 0,
                        "articles": [],
                    }

        for source in source_list:
            diagnostics.setdefault(
                source,
                {
                    "source": source,
                    "fetch_ok": False,
                    "healthy": False,
                    "reason": "missing_result",
                    "health_score": 0.0,
                    "latest_age_hours": None,
                    "fresh_ratio_48h": 0.0,
                    "total_entries": 0,
                    "parseable_entries": 0,
                    "fresh_entries": 0,
                    "articles": [],
                },
            )

        total_fetched = sum(int(diag.get("total_entries", 0)) for diag in diagnostics.values())
        filtered_missing_ts = sum(
            max(0, int(diag.get("total_entries", 0)) - int(diag.get("parseable_entries", 0)))
            for diag in diagnostics.values()
        )
        filtered_old = sum(
            max(0, int(diag.get("parseable_entries", 0)) - int(diag.get("fresh_entries", 0)))
            for diag in diagnostics.values()
        )
        unhealthy_sources = [name for name, diag in diagnostics.items() if not diag.get("healthy")]

        fresh_candidates: List[Dict[str, Any]] = []
        for source, diag in diagnostics.items():
            if not diag.get("healthy"):
                continue
            for item in diag.get("articles", []):
                age_hours = item.get("age_hours")
                if age_hours is None:
                    continue
                published_at = self._normalize_datetime(item.get("published_at"))
                if not published_at:
                    continue
                if float(age_hours) <= float(max_age_hours):
                    enriched = dict(item)
                    enriched["published_at"] = published_at
                    enriched["source_health"] = float(diag.get("health_score", 0.0))
                    fresh_candidates.append(enriched)

        clusters = self._cluster_brief_articles(fresh_candidates)
        ranked_clusters = [self._score_brief_cluster(cluster) for cluster in clusters]
        ranked_clusters.sort(key=lambda c: c["final_score"], reverse=True)
        selected_clusters = self._select_brief_clusters(ranked_clusters, total_limit=total_limit)

        stories: List[Dict[str, Any]] = []
        for cluster in selected_clusters:
            story = self._cluster_to_story(cluster)
            if story.get("published_at") is None:
                continue
            stories.append(story)

        selected_ages = [
            float(story["age_hours"])
            for story in stories
            if story.get("age_hours") is not None
        ]
        median_age = None
        if selected_ages:
            sorted_ages = sorted(selected_ages)
            n = len(sorted_ages)
            mid = n // 2
            median_age = sorted_ages[mid] if n % 2 else (sorted_ages[mid - 1] + sorted_ages[mid]) / 2

        logger.info(
            "✅ Brief diagnostics: total_fetched=%d filtered_missing_ts=%d filtered_old=%d "
            "unhealthy_sources=%s selected=%d median_age_hours=%s",
            total_fetched,
            filtered_missing_ts,
            filtered_old,
            ",".join(unhealthy_sources) if unhealthy_sources else "none",
            len(stories),
            f"{median_age:.2f}" if median_age is not None else "n/a",
        )

        for source, diag in diagnostics.items():
            logger.info(
                "✅ Brief source status: source=%s used=%s reason=%s health=%.2f latest_age=%s fresh_ratio=%.2f",
                source,
                bool(diag.get("healthy")),
                diag.get("reason", "ok"),
                float(diag.get("health_score", 0.0)),
                f"{diag.get('latest_age_hours'):.2f}" if diag.get("latest_age_hours") is not None else "n/a",
                float(diag.get("fresh_ratio_48h", 0.0)),
            )

        return stories

    @classmethod
    def _source_category(cls, source_name: str) -> str:
        if source_name in cls.TECH_SOURCES:
            return "Tech"
        return "Finance"

    @staticmethod
    def _normalize_datetime(value: Any) -> Optional[datetime]:
        """Normalize feed datetime values to UTC-aware datetime."""
        if value is None:
            return None

        if isinstance(value, datetime):
            dt = value
        elif hasattr(value, "tm_year"):
            try:
                dt = datetime.fromtimestamp(timegm(value), tz=timezone.utc)
            except Exception:
                return None
        elif isinstance(value, str):
            text = value.strip()
            if not text:
                return None
            dt = None
            try:
                dt = parsedate_to_datetime(text)
            except Exception:
                pass
            if dt is None:
                try:
                    dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
                except Exception:
                    return None
        else:
            return None

        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)

    @classmethod
    def _fallback_published_from_url(cls, url: str) -> Optional[datetime]:
        if not url:
            return None
        match = cls._URL_DATE_RE.search(url)
        if not match:
            return None
        year, month, day = match.groups()
        try:
            return datetime(int(year), int(month), int(day), tzinfo=timezone.utc)
        except ValueError:
            return None

    @classmethod
    def _extract_published_at(cls, entry: Dict[str, Any], url: str) -> Optional[datetime]:
        """Extract published timestamp with deterministic priority."""
        priority_fields = [
            "published_parsed",
            "updated_parsed",
            "published",
            "updated",
            "dc_date",
            "created",
        ]
        for field in priority_fields:
            raw = entry.get(field)
            dt = cls._normalize_datetime(raw)
            if dt:
                return dt

        # Some feeds expose namespaced keys via dict-style access.
        for namespaced_key in ("dc:date", "date"):
            if namespaced_key in entry:
                dt = cls._normalize_datetime(entry.get(namespaced_key))
                if dt:
                    return dt

        return cls._fallback_published_from_url(url)

    @staticmethod
    def _jaccard_similarity(a_keywords: set[str], b_keywords: set[str]) -> float:
        if not a_keywords or not b_keywords:
            return 0.0
        intersection = len(a_keywords & b_keywords)
        union = len(a_keywords | b_keywords)
        return (intersection / union) if union else 0.0

    @classmethod
    def _titles_similar(cls, left_title: str, right_title: str) -> bool:
        left_kw = set(cls._extract_keywords(left_title))
        right_kw = set(cls._extract_keywords(right_title))
        if cls._jaccard_similarity(left_kw, right_kw) >= 0.45:
            return True
        ratio = SequenceMatcher(None, (left_title or "").lower(), (right_title or "").lower()).ratio()
        return ratio >= 0.82

    @staticmethod
    def _content_quality_score(article: Dict[str, Any]) -> float:
        """Basic content quality signal used for representative selection."""
        title = (article.get("title") or "").strip()
        description = (article.get("description") or "").strip()
        title_score = min(len(title), 120) / 120
        desc_score = min(len(description), 200) / 200
        return title_score + desc_score

    @classmethod
    def _pick_cluster_representative(cls, items: List[Dict[str, Any]]) -> Dict[str, Any]:
        def _key(article: Dict[str, Any]):
            age = float(article.get("age_hours", 9999.0))
            source_health = float(article.get("source_health", 0.0))
            quality = cls._content_quality_score(article)
            return (age, -source_health, -quality)

        return sorted(items, key=_key)[0]

    @classmethod
    def _cluster_brief_articles(cls, articles: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        clusters: List[Dict[str, Any]] = []
        for article in articles:
            title = article.get("title") or ""
            if not title:
                continue

            matched_cluster: Optional[Dict[str, Any]] = None
            # Group near-duplicate headlines from different sources into one topic cluster.
            for cluster in clusters:
                if any(cls._titles_similar(title, (item.get("title") or "")) for item in cluster["items"]):
                    matched_cluster = cluster
                    break

            if matched_cluster is None:
                matched_cluster = {"items": []}
                clusters.append(matched_cluster)

            matched_cluster["items"].append(article)

        for cluster in clusters:
            items = cluster["items"]
            source_to_url: Dict[str, str] = {}
            for item in items:
                source = item.get("source")
                url = item.get("url") or ""
                if source and url and source not in source_to_url:
                    source_to_url[source] = url

            category_counts: Dict[str, int] = {}
            for item in items:
                category = item.get("category") or "Finance"
                category_counts[category] = category_counts.get(category, 0) + 1

            # Pre-compute cluster metadata once so scoring/selection can stay simple.
            representative = cls._pick_cluster_representative(items)
            unique_sources = sorted({item.get("source") for item in items if item.get("source")})
            avg_source_health = (
                sum(float(item.get("source_health", 0.0)) for item in items) / len(items)
                if items
                else 0.0
            )
            cluster["representative"] = representative
            cluster["unique_sources"] = unique_sources
            cluster["source_to_url"] = source_to_url
            cluster["source_count"] = len(unique_sources)
            cluster["cluster_item_count"] = len(items)
            cluster["avg_source_health"] = avg_source_health
            cluster["category"] = max(category_counts.items(), key=lambda kv: kv[1])[0] if category_counts else "Finance"

        return clusters

    @staticmethod
    def _recency_points(age_hours: float) -> int:
        """Recency bonus only for <=24h stories; older stories rely on other scoring factors."""
        if age_hours <= 3:
            return 40
        if age_hours <= 6:
            return 32
        if age_hours <= 12:
            return 24
        if age_hours <= 24:
            return 12
        return 0

    @classmethod
    def _score_brief_cluster(cls, cluster: Dict[str, Any]) -> Dict[str, Any]:
        representative = cluster["representative"]
        age_hours = float(representative.get("age_hours", 9999.0))
        source_count = int(cluster.get("source_count", 1))
        avg_source_health = float(cluster.get("avg_source_health", 0.0))
        cluster_item_count = int(cluster.get("cluster_item_count", 1))

        # Blend topic breadth, freshness, source reliability, and article momentum.
        cross_source_points = 25 * min(source_count, 4)
        recency_points = cls._recency_points(age_hours)
        source_health_points = round(15 * avg_source_health)
        momentum_points = min(15, 5 * max(0, cluster_item_count - 1))

        single_source_penalty = 0
        if source_count == 1:
            single_source_penalty = -25
            if age_hours <= 6 and avg_source_health >= 0.8:
                single_source_penalty = -10

        final_score = (
            cross_source_points
            + recency_points
            + source_health_points
            + momentum_points
            + single_source_penalty
        )

        scored = dict(cluster)
        scored["final_score"] = int(final_score)
        scored["score_breakdown"] = {
            "cross_source_points": cross_source_points,
            "recency_points": recency_points,
            "source_health_points": source_health_points,
            "momentum_points": momentum_points,
            "single_source_penalty": single_source_penalty,
        }
        return scored

    @classmethod
    def _clusters_too_similar(cls, left: Dict[str, Any], right: Dict[str, Any]) -> bool:
        left_title = (left.get("representative", {}) or {}).get("title", "")
        right_title = (right.get("representative", {}) or {}).get("title", "")
        if not left_title or not right_title:
            return False
        return cls._titles_similar(left_title, right_title)

    @classmethod
    def _select_brief_clusters(cls, ranked_clusters: List[Dict[str, Any]], total_limit: int) -> List[Dict[str, Any]]:
        if total_limit <= 0:
            return []
        if not ranked_clusters:
            return []

        selected: List[Dict[str, Any]] = []

        has_finance = any(cluster.get("category") == "Finance" for cluster in ranked_clusters)
        has_tech = any(cluster.get("category") == "Tech" for cluster in ranked_clusters)
        enforce_diversity = has_finance and has_tech

        if enforce_diversity:
            # Seed with best finance + tech topics, then fill remaining slots by score.
            best_finance = next((c for c in ranked_clusters if c.get("category") == "Finance"), None)
            best_tech = next((c for c in ranked_clusters if c.get("category") == "Tech"), None)
            seeds = [seed for seed in (best_finance, best_tech) if seed is not None]
            seeds.sort(key=lambda c: c.get("final_score", 0), reverse=True)
            for seed in seeds:
                if len(selected) >= total_limit:
                    break
                if any(cls._clusters_too_similar(seed, existing) for existing in selected):
                    continue
                selected.append(seed)

        for cluster in ranked_clusters:
            if len(selected) >= total_limit:
                break
            if any(cls._clusters_too_similar(cluster, existing) for existing in selected):
                continue
            if cluster in selected:
                continue
            selected.append(cluster)

        selected.sort(key=lambda c: c.get("final_score", 0), reverse=True)
        return selected[:total_limit]

    @classmethod
    def _cluster_to_story(cls, cluster: Dict[str, Any]) -> Dict[str, Any]:
        representative = cluster.get("representative", {})
        sources: List[str] = list(cluster.get("unique_sources", []))
        source_to_url: Dict[str, str] = cluster.get("source_to_url", {})
        source_urls = [source_to_url[src] for src in sources if src in source_to_url and source_to_url[src]]
        published_at = cls._normalize_datetime(representative.get("published_at"))

        return {
            "title": representative.get("title", ""),
            "description": representative.get("description", ""),
            "summary": (representative.get("description") or representative.get("title") or "")[:280],
            "source": representative.get("source", "Unknown"),
            "sources": sources,
            "source_urls": source_urls,
            "source_count": int(cluster.get("source_count", len(sources) or 1)),
            "url": representative.get("url", ""),
            "published_at": published_at,
            "age_hours": representative.get("age_hours"),
            "relevance_score": int(cluster.get("final_score", 0)),
            "score": int(cluster.get("final_score", 0)),
            "category": cluster.get("category", representative.get("category", "Finance")),
        }

    def _fetch_single_feed_for_brief(
        self,
        source_name: str,
        limit_per_source: int,
        max_age_hours: int,
        now_utc: datetime,
    ) -> Dict[str, Any]:
        """Fetch one feed and compute per-source health diagnostics for brief mode."""
        feed_url = self.FEEDS.get(source_name)
        if not feed_url:
            return {
                "source": source_name,
                "fetch_ok": False,
                "healthy": False,
                "reason": "source_not_configured",
                "health_score": 0.0,
                "latest_age_hours": None,
                "fresh_ratio_48h": 0.0,
                "total_entries": 0,
                "parseable_entries": 0,
                "fresh_entries": 0,
                "articles": [],
            }

        total_entries = 0
        parseable_entries = 0
        fresh_entries = 0
        articles: List[Dict[str, Any]] = []
        ages: List[float] = []

        try:
            import requests

            logger.info("✅ Brief fetch: source=%s", source_name)
            resp = requests.get(feed_url, timeout=self._FEED_TIMEOUT, headers={'User-Agent': 'HFI/1.0'})
            if resp.status_code != 200:
                return {
                    "source": source_name,
                    "fetch_ok": False,
                    "healthy": False,
                    "reason": f"http_{resp.status_code}",
                    "health_score": 0.0,
                    "latest_age_hours": None,
                    "fresh_ratio_48h": 0.0,
                    "total_entries": 0,
                    "parseable_entries": 0,
                    "fresh_entries": 0,
                    "articles": [],
                }

            feed = feedparser.parse(resp.content)
            if feed.bozo:
                logger.warning("⚠️ Brief parse warning for %s: %s", source_name, feed.bozo_exception)

            category = self._source_category(source_name)
            for entry in feed.entries[:limit_per_source]:
                total_entries += 1
                title = entry.get("title", "")
                link = entry.get("link", "")
                published_at = self._extract_published_at(entry, link)
                if not published_at:
                    continue

                parseable_entries += 1
                age_hours = (now_utc - published_at).total_seconds() / 3600
                ages.append(age_hours)
                if age_hours <= max_age_hours:
                    fresh_entries += 1

                articles.append(
                    {
                        "title": title,
                        "description": self._clean_html(entry.get('summary', '') or entry.get('description', '')),
                        "source": source_name,
                        "url": link,
                        "published_at": published_at,
                        "age_hours": age_hours,
                        "category": category,
                    }
                )

            fetch_ok = parseable_entries > 0
            latest_age_hours = min(ages) if ages else None
            fresh_ratio = (fresh_entries / parseable_entries) if parseable_entries else 0.0
            latest_component = 0.0
            if latest_age_hours is not None:
                latest_component = max(0.0, min(1.0, 1 - (latest_age_hours / 72.0)))
            health_score = round((0.6 * fresh_ratio) + (0.4 * latest_component), 3)

            healthy = True
            reason = "ok"
            if not fetch_ok:
                healthy = False
                reason = "no_parseable_entries"
            elif latest_age_hours is None or latest_age_hours > 72:
                healthy = False
                reason = "latest_age_gt_72h"
            elif fresh_ratio < 0.2:
                healthy = False
                reason = "fresh_ratio_lt_0.2"

            return {
                "source": source_name,
                "fetch_ok": fetch_ok,
                "healthy": healthy,
                "reason": reason,
                "health_score": health_score,
                "latest_age_hours": latest_age_hours,
                "fresh_ratio_48h": fresh_ratio,
                "total_entries": total_entries,
                "parseable_entries": parseable_entries,
                "fresh_entries": fresh_entries,
                "articles": articles,
            }
        except Exception as exc:
            logger.error("❌ Brief fetch error for %s: %s", source_name, exc)
            return {
                "source": source_name,
                "fetch_ok": False,
                "healthy": False,
                "reason": f"exception:{exc}",
                "health_score": 0.0,
                "latest_age_hours": None,
                "fresh_ratio_48h": 0.0,
                "total_entries": total_entries,
                "parseable_entries": parseable_entries,
                "fresh_entries": fresh_entries,
                "articles": [],
            }

    def _fetch_single_feed(self, source_name: str, limit_per_source: int, category: str) -> List[Dict]:
        """Fetch articles from a single RSS feed (called in parallel)."""
        feed_url = self.FEEDS.get(source_name)
        if not feed_url:
            return []

        try:
            logger.info(f"Fetching {category} news from {source_name}...")
            import requests
            resp = requests.get(feed_url, timeout=self._FEED_TIMEOUT, headers={'User-Agent': 'HFI/1.0'})
            feed = feedparser.parse(resp.content)

            if feed.bozo:
                logger.warning(f"Potential issue parsing {source_name}: {feed.bozo_exception}")

            articles = []
            for entry in feed.entries[:limit_per_source]:
                articles.append({
                    "title": entry.title,
                    "description": self._clean_html(entry.get('summary', '') or entry.get('description', '')),
                    "source": source_name,
                    "url": entry.link,
                    "discovered_at": datetime.utcnow(),
                    "category": category
                })

            logger.info(f"Retrieved {len(articles)} {category} articles from {source_name}")
            return articles

        except Exception as e:
            logger.error(f"Error fetching {source_name}: {str(e)}")
            return []

    def _fetch_by_category(self, sources: List[str], limit_per_source: int, category: str) -> List[Dict]:
        """Fetch articles from sources in parallel with timeout."""
        valid_sources = [s for s in sources if s in self.FEEDS]
        if not valid_sources:
            return []

        articles = []
        with ThreadPoolExecutor(max_workers=len(valid_sources)) as executor:
            futures = {
                executor.submit(self._fetch_single_feed, src, limit_per_source, category): src
                for src in valid_sources
            }
            for future in as_completed(futures, timeout=self._FEED_TIMEOUT + 5):
                try:
                    articles.extend(future.result())
                except Exception as e:
                    logger.error(f"Feed fetch failed for {futures[future]}: {e}")

        return articles

    def _rank_articles(self, articles: List[Dict]) -> List[Dict]:
        """
        Rank articles by cross-source keyword overlap with Wall Street focus.

        Algorithm:
        1. Extract keywords from each article title
        2. Build map: keyword -> set of sources mentioning it
        3. Score each article:
           - Cross-source keywords: +10 * source_count
           - Wall Street keywords: +15 bonus
           - General economy keywords: -10 penalty (for finance sources)
           - Single-source keywords: +1
        4. Deduplicate similar articles (keep highest scored)
        5. Sort by score descending
        """
        # Build keyword -> set of sources
        keyword_sources: Dict[str, set] = {}
        for article in articles:
            keywords = self._extract_keywords(article.get('title', ''))
            source = article['source']
            for kw in set(keywords):
                if kw not in keyword_sources:
                    keyword_sources[kw] = set()
                keyword_sources[kw].add(source)

        # Score each article (using title + description keywords)
        for article in articles:
            keywords = self._extract_article_keywords(article)
            score = 0

            # Base score from keyword cross-source overlap
            for kw in set(keywords):
                sources = keyword_sources.get(kw, set())
                if len(sources) >= 2:
                    score += 10 * len(sources)
                else:
                    score += 1

            # Boost Wall Street focused articles
            wall_street_count = sum(1 for kw in keywords if kw in self.WALL_STREET_KEYWORDS)
            score += wall_street_count * 15

            # Penalize general economy articles (for finance sources only)
            if article.get('category') == 'Finance':
                economy_count = sum(1 for kw in keywords if kw in self.GENERAL_ECONOMY_KEYWORDS)
                score -= economy_count * 10

            # Recency bonus: fresher articles score higher
            discovered_at = article.get('discovered_at')
            if discovered_at:
                age_hours = (datetime.utcnow() - discovered_at).total_seconds() / 3600
                if age_hours <= 6:
                    score += 20
                elif age_hours <= 24:
                    score += 10
                elif age_hours > 72:
                    score -= 5

            article['score'] = score

        # Remove duplicates (similar articles from different sources)
        articles = self._deduplicate_articles(articles)

        articles.sort(key=lambda a: a['score'], reverse=True)
        return articles

    def _deduplicate_articles(self, articles: List[Dict]) -> List[Dict]:
        """
        Remove duplicate articles based on title similarity.

        Pre-computes keywords once per article to avoid O(n^2) re-extraction.
        """
        # Pre-compute keyword sets for all articles
        article_keywords = [set(self._extract_keywords(a.get('title', ''))) for a in articles]

        unique_articles = []
        unique_kw_sets = []

        for i, article in enumerate(articles):
            keywords = article_keywords[i]

            is_duplicate = False
            for seen_keywords in unique_kw_sets:
                if not keywords or not seen_keywords:
                    continue

                intersection = len(keywords & seen_keywords)
                union = len(keywords | seen_keywords)
                if union > 0 and intersection / union > 0.6:
                    is_duplicate = True
                    break

            if not is_duplicate:
                unique_articles.append(article)
                unique_kw_sets.append(keywords)

        logger.info(f"Deduplication: {len(articles)} → {len(unique_articles)} articles")
        return unique_articles

    @staticmethod
    def _extract_keywords(title: str) -> List[str]:
        """Extract significant words from an article title."""
        words = re.findall(r"[A-Za-z0-9']+", title.lower())
        return [w for w in words if w not in STOPWORDS and len(w) > 2]

    @staticmethod
    def _extract_article_keywords(article: Dict) -> List[str]:
        """Extract keywords from both title (2x weight) and description.

        Title keywords appear twice to give them higher weight in scoring.
        Description keywords add once for additional context.
        """
        title = article.get('title', '')
        desc = article.get('description', '')
        title_kws = NewsScraper._extract_keywords(title)
        desc_kws = NewsScraper._extract_keywords(desc)
        return title_kws + title_kws + desc_kws

    def _clean_html(self, text: str) -> str:
        """Remove HTML tags safely without regex."""
        if not text:
            return ""
        stripper = _HTMLStripper()
        try:
            stripper.feed(text)
            return stripper.get_data().strip()
        except Exception:
            return self._HTML_RE.sub('', text).strip()


if __name__ == "__main__":
    scraper = NewsScraper()
    print("Fetching news with weighted sampling (70% finance, 30% tech)...\n")
    news = scraper.get_latest_news(limit_per_source=5, total_limit=10, finance_weight=0.7)

    finance_count = sum(1 for a in news if a.get('category') == 'Finance')
    tech_count = sum(1 for a in news if a.get('category') == 'Tech')

    print(f"\n📊 Distribution: {finance_count} Finance ({finance_count/len(news)*100:.0f}%) + {tech_count} Tech ({tech_count/len(news)*100:.0f}%)\n")

    for i, article in enumerate(news, 1):
        category_emoji = "💰" if article.get('category') == 'Finance' else "💻"
        print(f"#{i} {category_emoji} [{article['source']}] (score={article.get('score', 0)}) {article['title']}")
