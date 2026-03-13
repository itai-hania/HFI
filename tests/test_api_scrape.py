"""Tests for scrape and content-from-thread API endpoints."""

import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from common.models import Base, Tweet, TweetStatus


MOCK_THREAD_RESULT = {
    "source_url": "https://x.com/user/status/100",
    "author_handle": "@fintech_guru",
    "author_name": "Fintech Guru",
    "tweet_count": 3,
    "tweets": [
        {"tweet_id": "100", "text": "Thread intro about fintech", "author_handle": "@fintech_guru"},
        {"tweet_id": "101", "text": "Second point on regulation", "author_handle": "@fintech_guru"},
        {"tweet_id": "102", "text": "Final thoughts", "author_handle": "@fintech_guru"},
    ],
    "scraped_at": "2026-03-13T12:00:00",
}

MOCK_TWEET_RESULT = {
    "text": "Breaking: SEC approves new ETF",
    "media_url": "https://pbs.twimg.com/media/photo.jpg",
    "author": "sec_watcher",
    "timestamp": "2026-03-13T10:00:00.000Z",
    "source_url": "https://x.com/sec_watcher/status/999",
    "scraped_at": "2026-03-13T12:00:00",
}

MOCK_TRENDS_RESULT = [
    {"title": "#Bitcoin", "description": "50K tweets", "category": "Finance", "scraped_at": "2026-03-13T12:00:00"},
    {"title": "#Ethereum", "description": "30K tweets", "category": "Finance", "scraped_at": "2026-03-13T12:00:00"},
    {"title": "#Fintech", "description": "20K tweets", "category": "Technology", "scraped_at": "2026-03-13T12:00:00"},
]


@pytest.fixture
def db_and_client():
    os.environ["DASHBOARD_PASSWORD"] = "testpass123"
    os.environ["JWT_SECRET"] = "test-jwt-secret-key-with-at-least-32-chars"

    from api.main import app
    from api.dependencies import get_db, require_jwt

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
    app.dependency_overrides[require_jwt] = lambda: "test-user"
    client = TestClient(app)

    yield shared_session, client

    app.dependency_overrides.clear()
    shared_session.close()


class TestScrapeThread:
    def test_scrape_thread_success(self, db_and_client):
        _, client = db_and_client
        mock_scraper = AsyncMock()
        mock_scraper.fetch_raw_thread.return_value = MOCK_THREAD_RESULT

        with patch("api.routes.scrape.get_scraper", new_callable=AsyncMock, return_value=mock_scraper):
            resp = client.post("/api/scrape/thread", json={"url": "https://x.com/user/status/100"})

        assert resp.status_code == 200
        data = resp.json()
        assert data["source_url"] == "https://x.com/user/status/100"
        assert data["author_handle"] == "@fintech_guru"
        assert data["tweet_count"] == 3
        assert len(data["tweets"]) == 3

    def test_scrape_thread_failure_returns_502(self, db_and_client):
        _, client = db_and_client
        mock_scraper = AsyncMock()
        mock_scraper.fetch_raw_thread.side_effect = Exception("Browser timeout")

        with patch("api.routes.scrape.get_scraper", new_callable=AsyncMock, return_value=mock_scraper):
            resp = client.post("/api/scrape/thread", json={"url": "https://x.com/user/status/100"})

        assert resp.status_code == 502
        assert "Scrape failed" in resp.json()["detail"]

    def test_scrape_thread_requires_auth(self, db_and_client):
        _, client = db_and_client
        from api.main import app
        from api.dependencies import require_jwt

        app.dependency_overrides.pop(require_jwt, None)
        resp = client.post("/api/scrape/thread", json={"url": "https://x.com/user/status/100"})
        assert resp.status_code == 401
        app.dependency_overrides[require_jwt] = lambda: "test-user"

    def test_scrape_thread_invalid_url(self, db_and_client):
        _, client = db_and_client
        resp = client.post("/api/scrape/thread", json={"url": "not-a-url"})
        assert resp.status_code == 422


