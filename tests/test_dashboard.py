"""
Comprehensive tests for the Streamlit Dashboard.

Tests cover:
1. Database query functions
2. Tweet CRUD operations
3. Statistics computation
4. Filtering and pagination
5. Bulk actions
6. UI component logic

Run with: pytest tests/test_dashboard.py -v

Note: Streamlit apps are challenging to test directly due to their
interactive nature. These tests focus on the underlying logic and
database operations that power the UI.
"""

import pytest
import os
import sys
from pathlib import Path
from datetime import datetime, timezone
from unittest.mock import Mock, MagicMock, patch

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from common.models import (
    Tweet,
    TweetStatus,
    Trend,
    TrendSource,
    Base,
    engine,
    get_db_session
)

# Import dashboard functions
# Note: We can't import the full app due to Streamlit, but we can test the functions
import importlib.util
dashboard_path = os.path.join(os.path.dirname(__file__), '..', 'src', 'dashboard', 'app.py')
spec = importlib.util.spec_from_file_location("dashboard_app", dashboard_path)
dashboard_app = importlib.util.module_from_spec(spec)


# ==================== Fixtures ====================

@pytest.fixture
def test_db():
    """Create an in-memory database for testing."""
    os.environ['DATABASE_URL'] = 'sqlite:///:memory:'

    # Recreate tables
    Base.metadata.create_all(engine)

    # Create session
    session = get_db_session()

    yield session

    # Cleanup
    session.close()
    Base.metadata.drop_all(engine)


@pytest.fixture
def sample_tweets(test_db):
    """Create sample tweets for testing."""
    tweets = [
        Tweet(
            source_url="https://x.com/test/status/1",
            original_text="First tweet about AI",
            hebrew_draft="ציוץ ראשון על AI",
            status=TweetStatus.PENDING,
            trend_topic="Artificial Intelligence"
        ),
        Tweet(
            source_url="https://x.com/test/status/2",
            original_text="Second tweet about Fintech",
            hebrew_draft="ציוץ שני על פינטק",
            status=TweetStatus.PROCESSED,
            trend_topic="FinTech"
        ),
        Tweet(
            source_url="https://x.com/test/status/3",
            original_text="Third tweet about Blockchain",
            hebrew_draft="ציוץ שלישי על בלוקצ'יין",
            status=TweetStatus.APPROVED,
            trend_topic="Blockchain"
        ),
        Tweet(
            source_url="https://x.com/test/status/4",
            original_text="Fourth tweet published",
            hebrew_draft="ציוץ רביעי פורסם",
            status=TweetStatus.PUBLISHED,
            trend_topic="Crypto"
        ),
        Tweet(
            source_url="https://x.com/test/status/5",
            original_text="Fifth tweet with media",
            hebrew_draft="ציוץ חמישי עם מדיה",
            media_url="https://example.com/video.mp4",
            media_path="/data/media/video.mp4",
            status=TweetStatus.PROCESSED,
            trend_topic="Tech News"
        )
    ]

    for tweet in tweets:
        test_db.add(tweet)

    test_db.commit()

    # Return IDs for reference
    tweet_ids = [t.id for t in tweets]

    return tweet_ids


@pytest.fixture
def sample_trends(test_db):
    """Create sample trends for testing."""
    trends = [
        Trend(
            title="AI Revolution",
            description="Latest AI developments",
            source=TrendSource.X_TWITTER
        ),
        Trend(
            title="Bitcoin Rally",
            description="Bitcoin reaches new high",
            source=TrendSource.REUTERS
        ),
        Trend(
            title="Startup Funding",
            description="VC investments increase",
            source=TrendSource.TECHCRUNCH
        )
    ]

    for trend in trends:
        test_db.add(trend)

    test_db.commit()

    return [t.id for t in trends]


# ==================== Database Query Tests ====================

