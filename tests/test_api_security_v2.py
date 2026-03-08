"""Security-focused API tests for v2 endpoints."""

import os

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from common.models import Base


@pytest.fixture
def client_db():
    os.environ["DASHBOARD_PASSWORD"] = "testpass123"
    os.environ["JWT_SECRET"] = "this-is-a-test-jwt-secret-with-at-least-32-chars"

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
    client = TestClient(app)

    login = client.post("/api/auth/login", json={"password": "testpass123"})
    token = login.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    yield client, headers

    app.dependency_overrides.clear()
    session.close()


class TestInputValidation:
    def test_rejects_javascript_source_url(self, client_db):
        client, headers = client_db
        resp = client.post(
            "/api/content",
            json={
                "source_url": "javascript:alert(1)",
                "original_text": "Test",
            },
            headers=headers,
        )
        assert resp.status_code == 422

    def test_rejects_non_http_translate_url(self, client_db):
        client, headers = client_db
        resp = client.post(
            "/api/generation/translate",
            json={"url": "ftp://x.com/user/status/1"},
            headers=headers,
        )
        assert resp.status_code == 422
