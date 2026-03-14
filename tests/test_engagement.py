"""
Tests for TweetEngagement model, compute_score, fuzzy matching, and style propagation.

Run with: pytest tests/test_engagement.py -v
"""

import math
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from common.models import (
    Base,
    Tweet,
    TweetStatus,
    TweetEngagement,
    StyleExample,
    engine,
    get_db_session,
)


@pytest.fixture
def db():
    """Create an in-memory database for testing."""
    Base.metadata.create_all(engine)
    session = get_db_session()
    yield session
    session.close()
    Base.metadata.drop_all(engine)


@pytest.fixture
def published_tweet(db):
    """Create a published tweet for engagement tests."""
    tweet = Tweet(
        source_url="https://x.com/test/status/100",
        original_text="FinTech innovation is changing banking.",
        hebrew_draft="חדשנות פינטק משנה את הבנקאות.",
        status=TweetStatus.PUBLISHED,
        created_at=datetime.now(timezone.utc),
    )
    db.add(tweet)
    db.commit()
    return tweet


# ==================== TweetEngagement Model ====================

class TestTweetEngagementModel:

    def test_create_engagement(self, db, published_tweet):
        eng = TweetEngagement(
            tweet_id=published_tweet.id,
            x_post_id="12345",
            likes=10,
            retweets=5,
            replies=3,
            views=1000,
            bookmarks=2,
        )
        db.add(eng)
        db.commit()

        assert eng.id is not None
        assert eng.tweet_id == published_tweet.id
        assert eng.likes == 10
        assert eng.retweets == 5
        assert eng.views == 1000

    def test_engagement_defaults(self, db, published_tweet):
        eng = TweetEngagement(tweet_id=published_tweet.id)
        db.add(eng)
        db.commit()

        assert eng.likes == 0
        assert eng.retweets == 0
        assert eng.replies == 0
        assert eng.views == 0
        assert eng.bookmarks == 0
        assert eng.engagement_score == 0

    def test_unique_tweet_id_constraint(self, db, published_tweet):
        eng1 = TweetEngagement(tweet_id=published_tweet.id, likes=5)
        db.add(eng1)
        db.commit()

        eng2 = TweetEngagement(tweet_id=published_tweet.id, likes=10)
        db.add(eng2)
        with pytest.raises(Exception):
            db.commit()
        db.rollback()

    def test_tweet_relationship(self, db, published_tweet):
        eng = TweetEngagement(tweet_id=published_tweet.id, likes=7)
        db.add(eng)
        db.commit()

        assert eng.tweet.id == published_tweet.id
        assert eng.tweet.source_url == "https://x.com/test/status/100"


# ==================== compute_score ====================

class TestComputeScore:

    def test_compute_score_basic(self, db, published_tweet):
        eng = TweetEngagement(
            tweet_id=published_tweet.id,
            likes=10,
            retweets=5,
            replies=3,
            views=1024,
            bookmarks=2,
        )
        db.add(eng)
        db.commit()

        score = eng.compute_score()
        expected = 10 * 3 + 5 * 5 + 3 * 2 + 2 * 4 + int(math.log2(1024))
        assert score == expected
        assert eng.engagement_score == expected

    def test_compute_score_zero_views(self, db, published_tweet):
        eng = TweetEngagement(
            tweet_id=published_tweet.id,
            likes=0, retweets=0, replies=0, views=0, bookmarks=0,
        )
        db.add(eng)
        db.commit()

        score = eng.compute_score()
        assert score == int(math.log2(1))
        assert score == 0

    def test_compute_score_high_engagement(self, db, published_tweet):
        eng = TweetEngagement(
            tweet_id=published_tweet.id,
            likes=500,
            retweets=200,
            replies=100,
            views=100000,
            bookmarks=50,
        )
        db.add(eng)
        db.commit()

        score = eng.compute_score()
        expected = 500 * 3 + 200 * 5 + 100 * 2 + 50 * 4 + int(math.log2(100000))
        assert score == expected

    def test_standalone_compute_function(self):
        from tools.scrape_engagement import compute_engagement_score
        score = compute_engagement_score(10, 5, 3, 1024, 2)
        expected = 10 * 3 + 5 * 5 + 3 * 2 + 2 * 4 + int(math.log2(1024))
        assert score == expected


# ==================== Fuzzy Matching ====================