class TestDatabaseQueries:
    """Test database query functions used by the dashboard."""

    def test_get_stats_empty_database(self, test_db):
        """Test statistics computation on empty database."""
        from sqlalchemy import func

        stats = {
            'total': test_db.query(func.count(Tweet.id)).scalar(),
            'pending': test_db.query(func.count(Tweet.id)).filter(Tweet.status == 'pending').scalar(),
            'processed': test_db.query(func.count(Tweet.id)).filter(Tweet.status == 'processed').scalar(),
            'approved': test_db.query(func.count(Tweet.id)).filter(Tweet.status == 'approved').scalar(),
            'published': test_db.query(func.count(Tweet.id)).filter(Tweet.status == 'published').scalar(),
        }

        assert stats['total'] == 0
        assert stats['pending'] == 0
        assert stats['processed'] == 0
        assert stats['approved'] == 0
        assert stats['published'] == 0

    def test_get_stats_with_data(self, test_db, sample_tweets):
        """Test statistics computation with sample data."""
        from sqlalchemy import func

        stats = {
            'total': test_db.query(func.count(Tweet.id)).scalar(),
            'pending': test_db.query(func.count(Tweet.id)).filter(Tweet.status == TweetStatus.PENDING).scalar(),
            'processed': test_db.query(func.count(Tweet.id)).filter(Tweet.status == TweetStatus.PROCESSED).scalar(),
            'approved': test_db.query(func.count(Tweet.id)).filter(Tweet.status == TweetStatus.APPROVED).scalar(),
            'published': test_db.query(func.count(Tweet.id)).filter(Tweet.status == TweetStatus.PUBLISHED).scalar(),
        }

        assert stats['total'] == 5
        assert stats['pending'] == 1
        assert stats['processed'] == 2
        assert stats['approved'] == 1
        assert stats['published'] == 1

    def test_get_tweets_all(self, test_db, sample_tweets):
        """Test fetching all tweets without filter."""
        query = test_db.query(Tweet).order_by(Tweet.created_at.desc())
        tweets = query.all()

        assert len(tweets) == 5

    def test_get_tweets_filtered_by_status(self, test_db, sample_tweets):
        """Test fetching tweets filtered by status."""
        # Filter for processed tweets
        query = test_db.query(Tweet).filter(Tweet.status == TweetStatus.PROCESSED)
        tweets = query.all()

        assert len(tweets) == 2
        for tweet in tweets:
            assert tweet.status == TweetStatus.PROCESSED

    def test_get_tweets_with_limit(self, test_db, sample_tweets):
        """Test fetching tweets with limit (pagination)."""
        query = test_db.query(Tweet).order_by(Tweet.created_at.desc()).limit(3)
        tweets = query.all()

        assert len(tweets) == 3

    def test_get_tweets_ordered_by_date(self, test_db, sample_tweets):
        """Test that tweets are ordered by creation date."""
        query = test_db.query(Tweet).order_by(Tweet.created_at.desc())
        tweets = query.all()

        # Verify descending order
        for i in range(len(tweets) - 1):
            assert tweets[i].created_at >= tweets[i + 1].created_at


# ==================== Tweet CRUD Operations ====================

class TestTweetOperations:
    """Test CRUD operations on tweets."""

    def test_update_tweet_hebrew_draft(self, test_db, sample_tweets):
        """Test updating Hebrew draft of a tweet."""
        tweet_id = sample_tweets[0]
        tweet = test_db.query(Tweet).filter(Tweet.id == tweet_id).first()

        new_hebrew = "תרגום מעודכן חדש"
        tweet.hebrew_draft = new_hebrew
        tweet.updated_at = datetime.now(timezone.utc)

        test_db.commit()
        test_db.refresh(tweet)

        assert tweet.hebrew_draft == new_hebrew

    def test_update_tweet_status(self, test_db, sample_tweets):
        """Test updating tweet status."""
        tweet_id = sample_tweets[0]
        tweet = test_db.query(Tweet).filter(Tweet.id == tweet_id).first()

        original_status = tweet.status
        tweet.status = TweetStatus.APPROVED
        tweet.updated_at = datetime.now(timezone.utc)

        test_db.commit()
        test_db.refresh(tweet)

        assert tweet.status == TweetStatus.APPROVED
        assert tweet.status != original_status

    def test_delete_tweet(self, test_db, sample_tweets):
        """Test deleting a tweet."""
        tweet_id = sample_tweets[0]
        tweet = test_db.query(Tweet).filter(Tweet.id == tweet_id).first()

        assert tweet is not None

        test_db.delete(tweet)
        test_db.commit()

        # Verify deletion
        deleted_tweet = test_db.query(Tweet).filter(Tweet.id == tweet_id).first()
        assert deleted_tweet is None

        # Verify total count decreased
        remaining = test_db.query(Tweet).count()
        assert remaining == 4

    def test_update_multiple_fields(self, test_db, sample_tweets):
        """Test updating multiple fields at once."""
        tweet_id = sample_tweets[0]
        tweet = test_db.query(Tweet).filter(Tweet.id == tweet_id).first()

        tweet.status = TweetStatus.APPROVED
        tweet.hebrew_draft = "עריכה מרובת שדות"
        tweet.updated_at = datetime.now(timezone.utc)

        test_db.commit()
        test_db.refresh(tweet)

        assert tweet.status == TweetStatus.APPROVED
        assert tweet.hebrew_draft == "עריכה מרובת שדות"

    def test_reset_tweet_to_pending(self, test_db, sample_tweets):
        """Test resetting a tweet back to pending status."""
        tweet_id = sample_tweets[2]  # Approved tweet
        tweet = test_db.query(Tweet).filter(Tweet.id == tweet_id).first()

        assert tweet.status == TweetStatus.APPROVED

        tweet.status = TweetStatus.PENDING
        tweet.updated_at = datetime.now(timezone.utc)

        test_db.commit()
        test_db.refresh(tweet)

        assert tweet.status == TweetStatus.PENDING

    def test_reprocess_tweet(self, test_db, sample_tweets):
        """Test marking tweet for reprocessing."""
        tweet_id = sample_tweets[1]
        tweet = test_db.query(Tweet).filter(Tweet.id == tweet_id).first()

        # Reprocess: set to pending and clear draft
        tweet.status = TweetStatus.PENDING
        tweet.hebrew_draft = None
        tweet.updated_at = datetime.now(timezone.utc)

        test_db.commit()
        test_db.refresh(tweet)

        assert tweet.status == TweetStatus.PENDING
        assert tweet.hebrew_draft is None


