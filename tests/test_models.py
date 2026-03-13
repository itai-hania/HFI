"""
Unit tests for HFI database models.

Run with: pytest tests/test_models.py -v
"""

import pytest
import os
from datetime import datetime, timezone

from common.models import (
    create_tables,
    get_db_session,
    health_check,
    Tweet,
    Trend,
    TweetStatus,
    TrendSource,
    Base,
    engine,
)


@pytest.fixture
def db():
    """Create an in-memory database for testing."""
    # Use in-memory database for tests
    os.environ['DATABASE_URL'] = 'sqlite:///:memory:'

    # Recreate tables in memory
    Base.metadata.create_all(engine)

    # Create session
    session = get_db_session()

    yield session

    # Cleanup
    session.close()
    Base.metadata.drop_all(engine)


class TestTweetModel:
    """Test cases for Tweet model."""

    def test_create_tweet(self, db):
        """Test creating a new tweet."""
        tweet = Tweet(
            source_url="https://x.com/test/status/123456",
            original_text="This is a test tweet about FinTech innovation.",
            status=TweetStatus.PENDING,
            created_at=datetime.now(timezone.utc)
        )

        db.add(tweet)
        db.commit()

        assert tweet.id is not None
        assert tweet.status == TweetStatus.PENDING
        assert tweet.hebrew_draft is None
        assert tweet.media_path is None

    def test_tweet_unique_url_constraint(self, db):
        """Test that duplicate URLs are rejected."""
        url = "https://x.com/test/status/999999"

        # First tweet
        tweet1 = Tweet(
            source_url=url,
            original_text="First tweet",
            status=TweetStatus.PENDING
        )
        db.add(tweet1)
        db.commit()

        # Second tweet with same URL should fail
        tweet2 = Tweet(
            source_url=url,
            original_text="Duplicate tweet",
            status=TweetStatus.PENDING
        )
        db.add(tweet2)

        with pytest.raises(Exception):  # Should raise IntegrityError
            db.commit()

    def test_tweet_to_dict(self, db):
        """Test converting tweet to dictionary."""
        tweet = Tweet(
            source_url="https://x.com/test/status/222222",
            original_text="Test tweet",
            hebrew_draft="טוויט בדיקה",
            status=TweetStatus.APPROVED,
            trend_topic="AI Testing"
        )
        db.add(tweet)
        db.commit()

        tweet_dict = tweet.to_dict()

        assert tweet_dict['id'] == tweet.id
        assert tweet_dict['source_url'] == tweet.source_url
        assert tweet_dict['original_text'] == "Test tweet"
        assert tweet_dict['hebrew_draft'] == "טוויט בדיקה"
        assert tweet_dict['status'] == "approved"
        assert tweet_dict['trend_topic'] == "AI Testing"


class TestTrendModel:
    """Test cases for Trend model."""

    def test_create_trend(self, db):
        """Test creating a new trend."""
        trend = Trend(
            title="Bitcoin Rally",
            description="Bitcoin reaches new all-time high",
            source=TrendSource.X_TWITTER,
            discovered_at=datetime.now(timezone.utc)
        )

        db.add(trend)
        db.commit()

        assert trend.id is not None
        assert trend.title == "Bitcoin Rally"
        assert trend.source == TrendSource.X_TWITTER

    def test_trend_to_dict(self, db):
        """Test converting trend to dictionary."""
        trend = Trend(
            title="AI Regulation",
            description="New EU AI Act",
            source=TrendSource.YAHOO_FINANCE
        )
        db.add(trend)
        db.commit()

        trend_dict = trend.to_dict()

        assert trend_dict['id'] == trend.id
        assert trend_dict['title'] == "AI Regulation"
        assert trend_dict['source'] == "Yahoo Finance"


class TestDatabaseUtilities:
    """Test cases for database utility functions."""

    def test_health_check_empty_db(self):
        """Test health check on empty database."""
        # Note: This uses the actual database, not in-memory
        health = health_check()

        assert 'status' in health
        assert health['status'] in ['healthy', 'unhealthy']

        if health['status'] == 'healthy':
            assert 'tweet_count' in health
            assert 'trend_count' in health
            assert 'status_breakdown' in health


class TestEnums:
    """Test cases for enum types."""

    def test_tweet_status_enum(self):
        """Test TweetStatus enum values."""
        assert TweetStatus.PENDING.value == "pending"
        assert TweetStatus.PROCESSED.value == "processed"
        assert TweetStatus.APPROVED.value == "approved"
        assert TweetStatus.PUBLISHED.value == "published"

        assert str(TweetStatus.PENDING) == "pending"

    def test_trend_source_enum(self):
        """Test TrendSource enum values."""
        assert TrendSource.X_TWITTER.value == "X"
        assert TrendSource.YAHOO_FINANCE.value == "Yahoo Finance"
        assert TrendSource.TECHCRUNCH.value == "TechCrunch"
        assert TrendSource.MANUAL.value == "Manual"

        assert str(TrendSource.X_TWITTER) == "X"


if __name__ == "__main__":
    # Run tests with verbose output
    pytest.main([__file__, "-v", "--tb=short"])