class TestScrapeTweet:
    def test_scrape_tweet_success(self, db_and_client):
        _, client = db_and_client
        mock_scraper = AsyncMock()
        mock_scraper.get_tweet_content.return_value = MOCK_TWEET_RESULT

        with patch("api.routes.scrape.get_scraper", new_callable=AsyncMock, return_value=mock_scraper):
            resp = client.post("/api/scrape/tweet", json={"url": "https://x.com/sec_watcher/status/999"})

        assert resp.status_code == 200
        data = resp.json()
        assert data["text"] == "Breaking: SEC approves new ETF"
        assert data["author"] == "sec_watcher"
        assert data["media_url"] == "https://pbs.twimg.com/media/photo.jpg"

    def test_scrape_tweet_failure_returns_502(self, db_and_client):
        _, client = db_and_client
        mock_scraper = AsyncMock()
        mock_scraper.get_tweet_content.side_effect = Exception("Element not found")

        with patch("api.routes.scrape.get_scraper", new_callable=AsyncMock, return_value=mock_scraper):
            resp = client.post("/api/scrape/tweet", json={"url": "https://x.com/user/status/100"})

        assert resp.status_code == 502

    def test_scrape_tweet_no_media(self, db_and_client):
        _, client = db_and_client
        result = {**MOCK_TWEET_RESULT, "media_url": None}
        mock_scraper = AsyncMock()
        mock_scraper.get_tweet_content.return_value = result

        with patch("api.routes.scrape.get_scraper", new_callable=AsyncMock, return_value=mock_scraper):
            resp = client.post("/api/scrape/tweet", json={"url": "https://x.com/user/status/100"})

        assert resp.status_code == 200
        assert resp.json()["media_url"] is None


class TestScrapeTrends:
    def test_scrape_trends_success(self, db_and_client):
        _, client = db_and_client
        mock_scraper = AsyncMock()
        mock_scraper.get_trending_topics.return_value = MOCK_TRENDS_RESULT

        with patch("api.routes.scrape.get_scraper", new_callable=AsyncMock, return_value=mock_scraper):
            resp = client.post("/api/scrape/trends", json={"limit": 3})

        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] == 3
        assert len(data["trends"]) == 3
        assert data["trends"][0]["title"] == "#Bitcoin"

    def test_scrape_trends_default_limit(self, db_and_client):
        _, client = db_and_client
        mock_scraper = AsyncMock()
        mock_scraper.get_trending_topics.return_value = MOCK_TRENDS_RESULT

        with patch("api.routes.scrape.get_scraper", new_callable=AsyncMock, return_value=mock_scraper):
            resp = client.post("/api/scrape/trends")

        assert resp.status_code == 200
        mock_scraper.get_trending_topics.assert_called_once_with(limit=10)

    def test_scrape_trends_custom_limit(self, db_and_client):
        _, client = db_and_client
        mock_scraper = AsyncMock()
        mock_scraper.get_trending_topics.return_value = MOCK_TRENDS_RESULT[:2]

        with patch("api.routes.scrape.get_scraper", new_callable=AsyncMock, return_value=mock_scraper):
            resp = client.post("/api/scrape/trends", json={"limit": 2})

        assert resp.status_code == 200
        mock_scraper.get_trending_topics.assert_called_once_with(limit=2)

    def test_scrape_trends_failure_returns_502(self, db_and_client):
        _, client = db_and_client
        mock_scraper = AsyncMock()
        mock_scraper.get_trending_topics.side_effect = Exception("Page crashed")

        with patch("api.routes.scrape.get_scraper", new_callable=AsyncMock, return_value=mock_scraper):
            resp = client.post("/api/scrape/trends", json={"limit": 5})

        assert resp.status_code == 502


