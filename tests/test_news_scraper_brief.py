"""Tests for strict-fresh brief ranking in NewsScraper."""

from concurrent.futures import TimeoutError as FuturesTimeoutError
from datetime import datetime, timedelta, timezone
from time import gmtime

from scraper.news_scraper import NewsScraper


def _article(
    *,
    title: str,
    source: str,
    category: str,
    age_hours: float,
    url: str,
    source_health: float = 0.9,
    description: str = "desc",
):
    now = datetime.now(timezone.utc)
    published_at = now - timedelta(hours=age_hours)
    return {
        "title": title,
        "description": description,
        "source": source,
        "url": url,
        "published_at": published_at,
        "age_hours": age_hours,
        "category": category,
        "source_health": source_health,
    }


def test_extract_published_at_priority_and_fallback():
    dt_from_parsed = NewsScraper._extract_published_at(
        {
            "published_parsed": gmtime(1_710_000_000),
            "updated": "Mon, 10 Mar 2026 10:00:00 GMT",
        },
        "https://example.com/news/2026-03-10/topic",
    )
    assert dt_from_parsed is not None
    assert dt_from_parsed.tzinfo is not None

    dt_from_updated = NewsScraper._extract_published_at(
        {"updated": "Tue, 10 Mar 2026 14:00:00 GMT"},
        "https://example.com/news/topic",
    )
    assert dt_from_updated is not None
    assert dt_from_updated.year == 2026
    assert dt_from_updated.month == 3

    dt_from_dc = NewsScraper._extract_published_at(
        {"dc_date": "2026-03-10T09:30:00Z"},
        "https://example.com/news/topic",
    )
    assert dt_from_dc is not None
    assert dt_from_dc.hour == 9

    dt_from_url = NewsScraper._extract_published_at(
        {},
        "https://www.bloomberg.com/news/articles/2026-03-10/some-headline",
    )
    assert dt_from_url is not None
    assert dt_from_url.year == 2026
    assert dt_from_url.month == 3
    assert dt_from_url.day == 10


def test_source_health_gating_excludes_stale_sources(monkeypatch):
    scraper = NewsScraper()
    now = datetime.now(timezone.utc)

    def fake_fetch(source_name, limit_per_source, max_age_hours, now_utc):
        if source_name == "WSJ":
            return {
                "source": "WSJ",
                "fetch_ok": True,
                "healthy": False,
                "reason": "latest_age_gt_72h",
                "health_score": 0.0,
                "latest_age_hours": 120.0,
                "fresh_ratio_48h": 0.0,
                "total_entries": 10,
                "parseable_entries": 10,
                "fresh_entries": 0,
                "articles": [],
            }
        if source_name == "Bloomberg":
            return {
                "source": "Bloomberg",
                "fetch_ok": True,
                "healthy": True,
                "reason": "ok",
                "health_score": 0.95,
                "latest_age_hours": 1.0,
                "fresh_ratio_48h": 1.0,
                "total_entries": 2,
                "parseable_entries": 2,
                "fresh_entries": 2,
                "articles": [
                    {
                        "title": "ETF demand rises on Wall Street",
                        "description": "Fresh story",
                        "source": "Bloomberg",
                        "url": "https://bloomberg.com/etf-demand",
                        "published_at": now - timedelta(hours=1),
                        "age_hours": 1.0,
                        "category": "Finance",
                    }
                ],
            }
        return {
            "source": source_name,
            "fetch_ok": True,
            "healthy": False,
            "reason": "fresh_ratio_lt_0.2",
            "health_score": 0.1,
            "latest_age_hours": 90.0,
            "fresh_ratio_48h": 0.0,
            "total_entries": 5,
            "parseable_entries": 5,
            "fresh_entries": 0,
            "articles": [],
        }

    monkeypatch.setattr(scraper, "_fetch_single_feed_for_brief", fake_fetch)
    stories = scraper.get_brief_news(total_limit=8, max_age_hours=48)
    assert len(stories) == 1
    assert stories[0]["sources"] == ["Bloomberg"]
    assert "WSJ" not in stories[0]["sources"]


