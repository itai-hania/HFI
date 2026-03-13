"""Tests for NewsScraper source configuration."""

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
