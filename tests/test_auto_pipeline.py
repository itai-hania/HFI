"""
Tests for the AutoPipeline module (two-phase trend-to-post autopilot).

Tests cover:
1. AutoPipeline initialization and lazy property loading
2. Phase A: fetch_and_rank() — fetch, save, rank, summarize
3. Phase B: generate_for_confirmed() — generate, save tweets, batch IDs
4. Edge cases: empty results, duplicate trends, missing trends

Run with: pytest tests/test_auto_pipeline.py -v
"""

import pytest
import json
from unittest.mock import MagicMock, patch
from datetime import datetime, timezone

from common.models import (
    Tweet, Trend, TweetStatus, TrendSource,
    Base, engine, get_db_session,
)


# ==================== Fixtures ====================

@pytest.fixture
def test_db():
    """Create test database with fresh schema."""
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    session = get_db_session()
    yield session
    session.close()
    Base.metadata.drop_all(engine)


@pytest.fixture
def mock_news_scraper():
    """Mock NewsScraper that returns ranked articles."""
    scraper = MagicMock()
    scraper.get_latest_news.return_value = [
        {
            'title': 'Bitcoin Surges Past $100K',
            'description': 'Cryptocurrency rally continues as institutional investors pile in.',
            'source': 'Yahoo Finance',
            'url': 'https://finance.yahoo.com/article/btc-100k',
            'score': 85,
            'category': 'Finance',
            'discovered_at': datetime.utcnow(),
        },
        {
            'title': 'Stripe Launches New Fintech API',
            'description': 'Payment processor expands into embedded finance.',
            'source': 'TechCrunch',
            'url': 'https://techcrunch.com/stripe-api',
            'score': 60,
            'category': 'Tech',
            'discovered_at': datetime.utcnow(),
        },
        {
            'title': 'S&P 500 Hits Record High',
            'description': 'Markets rally as earnings season beats expectations.',
            'source': 'WSJ',
            'url': 'https://wsj.com/sp500-record',
            'score': 72,
            'category': 'Finance',
            'discovered_at': datetime.utcnow(),
        },
    ]
    return scraper


@pytest.fixture
def mock_summary_generator():
    """Mock SummaryGenerator that sets summary on trend."""
    gen = MagicMock()
    def process_trend_side_effect(db, trend_id):
        trend = db.query(Trend).filter_by(id=trend_id).first()
        if trend:
            trend.summary = f"AI summary for: {trend.title}"
            trend.keywords = ['test', 'keyword']
            db.commit()
        return True
    gen.process_trend.side_effect = process_trend_side_effect
    return gen


@pytest.fixture
def mock_content_generator():
    """Mock ContentGenerator that returns Hebrew content."""
    gen = MagicMock()
    gen.generate_post.return_value = [{
        'angle': 'news',
        'label': 'News/Breaking',
        'content': 'ביטקוין חצה את רף 100 אלף דולר. המשקיעים המוסדיים ממשיכים להצטרף.',
        'char_count': 65,
        'is_valid_hebrew': True,
        'source_hash': 'abc123',
    }]
    return gen


@pytest.fixture
def pipeline(mock_news_scraper, mock_summary_generator, mock_content_generator):
    """Create AutoPipeline with all mocked dependencies."""
    from processor.auto_pipeline import AutoPipeline
    return AutoPipeline(
        news_scraper=mock_news_scraper,
        summary_generator=mock_summary_generator,
        content_generator=mock_content_generator,
    )


# ==================== Init Tests ====================

class TestAutoPipelineInit:

    def test_init_with_dependencies(self, mock_news_scraper, mock_summary_generator, mock_content_generator):
        from processor.auto_pipeline import AutoPipeline
        p = AutoPipeline(mock_news_scraper, mock_summary_generator, mock_content_generator)
        assert p.news_scraper is mock_news_scraper
        assert p.summary_generator is mock_summary_generator
        assert p.content_generator is mock_content_generator

    def test_init_without_dependencies(self):
        from processor.auto_pipeline import AutoPipeline
        p = AutoPipeline()
        assert p._news_scraper is None
        assert p._summary_generator is None
        assert p._content_generator is None

    def test_lazy_news_scraper(self):
        from processor.auto_pipeline import AutoPipeline
        p = AutoPipeline()
        with patch('scraper.news_scraper.NewsScraper') as MockNS:
            result = p.news_scraper
            MockNS.assert_called_once()

    def test_lazy_summary_generator(self):
        from processor.auto_pipeline import AutoPipeline
        p = AutoPipeline()
        with patch('processor.summary_generator.SummaryGenerator') as MockSG:
            result = p.summary_generator
            MockSG.assert_called_once()

    def test_lazy_content_generator(self):
        from processor.auto_pipeline import AutoPipeline
        p = AutoPipeline()
        with patch('processor.content_generator.ContentGenerator') as MockCG:
            result = p.content_generator
            MockCG.assert_called_once()