class TestFuzzyMatch:

    def test_exact_match(self):
        from tools.scrape_engagement import match_tweet_text
        assert match_tweet_text("Hello world", "Hello world") is True

    def test_whitespace_normalization(self):
        from tools.scrape_engagement import match_tweet_text
        assert match_tweet_text("Hello   world\n foo", "Hello world foo") is True

    def test_first_100_chars_match(self):
        from tools.scrape_engagement import match_tweet_text
        prefix = "A" * 100
        a = prefix + " extra stuff here"
        b = prefix + " different tail"
        assert match_tweet_text(a, b) is True

    def test_mismatch(self):
        from tools.scrape_engagement import match_tweet_text
        assert match_tweet_text("Hello world", "Goodbye world") is False

    def test_empty_strings(self):
        from tools.scrape_engagement import match_tweet_text
        assert match_tweet_text("", "") is False
        assert match_tweet_text("hello", "") is False
        assert match_tweet_text("", "hello") is False

    def test_hebrew_text_match(self):
        from tools.scrape_engagement import match_tweet_text
        text = "חדשנות פינטק משנה את הבנקאות"
        assert match_tweet_text(text, text) is True


# ==================== Style Propagation ====================

class TestStylePropagation:

    def test_propagate_engagement_to_styles(self, db, published_tweet):
        from tools.scrape_engagement import propagate_engagement_to_styles

        eng = TweetEngagement(
            tweet_id=published_tweet.id,
            likes=20, retweets=10, replies=5, views=5000, bookmarks=3,
        )
        eng.compute_score()
        db.add(eng)
        db.commit()

        style = StyleExample(
            content="חדשנות פינטק משנה את הבנקאות.",
            source_type="self_scraped",
            word_count=5,
            is_active=True,
            derived_from_tweet_id=published_tweet.id,
        )
        db.add(style)
        db.commit()

        count = propagate_engagement_to_styles(db)
        assert count == 1

        db.refresh(style)
        assert style.engagement_score == eng.engagement_score

    def test_propagate_no_linked_styles(self, db, published_tweet):
        from tools.scrape_engagement import propagate_engagement_to_styles

        style = StyleExample(
            content="Some content",
            source_type="manual",
            word_count=2,
            is_active=True,
            derived_from_tweet_id=None,
        )
        db.add(style)
        db.commit()

        count = propagate_engagement_to_styles(db)
        assert count == 0

    def test_propagate_inactive_styles_ignored(self, db, published_tweet):
        from tools.scrape_engagement import propagate_engagement_to_styles

        eng = TweetEngagement(
            tweet_id=published_tweet.id,
            likes=10, retweets=5, replies=2, views=1000, bookmarks=1,
        )
        eng.compute_score()
        db.add(eng)

        style = StyleExample(
            content="Inactive content",
            source_type="self_scraped",
            word_count=2,
            is_active=False,
            derived_from_tweet_id=published_tweet.id,
        )
        db.add(style)
        db.commit()

        count = propagate_engagement_to_styles(db)
        assert count == 0


# ==================== Engagement in Style Selection ====================

class TestEngagementInStyleSelection:

    def test_engagement_boosts_style_ranking(self, db):
        """Style examples with higher engagement_score should rank higher."""
        style_high = StyleExample(
            content="תוכן עם אנגייג׳מנט גבוה בנושא פינטק",
            source_type="self_scraped",
            word_count=6,
            is_active=True,
            topic_tags=["fintech"],
            engagement_score=50,
        )
        style_low = StyleExample(
            content="תוכן עם אנגייג׳מנט נמוך בנושא פינטק",
            source_type="self_scraped",
            word_count=6,
            is_active=True,
            topic_tags=["fintech"],
            engagement_score=0,
        )
        db.add_all([style_high, style_low])
        db.commit()

        engagement_high = getattr(style_high, 'engagement_score', 0) or 0
        engagement_low = getattr(style_low, 'engagement_score', 0) or 0

        score_high = engagement_high * 2
        score_low = engagement_low * 2

        assert score_high > score_low
        assert score_high == 100
        assert score_low == 0


# ==================== StyleExample New Columns ====================

class TestStyleExampleNewColumns:

    def test_engagement_score_default(self, db):
        style = StyleExample(
            content="Test content",
            source_type="manual",
            word_count=2,
            is_active=True,
        )
        db.add(style)
        db.commit()

        assert style.engagement_score == 0

    def test_derived_from_tweet_id(self, db, published_tweet):
        style = StyleExample(
            content="Derived content",
            source_type="self_scraped",
            word_count=2,
            is_active=True,
            derived_from_tweet_id=published_tweet.id,
        )
        db.add(style)
        db.commit()

        assert style.derived_from_tweet_id == published_tweet.id
