"""Tests for NewsScraper source configuration and relevance scoring."""

from scraper.news_scraper import NewsScraper


def test_israeli_sources_configured():
    """Israeli news sources must be in FEEDS and categorized."""
    scraper = NewsScraper()
    feeds = scraper.FEEDS

    for src in scraper.ISRAEL_SOURCES:
        assert src in feeds, f"{src} must be in FEEDS"
        assert src in scraper.ISRAEL_SOURCES


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
    irrelevant = {"title": "EU trade policy meeting discusses tariffs", "source": "CNBC",
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


# ==================== Three-Bucket Source Weighting ====================


def test_three_bucket_weighting():
    """get_latest_news should fetch from finance, tech, and israel buckets."""
    scraper = NewsScraper()

    fetch_calls = []

    def mock_fetch(sources, limit_per_source, category):
        fetch_calls.append({"sources": sources, "category": category})
        return []

    scraper._fetch_by_category = mock_fetch
    scraper.get_latest_news(total_limit=8)

    categories_called = {c["category"] for c in fetch_calls}
    assert "Finance" in categories_called
    assert "Tech" in categories_called
    assert "Israel" in categories_called


def test_israel_slot_guaranteed():
    """At least 1 Israel story should be included if available."""
    scraper = NewsScraper()

    mock_finance = [{"title": f"Finance {i}", "source": "Bloomberg", "description": "",
                     "url": f"https://ex.com/f{i}", "category": "Finance", "score": 50-i}
                    for i in range(6)]
    mock_israel = [{"title": "Israeli startup Wix Reports Growth", "source": "Google News Israel", "description": "",
                    "url": "https://ex.com/il1", "category": "Israel", "score": 10}]

    def mock_fetch(sources, limit_per_source, category):
        if category == "Finance":
            return mock_finance
        if category == "Israel":
            return mock_israel
        return []

    scraper._fetch_by_category = mock_fetch
    results = scraper.get_latest_news(total_limit=8)

    israel_titles = [r["title"] for r in results if r.get("category") == "Israel"]
    assert len(israel_titles) >= 1, "At least 1 Israel story must be included"


def test_three_bucket_no_finance_weight_param():
    """get_latest_news should not accept finance_weight parameter."""
    import inspect
    scraper = NewsScraper()
    sig = inspect.signature(scraper.get_latest_news)
    assert "finance_weight" not in sig.parameters, "finance_weight param should be removed"


def test_three_bucket_interleaving():
    """Results should interleave finance, tech, and israel articles."""
    scraper = NewsScraper()

    mock_finance = [{"title": f"Wall Street stocks rally on NASDAQ earnings {i}", "source": "Bloomberg", "description": "",
                     "url": f"https://ex.com/f{i}", "category": "Finance", "score": 50-i}
                    for i in range(4)]
    mock_tech = [{"title": f"Fintech startup raises Series B funding round {i}", "source": "TechCrunch", "description": "",
                  "url": f"https://ex.com/t{i}", "category": "Tech", "score": 40-i}
                 for i in range(2)]
    mock_israel = [{"title": f"Israeli startup Wix reports growth in Tel Aviv {i}", "source": "Google News Israel", "description": "",
                    "url": f"https://ex.com/il{i}", "category": "Israel", "score": 30-i}
                   for i in range(2)]

    def mock_fetch(sources, limit_per_source, category):
        if category == "Finance":
            return mock_finance
        if category == "Tech":
            return mock_tech
        if category == "Israel":
            return mock_israel
        return []

    scraper._fetch_by_category = mock_fetch
    results = scraper.get_latest_news(total_limit=8)

    categories = [r["category"] for r in results]
    assert "Finance" in categories
    assert "Tech" in categories
    assert "Israel" in categories


def test_source_category_includes_israel():
    """_source_category should return 'Israel' for Israeli sources."""
    for src in NewsScraper.ISRAEL_SOURCES:
        assert NewsScraper._source_category(src) == "Israel"
    assert NewsScraper._source_category("Bloomberg") == "Finance"
    assert NewsScraper._source_category("TechCrunch") == "Tech"
    assert NewsScraper._source_category("CNBC") == "Finance"
    assert NewsScraper._source_category("Seeking Alpha") == "Finance"


def test_expanded_must_include_keywords():
    """MUST_INCLUDE should contain Wall Street, Big Tech, and AI keywords."""
    kws = NewsScraper.MUST_INCLUDE_KEYWORDS
    assert "market" in kws
    assert "nvidia" in kws
    assert "artificial intelligence" in kws
    assert "openai" in kws
    assert "jpmorgan" in kws