class TestContentFromThread:
    def test_consolidated_with_translation(self, db_and_client):
        db, client = db_and_client
        mock_scraper = AsyncMock()
        mock_scraper.fetch_raw_thread.return_value = MOCK_THREAD_RESULT

        mock_translator = MagicMock()
        mock_translator.translate_long_text.return_value = "תוכן מאוחד בעברית על פינטק"

        with patch("api.routes.scrape.get_scraper", new_callable=AsyncMock, return_value=mock_scraper), \
             patch("api.routes.scrape.get_translation_service", return_value=mock_translator):
            resp = client.post("/api/content/from-thread", json={
                "url": "https://x.com/user/status/100",
                "mode": "consolidated",
                "auto_translate": True,
            })

        assert resp.status_code == 200
        data = resp.json()
        assert data["mode"] == "consolidated"
        assert data["tweet_count"] == 3
        assert len(data["saved_items"]) == 1
        assert data["saved_items"][0]["status"] == "processed"

        saved = db.query(Tweet).filter_by(id=data["saved_items"][0]["id"]).first()
        assert saved is not None
        assert saved.content_type == "thread_consolidated"
        assert saved.hebrew_draft == "תוכן מאוחד בעברית על פינטק"
        assert saved.generation_metadata["mode"] == "consolidated"
        assert saved.generation_metadata["tweet_count"] == 3

    def test_consolidated_without_translation(self, db_and_client):
        db, client = db_and_client
        mock_scraper = AsyncMock()
        mock_scraper.fetch_raw_thread.return_value = MOCK_THREAD_RESULT

        with patch("api.routes.scrape.get_scraper", new_callable=AsyncMock, return_value=mock_scraper):
            resp = client.post("/api/content/from-thread", json={
                "url": "https://x.com/user/status/100",
                "mode": "consolidated",
                "auto_translate": False,
            })

        assert resp.status_code == 200
        data = resp.json()
        assert data["saved_items"][0]["status"] == "pending"

        saved = db.query(Tweet).filter_by(id=data["saved_items"][0]["id"]).first()
        assert saved.hebrew_draft is None
        assert saved.original_text == "Thread intro about fintech\n\nSecond point on regulation\n\nFinal thoughts"

    def test_separate_with_translation(self, db_and_client):
        db, client = db_and_client
        mock_scraper = AsyncMock()
        mock_scraper.fetch_raw_thread.return_value = MOCK_THREAD_RESULT

        mock_translator = MagicMock()
        mock_translator.translate_and_rewrite.side_effect = [
            "תרגום ראשון",
            "תרגום שני",
            "תרגום שלישי",
        ]

        with patch("api.routes.scrape.get_scraper", new_callable=AsyncMock, return_value=mock_scraper), \
             patch("api.routes.scrape.get_translation_service", return_value=mock_translator):
            resp = client.post("/api/content/from-thread", json={
                "url": "https://x.com/user/status/100",
                "mode": "separate",
                "auto_translate": True,
            })

        assert resp.status_code == 200
        data = resp.json()
        assert data["mode"] == "separate"
        assert len(data["saved_items"]) == 3
        for item in data["saved_items"]:
            assert item["status"] == "processed"

        tweets = db.query(Tweet).filter(Tweet.content_type == "thread_separate").all()
        assert len(tweets) == 3
        hebrew_drafts = [t.hebrew_draft for t in tweets]
        assert "תרגום ראשון" in hebrew_drafts

    def test_separate_without_translation(self, db_and_client):
        db, client = db_and_client
        mock_scraper = AsyncMock()
        mock_scraper.fetch_raw_thread.return_value = MOCK_THREAD_RESULT

        with patch("api.routes.scrape.get_scraper", new_callable=AsyncMock, return_value=mock_scraper):
            resp = client.post("/api/content/from-thread", json={
                "url": "https://x.com/user/status/100",
                "mode": "separate",
                "auto_translate": False,
            })

        assert resp.status_code == 200
        data = resp.json()
        assert len(data["saved_items"]) == 3
        for item in data["saved_items"]:
            assert item["status"] == "pending"

    def test_content_from_thread_empty_thread(self, db_and_client):
        _, client = db_and_client
        mock_scraper = AsyncMock()
        mock_scraper.fetch_raw_thread.return_value = {
            "source_url": "https://x.com/user/status/100",
            "author_handle": "@user",
            "author_name": "User",
            "tweet_count": 0,
            "tweets": [],
            "scraped_at": "2026-03-13T12:00:00",
        }

        with patch("api.routes.scrape.get_scraper", new_callable=AsyncMock, return_value=mock_scraper):
            resp = client.post("/api/content/from-thread", json={
                "url": "https://x.com/user/status/100",
            })

        assert resp.status_code == 404
        assert "No tweets found" in resp.json()["detail"]

    def test_content_from_thread_scrape_failure(self, db_and_client):
        _, client = db_and_client
        mock_scraper = AsyncMock()
        mock_scraper.fetch_raw_thread.side_effect = Exception("Network error")

        with patch("api.routes.scrape.get_scraper", new_callable=AsyncMock, return_value=mock_scraper):
            resp = client.post("/api/content/from-thread", json={
                "url": "https://x.com/user/status/100",
            })

        assert resp.status_code == 502

    def test_content_from_thread_translation_service_unavailable(self, db_and_client):
        """When TranslationService can't init, content saves as pending."""
        db, client = db_and_client
        mock_scraper = AsyncMock()
        mock_scraper.fetch_raw_thread.return_value = MOCK_THREAD_RESULT

        with patch("api.routes.scrape.get_scraper", new_callable=AsyncMock, return_value=mock_scraper), \
             patch("api.routes.scrape.get_translation_service", side_effect=Exception("No OPENAI_API_KEY")):
            resp = client.post("/api/content/from-thread", json={
                "url": "https://x.com/user/status/100",
                "mode": "consolidated",
                "auto_translate": True,
            })

        assert resp.status_code == 200
        data = resp.json()
        assert data["saved_items"][0]["status"] == "pending"

    def test_content_from_thread_translation_failure_falls_back(self, db_and_client):
        """When translation itself fails, content saves as pending."""
        db, client = db_and_client
        mock_scraper = AsyncMock()
        mock_scraper.fetch_raw_thread.return_value = MOCK_THREAD_RESULT

        mock_translator = MagicMock()
        mock_translator.translate_long_text.side_effect = Exception("API quota exceeded")

        with patch("api.routes.scrape.get_scraper", new_callable=AsyncMock, return_value=mock_scraper), \
             patch("api.routes.scrape.get_translation_service", return_value=mock_translator):
            resp = client.post("/api/content/from-thread", json={
                "url": "https://x.com/user/status/100",
                "mode": "consolidated",
                "auto_translate": True,
            })

        assert resp.status_code == 200
        data = resp.json()
        assert data["saved_items"][0]["status"] == "pending"

    def test_content_from_thread_separate_builds_per_tweet_urls(self, db_and_client):
        """Separate mode builds individual tweet URLs from tweet_id."""
        db, client = db_and_client
        mock_scraper = AsyncMock()
        mock_scraper.fetch_raw_thread.return_value = MOCK_THREAD_RESULT

        with patch("api.routes.scrape.get_scraper", new_callable=AsyncMock, return_value=mock_scraper):
            resp = client.post("/api/content/from-thread", json={
                "url": "https://x.com/user/status/100",
                "mode": "separate",
                "auto_translate": False,
            })

        assert resp.status_code == 200
        tweets = db.query(Tweet).filter(Tweet.content_type == "thread_separate").all()
        urls = sorted(t.source_url for t in tweets)
        assert "https://x.com/user/status/100" in urls
        assert "https://x.com/user/status/101" in urls
        assert "https://x.com/user/status/102" in urls

    def test_content_from_thread_requires_auth(self, db_and_client):
        _, client = db_and_client
        from api.main import app
        from api.dependencies import require_jwt

        app.dependency_overrides.pop(require_jwt, None)
        resp = client.post("/api/content/from-thread", json={
            "url": "https://x.com/user/status/100",
        })
        assert resp.status_code == 401
        app.dependency_overrides[require_jwt] = lambda: "test-user"

    def test_consolidated_duplicate_returns_409(self, db_and_client):
        """Scraping the same thread URL twice in consolidated mode returns 409."""
        db, client = db_and_client
        mock_scraper = AsyncMock()
        mock_scraper.fetch_raw_thread.return_value = MOCK_THREAD_RESULT

        with patch("api.routes.scrape.get_scraper", new_callable=AsyncMock, return_value=mock_scraper):
            resp1 = client.post("/api/content/from-thread", json={
                "url": "https://x.com/user/status/200",
                "mode": "consolidated",
                "auto_translate": False,
            })
            assert resp1.status_code == 200

            resp2 = client.post("/api/content/from-thread", json={
                "url": "https://x.com/user/status/200",
                "mode": "consolidated",
                "auto_translate": False,
            })
            assert resp2.status_code == 409
            assert "already saved" in resp2.json()["detail"]

    def test_separate_duplicate_skips_existing(self, db_and_client):
        """Scraping the same thread twice in separate mode returns existing items."""
        db, client = db_and_client
        mock_scraper = AsyncMock()
        mock_scraper.fetch_raw_thread.return_value = MOCK_THREAD_RESULT

        with patch("api.routes.scrape.get_scraper", new_callable=AsyncMock, return_value=mock_scraper):
            resp1 = client.post("/api/content/from-thread", json={
                "url": "https://x.com/user/status/300",
                "mode": "separate",
                "auto_translate": False,
            })
            assert resp1.status_code == 200
            first_ids = [item["id"] for item in resp1.json()["saved_items"]]

            resp2 = client.post("/api/content/from-thread", json={
                "url": "https://x.com/user/status/300",
                "mode": "separate",
                "auto_translate": False,
            })
            assert resp2.status_code == 200
            second_ids = [item["id"] for item in resp2.json()["saved_items"]]
            assert first_ids == second_ids

    def test_saved_items_include_text_fields(self, db_and_client):
        """saved_items include original_text and hebrew_draft for bot/frontend preview."""
        db, client = db_and_client
        mock_scraper = AsyncMock()
        mock_scraper.fetch_raw_thread.return_value = MOCK_THREAD_RESULT

        mock_translator = MagicMock()
        mock_translator.translate_long_text.return_value = "תוכן בעברית"

        with patch("api.routes.scrape.get_scraper", new_callable=AsyncMock, return_value=mock_scraper), \
             patch("api.routes.scrape.get_translation_service", return_value=mock_translator):
            resp = client.post("/api/content/from-thread", json={
                "url": "https://x.com/user/status/400",
                "mode": "consolidated",
                "auto_translate": True,
            })

        assert resp.status_code == 200
        item = resp.json()["saved_items"][0]
        assert "original_text" in item
        assert "hebrew_draft" in item
        assert item["hebrew_draft"] == "תוכן בעברית"
        assert "fintech" in item["original_text"]
