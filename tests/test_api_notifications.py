"""Tests for notification APIs."""

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
    def test_generate_brief(self, db_and_client):
        _, client = db_and_client
        with patch("api.routes.notifications.NewsScraper.get_latest_news") as mock_news:
            mock_news.return_value = [
                {
                    "title": "SEC approves Bitcoin ETF",
                    "description": "Major approval for institutional investors",
                    "source": "Bloomberg",
                    "source_count": 3,
                }
            ]
            resp = client.post("/api/notifications/brief", headers={"Authorization": "Bearer test"})

        assert resp.status_code == 200
        data = resp.json()
        assert "stories" in data
        assert isinstance(data["stories"], list)

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
        with patch("api.routes.notifications.NewsScraper.get_latest_news") as mock_news:
            mock_news.return_value = [
                {
                    "title": "SEC approves Bitcoin ETF",
                    "description": "Major approval",
                    "source": "Bloomberg",
                    "source_count": 3,
                    "url": "https://bloomberg.com/news/sec-bitcoin-etf",
                }
            ]
            resp = client.post("/api/notifications/brief", headers={"Authorization": "Bearer test"})

        assert resp.status_code == 200
        story = resp.json()["stories"][0]
        assert "source_urls" in story
        assert story["source_urls"] == ["https://bloomberg.com/news/sec-bitcoin-etf"]

    def test_cached_brief_includes_source_urls(self, db_and_client):
        db, client = db_and_client
        with patch("api.routes.notifications.NewsScraper.get_latest_news") as mock_news:
            mock_news.return_value = [
                {
                    "title": "PayPal stablecoin",
                    "description": "PYUSD launch",
                    "source": "TechCrunch",
                    "source_count": 2,
                    "url": "https://techcrunch.com/paypal-stablecoin",
                }
            ]
            first = client.post("/api/notifications/brief", headers={"Authorization": "Bearer test"})
        assert first.status_code == 200

        second = client.post("/api/notifications/brief", headers={"Authorization": "Bearer test"})
        assert second.status_code == 200
        story = second.json()["stories"][0]
        assert story["source_urls"] == ["https://techcrunch.com/paypal-stablecoin"]

    def test_brief_summary_is_english_not_translated(self, db_and_client):
        _, client = db_and_client
        with patch("api.routes.notifications.NewsScraper.get_latest_news") as mock_news:
            mock_news.return_value = [
                {
                    "title": "Stripe raises $6.5B",
                    "description": "Stripe valuation reaches $50B after new round",
                    "source": "WSJ",
                    "source_count": 1,
                    "url": "https://wsj.com/stripe",
                }
            ]
            resp = client.post("/api/notifications/brief", headers={"Authorization": "Bearer test"})

        story = resp.json()["stories"][0]
        assert story["summary"] == "Stripe valuation reaches $50B after new round"