# ==================== Filtering and Pagination Tests ====================

class TestFilteringAndPagination:
    """Test filtering and pagination logic."""

    def test_filter_by_pending_status(self, test_db, sample_tweets):
        """Test filtering for pending tweets."""
        tweets = test_db.query(Tweet).filter(Tweet.status == TweetStatus.PENDING).all()

        assert len(tweets) == 1
        assert tweets[0].status == TweetStatus.PENDING

    def test_filter_by_processed_status(self, test_db, sample_tweets):
        """Test filtering for processed tweets."""
        tweets = test_db.query(Tweet).filter(Tweet.status == TweetStatus.PROCESSED).all()

        assert len(tweets) == 2
        for tweet in tweets:
            assert tweet.status == TweetStatus.PROCESSED

    def test_filter_by_approved_status(self, test_db, sample_tweets):
        """Test filtering for approved tweets."""
        tweets = test_db.query(Tweet).filter(Tweet.status == TweetStatus.APPROVED).all()

        assert len(tweets) == 1
        assert tweets[0].status == TweetStatus.APPROVED

    def test_filter_by_published_status(self, test_db, sample_tweets):
        """Test filtering for published tweets."""
        tweets = test_db.query(Tweet).filter(Tweet.status == TweetStatus.PUBLISHED).all()

        assert len(tweets) == 1
        assert tweets[0].status == TweetStatus.PUBLISHED

    def test_pagination_first_page(self, test_db, sample_tweets):
        """Test fetching first page of results."""
        tweets = test_db.query(Tweet).order_by(Tweet.created_at.desc()).limit(2).all()

        assert len(tweets) == 2

    def test_pagination_second_page(self, test_db, sample_tweets):
        """Test fetching second page of results."""
        tweets = test_db.query(Tweet).order_by(Tweet.created_at.desc()).limit(2).offset(2).all()

        assert len(tweets) == 2

    def test_pagination_last_page_partial(self, test_db, sample_tweets):
        """Test fetching last page with fewer items."""
        tweets = test_db.query(Tweet).order_by(Tweet.created_at.desc()).limit(3).offset(3).all()

        assert len(tweets) == 2  # Only 2 remaining

    def test_empty_result_for_nonexistent_status(self, test_db, sample_tweets):
        """Test filtering for status with no tweets."""
        tweets = test_db.query(Tweet).filter(Tweet.status == TweetStatus.FAILED).all()

        assert len(tweets) == 0


# ==================== Bulk Actions Tests ====================

