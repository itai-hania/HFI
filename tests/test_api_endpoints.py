"""
Unit tests for FastAPI endpoints.

Tests trend endpoints, summary generation, and filtering.

Author: HFI Development Team
Last Updated: 2026-02-01
"""

import pytest
from fastapi.testclient import TestClient
import os
import sys
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, Mock

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from api.main import app
import common.models as models_mod
from common.models import Trend, TrendSource, Base, get_db


@pytest.fixture(scope="function")
def setup_database():
    """Set up in-memory database for testing."""
    os.environ['OPENAI_API_KEY'] = 'test-key'

    # Create in-memory engine and session factory
    test_engine = create_engine(
        'sqlite:///:memory:',
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestSession = sessionmaker(autocommit=False, autoflush=False, bind=test_engine, expire_on_commit=False)

    # Swap module-level engine and SessionLocal
    orig_engine = models_mod.engine
    orig_session_local = models_mod.SessionLocal
    models_mod.engine = test_engine
    models_mod.SessionLocal = TestSession

    # Also swap in api.dependencies
    api_deps = sys.modules.get('api.dependencies')
    old_deps_sl = getattr(api_deps, 'SessionLocal', None) if api_deps else None
    if api_deps:
        api_deps.SessionLocal = TestSession

    Base.metadata.create_all(bind=test_engine)

    yield

    # Restore originals
    models_mod.engine = orig_engine
    models_mod.SessionLocal = orig_session_local
    if api_deps:
        api_deps.SessionLocal = old_deps_sl or orig_session_local


@pytest.fixture
def client(setup_database):
    """Create test client."""
    return TestClient(app)


@pytest.fixture
def db_session(setup_database):
    """Provide database session."""
    db = models_mod.SessionLocal()
    # Clean database before each test
    db.query(Trend).delete()
    db.commit()
    yield db
    db.close()


@pytest.fixture
def sample_trends(db_session):
    """Create sample trends for testing."""
    trends = [
        Trend(
            title="SEC Approves Bitcoin ETF",
            description="The SEC has approved Bitcoin ETF applications.",
            article_url="https://example.com/btc-etf",
            source=TrendSource.BLOOMBERG,
            summary="SEC approves Bitcoin ETFs for mainstream investors.",
            keywords=['sec', 'approves', 'bitcoin', 'etf'],
            source_count=2,
            discovered_at=datetime.now(timezone.utc)
        ),
        Trend(
            title="PayPal Launches Crypto Service",
            description="PayPal announces cryptocurrency payment features.",
            article_url="https://example.com/paypal-crypto",
            source=TrendSource.TECHCRUNCH,
            summary="PayPal introduces crypto payments for merchants.",
            keywords=['paypal', 'launches', 'crypto', 'service'],
            source_count=1,
            discovered_at=datetime.now(timezone.utc) - timedelta(days=1)
        ),
        Trend(
            title="AI Fraud Detection Adopted by Banks",
            description="Major banks implement AI for fraud prevention.",
            article_url="https://example.com/ai-fraud",
            source=TrendSource.WSJ,
            # No summary (for testing generation)
            discovered_at=datetime.now(timezone.utc) - timedelta(days=2)
        )
    ]

    for trend in trends:
        db_session.add(trend)
    db_session.commit()

    return trends


class TestRootEndpoints:
    """Test root and health check endpoints."""

    def test_root_endpoint(self, client):
        """Test root endpoint returns API info."""
        response = client.get("/")
        assert response.status_code == 200

        data = response.json()
        assert data['name'] == 'HFI API'
        assert data['version'] == '1.0.0'
        assert data['status'] == 'running'

    def test_health_check(self, client):
        """Test health check endpoint."""
        response = client.get("/health")
        assert response.status_code == 200

        data = response.json()
        assert data['status'] == 'healthy'
        assert 'database' in data


class TestGetTrends:
    """Test GET /api/trends endpoint."""

    def test_get_trends_default(self, client, sample_trends):
        """Test getting trends with default parameters."""
        response = client.get("/api/trends")
        assert response.status_code == 200

        data = response.json()
        assert 'trends' in data
        assert 'total' in data
        assert 'page' in data
        assert 'per_page' in data
        assert 'total_pages' in data

        assert len(data['trends']) == 3
        assert data['total'] == 3
        assert data['page'] == 1
        assert data['per_page'] == 12

    def test_get_trends_with_pagination(self, client, sample_trends):
        """Test pagination parameters."""
        response = client.get("/api/trends?page=1&limit=2")
        assert response.status_code == 200

        data = response.json()
        assert len(data['trends']) == 2
        assert data['per_page'] == 2
        assert data['total'] == 3
        assert data['total_pages'] == 2

    def test_get_trends_filter_by_source(self, client, sample_trends):
        """Test filtering by source."""
        response = client.get("/api/trends?source=Bloomberg")
        assert response.status_code == 200

        data = response.json()
        assert len(data['trends']) == 1
        assert data['trends'][0]['source'] == 'Bloomberg'

    def test_get_trends_filter_by_invalid_source(self, client, sample_trends):
        """Test filtering by invalid source returns error."""
        response = client.get("/api/trends?source=InvalidSource")
        assert response.status_code == 400

    def test_get_trends_filter_has_summary(self, client, sample_trends):
        """Test filtering trends with summaries."""
        response = client.get("/api/trends?has_summary=true")
        assert response.status_code == 200

        data = response.json()
        assert len(data['trends']) == 2  # Only 2 have summaries

        for trend in data['trends']:
            assert trend['summary'] is not None

    def test_get_trends_filter_no_summary(self, client, sample_trends):
        """Test filtering trends without summaries."""
        response = client.get("/api/trends?has_summary=false")
        assert response.status_code == 200

        data = response.json()
        assert len(data['trends']) == 1  # Only 1 without summary

        for trend in data['trends']:
            assert trend['summary'] is None

    def test_get_trends_sort_order(self, client, sample_trends):
        """Test trends are sorted by discovered_at desc."""
        response = client.get("/api/trends")
        assert response.status_code == 200

        data = response.json()
        trends = data['trends']

        # Should be sorted newest first
        for i in range(len(trends) - 1):
            date1 = datetime.fromisoformat(trends[i]['discovered_at'])
            date2 = datetime.fromisoformat(trends[i + 1]['discovered_at'])
            assert date1 >= date2


class TestGetTrendDetail:
    """Test GET /api/trends/{trend_id} endpoint."""

    def test_get_trend_detail(self, client, sample_trends):
        """Test getting single trend details."""
        trend_id = sample_trends[0].id

        response = client.get(f"/api/trends/{trend_id}")
        assert response.status_code == 200

        data = response.json()
        assert data['id'] == trend_id
        assert data['title'] == sample_trends[0].title
        assert data['summary'] == sample_trends[0].summary
        assert data['keywords'] == sample_trends[0].keywords

    def test_get_trend_detail_not_found(self, client):
        """Test getting non-existent trend returns 404."""
        response = client.get("/api/trends/99999")
        assert response.status_code == 404


class TestGetTrendsStats:
    """Test GET /api/trends/stats/summary endpoint."""

    def test_get_trends_stats(self, client, sample_trends):
        """Test getting trend statistics."""
        response = client.get("/api/trends/stats/summary")
        assert response.status_code == 200

        data = response.json()
        assert data['total'] == 3
        assert data['with_summaries'] == 2
        assert data['without_summaries'] == 1
        assert 'by_source' in data
        assert data['by_source']['Bloomberg'] == 1
        assert data['by_source']['TechCrunch'] == 1
        assert data['by_source']['WSJ'] == 1


class TestGenerateSummary:
    """Test POST /api/trends/{trend_id}/generate-summary endpoint."""

    @patch('processor.summary_generator.get_openai_client')
    def test_generate_summary_success(self, mock_openai, client, sample_trends, db_session):
        """Test successful summary generation."""
        # Mock OpenAI response
        mock_client = Mock()
        mock_response = Mock()
        mock_response.choices = [Mock(message=Mock(content="AI generated summary."))]
        mock_client.chat.completions.create.return_value = mock_response
        mock_openai.return_value = mock_client

        # Get trend without summary
        trend = sample_trends[2]  # AI Fraud Detection (no summary)

        response = client.post(f"/api/trends/{trend.id}/generate-summary")
        assert response.status_code == 200

        data = response.json()
        assert data['trend_id'] == trend.id
        assert data['summary'] is not None
        assert isinstance(data['keywords'], list)
        assert len(data['keywords']) >= 2  # Should extract keywords from trend title
        assert data['source_count'] >= 1

    @patch('processor.summary_generator.get_openai_client')
    def test_generate_summary_already_exists(self, mock_openai, client, sample_trends):
        """Test generating summary for trend that already has one."""
        trend = sample_trends[0]  # Has summary

        response = client.post(f"/api/trends/{trend.id}/generate-summary")
        assert response.status_code == 400
        assert 'already has a summary' in response.json()['detail']

    @patch('processor.summary_generator.get_openai_client')
    def test_generate_summary_force_regenerate(self, mock_openai, client, sample_trends):
        """Test forcing summary regeneration."""
        mock_client = Mock()
        mock_response = Mock()
        mock_response.choices = [Mock(message=Mock(content="New summary."))]
        mock_client.chat.completions.create.return_value = mock_response
        mock_openai.return_value = mock_client

        trend = sample_trends[0]  # Has summary

        response = client.post(
            f"/api/trends/{trend.id}/generate-summary",
            json={"force": True}
        )
        assert response.status_code == 200

        data = response.json()
        assert data['summary'] is not None

    def test_generate_summary_not_found(self, client):
        """Test generating summary for non-existent trend."""
        response = client.post("/api/trends/99999/generate-summary")
        assert response.status_code == 404


class TestGenerateSummariesBulk:
    """Test POST /api/trends/generate-summaries endpoint."""

    @patch('processor.summary_generator.get_openai_client')
    def test_generate_summaries_bulk(self, mock_openai, client, sample_trends):
        """Test bulk summary generation."""
        mock_client = Mock()
        mock_response = Mock()
        mock_response.choices = [Mock(message=Mock(content="Bulk summary."))]
        mock_client.chat.completions.create.return_value = mock_response
        mock_openai.return_value = mock_client

        response = client.post("/api/trends/generate-summaries")
        assert response.status_code == 200

        data = response.json()
        assert 'success' in data
        assert 'failed' in data
        assert 'skipped' in data

        # Should process only 1 trend (the one without summary)
        assert data['success'] == 1

    @patch('processor.summary_generator.get_openai_client')
    def test_generate_summaries_bulk_with_limit(self, mock_openai, client, db_session):
        """Test bulk generation with limit."""
        mock_client = Mock()
        mock_response = Mock()
        mock_response.choices = [Mock(message=Mock(content="Bulk summary."))]
        mock_client.chat.completions.create.return_value = mock_response
        mock_openai.return_value = mock_client

        # Create multiple trends without summaries
        for i in range(5):
            trend = Trend(
                title=f"Test Trend {i}",
                source=TrendSource.BLOOMBERG
            )
            db_session.add(trend)
        db_session.commit()

        response = client.post("/api/trends/generate-summaries?limit=2")
        assert response.status_code == 200

        data = response.json()
        assert data['success'] == 2


class TestDeleteSummary:
    """Test DELETE /api/trends/{trend_id}/summary endpoint."""

    def test_delete_summary(self, client, sample_trends, db_session):
        """Test deleting a summary."""
        trend = sample_trends[0]  # Has summary

        response = client.delete(f"/api/trends/{trend.id}/summary")
        assert response.status_code == 200

        # Verify summary was deleted
        db_session.refresh(trend)
        assert trend.summary is None
        assert trend.keywords is None

    def test_delete_summary_not_found(self, client):
        """Test deleting summary for non-existent trend."""
        response = client.delete("/api/trends/99999/summary")
        assert response.status_code == 404

    def test_delete_summary_no_summary(self, client, sample_trends):
        """Test deleting summary that doesn't exist."""
        trend = sample_trends[2]  # No summary

        response = client.delete(f"/api/trends/{trend.id}/summary")
        assert response.status_code == 400
        assert 'does not have a summary' in response.json()['detail']


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
