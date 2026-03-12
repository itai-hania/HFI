"""Tests for JWT auth endpoints and middleware."""

import os
import time

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from common.models import Base


@pytest.fixture
def client():
    previous_password = os.environ.get("DASHBOARD_PASSWORD")
    previous_jwt_secret = os.environ.get("JWT_SECRET")
    os.environ["DASHBOARD_PASSWORD"] = "testpass123"
    os.environ["JWT_SECRET"] = "test-jwt-secret-key-with-at-least-32-chars"

    from api.main import app
    from api.dependencies import get_db
    from api.routes import auth as auth_routes

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
    auth_routes._failed_attempts.clear()
    auth_routes._failed_attempts_checks = 0
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()
        auth_routes._failed_attempts.clear()
        auth_routes._failed_attempts_checks = 0
        if previous_password is None:
            os.environ.pop("DASHBOARD_PASSWORD", None)
        else:
            os.environ["DASHBOARD_PASSWORD"] = previous_password
        if previous_jwt_secret is None:
            os.environ.pop("JWT_SECRET", None)
        else:
            os.environ["JWT_SECRET"] = previous_jwt_secret


class TestAuthEndpoints:
    def test_login_without_password_is_rejected(self, client):
        resp = client.post("/api/auth/login")
        assert resp.status_code == 401
        assert resp.json()["detail"] == "Invalid credentials"

    def test_login_with_blank_password_is_rejected(self, client):
        resp = client.post("/api/auth/login", json={"password": "   "})
        assert resp.status_code == 401
        assert resp.json()["detail"] == "Invalid credentials"

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

    def test_rejects_expired_token(self, client):
        from api.dependencies import create_access_token

        expired_token = create_access_token(subject="hfi-user", expires_hours=-1)
        resp = client.get(
            "/api/content/drafts",
            headers={"Authorization": f"Bearer {expired_token}"},
        )
        assert resp.status_code == 401
        assert resp.json()["detail"] == "Token expired"

    def test_failed_attempts_cleanup_removes_stale_ips(self, client):
        from api.routes import auth as auth_routes

        stale_ts = time.time() - (auth_routes._LOGIN_WINDOW_SECONDS + 5)
        auth_routes._failed_attempts["stale-ip"] = [stale_ts]
        auth_routes._failed_attempts_checks = auth_routes._FAILED_ATTEMPTS_CLEANUP_EVERY - 1

        resp = client.post("/api/auth/login", json={"password": "wrong"})
        assert resp.status_code == 401
        assert "stale-ip" not in auth_routes._failed_attempts

    def test_production_fails_closed_without_jwt_secret(self, monkeypatch):
        monkeypatch.setenv("DASHBOARD_PASSWORD", "testpass123")
        monkeypatch.setenv("ENVIRONMENT", "production")
        monkeypatch.delenv("JWT_SECRET", raising=False)

        from api.main import app
        from api.routes import auth as auth_routes

        auth_routes._failed_attempts.clear()
        auth_routes._failed_attempts_checks = 0

        with pytest.raises(RuntimeError) as exc:
            with TestClient(app):
                pass
        assert "Missing required api environment variables: JWT_SECRET" in str(exc.value)


def test_rate_limit_middleware_returns_429():
    from api.main import RateLimitMiddleware

    app = FastAPI()
    app.add_middleware(RateLimitMiddleware, max_requests=2, window_seconds=60)

    @app.get("/ping")
    def ping():
        return {"ok": True}

    client = TestClient(app)
    assert client.get("/ping").status_code == 200
    assert client.get("/ping").status_code == 200

    resp = client.get("/ping")
    assert resp.status_code == 429
    assert resp.json()["detail"] == "Too many requests"