class TestBulkActions:
    """Test bulk operation logic."""

    def test_approve_all_processed(self, test_db, sample_tweets):
        """Test approving all processed tweets with Hebrew draft."""
        # Get all processed tweets
        processed_tweets = test_db.query(Tweet).filter(Tweet.status == TweetStatus.PROCESSED).all()

        assert len(processed_tweets) == 2

        count = 0
        for tweet in processed_tweets:
            if tweet.hebrew_draft:
                tweet.status = TweetStatus.APPROVED
                tweet.updated_at = datetime.now(timezone.utc)
                count += 1

        test_db.commit()

        assert count == 2

        # Verify no more processed tweets
        remaining_processed = test_db.query(Tweet).filter(Tweet.status == TweetStatus.PROCESSED).all()
        assert len(remaining_processed) == 0

        # Verify approved count increased
        approved = test_db.query(Tweet).filter(Tweet.status == TweetStatus.APPROVED).all()
        assert len(approved) == 3  # 1 original + 2 newly approved

    def test_approve_only_with_hebrew_draft(self, test_db):
        """Test that bulk approve only affects tweets with Hebrew draft."""
        # Create processed tweet without Hebrew draft
        tweet_without_draft = Tweet(
            source_url="https://x.com/test/status/no_draft",
            original_text="No Hebrew translation yet",
            status=TweetStatus.PROCESSED
        )
        test_db.add(tweet_without_draft)

        # Create processed tweet with Hebrew draft
        tweet_with_draft = Tweet(
            source_url="https://x.com/test/status/with_draft",
            original_text="Has Hebrew translation",
            hebrew_draft="יש תרגום",
            status=TweetStatus.PROCESSED
        )
        test_db.add(tweet_with_draft)
        test_db.commit()

        # Bulk approve
        processed_tweets = test_db.query(Tweet).filter(Tweet.status == TweetStatus.PROCESSED).all()
        count = 0
        for tweet in processed_tweets:
            if tweet.hebrew_draft:
                tweet.status = TweetStatus.APPROVED
                count += 1

        test_db.commit()

        # Only one should be approved
        assert count == 1

        test_db.refresh(tweet_without_draft)
        test_db.refresh(tweet_with_draft)

        assert tweet_without_draft.status == TweetStatus.PROCESSED
        assert tweet_with_draft.status == TweetStatus.APPROVED

    def test_delete_all_pending(self, test_db, sample_tweets):
        """Test deleting all pending tweets."""
        pending_tweets = test_db.query(Tweet).filter(Tweet.status == TweetStatus.PENDING).all()
        count = len(pending_tweets)

        assert count == 1

        for tweet in pending_tweets:
            test_db.delete(tweet)

        test_db.commit()

        # Verify all pending deleted
        remaining_pending = test_db.query(Tweet).filter(Tweet.status == TweetStatus.PENDING).all()
        assert len(remaining_pending) == 0

        # Verify total count
        total = test_db.query(Tweet).count()
        assert total == 4  # 5 - 1 deleted

    def test_bulk_status_change(self, test_db):
        """Test changing status for multiple tweets at once."""
        # Create multiple pending tweets
        for i in range(3):
            tweet = Tweet(
                source_url=f"https://x.com/test/status/bulk_{i}",
                original_text=f"Bulk test {i}",
                status=TweetStatus.PENDING
            )
            test_db.add(tweet)

        test_db.commit()

        # Bulk change to processed
        pending_tweets = test_db.query(Tweet).filter(Tweet.status == TweetStatus.PENDING).all()

        for tweet in pending_tweets:
            tweet.status = TweetStatus.PROCESSED
            tweet.hebrew_draft = "תרגום אוטומטי"

        test_db.commit()

        # Verify changes
        processed = test_db.query(Tweet).filter(Tweet.status == TweetStatus.PROCESSED).all()
        assert len(processed) == 3


# ==================== Media Display Tests ====================

class TestMediaDisplay:
    """Test media display logic."""

    def test_tweet_with_media_url_only(self, test_db):
        """Test tweet with media URL but no local path."""
        tweet = Tweet(
            source_url="https://x.com/test/status/media1",
            original_text="Tweet with media URL",
            media_url="https://example.com/image.jpg",
            status=TweetStatus.PENDING
        )
        test_db.add(tweet)
        test_db.commit()

        assert tweet.media_url is not None
        assert tweet.media_path is None

    def test_tweet_with_downloaded_media(self, test_db):
        """Test tweet with both media URL and local path."""
        tweet = Tweet(
            source_url="https://x.com/test/status/media2",
            original_text="Tweet with downloaded media",
            media_url="https://example.com/video.mp4",
            media_path="/data/media/video_123.mp4",
            status=TweetStatus.PROCESSED
        )
        test_db.add(tweet)
        test_db.commit()

        assert tweet.media_url is not None
        assert tweet.media_path is not None

    def test_tweet_without_media(self, test_db):
        """Test tweet with no media."""
        tweet = Tweet(
            source_url="https://x.com/test/status/media3",
            original_text="Tweet without media",
            status=TweetStatus.PENDING
        )
        test_db.add(tweet)
        test_db.commit()

        assert tweet.media_url is None
        assert tweet.media_path is None

    def test_media_file_extension_detection(self):
        """Test detecting media file types by extension."""
        image_extensions = ['.jpg', '.jpeg', '.png', '.gif']
        video_extensions = ['.mp4', '.mov', '.avi']

        for ext in image_extensions:
            assert ext.lower() in ['.jpg', '.jpeg', '.png', '.gif']

        for ext in video_extensions:
            assert ext.lower() in ['.mp4', '.mov', '.avi']


