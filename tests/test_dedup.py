"""
Tests for the topic deduplication module.

Tests cover:
1. extract_topic_fingerprint — keyword extraction, hashing, entities
2. is_duplicate_topic — Jaccard similarity, thresholds, edge cases
3. get_recent_topics — DB queries with in-memory SQLite
4. build_dedup_metadata — structure and keyword population

Run with: pytest tests/test_dedup.py -v
"""

import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from common.models import Base, Tweet, TweetStatus
from processor.dedup import (
    extract_topic_fingerprint,
    is_duplicate_topic,
    get_recent_topics,
    build_dedup_metadata,
    _jaccard_similarity,
    STOPWORDS,
)


# ==================== Fixtures ====================

@pytest.fixture
def mem_db():
    """Create an in-memory SQLite database with Tweet table."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    session = Session()
    yield session
    session.close()
    Base.metadata.drop_all(engine)


def _make_tweet(source_url, original_text, status, created_at, generation_metadata=None):
    """Helper to build a Tweet instance."""
    return Tweet(
        source_url=source_url,
        original_text=original_text,
        status=status,
        created_at=created_at,
        updated_at=created_at,
        generation_metadata=generation_metadata,
    )


# ==================== extract_topic_fingerprint ====================

def test_extract_topic_fingerprint_basic():
    text = "Bitcoin reaches new all-time high as institutional investors pile in"
    fp = extract_topic_fingerprint(text)
    assert isinstance(fp['keywords'], set)
    assert len(fp['keywords']) > 0
    assert 'bitcoin' in fp['keywords']
    assert isinstance(fp['source_hash'], str)
    assert len(fp['source_hash']) == 12
    assert isinstance(fp['entities'], set)


def test_extract_topic_fingerprint_empty():
    fp = extract_topic_fingerprint("")
    assert fp['keywords'] == set()
    assert len(fp['source_hash']) == 12
    assert fp['entities'] == set()


def test_extract_topic_fingerprint_removes_stopwords():
    text = "The quick brown fox jumps over the lazy dog and it was very good"
    fp = extract_topic_fingerprint(text)
    for sw in ['the', 'and', 'was', 'very', 'over']:
        assert sw not in fp['keywords']
    assert 'quick' in fp['keywords']
    assert 'brown' in fp['keywords']
    assert 'jumps' in fp['keywords']


def test_extract_topic_fingerprint_source_hash():
    text_a = "Bitcoin price surges to new high"
    text_b = "Ethereum price drops to new low"
    fp_a = extract_topic_fingerprint(text_a)
    fp_b = extract_topic_fingerprint(text_b)
    assert fp_a['source_hash'] != fp_b['source_hash']
    fp_a2 = extract_topic_fingerprint(text_a)
    assert fp_a['source_hash'] == fp_a2['source_hash']


# ==================== is_duplicate_topic ====================

def test_is_duplicate_exact_match():
    fp = extract_topic_fingerprint("Bitcoin reaches new all-time high for 2026")
    recent = [{'keywords': list(fp['keywords'])}]
    is_dup, reason = is_duplicate_topic(fp, recent, threshold=0.6)
    assert is_dup is True
    assert reason is not None
    assert 'threshold' in reason


def test_is_duplicate_high_overlap():
    fp = extract_topic_fingerprint("Bitcoin price surges past hundred thousand dollars today")
    recent = [{'keywords': ['bitcoin', 'price', 'surges', 'thousand', 'dollars']}]
    is_dup, reason = is_duplicate_topic(fp, recent, threshold=0.5)
    assert is_dup is True


def test_is_duplicate_low_overlap_not_dup():
    fp = extract_topic_fingerprint("Bitcoin reaches new all-time high")
    recent = [{'keywords': ['ethereum', 'staking', 'rewards', 'validator']}]
    is_dup, reason = is_duplicate_topic(fp, recent, threshold=0.6)
    assert is_dup is False
    assert reason is None


def test_is_duplicate_different_topic():
    fp = extract_topic_fingerprint("Apple launches new MacBook Pro with M4 chip")
    recent = [{'keywords': ['bitcoin', 'cryptocurrency', 'blockchain', 'mining', 'hashrate']}]
    is_dup, reason = is_duplicate_topic(fp, recent, threshold=0.6)
    assert is_dup is False
    assert reason is None


def test_is_duplicate_empty_recent():
    fp = extract_topic_fingerprint("Bitcoin reaches new all-time high")
    is_dup, reason = is_duplicate_topic(fp, [], threshold=0.6)
    assert is_dup is False
    assert reason is None


# ==================== get_recent_topics (DB) ====================

def test_get_recent_topics_with_data(mem_db):
    now = datetime.now(timezone.utc)
    meta = {'keywords': ['bitcoin', 'price'], 'angle': 'news', 'source_hash': 'abc123abc123'}
    tweet = _make_tweet(
        source_url="https://x.com/test/1",
        original_text="Bitcoin hits $100K",
        status=TweetStatus.PROCESSED,
        created_at=now - timedelta(hours=1),
        generation_metadata=meta,
    )
    mem_db.add(tweet)
    mem_db.commit()

    topics = get_recent_topics(mem_db, lookback_hours=72)
    assert len(topics) == 1
    assert topics[0]['keywords'] == ['bitcoin', 'price']


def test_get_recent_topics_respects_lookback(mem_db):
    now = datetime.now(timezone.utc)
    old_meta = {'keywords': ['old', 'topic'], 'angle': 'news'}
    recent_meta = {'keywords': ['recent', 'topic'], 'angle': 'analysis'}

    old_tweet = _make_tweet(
        source_url="https://x.com/test/old",
        original_text="Old news",
        status=TweetStatus.APPROVED,
        created_at=now - timedelta(hours=100),
        generation_metadata=old_meta,
    )
    recent_tweet = _make_tweet(
        source_url="https://x.com/test/recent",
        original_text="Recent news",
        status=TweetStatus.APPROVED,
        created_at=now - timedelta(hours=10),
        generation_metadata=recent_meta,
    )
    mem_db.add_all([old_tweet, recent_tweet])
    mem_db.commit()

    topics = get_recent_topics(mem_db, lookback_hours=72)
    assert len(topics) == 1
    assert topics[0]['keywords'] == ['recent', 'topic']


def test_get_recent_topics_filters_status(mem_db):
    now = datetime.now(timezone.utc)
    pending_meta = {'keywords': ['pending'], 'angle': 'news'}
    approved_meta = {'keywords': ['approved'], 'angle': 'analysis'}

    pending_tweet = _make_tweet(
        source_url="https://x.com/test/pending",
        original_text="Pending tweet",
        status=TweetStatus.PENDING,
        created_at=now - timedelta(hours=1),
        generation_metadata=pending_meta,
    )
    approved_tweet = _make_tweet(
        source_url="https://x.com/test/approved",
        original_text="Approved tweet",
        status=TweetStatus.APPROVED,
        created_at=now - timedelta(hours=1),
        generation_metadata=approved_meta,
    )
    mem_db.add_all([pending_tweet, approved_tweet])
    mem_db.commit()

    # Default statuses exclude PENDING
    topics = get_recent_topics(mem_db, lookback_hours=72)
    assert len(topics) == 1
    assert topics[0]['keywords'] == ['approved']

    # Explicitly request PENDING
    topics_pending = get_recent_topics(mem_db, lookback_hours=72, statuses=[TweetStatus.PENDING])
    assert len(topics_pending) == 1
    assert topics_pending[0]['keywords'] == ['pending']


# ==================== build_dedup_metadata ====================

def test_build_dedup_metadata_structure():
    meta = build_dedup_metadata(
        source_text="Bitcoin price surges to new high",
        angle="news-breaking",
        tweet_type="single",
    )
    assert 'angle' in meta
    assert meta['angle'] == 'news-breaking'
    assert meta['tweet_type'] == 'single'
    assert 'source_hash' in meta
    assert len(meta['source_hash']) == 12
    assert 'keywords' in meta
    assert isinstance(meta['keywords'], list)
    assert 'generated_at' in meta


def test_build_dedup_metadata_keywords():
    meta = build_dedup_metadata(
        source_text="Ethereum staking rewards increase significantly",
        angle="educational",
    )
    assert 'ethereum' in meta['keywords']
    assert 'staking' in meta['keywords']
    assert 'rewards' in meta['keywords']
    assert meta['tweet_type'] is None
    # Keywords should be sorted
    assert meta['keywords'] == sorted(meta['keywords'])


# ==================== Jaccard edge cases ====================

def test_jaccard_edge_cases():
    assert _jaccard_similarity(set(), set()) == 1.0
    assert _jaccard_similarity({'a'}, set()) == 0.0
    assert _jaccard_similarity(set(), {'b'}) == 0.0
    assert _jaccard_similarity({'a', 'b'}, {'a', 'b'}) == 1.0
    assert _jaccard_similarity({'a', 'b'}, {'b', 'c'}) == pytest.approx(1 / 3)
    assert _jaccard_similarity({'a'}, {'b'}) == 0.0
