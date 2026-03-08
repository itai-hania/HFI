"""Tests for content CRUD API."""

import os

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from common.models import Base, Tweet, TweetStatus


@pytest.fixture
def db_and_client():
    os.environ["DASHBOARD_PASSWORD"] = "testpass123"
    os.environ["JWT_SECRET"] = "test-jwt-secret-key-with-at-least-32-chars"

    from api.main import app
    from api.dependencies import get_db

    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestSession = sessionmaker(autocommit=False, autoflush=False, bind=engine, expire_on_commit=False)
    Base.metadata.create_all(bind=engine)

    shared_session = TestSession()

    def override_get_db():
        try:
            yield shared_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)

    yield shared_session, client

    app.dependency_overrides.clear()
    shared_session.close()


class TestContentEndpoints:
    def _auth_header(self, client):
        login = client.post("/api/auth/login", json={"password": "testpass123"})
        token = login.json()["access_token"]
        return {"Authorization": f"Bearer {token}"}

    def test_list_drafts_empty(self, db_and_client):
        _, client = db_and_client
        resp = client.get("/api/content/drafts", headers=self._auth_header(client))
        assert resp.status_code == 200
        assert resp.json()["items"] == []

    def test_create_content(self, db_and_client):
        _, client = db_and_client
        resp = client.post(
            "/api/content",
            json={
                "source_url": "https://x.com/test/status/123",
                "original_text": "Test fintech news",
                "hebrew_draft": "חדשות פינטק",
                "content_type": "translation",
            },
            headers=self._auth_header(client),
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["original_text"] == "Test fintech news"
        assert data["hebrew_draft"] == "חדשות פינטק"

    def test_create_content_respects_explicit_status(self, db_and_client):
        _, client = db_and_client
        resp = client.post(
            "/api/content",
            json={
                "source_url": "https://x.com/test/status/124",
                "original_text": "Scheduled content",
                "hebrew_draft": "תוכן מתוזמן",
                "status": "approved",
                "scheduled_at": "2026-03-10T09:30:00Z",
            },
            headers=self._auth_header(client),
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["status"] == "approved"
        assert data["scheduled_at"] is not None

    def test_create_content_duplicate_source_url_returns_conflict(self, db_and_client):
        _, client = db_and_client
        payload = {
            "source_url": "https://x.com/test/status/125",
            "original_text": "Duplicate source",
        }

        first = client.post("/api/content", json=payload, headers=self._auth_header(client))
        assert first.status_code == 201

        second = client.post("/api/content", json=payload, headers=self._auth_header(client))
        assert second.status_code == 409

    def test_get_content_by_id(self, db_and_client):
        db, client = db_and_client
        tweet = Tweet(source_url="https://x.com/t/1", original_text="Hello", status=TweetStatus.PENDING)
        db.add(tweet)
        db.commit()

        resp = client.get(f"/api/content/{tweet.id}", headers=self._auth_header(client))
        assert resp.status_code == 200
        assert resp.json()["original_text"] == "Hello"

    def test_update_content(self, db_and_client):
        db, client = db_and_client
        tweet = Tweet(source_url="https://x.com/t/2", original_text="Hello", status=TweetStatus.PENDING)
        db.add(tweet)
        db.commit()

        resp = client.patch(
            f"/api/content/{tweet.id}",
            json={"hebrew_draft": "שלום", "status": "processed"},
            headers=self._auth_header(client),
        )
        assert resp.status_code == 200
        assert resp.json()["hebrew_draft"] == "שלום"
        assert resp.json()["status"] == "processed"

    def test_delete_content(self, db_and_client):
        db, client = db_and_client
        tweet = Tweet(source_url="https://x.com/t/3", original_text="Delete me", status=TweetStatus.PENDING)
        db.add(tweet)
        db.commit()

        resp = client.delete(f"/api/content/{tweet.id}", headers=self._auth_header(client))
        assert resp.status_code == 204

    def test_list_by_status(self, db_and_client):
        db, client = db_and_client
        db.add(Tweet(source_url="https://x.com/t/4", original_text="a", status=TweetStatus.PENDING))
        db.add(Tweet(source_url="https://x.com/t/5", original_text="b", status=TweetStatus.APPROVED))
        db.commit()

        resp = client.get("/api/content/drafts?status=approved", headers=self._auth_header(client))
        assert resp.status_code == 200
        assert len(resp.json()["items"]) == 1

    def test_increment_copy_count(self, db_and_client):
        db, client = db_and_client
        tweet = Tweet(source_url="https://x.com/t/6", original_text="Copy me", status=TweetStatus.APPROVED)
        db.add(tweet)
        db.commit()

        resp = client.post(f"/api/content/{tweet.id}/copy", headers=self._auth_header(client))
        assert resp.status_code == 200
        assert resp.json()["copy_count"] == 1
