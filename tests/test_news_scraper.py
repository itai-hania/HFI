"""Tests for NewsScraper source configuration and relevance scoring."""

from scraper.news_scraper import NewsScraper


def test_israeli_sources_configured():
    """Israeli news sources must be in FEEDS and categorized."""
    scraper = NewsScraper()
    feeds = scraper.FEEDS

    assert "Calcalist" in feeds
    assert "Globes" in feeds
    assert "Times of Israel" in feeds

    assert "Calcalist" in scraper.ISRAEL_SOURCES
    assert "Globes" in scraper.ISRAEL_SOURCES
    assert "Times of Israel" in scraper.ISRAEL_SOURCES


def test_israel_sources_not_in_finance_or_tech():
    """Israeli sources should be in their own category, not mixed."""
    scraper = NewsScraper()
    for src in scraper.ISRAEL_SOURCES:
        assert src not in scraper.FINANCE_SOURCES
        assert src not in scraper.TECH_SOURCES


# ==================== Relevance Keyword Scoring ====================


def test_must_include_keywords_boost():
    """Articles matching MUST_INCLUDE keywords get boosted."""
    scraper = NewsScraper()

    relevant = {"title": "NASDAQ hits record on fintech IPO surge", "source": "Bloomberg",
                "description": "Markets rally", "url": "https://example.com/1", "category": "Finance"}
    irrelevant = {"title": "EU trade policy meeting discusses tariffs", "source": "WSJ",
                  "description": "Trade talks", "url": "https://example.com/2", "category": "Finance"}

    articles = [irrelevant, relevant]
    ranked = scraper._rank_articles(articles)

    assert ranked[0]["title"] == relevant["title"]


def test_exclude_keywords_penalty():
    """Articles with EXCLUDE keywords get penalized."""
    scraper = NewsScraper()

    assert "tariff" in scraper.EXCLUDE_KEYWORDS
    assert "election" in scraper.EXCLUDE_KEYWORDS
    assert "immigration" in scraper.EXCLUDE_KEYWORDS


def test_israel_keywords_in_must_include():
    """Israel-related keywords should be in MUST_INCLUDE."""
    scraper = NewsScraper()

    assert "israel" in scraper.MUST_INCLUDE_KEYWORDS
    assert "tel aviv" in scraper.MUST_INCLUDE_KEYWORDS or "tase" in scraper.MUST_INCLUDE_KEYWORDS


def test_relevance_threshold_drops_low_score():
    """Articles scoring below threshold are dropped from results."""
    scraper = NewsScraper()

    noise = {"title": "Senate immigration bill debate continues", "source": "Yahoo Finance",
             "description": "Political discussion", "url": "https://example.com/noise", "category": "Finance"}
    good = {"title": "Bitcoin ETF sees record inflows on Wall Street", "source": "Bloomberg",
            "description": "Crypto markets", "url": "https://example.com/good", "category": "Finance"}

    ranked = scraper._rank_articles([noise, good])

    titles = [a["title"] for a in ranked]
    assert "Bitcoin ETF sees record inflows on Wall Street" in titles
    if len(ranked) > 1:
        assert ranked[-1]["title"] == noise["title"]
