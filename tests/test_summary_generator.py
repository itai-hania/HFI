"""
Unit tests for Summary Generator service.

Tests AI summary generation, keyword extraction, and related content grouping.

Author: HFI Development Team
Last Updated: 2026-02-01
"""

import pytest
import os
from unittest.mock import Mock, patch, MagicMock
import sys
from pathlib import Path

# Add src directory to path
sys.path.append(str(Path(__file__).parent.parent))

from src.processor.summary_generator import SummaryGenerator
from src.common.models import Trend, TrendSource, create_tables, SessionLocal, get_db
from datetime import datetime, timezone, timedelta


@pytest.fixture(scope="module")
def setup_database():
    """Set up in-memory database for testing."""
    # Use in-memory database for tests
    os.environ['DATABASE_URL'] = 'sqlite:///:memory:'

    # Force reload of models module to use test database
    import importlib
    import src.common.models
    importlib.reload(src.common.models)

    from src.common.models import create_tables
    create_tables()

    yield

    # Cleanup
    del os.environ['DATABASE_URL']


@pytest.fixture
def db_session(setup_database):
    """Provide a database session for each test."""
    with get_db() as db:
        # Clean up all trends before each test
        db.query(Trend).delete()
        db.commit()
        yield db


@pytest.fixture
def mock_openai():
    """Mock OpenAI client for testing."""
    with patch('src.processor.summary_generator.OpenAI') as mock:
        mock_client = Mock()
        mock_response = Mock()
        mock_response.choices = [Mock(message=Mock(content="This is a test summary."))]
        mock_client.chat.completions.create.return_value = mock_response
        mock.return_value = mock_client
        yield mock


@pytest.fixture
def generator(mock_openai):
    """Create a SummaryGenerator instance with mocked OpenAI."""
    os.environ['OPENAI_API_KEY'] = 'test-key'
    return SummaryGenerator()


class TestKeywordExtraction:
    """Test keyword extraction from article titles."""

    def test_extract_keywords_basic(self, generator):
        """Test basic keyword extraction."""
        title = "SEC Approves Bitcoin ETF Applications"
        keywords = generator.extract_keywords(title)

        assert 'sec' in keywords
        assert 'approves' in keywords
        assert 'bitcoin' in keywords
        assert 'etf' in keywords
        assert 'applications' in keywords

    def test_extract_keywords_removes_stopwords(self, generator):
        """Test that stopwords are removed."""
        title = "The Big Banks Are Implementing AI for Fraud Detection"
        keywords = generator.extract_keywords(title)

        # Stopwords should not be in keywords
        assert 'the' not in keywords
        assert 'are' not in keywords
        assert 'for' not in keywords

        # Content words should be present
        assert 'big' in keywords
        assert 'banks' in keywords
        assert 'implementing' in keywords
        assert 'fraud' in keywords
        assert 'detection' in keywords

    def test_extract_keywords_removes_short_words(self, generator):
        """Test that words <= 2 chars are removed."""
        title = "AI is on the Go to Be Big"
        keywords = generator.extract_keywords(title)

        assert 'is' not in keywords
        assert 'on' not in keywords
        assert 'to' not in keywords
        assert 'be' not in keywords

        # AI should be removed (2 chars)
        assert 'ai' not in keywords

        # 'big' should be present (3 chars)
        assert 'big' in keywords

    def test_extract_keywords_lowercase(self, generator):
        """Test that keywords are lowercased."""
        title = "PayPal LAUNCHES CryptoCurrency Payment SERVICE"
        keywords = generator.extract_keywords(title)

        assert 'paypal' in keywords
        assert 'launches' in keywords
        assert 'cryptocurrency' in keywords
        assert 'payment' in keywords
        assert 'service' in keywords

    def test_extract_keywords_unique(self, generator):
        """Test that duplicate keywords are removed."""
        title = "Bitcoin Bitcoin Bitcoin Goes Up"
        keywords = generator.extract_keywords(title)

        # Should only appear once
        assert keywords.count('bitcoin') == 1
        assert keywords.count('goes') == 1

    def test_extract_keywords_empty_title(self, generator):
        """Test handling of empty title."""
        keywords = generator.extract_keywords("")
        assert keywords == []

    def test_extract_keywords_only_stopwords(self, generator):
        """Test title with only stopwords."""
        title = "the and or but in on at to for of with"
        keywords = generator.extract_keywords(title)
        assert keywords == []


