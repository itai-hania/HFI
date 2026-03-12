"""Tests for notification APIs."""

from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from common.models import Base, Notification


@pytest.fixture
def db_and_client():
    from api.main import app
    from api.dependencies import get_db, require_jwt

    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestSession = sessionmaker(autocommit=False, autoflush=False, bind=engine, expire_on_commit=False)
    Base.metadata.create_all(bind=engine)
    session = TestSession()

    def override_get_db():
        try:
            yield session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[require_jwt] = lambda: "test-user"

    yield session, TestClient(app)

    app.dependency_overrides.clear()
    session.close()


class TestNotificationEndpoints:
    def test_latest_brief_404_when_empty(self, db_and_client):
        _, client = db_and_client
        resp = client.get("/api/notifications/brief/latest", headers={"Authorization": "Bearer test"})
        assert resp.status_code == 404

    def test_generate_brief(self, db_and_client):
        _, client = db_and_client
        published_at = datetime.now(timezone.utc)
        with patch("api.routes.notifications.NewsScraper.get_brief_news") as mock_news:
            mock_news.return_value = [
                {
                    "title": "SEC approves Bitcoin ETF",
                    "description": "Major approval for institutional investors",
                    "source": "Bloomberg",
                    "sources": ["Bloomberg", "WSJ"],
                    "source_urls": [
                        "https://bloomberg.com/news/sec-bitcoin-etf",
                        "https://wsj.com/markets/sec-bitcoin-etf",
                    ],
                    "source_count": 3,
                    "published_at": published_at,
                    "relevance_score": 91,
                }
            ]
            resp = client.post("/api/notifications/brief", headers={"Authorization": "Bearer test"})

        assert resp.status_code == 200
        data = resp.json()
        assert "stories" in data
        assert isinstance(data["stories"], list)
        assert data["stories"][0]["published_at"] is not None
        assert data["stories"][0]["relevance_score"] == 91

    def test_get_pending_alerts(self, db_and_client):
        db, client = db_and_client
        db.add(Notification(type="alert", content={"title": "Alert 1"}, delivered=False))
        db.add(Notification(type="alert", content={"title": "Alert 2"}, delivered=True))
        db.commit()

        resp = client.get("/api/notifications/alerts?delivered=false", headers={"Authorization": "Bearer test"})
        assert resp.status_code == 200
        assert len(resp.json()["alerts"]) == 1

    def test_mark_alert_delivered(self, db_and_client):
        db, client = db_and_client
        notif = Notification(type="alert", content={"title": "test"}, delivered=False)
        db.add(notif)
        db.commit()

        resp = client.patch(f"/api/notifications/{notif.id}/delivered", headers={"Authorization": "Bearer test"})
        assert resp.status_code == 200
        assert resp.json()["delivered"] is True

    def test_brief_includes_source_urls(self, db_and_client):
        _, client = db_and_client
        with patch("api.routes.notifications.NewsScraper.get_brief_news") as mock_news:
            mock_news.return_value = [
                {
                    "title": "SEC approves Bitcoin ETF",
                    "description": "Major approval",
                    "source": "Bloomberg",
                    "sources": ["Bloomberg"],
                    "source_count": 3,
                    "source_urls": ["https://bloomberg.com/news/sec-bitcoin-etf"],
                }
            ]
            resp = client.post("/api/notifications/brief", headers={"Authorization": "Bearer test"})

        assert resp.status_code == 200
        story = resp.json()["stories"][0]
        assert "source_urls" in story
        assert story["source_urls"] == ["https://bloomberg.com/news/sec-bitcoin-etf"]

    def test_cached_brief_includes_source_urls(self, db_and_client):
        db, client = db_and_client
        with patch("api.routes.notifications.NewsScraper.get_brief_news") as mock_news:
            mock_news.return_value = [
                {
                    "title": "PayPal stablecoin",
                    "description": "PYUSD launch",
                    "source": "TechCrunch",
                    "sources": ["TechCrunch"],
                    "source_count": 2,
                    "source_urls": ["https://techcrunch.com/paypal-stablecoin"],
                    "published_at": datetime.now(timezone.utc).isoformat(),
                    "relevance_score": 77,
                }
            ]
            first = client.post("/api/notifications/brief", headers={"Authorization": "Bearer test"})
        assert first.status_code == 200

        second = client.post("/api/notifications/brief", headers={"Authorization": "Bearer test"})
        assert second.status_code == 200
        story = second.json()["stories"][0]
        assert story["source_urls"] == ["https://techcrunch.com/paypal-stablecoin"]
        assert story["published_at"] is not None
        assert story["relevance_score"] == 77

    def test_brief_summary_is_english_not_translated(self, db_and_client):
        _, client = db_and_client
        with patch("api.routes.notifications.NewsScraper.get_brief_news") as mock_news:
            mock_news.return_value = [
                {
                    "title": "Stripe raises $6.5B",
                    "description": "Stripe valuation reaches $50B after new round",
                    "source": "WSJ",
                    "sources": ["WSJ"],
                    "source_count": 1,
                    "source_urls": ["https://wsj.com/stripe"],
                }
            ]
            resp = client.post("/api/notifications/brief", headers={"Authorization": "Bearer test"})

        story = resp.json()["stories"][0]
        assert story["summary"] == "Stripe valuation reaches $50B after new round"

    def test_brief_can_return_less_than_target_count(self, db_and_client):
        _, client = db_and_client
        with patch("api.routes.notifications.NewsScraper.get_brief_news") as mock_news:
            mock_news.return_value = [
                {
                    "title": "Only fresh story #1",
                    "description": "Fresh content",
                    "source": "Bloomberg",
                    "sources": ["Bloomberg"],
                    "source_urls": ["https://bloomberg.com/only-1"],
                    "source_count": 1,
                    "published_at": datetime.now(timezone.utc).isoformat(),
                    "relevance_score": 60,
                },
                {
                    "title": "Only fresh story #2",
                    "description": "Fresh content",
                    "source": "MarketWatch",
                    "sources": ["MarketWatch"],
                    "source_urls": ["https://marketwatch.com/only-2"],
                    "source_count": 1,
                    "published_at": datetime.now(timezone.utc).isoformat(),
                    "relevance_score": 58,
                },
            ]
            resp = client.post("/api/notifications/brief", headers={"Authorization": "Bearer test"})

        assert resp.status_code == 200
        assert len(resp.json()["stories"]) == 2

    def test_route_preserves_scraper_ranking_multi_source_over_single_source(self, db_and_client):
        _, client = db_and_client
        now = datetime.now(timezone.utc)
        with patch("api.routes.notifications.NewsScraper.get_brief_news") as mock_news:
            mock_news.return_value = [
                {
                    "title": "Cross-source ETF move",
                    "description": "Seen across multiple outlets",
                    "source": "Bloomberg",
                    "sources": ["Bloomberg", "Yahoo Finance", "MarketWatch"],
                    "source_urls": [
                        "https://bloomberg.com/etf",
                        "https://finance.yahoo.com/etf",
                        "https://marketwatch.com/etf",
                    ],
                    "source_count": 3,
                    "published_at": now.isoformat(),
                    "relevance_score": 95,
                },
                {
                    "title": "Single-source niche story",
                    "description": "Only one source",
                    "source": "TechCrunch",
                    "sources": ["TechCrunch"],
                    "source_urls": ["https://techcrunch.com/niche"],
                    "source_count": 1,
                    "published_at": (now - timedelta(hours=2)).isoformat(),
                    "relevance_score": 52,
                },
            ]
            resp = client.post("/api/notifications/brief", headers={"Authorization": "Bearer test"})

        assert resp.status_code == 200
        data = resp.json()["stories"]
        assert data[0]["title"] == "Cross-source ETF move"
        assert data[0]["relevance_score"] > data[1]["relevance_score"]

    def test_cache_backfills_missing_new_fields_with_defaults(self, db_and_client):
        db, client = db_and_client
        now = datetime.now(timezone.utc)
        db.add(
            Notification(
                type="brief",
                content={
                    "stories": [
                        {
                            "title": "Legacy cached story",
                            "summary": "summary",
                            "sources": ["Bloomberg"],
                            "source_urls": ["https://bloomberg.com/legacy"],
                            "source_count": 1,
                        }
                    ]
                },
                delivered=False,
                created_at=now,
            )
        )
        db.commit()

        with patch("api.routes.notifications.NewsScraper.get_brief_news") as mock_news:
            resp = client.post("/api/notifications/brief", headers={"Authorization": "Bearer test"})

        assert resp.status_code == 200
        story = resp.json()["stories"][0]
        assert story["title"] == "Legacy cached story"
        assert story["published_at"] is None
        assert story["relevance_score"] == 0
        mock_news.assert_not_called()

    def test_empty_cached_brief_regenerates_instead_of_returning_404(self, db_and_client):
        db, client = db_and_client
        now = datetime.now(timezone.utc)
        db.add(
            Notification(
                type="brief",
                content={"stories": []},
                delivered=False,
                created_at=now,
            )
        )
        db.commit()

        with patch("api.routes.notifications.NewsScraper.get_brief_news") as mock_news:
            mock_news.return_value = [
                {
                    "title": "Fresh fallback story",
                    "description": "Generated after empty cache",
                    "source": "Bloomberg",
                    "sources": ["Bloomberg"],
                    "source_urls": ["https://bloomberg.com/fresh-fallback"],
                    "source_count": 1,
                }
            ]
            resp = client.post("/api/notifications/brief", headers={"Authorization": "Bearer test"})

        assert resp.status_code == 200
        assert resp.json()["stories"][0]["title"] == "Fresh fallback story"
        mock_news.assert_called_once()

    def test_latest_brief_returns_persisted_payload(self, db_and_client):
        db, client = db_and_client
        db.add(
            Notification(
                type="brief",
                content={
                    "stories": [
                        {
                            "title": "Latest cached story",
                            "summary": "cached summary",
                            "sources": ["Bloomberg"],
                            "source_urls": ["https://bloomberg.com/latest"],
                            "source_count": 1,
                        }
                    ]
                },
                delivered=False,
                created_at=datetime.now(timezone.utc),
            )
        )
        db.commit()

        resp = client.get("/api/notifications/brief/latest", headers={"Authorization": "Bearer test"})
        assert resp.status_code == 200
        assert resp.json()["stories"][0]["title"] == "Latest cached story"