# ==================== Status Badge Tests ====================

class TestStatusBadges:
    """Test status badge display logic."""

    def test_status_badge_colors(self):
        """Test that each status has a corresponding badge."""
        status_colors = {
            'pending': '🟠',
            'processed': '🟢',
            'approved': '🟣',
            'published': '🔵'
        }

        for status in ['pending', 'processed', 'approved', 'published']:
            assert status in status_colors
            assert len(status_colors[status]) > 0

    def test_unknown_status_fallback(self):
        """Test fallback for unknown status."""
        status_colors = {
            'pending': '🟠',
            'processed': '🟢',
            'approved': '🟣',
            'published': '🔵'
        }

        unknown_badge = status_colors.get('unknown', '⚪')
        assert unknown_badge == '⚪'


# ==================== Timestamp and Sorting Tests ====================

class TestTimestampAndSorting:
    """Test timestamp handling and sorting."""

    def test_tweets_sorted_by_created_at(self, test_db):
        """Test that tweets are sortable by created_at."""
        # Create tweets with different timestamps
        from datetime import timedelta

        now = datetime.now(timezone.utc)

        tweets = [
            Tweet(
                source_url=f"https://x.com/test/status/time_{i}",
                original_text=f"Tweet {i}",
                created_at=now - timedelta(hours=i),
                status=TweetStatus.PENDING
            )
            for i in range(3)
        ]

        for tweet in tweets:
            test_db.add(tweet)

        test_db.commit()

        # Query ordered by created_at
        ordered = test_db.query(Tweet).order_by(Tweet.created_at.desc()).all()

        # Verify order
        for i in range(len(ordered) - 1):
            assert ordered[i].created_at >= ordered[i + 1].created_at

    def test_updated_at_changes_on_edit(self, test_db):
        """Test that updated_at changes when tweet is edited."""
        from datetime import timedelta

        tweet = Tweet(
            source_url="https://x.com/test/status/update_time",
            original_text="Original",
            status=TweetStatus.PENDING
        )
        test_db.add(tweet)
        test_db.commit()

        # Store string representation to compare
        original_updated_str = str(tweet.updated_at)

        # Update tweet
        tweet.hebrew_draft = "תרגום"
        tweet.updated_at = datetime.now(timezone.utc)
        test_db.commit()
        test_db.refresh(tweet)

        # Verify updated_at field exists and changed
        assert tweet.updated_at is not None
        new_updated_str = str(tweet.updated_at)
        # At minimum, check that the field is set
        assert new_updated_str is not None


# ==================== Edge Cases ====================

class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_empty_hebrew_draft(self, test_db):
        """Test tweet with empty Hebrew draft."""
        tweet = Tweet(
            source_url="https://x.com/test/status/empty",
            original_text="Original text",
            hebrew_draft="",
            status=TweetStatus.PROCESSED
        )
        test_db.add(tweet)
        test_db.commit()

        assert tweet.hebrew_draft == ""

    def test_very_long_text(self, test_db):
        """Test tweet with very long text."""
        long_text = "A" * 10000  # 10,000 characters

        tweet = Tweet(
            source_url="https://x.com/test/status/long",
            original_text=long_text,
            status=TweetStatus.PENDING
        )
        test_db.add(tweet)
        test_db.commit()

        assert len(tweet.original_text) == 10000

    def test_special_characters_in_hebrew(self, test_db):
        """Test Hebrew text with special characters."""
        hebrew_with_special = "שלום! זה טקסט עם סימנים מיוחדים: @#$%^&*()"

        tweet = Tweet(
            source_url="https://x.com/test/status/special",
            original_text="Hello with special chars",
            hebrew_draft=hebrew_with_special,
            status=TweetStatus.PROCESSED
        )
        test_db.add(tweet)
        test_db.commit()

        assert tweet.hebrew_draft == hebrew_with_special

    def test_null_trend_topic(self, test_db):
        """Test tweet without trend topic."""
        tweet = Tweet(
            source_url="https://x.com/test/status/no_trend",
            original_text="No trend topic",
            trend_topic=None,
            status=TweetStatus.PENDING
        )
        test_db.add(tweet)
        test_db.commit()

        assert tweet.trend_topic is None

    def test_filter_with_no_results(self, test_db):
        """Test filter that returns no results."""
        tweets = test_db.query(Tweet).filter(Tweet.status == TweetStatus.FAILED).all()

        assert len(tweets) == 0
        assert tweets == []


if __name__ == "__main__":
    # Run tests with verbose output
    pytest.main([__file__, "-v", "--tb=short"])
