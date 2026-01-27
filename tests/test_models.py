"""
Unit tests for HFI database models.

Run with: pytest tests/test_models.py -v
"""

import pytest
import os
import sys
from datetime import datetime, timezone

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from common.models import (
    create_tables,
    get_db_session,
    get_tweets_by_status,
    get_recent_trends,
    update_tweet_status,
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

    def test_update_tweet_status(self, db):
        """Test updating tweet status and content."""
        # Create initial tweet
        tweet = Tweet(
            source_url="https://x.com/test/status/111111",
            original_text="Original text",
            status=TweetStatus.PENDING
        )
        db.add(tweet)
        db.commit()

        tweet_id = tweet.id

        # Update using helper function
        updated_tweet = update_tweet_status(
            db,
            tweet_id=tweet_id,
            new_status=TweetStatus.PROCESSED,
            hebrew_draft="טקסט מתורגם",
            media_path="data/media/test.mp4"
        )

        assert updated_tweet is not None
        assert updated_tweet.status == TweetStatus.PROCESSED
        assert updated_tweet.hebrew_draft == "טקסט מתורגם"
        assert updated_tweet.media_path == "data/media/test.mp4"

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


class TestHelperFunctions:
    """Test cases for helper functions."""

    def test_get_tweets_by_status(self, db):
        """Test filtering tweets by status."""
        # Create tweets with different statuses
        for i in range(5):
            tweet = Tweet(
                source_url=f"https://x.com/test/status/{i}",
                original_text=f"Tweet {i}",
                status=TweetStatus.PENDING if i < 3 else TweetStatus.PROCESSED
            )
            db.add(tweet)
        db.commit()

        # Get pending tweets
        pending = get_tweets_by_status(db, TweetStatus.PENDING)
        assert len(pending) == 3

        # Get processed tweets
        processed = get_tweets_by_status(db, TweetStatus.PROCESSED)
        assert len(processed) == 2

    def test_get_tweets_by_status_pagination(self, db):
        """Test pagination in get_tweets_by_status."""
        # Create 15 pending tweets
        for i in range(15):
            tweet = Tweet(
                source_url=f"https://x.com/test/status/{i}",
                original_text=f"Tweet {i}",
                status=TweetStatus.PENDING
            )
            db.add(tweet)
        db.commit()

        # Get first 10
        page1 = get_tweets_by_status(db, TweetStatus.PENDING, limit=10, offset=0)
        assert len(page1) == 10

        # Get next 5
        page2 = get_tweets_by_status(db, TweetStatus.PENDING, limit=10, offset=10)
        assert len(page2) == 5

    def test_get_recent_trends(self, db):
        """Test retrieving recent trends."""
        # Create trends from different sources
        trends_data = [
            ("Trend 1", TrendSource.X_TWITTER),
            ("Trend 2", TrendSource.YAHOO_FINANCE),
            ("Trend 3", TrendSource.X_TWITTER),
            ("Trend 4", TrendSource.TECHCRUNCH),
        ]

        for title, source in trends_data:
            trend = Trend(title=title, source=source)
            db.add(trend)
        db.commit()

        # Get all trends
        all_trends = get_recent_trends(db, limit=10)
        assert len(all_trends) == 4

        # Get only X trends
        x_trends = get_recent_trends(db, source=TrendSource.X_TWITTER, limit=10)
        assert len(x_trends) == 2

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
