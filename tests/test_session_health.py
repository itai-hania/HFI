"""Tests for scraper session health endpoint."""

import os
import sys
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from api.main import app
import common.models as models_mod
from common.models import Base


@pytest.fixture(scope="function")
def setup_database():
    """Set up in-memory database for testing."""
    os.environ["OPENAI_API_KEY"] = "test-key"

    test_engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestSession = sessionmaker(autocommit=False, autoflush=False, bind=test_engine, expire_on_commit=False)

    orig_engine = models_mod.engine
    orig_session_local = models_mod.SessionLocal
    models_mod.engine = test_engine
    models_mod.SessionLocal = TestSession

    api_deps = sys.modules.get("api.dependencies")
    old_deps_sl = getattr(api_deps, "SessionLocal", None) if api_deps else None
    if api_deps:
        api_deps.SessionLocal = TestSession

    Base.metadata.create_all(bind=test_engine)

    yield

    models_mod.engine = orig_engine
    models_mod.SessionLocal = orig_session_local
    if api_deps:
        api_deps.SessionLocal = old_deps_sl or orig_session_local


@pytest.fixture
def client(setup_database):
    """Create test client."""
    return TestClient(app)


class TestScraperSessionHealth:
    def test_session_missing(self, client):
        with patch("api.main._get_session_path") as mock_path:
            mock_path.return_value = Path("/nonexistent/storage_state.json")
            response = client.get("/health/scraper-session")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "missing"
        assert data["file_exists"] is False
        assert data["age_hours"] is None
        assert "message" in data

    def test_session_valid(self, client, tmp_path):
        session_file = tmp_path / "storage_state.json"
        session_file.write_text('{"cookies": []}')
        with patch("api.main._get_session_path", return_value=session_file):
            response = client.get("/health/scraper-session")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "valid"
        assert data["file_exists"] is True
        assert isinstance(data["age_hours"], float)

    def test_session_warning(self, client, tmp_path):
        session_file = tmp_path / "storage_state.json"
        session_file.write_text('{"cookies": []}')
        five_and_half_days_ago = 5.5 * 24 * 3600
        with patch("api.main._get_session_path", return_value=session_file):
            with patch("api.main.time.time", return_value=os.path.getmtime(session_file) + five_and_half_days_ago):
                response = client.get("/health/scraper-session")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "warning"
        assert data["file_exists"] is True

    def test_session_expired(self, client, tmp_path):
        session_file = tmp_path / "storage_state.json"
        session_file.write_text('{"cookies": []}')
        eight_days_ago = 8 * 24 * 3600
        with patch("api.main._get_session_path", return_value=session_file):
            with patch("api.main.time.time", return_value=os.path.getmtime(session_file) + eight_days_ago):
                response = client.get("/health/scraper-session")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "expired"
        assert data["file_exists"] is True