class TestSummaryGeneration:
    """Test AI summary generation."""

    def test_generate_summary_with_title_only(self, generator, mock_openai):
        """Test summary generation with only title."""
        title = "SEC Approves Bitcoin ETF Applications"
        summary = generator.generate_summary(title)

        assert summary == "This is a test summary."
        mock_openai.return_value.chat.completions.create.assert_called_once()

    def test_generate_summary_with_description(self, generator, mock_openai):
        """Test summary generation with title and description."""
        title = "SEC Approves Bitcoin ETF Applications"
        description = "The SEC has approved multiple Bitcoin ETF applications."

        summary = generator.generate_summary(title, description)

        assert summary == "This is a test summary."

        # Verify the prompt includes both title and description
        call_args = mock_openai.return_value.chat.completions.create.call_args
        prompt = call_args[1]['messages'][1]['content']
        assert title in prompt
        assert description in prompt

    def test_generate_summary_api_failure_with_description(self, generator, mock_openai):
        """Test fallback when API fails and description is available."""
        mock_openai.return_value.chat.completions.create.side_effect = Exception("API Error")

        title = "Test Title"
        description = "This is a long description. It has multiple sentences."

        summary = generator.generate_summary(title, description)

        # Should fallback to first sentence of description
        assert summary == "This is a long description."

    def test_generate_summary_api_failure_no_description(self, generator, mock_openai):
        """Test fallback when API fails and no description."""
        mock_openai.return_value.chat.completions.create.side_effect = Exception("API Error")

        title = "Test Title"
        summary = generator.generate_summary(title)

        # Should fallback to title
        assert summary == title

    def test_generate_summary_uses_correct_model(self, generator, mock_openai):
        """Test that correct OpenAI model is used."""
        generator.generate_summary("Test")

        call_args = mock_openai.return_value.chat.completions.create.call_args
        assert call_args[1]['model'] == 'gpt-4o'

    def test_generate_summary_token_limit(self, generator, mock_openai):
        """Test that token limit is set correctly."""
        generator.generate_summary("Test")

        call_args = mock_openai.return_value.chat.completions.create.call_args
        assert call_args[1]['max_tokens'] == 100


class TestSourceCount:
    """Test source count calculation."""

    def test_calculate_source_count_single_source(self, generator, db_session):
        """Test source count with single source."""
        trend = Trend(
            title="Bitcoin ETF Approved",
            source=TrendSource.BLOOMBERG,
            keywords=['bitcoin', 'etf', 'approved']
        )
        db_session.add(trend)
        db_session.commit()

        count = generator.calculate_source_count(db_session, trend)
        assert count == 1

    def test_calculate_source_count_multiple_sources(self, generator, db_session):
        """Test source count with overlapping keywords from multiple sources."""
        # Create primary trend
        trend1 = Trend(
            title="Bitcoin ETF Approved by SEC",
            source=TrendSource.BLOOMBERG,
            keywords=['bitcoin', 'etf', 'approved', 'sec']
        )
        db_session.add(trend1)
        db_session.commit()

        # Create related trend from different source
        trend2 = Trend(
            title="SEC Approves Bitcoin ETF",
            source=TrendSource.WSJ,
            keywords=['sec', 'approves', 'bitcoin', 'etf']
        )
        db_session.add(trend2)
        db_session.commit()

        # Refresh to get updated data
        db_session.refresh(trend1)

        count = generator.calculate_source_count(db_session, trend1)
        assert count == 2  # Bloomberg + WSJ

    def test_calculate_source_count_no_overlap(self, generator, db_session):
        """Test source count with no keyword overlap."""
        trend1 = Trend(
            title="Bitcoin ETF Approved",
            source=TrendSource.BLOOMBERG,
            keywords=['bitcoin', 'etf', 'approved']
        )
        db_session.add(trend1)

        trend2 = Trend(
            title="PayPal Launches Crypto Service",
            source=TrendSource.TECHCRUNCH,
            keywords=['paypal', 'launches', 'crypto', 'service']
        )
        db_session.add(trend2)
        db_session.commit()

        db_session.refresh(trend1)

        count = generator.calculate_source_count(db_session, trend1)
        assert count == 1  # Only Bloomberg

    def test_calculate_source_count_requires_two_keywords(self, generator, db_session):
        """Test that source count requires at least 2 overlapping keywords."""
        trend1 = Trend(
            title="Bitcoin Regulation News",
            source=TrendSource.BLOOMBERG,
            keywords=['bitcoin', 'regulation', 'news']
        )
        db_session.add(trend1)

        # Only 1 overlapping keyword (bitcoin)
        trend2 = Trend(
            title="Bitcoin Price Surges",
            source=TrendSource.YAHOO_FINANCE,
            keywords=['bitcoin', 'price', 'surges']
        )
        db_session.add(trend2)
        db_session.commit()

        db_session.refresh(trend1)

        count = generator.calculate_source_count(db_session, trend1)
        assert count == 1  # Should not count trend2 (only 1 keyword overlap)


