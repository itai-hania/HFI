"""Tests for inspiration APIs."""

from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from common.models import Base, InspirationPost


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


class TestInspirationEndpoints:
    def test_add_account(self, db_and_client):
        _, client = db_and_client
        resp = client.post(
            "/api/inspiration/accounts",
            json={"username": "fintech_guru", "display_name": "FinTech Guru", "category": "fintech"},
            headers={"Authorization": "Bearer test"},
        )
        assert resp.status_code == 201
        assert resp.json()["username"] == "fintech_guru"

    def test_list_accounts(self, db_and_client):
        _, client = db_and_client
        client.post(
            "/api/inspiration/accounts",
            json={"username": "user1", "display_name": "U1"},
            headers={"Authorization": "Bearer test"},
        )
        client.post(
            "/api/inspiration/accounts",
            json={"username": "user2", "display_name": "U2"},
            headers={"Authorization": "Bearer test"},
        )

        resp = client.get("/api/inspiration/accounts", headers={"Authorization": "Bearer test"})
        assert resp.status_code == 200
        assert len(resp.json()["accounts"]) == 2

    def test_remove_account(self, db_and_client):
        _, client = db_and_client
        create_resp = client.post(
            "/api/inspiration/accounts",
            json={"username": "to_delete", "display_name": "D"},
            headers={"Authorization": "Bearer test"},
        )
        account_id = create_resp.json()["id"]

        resp = client.delete(f"/api/inspiration/accounts/{account_id}", headers={"Authorization": "Bearer test"})
        assert resp.status_code == 204

    def test_search_posts(self, db_and_client):
        _, client = db_and_client
        client.post(
            "/api/inspiration/accounts",
            json={"username": "fintech_guru", "display_name": "FinTech Guru"},
            headers={"Authorization": "Bearer test"},
        )

        with patch("api.routes.inspiration.get_scraper") as mock_get_scraper:
            scraper = mock_get_scraper.return_value
            scraper.search_by_user_engagement = AsyncMock(
                return_value=[
                    {
                        "tweet_id": "111",
                        "text": "Bitcoin ETF explainer",
                        "likes": 250,
                        "retweets": 35,
                        "views": 10000,
                        "url": "https://x.com/a/status/111",
                    }
                ]
            )
            scraper.close = AsyncMock(return_value=None)

            resp = client.post(
                "/api/inspiration/search",
                json={"username": "fintech_guru", "min_likes": 100, "keyword": "bitcoin"},
                headers={"Authorization": "Bearer test"},
            )

        assert resp.status_code == 200
        data = resp.json()
        assert len(data["posts"]) == 1
        assert data["posts"][0]["x_post_id"] == "111"

    def test_search_posts_updates_existing_post_on_upsert(self, db_and_client):
        db, client = db_and_client
        client.post(
            "/api/inspiration/accounts",
            json={"username": "fintech_guru", "display_name": "FinTech Guru"},
            headers={"Authorization": "Bearer test"},
        )

        with patch("api.routes.inspiration.get_scraper") as mock_get_scraper:
            scraper = mock_get_scraper.return_value
            scraper.search_by_user_engagement = AsyncMock(
                return_value=[
                    {
                        "tweet_id": "111",
                        "text": "Original text",
                        "likes": 120,
                        "retweets": 20,
                        "views": 1000,
                        "url": "https://x.com/a/status/111",
                    }
                ]
            )
            scraper.close = AsyncMock(return_value=None)
            first = client.post(
                "/api/inspiration/search",
                json={"username": "fintech_guru", "min_likes": 100, "keyword": "btc"},
                headers={"Authorization": "Bearer test"},
            )
        assert first.status_code == 200

        with patch("api.routes.inspiration.get_scraper") as mock_get_scraper:
            scraper = mock_get_scraper.return_value
            scraper.search_by_user_engagement = AsyncMock(
                return_value=[
                    {
                        "tweet_id": "111",
                        "text": "Updated text",
                        "likes": 560,
                        "retweets": 60,
                        "views": 12000,
                        "url": "https://x.com/a/status/111",
                    }
                ]
            )
            scraper.close = AsyncMock(return_value=None)
            second = client.post(
                "/api/inspiration/search",
                json={"username": "fintech_guru", "min_likes": 100, "keyword": "eth"},
                headers={"Authorization": "Bearer test"},
            )
        assert second.status_code == 200

        rows = db.query(InspirationPost).filter(InspirationPost.x_post_id == "111").all()
        assert len(rows) == 1
        assert rows[0].content == "Updated text"
        assert rows[0].likes == 560
