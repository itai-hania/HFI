"""End-to-end API workflow test for v2 content flow."""

import os
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from common.models import Base


@pytest.fixture
def client_db():
    os.environ["DASHBOARD_PASSWORD"] = "testpass"
    os.environ["JWT_SECRET"] = "test-jwt-secret-with-at-least-32-characters"

    from api.main import app
    from api.dependencies import get_db

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

    yield TestClient(app), session

    app.dependency_overrides.clear()
    session.close()


class TestE2EWorkflow:
    def test_full_content_creation_flow(self, client_db):
        client, _ = client_db

        # 1. Login
        resp = client.post("/api/auth/login", json={"password": "testpass"})
        assert resp.status_code == 200
        token = resp.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # 2. Generate post
        with patch("api.routes.generation.get_content_generator") as mock_generator:
            mock_generator.return_value.generate_post.return_value = [
                {
                    "angle": "news",
                    "label": "News/Breaking",
                    "content": "ה-SEC מאשר מסגרת חדשה ל-Bitcoin ETF.",
                    "char_count": 42,
                    "is_valid_hebrew": True,
                    "quality_score": 91,
                },
                {
                    "angle": "educational",
                    "label": "Educational",
                    "content": "המהלך פותח גישה מוסדית רחבה יותר ל-Bitcoin ETF.",
                    "char_count": 54,
                    "is_valid_hebrew": True,
                    "quality_score": 88,
                },
            ]
            resp = client.post(
                "/api/generation/post",
                json={
                    "source_text": "SEC approves new Bitcoin ETF framework for institutional investors",
                    "num_variants": 2,
                    "angles": ["news", "educational"],
                },
                headers=headers,
            )

        assert resp.status_code == 200
        variants = resp.json()["variants"]
        assert len(variants) == 2

        # 3. Save best variant as draft
        best = variants[0]
        resp = client.post(
            "/api/content",
            json={
                "source_url": "https://example.com/article",
                "original_text": "SEC approves new Bitcoin ETF framework",
                "hebrew_draft": best["content"],
                "content_type": "generation",
            },
            headers=headers,
        )
        assert resp.status_code == 201
        content_id = resp.json()["id"]

        # 4. Approve
        resp = client.patch(
            f"/api/content/{content_id}",
            json={"status": "approved"},
            headers=headers,
        )
        assert resp.status_code == 200

        # 5. Copy
        resp = client.post(f"/api/content/{content_id}/copy", headers=headers)
        assert resp.status_code == 200
        assert resp.json()["copy_count"] == 1

        # 6. Search
        resp = client.get("/api/content/drafts?search=Bitcoin", headers=headers)
        assert resp.status_code == 200
        assert resp.json()["total"] >= 1