def test_brief_news_enforces_48h_cutoff(monkeypatch):
    scraper = NewsScraper()
    now = datetime.now(timezone.utc)

    def fake_fetch(source_name, limit_per_source, max_age_hours, now_utc):
        if source_name == "Bloomberg":
            return {
                "source": "Bloomberg",
                "fetch_ok": True,
                "healthy": True,
                "reason": "ok",
                "health_score": 0.92,
                "latest_age_hours": 2.0,
                "fresh_ratio_48h": 0.5,
                "total_entries": 2,
                "parseable_entries": 2,
                "fresh_entries": 1,
                "articles": [
                    {
                        "title": "Fresh policy update",
                        "description": "fresh",
                        "source": "Bloomberg",
                        "url": "https://bloomberg.com/fresh-policy",
                        "published_at": now - timedelta(hours=2),
                        "age_hours": 2.0,
                        "category": "Finance",
                    },
                    {
                        "title": "Older market wrap",
                        "description": "old",
                        "source": "Bloomberg",
                        "url": "https://bloomberg.com/older-wrap",
                        "published_at": now - timedelta(hours=60),
                        "age_hours": 60.0,
                        "category": "Finance",
                    },
                ],
            }
        return {
            "source": source_name,
            "fetch_ok": False,
            "healthy": False,
            "reason": "no_parseable_entries",
            "health_score": 0.0,
            "latest_age_hours": None,
            "fresh_ratio_48h": 0.0,
            "total_entries": 0,
            "parseable_entries": 0,
            "fresh_entries": 0,
            "articles": [],
        }

    monkeypatch.setattr(scraper, "_fetch_single_feed_for_brief", fake_fetch)
    stories = scraper.get_brief_news(total_limit=8, max_age_hours=48)
    assert len(stories) == 1
    assert stories[0]["title"] == "Fresh policy update"
    assert float(stories[0]["age_hours"]) <= 48


def test_brief_news_timeout_returns_empty_instead_of_raising(monkeypatch):
    scraper = NewsScraper()
    now = datetime.now(timezone.utc)

    def fake_fetch(source_name, limit_per_source, max_age_hours, now_utc):
        return {
            "source": source_name,
            "fetch_ok": True,
            "healthy": True,
            "reason": "ok",
            "health_score": 0.9,
            "latest_age_hours": 1.0,
            "fresh_ratio_48h": 1.0,
            "total_entries": 1,
            "parseable_entries": 1,
            "fresh_entries": 1,
            "articles": [
                {
                    "title": f"{source_name} fresh story",
                    "description": "fresh",
                    "source": source_name,
                    "url": f"https://example.com/{source_name}",
                    "published_at": now - timedelta(hours=1),
                    "age_hours": 1.0,
                    "category": "Finance",
                }
            ],
        }

    def fake_as_completed(_futures, timeout=None):
        raise FuturesTimeoutError()

    monkeypatch.setattr(scraper, "_fetch_single_feed_for_brief", fake_fetch)
    monkeypatch.setattr("scraper.news_scraper.as_completed", fake_as_completed)

    stories = scraper.get_brief_news(total_limit=8, max_age_hours=48)
    assert stories == []


