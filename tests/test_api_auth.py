"""Tests for JWT auth endpoints and middleware."""

import os

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from common.models import Base


@pytest.fixture
def client():
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

    def override_get_db():
        db = TestSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


class TestAuthEndpoints:
    def test_login_success(self, client):
        resp = client.post("/api/auth/login", json={"password": "testpass123"})
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"

    def test_login_wrong_password(self, client):
        resp = client.post("/api/auth/login", json={"password": "wrong"})
        assert resp.status_code == 401

    def test_protected_endpoint_without_token(self, client):
        resp = client.get("/api/content/drafts")
        assert resp.status_code == 401

    def test_protected_endpoint_with_token(self, client):
        login_resp = client.post("/api/auth/login", json={"password": "testpass123"})
        token = login_resp.json()["access_token"]
        resp = client.get(
            "/api/content/drafts",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200

    def test_refresh_token(self, client):
        login_resp = client.post("/api/auth/login", json={"password": "testpass123"})
        token = login_resp.json()["access_token"]
        resp = client.post(
            "/api/auth/refresh",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        assert "access_token" in resp.json()