# ==================== Phase A Tests ====================

class TestFetchAndRank:

    def test_basic_fetch_and_rank(self, pipeline, test_db):
        candidates = pipeline.fetch_and_rank(test_db, top_n=3)
        assert len(candidates) <= 3
        assert all('trend_id' in c for c in candidates)
        assert all('title' in c for c in candidates)

    def test_saves_new_trends_to_db(self, pipeline, test_db):
        before = test_db.query(Trend).count()
        pipeline.fetch_and_rank(test_db, top_n=3)
        after = test_db.query(Trend).count()
        assert after > before

    def test_does_not_duplicate_trends(self, pipeline, test_db):
        pipeline.fetch_and_rank(test_db, top_n=3)
        count_first = test_db.query(Trend).count()
        pipeline.fetch_and_rank(test_db, top_n=3)
        count_second = test_db.query(Trend).count()
        assert count_first == count_second

    def test_excludes_already_queued(self, pipeline, test_db):
        # Pre-add a tweet with matching trend_topic
        test_db.add(Tweet(
            source_url='https://example.com/btc',
            original_text='test',
            trend_topic='Bitcoin Surges Past $100K',
            status=TweetStatus.PENDING,
        ))
        test_db.commit()

        candidates = pipeline.fetch_and_rank(test_db, top_n=3)
        titles = [c['title'] for c in candidates]
        assert 'Bitcoin Surges Past $100K' not in titles

    def test_auto_summarize_true(self, pipeline, test_db, mock_summary_generator):
        candidates = pipeline.fetch_and_rank(test_db, top_n=2, auto_summarize=True)
        assert mock_summary_generator.process_trend.called
        for c in candidates:
            assert c.get('summary', '') != ''

    def test_auto_summarize_false(self, pipeline, test_db, mock_summary_generator):
        pipeline.fetch_and_rank(test_db, top_n=2, auto_summarize=False)
        mock_summary_generator.process_trend.assert_not_called()

    def test_respects_top_n(self, pipeline, test_db):
        candidates = pipeline.fetch_and_rank(test_db, top_n=1)
        assert len(candidates) <= 1

    def test_empty_news_returns_empty(self, test_db, mock_summary_generator, mock_content_generator):
        from processor.auto_pipeline import AutoPipeline
        empty_scraper = MagicMock()
        empty_scraper.get_latest_news.return_value = []
        p = AutoPipeline(empty_scraper, mock_summary_generator, mock_content_generator)
        candidates = p.fetch_and_rank(test_db, top_n=3)
        assert candidates == []

    def test_candidate_dict_keys(self, pipeline, test_db):
        candidates = pipeline.fetch_and_rank(test_db, top_n=1)
        if candidates:
            expected_keys = {'trend_id', 'title', 'description', 'summary', 'source', 'url', 'score', 'keywords', 'category'}
            assert expected_keys == set(candidates[0].keys())


# ==================== Phase B Tests ====================