class TestRelatedTrends:
    """Test related trend grouping."""

    def test_find_related_trends_with_overlap(self, generator, db_session):
        """Test finding related trends with keyword overlap."""
        base_time = datetime.now(timezone.utc)

        trend1 = Trend(
            title="Bitcoin ETF Approved",
            source=TrendSource.BLOOMBERG,
            keywords=['bitcoin', 'etf', 'approved'],
            discovered_at=base_time
        )
        db_session.add(trend1)
        db_session.commit()

        trend2 = Trend(
            title="SEC Approves Bitcoin ETF",
            source=TrendSource.WSJ,
            keywords=['sec', 'approves', 'bitcoin', 'etf'],
            discovered_at=base_time + timedelta(hours=2)
        )
        db_session.add(trend2)
        db_session.commit()

        db_session.refresh(trend1)

        related = generator.find_related_trends(db_session, trend1)
        assert trend2.id in related

    def test_find_related_trends_no_overlap(self, generator, db_session):
        """Test that unrelated trends are not grouped."""
        base_time = datetime.now(timezone.utc)

        trend1 = Trend(
            title="Bitcoin ETF Approved",
            source=TrendSource.BLOOMBERG,
            keywords=['bitcoin', 'etf', 'approved'],
            discovered_at=base_time
        )
        db_session.add(trend1)

        trend2 = Trend(
            title="PayPal Launches Service",
            source=TrendSource.TECHCRUNCH,
            keywords=['paypal', 'launches', 'service'],
            discovered_at=base_time + timedelta(hours=2)
        )
        db_session.add(trend2)
        db_session.commit()

        db_session.refresh(trend1)

        related = generator.find_related_trends(db_session, trend1)
        assert trend2.id not in related

    def test_find_related_trends_time_window(self, generator, db_session):
        """Test that trends outside 7-day window are not included."""
        base_time = datetime.now(timezone.utc)

        trend1 = Trend(
            title="Bitcoin ETF Approved",
            source=TrendSource.BLOOMBERG,
            keywords=['bitcoin', 'etf', 'approved'],
            discovered_at=base_time
        )
        db_session.add(trend1)

        # Trend from 10 days ago (outside window)
        trend2 = Trend(
            title="SEC Bitcoin ETF Review",
            source=TrendSource.WSJ,
            keywords=['sec', 'bitcoin', 'etf', 'review'],
            discovered_at=base_time - timedelta(days=10)
        )
        db_session.add(trend2)
        db_session.commit()

        db_session.refresh(trend1)

        related = generator.find_related_trends(db_session, trend1)
        assert trend2.id not in related


class TestProcessTrend:
    """Test full trend processing."""

    def test_process_trend_complete(self, generator, db_session, mock_openai):
        """Test complete trend processing flow."""
        trend = Trend(
            title="SEC Approves Bitcoin ETF",
            description="The SEC has approved Bitcoin ETF applications.",
            source=TrendSource.BLOOMBERG
        )
        db_session.add(trend)
        db_session.commit()

        result = generator.process_trend(db_session, trend.id)
        assert result is True

        db_session.refresh(trend)

        # Verify all fields are populated
        assert trend.summary is not None
        assert trend.keywords is not None
        assert len(trend.keywords) > 0
        assert trend.source_count >= 1
        assert trend.related_trend_ids is not None

    def test_process_trend_not_found(self, generator, db_session):
        """Test processing non-existent trend."""
        result = generator.process_trend(db_session, 99999)
        assert result is False

    def test_process_trend_skips_existing_summary(self, generator, db_session):
        """Test that existing summary is not overwritten."""
        existing_summary = "Existing summary"

        trend = Trend(
            title="Test Trend",
            source=TrendSource.BLOOMBERG,
            summary=existing_summary
        )
        db_session.add(trend)
        db_session.commit()

        generator.process_trend(db_session, trend.id)

        db_session.refresh(trend)
        assert trend.summary == existing_summary


class TestBackfillSummaries:
    """Test batch processing of trends."""

    def test_backfill_summaries_processes_all(self, generator, db_session, mock_openai):
        """Test backfilling summaries for all trends."""
        # Create trends without summaries
        for i in range(3):
            trend = Trend(
                title=f"Test Trend {i}",
                source=TrendSource.BLOOMBERG
            )
            db_session.add(trend)
        db_session.commit()

        stats = generator.backfill_summaries(db_session)

        assert stats['success'] == 3
        assert stats['failed'] == 0
        assert stats['skipped'] == 0

    def test_backfill_summaries_with_limit(self, generator, db_session, mock_openai):
        """Test backfilling with limit."""
        # Create 5 trends
        for i in range(5):
            trend = Trend(
                title=f"Test Trend {i}",
                source=TrendSource.BLOOMBERG
            )
            db_session.add(trend)
        db_session.commit()

        stats = generator.backfill_summaries(db_session, limit=2)

        assert stats['success'] == 2

    def test_backfill_summaries_skips_existing(self, generator, db_session, mock_openai):
        """Test that trends with summaries are skipped."""
        # Create trend with existing summary
        trend1 = Trend(
            title="Test Trend 1",
            source=TrendSource.BLOOMBERG,
            summary="Existing summary"
        )
        db_session.add(trend1)

        # Create trend without summary
        trend2 = Trend(
            title="Test Trend 2",
            source=TrendSource.BLOOMBERG
        )
        db_session.add(trend2)
        db_session.commit()

        stats = generator.backfill_summaries(db_session)

        # Should only process trend2
        assert stats['success'] == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