def test_brief_news_skips_articles_without_parseable_published_at(monkeypatch):
    scraper = NewsScraper()
    now = datetime.now(timezone.utc)

    def fake_fetch(source_name, limit_per_source, max_age_hours, now_utc):
        if source_name == "Bloomberg":
            return {
                "source": "Bloomberg",
                "fetch_ok": True,
                "healthy": True,
                "reason": "ok",
                "health_score": 0.95,
                "latest_age_hours": 1.0,
                "fresh_ratio_48h": 1.0,
                "total_entries": 2,
                "parseable_entries": 2,
                "fresh_entries": 2,
                "articles": [
                    {
                        "title": "Missing timestamp should be excluded",
                        "description": "missing timestamp",
                        "source": "Bloomberg",
                        "url": "https://bloomberg.com/missing-timestamp",
                        "published_at": None,
                        "age_hours": 2.0,
                        "category": "Finance",
                    },
                    {
                        "title": "Valid timestamp should remain",
                        "description": "valid timestamp",
                        "source": "Bloomberg",
                        "url": "https://bloomberg.com/valid-timestamp",
                        "published_at": now - timedelta(hours=1),
                        "age_hours": 1.0,
                        "category": "Finance",
                    },
                ],
            }
        return {
            "source": source_name,
            "fetch_ok": False,
            "healthy": False,
            "reason": "no_parseable_entries",
            "health_score": 0.0,
            "latest_age_hours": None,
            "fresh_ratio_48h": 0.0,
            "total_entries": 0,
            "parseable_entries": 0,
            "fresh_entries": 0,
            "articles": [],
        }

    monkeypatch.setattr(scraper, "_fetch_single_feed_for_brief", fake_fetch)
    stories = scraper.get_brief_news(total_limit=8, max_age_hours=48)
    assert len(stories) == 1
    assert stories[0]["title"] == "Valid timestamp should remain"
    assert stories[0]["published_at"] is not None


def test_cluster_merges_cross_source_similar_titles():
    articles = [
        _article(
            title="SEC approves spot Bitcoin ETF framework",
            source="Bloomberg",
            category="Finance",
            age_hours=2,
            url="https://bloomberg.com/sec-bitcoin-etf",
        ),
        _article(
            title="Bitcoin ETF framework approved by SEC",
            source="Yahoo Finance",
            category="Finance",
            age_hours=2.5,
            url="https://finance.yahoo.com/bitcoin-etf-sec",
        ),
        _article(
            title="Stripe expands payments API in Europe",
            source="TechCrunch",
            category="Tech",
            age_hours=3,
            url="https://techcrunch.com/stripe-api-europe",
        ),
    ]

    clusters = NewsScraper._cluster_brief_articles(articles)
    assert len(clusters) == 2
    source_counts = sorted(cluster["source_count"] for cluster in clusters)
    assert source_counts == [1, 2]


def test_scoring_prefers_fresh_multi_source_cluster():
    articles = [
        _article(
            title="SEC approves spot Bitcoin ETF framework",
            source="Bloomberg",
            category="Finance",
            age_hours=2,
            url="https://bloomberg.com/sec-bitcoin-etf",
        ),
        _article(
            title="Bitcoin ETF framework approved by SEC",
            source="Yahoo Finance",
            category="Finance",
            age_hours=3,
            url="https://finance.yahoo.com/bitcoin-etf-sec",
        ),
        _article(
            title="Niche startup launches new payment chip",
            source="TechCrunch",
            category="Tech",
            age_hours=20,
            url="https://techcrunch.com/payment-chip",
            source_health=0.85,
        ),
    ]

    clusters = NewsScraper._cluster_brief_articles(articles)
    scored = [NewsScraper._score_brief_cluster(cluster) for cluster in clusters]
    scored.sort(key=lambda c: c["final_score"], reverse=True)

    top = scored[0]
    assert top["source_count"] >= 2
    assert top["final_score"] > scored[1]["final_score"]


def test_soft_diversity_promotes_tech_when_available():
    ranked_clusters = [
        {
            "representative": {"title": "Finance topic one"},
            "category": "Finance",
            "final_score": 98,
        },
        {
            "representative": {"title": "Finance topic two"},
            "category": "Finance",
            "final_score": 96,
        },
        {
            "representative": {"title": "Tech infrastructure update"},
            "category": "Tech",
            "final_score": 72,
        },
        {
            "representative": {"title": "Finance topic three"},
            "category": "Finance",
            "final_score": 70,
        },
    ]

    selected = NewsScraper._select_brief_clusters(ranked_clusters, total_limit=3)
    categories = {cluster["category"] for cluster in selected}
    assert "Finance" in categories
    assert "Tech" in categories