class TestGenerateForConfirmed:

    def _setup_trends(self, db):
        """Helper to create test trends and return their IDs."""
        t1 = Trend(
            title='Bitcoin Surges Past $100K',
            description='Crypto rally continues.',
            source=TrendSource.YAHOO_FINANCE,
            article_url='https://finance.yahoo.com/article/btc-100k',
        )
        t2 = Trend(
            title='Stripe Launches New Fintech API',
            description='Payment processor expands.',
            source=TrendSource.TECHCRUNCH,
            article_url='https://techcrunch.com/stripe-api',
        )
        db.add_all([t1, t2])
        db.commit()
        return [t1.id, t2.id]

    def test_basic_generation(self, pipeline, test_db):
        ids = self._setup_trends(test_db)
        results = pipeline.generate_for_confirmed(test_db, ids[:1], angle='news')
        assert len(results) == 1
        assert results[0]['trend_title'] == 'Bitcoin Surges Past $100K'
        assert results[0]['variants']

    def test_saves_tweet_to_db(self, pipeline, test_db):
        ids = self._setup_trends(test_db)
        results = pipeline.generate_for_confirmed(test_db, ids[:1])
        tweet_id = results[0].get('tweet_id')
        assert tweet_id is not None
        tweet = test_db.query(Tweet).filter_by(id=tweet_id).first()
        assert tweet is not None
        assert tweet.status == TweetStatus.PROCESSED
        assert tweet.content_type == 'generation'

    def test_batch_id_assigned(self, pipeline, test_db):
        ids = self._setup_trends(test_db)
        results = pipeline.generate_for_confirmed(test_db, ids)
        batch_id = results[0].get('batch_id')
        assert batch_id is not None
        assert batch_id.startswith('pipeline_')
        # All results in same batch
        for r in results:
            assert r['batch_id'] == batch_id

    def test_pipeline_batch_id_on_tweet(self, pipeline, test_db):
        ids = self._setup_trends(test_db)
        results = pipeline.generate_for_confirmed(test_db, ids[:1])
        tweet_id = results[0].get('tweet_id')
        tweet = test_db.query(Tweet).filter_by(id=tweet_id).first()
        assert tweet.pipeline_batch_id is not None
        assert tweet.pipeline_batch_id.startswith('pipeline_')

    def test_generation_metadata(self, pipeline, test_db):
        ids = self._setup_trends(test_db)
        results = pipeline.generate_for_confirmed(test_db, ids[:1])
        tweet_id = results[0].get('tweet_id')
        tweet = test_db.query(Tweet).filter_by(id=tweet_id).first()
        meta = json.loads(tweet.generation_metadata) if isinstance(tweet.generation_metadata, str) else tweet.generation_metadata
        assert meta.get('pipeline') is True

    def test_missing_trend_id_skipped(self, pipeline, test_db):
        results = pipeline.generate_for_confirmed(test_db, [99999])
        assert len(results) == 0

    def test_no_duplicate_tweets(self, pipeline, test_db):
        ids = self._setup_trends(test_db)
        pipeline.generate_for_confirmed(test_db, ids[:1])
        count_first = test_db.query(Tweet).count()
        pipeline.generate_for_confirmed(test_db, ids[:1])
        count_second = test_db.query(Tweet).count()
        assert count_first == count_second

    def test_uses_provided_angle(self, pipeline, test_db, mock_content_generator):
        ids = self._setup_trends(test_db)
        pipeline.generate_for_confirmed(test_db, ids[:1], angle='educational')
        call_args = mock_content_generator.generate_post.call_args
        assert call_args[1].get('angles') == ['educational'] or call_args.kwargs.get('angles') == ['educational']

    def test_generation_error_handled(self, test_db, mock_news_scraper, mock_summary_generator):
        from processor.auto_pipeline import AutoPipeline
        bad_gen = MagicMock()
        bad_gen.generate_post.side_effect = Exception("API error")
        p = AutoPipeline(mock_news_scraper, mock_summary_generator, bad_gen)

        t = Trend(
            title='Test Trend',
            description='Test desc.',
            source=TrendSource.MANUAL,
        )
        test_db.add(t)
        test_db.commit()

        results = p.generate_for_confirmed(test_db, [t.id])
        assert len(results) == 1
        assert 'Error' in results[0]['variants'][0]['content']

    def test_multiple_trends_generation(self, pipeline, test_db):
        ids = self._setup_trends(test_db)
        results = pipeline.generate_for_confirmed(test_db, ids)
        assert len(results) == 2
        titles = {r['trend_title'] for r in results}
        assert 'Bitcoin Surges Past $100K' in titles
        assert 'Stripe Launches New Fintech API' in titles


# ==================== DB Schema Tests ====================

class TestNewColumns:

    def test_tweet_pipeline_batch_id_column(self, test_db):
        tweet = Tweet(
            source_url='https://test.com/1',
            original_text='test',
            pipeline_batch_id='pipeline_abc123',
            status=TweetStatus.PROCESSED,
        )
        test_db.add(tweet)
        test_db.commit()
        loaded = test_db.query(Tweet).filter_by(source_url='https://test.com/1').first()
        assert loaded.pipeline_batch_id == 'pipeline_abc123'

    def test_tweet_scheduled_at_column(self, test_db):
        from datetime import datetime, timezone
        scheduled = datetime(2026, 3, 1, 12, 0, tzinfo=timezone.utc)
        tweet = Tweet(
            source_url='https://test.com/2',
            original_text='test',
            scheduled_at=scheduled,
            status=TweetStatus.APPROVED,
        )
        test_db.add(tweet)
        test_db.commit()
        loaded = test_db.query(Tweet).filter_by(source_url='https://test.com/2').first()
        assert loaded.scheduled_at is not None

    def test_tweet_to_dict_includes_new_fields(self, test_db):
        tweet = Tweet(
            source_url='https://test.com/3',
            original_text='test',
            pipeline_batch_id='pipeline_xyz',
            status=TweetStatus.PENDING,
        )
        test_db.add(tweet)
        test_db.commit()
        d = tweet.to_dict()
        assert 'pipeline_batch_id' in d
        assert 'scheduled_at' in d
        assert d['pipeline_batch_id'] == 'pipeline_xyz'
