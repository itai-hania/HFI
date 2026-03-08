"""Tests for settings endpoints."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from common.models import Base


@pytest.fixture
def db_and_client(tmp_path: Path):
    from api.main import app
    from api.dependencies import get_db, require_jwt
    import api.routes.settings as settings_routes

    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestSession = sessionmaker(autocommit=False, autoflush=False, bind=engine, expire_on_commit=False)
    Base.metadata.create_all(bind=engine)
    session = TestSession()

    glossary_path = tmp_path / "glossary.json"
    settings_routes._GLOSSARY_PATH = glossary_path

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


class TestSettingsEndpoints:
    def test_get_glossary(self, db_and_client):
        _, client = db_and_client
        resp = client.get("/api/settings/glossary", headers={"Authorization": "Bearer test"})
        assert resp.status_code == 200
        assert isinstance(resp.json()["terms"], dict)

    def test_update_glossary(self, db_and_client):
        _, client = db_and_client
        resp = client.put(
            "/api/settings/glossary",
            json={"terms": {"fintech": "פינטק", "blockchain": "בלוקצ'יין"}},
            headers={"Authorization": "Bearer test"},
        )
        assert resp.status_code == 200
        assert resp.json()["terms"]["fintech"] == "פינטק"

    def test_get_preferences(self, db_and_client):
        _, client = db_and_client
        resp = client.get("/api/settings/preferences", headers={"Authorization": "Bearer test"})
        assert resp.status_code == 200
        assert isinstance(resp.json()["preferences"], dict)

    def test_update_preferences(self, db_and_client):
        _, client = db_and_client
        resp = client.put(
            "/api/settings/preferences",
            json={
                "preferences": {
                    "default_angle": "news",
                    "posts_per_day": 5,
                    "brief_times": ["08:00", "19:00"],
                }
            },
            headers={"Authorization": "Bearer test"},
        )
        assert resp.status_code == 200
        assert resp.json()["preferences"]["default_angle"] == "news"

    def test_list_style_examples(self, db_and_client):
        _, client = db_and_client
        resp = client.get("/api/settings/style-examples", headers={"Authorization": "Bearer test"})
        assert resp.status_code == 200
        assert "items" in resp.json()

    def test_add_style_example(self, db_and_client):
        _, client = db_and_client
        resp = client.post(
            "/api/settings/style-examples",
            json={
                "content": "דוגמה לסגנון בעברית",
                "topic_tags": ["fintech", "crypto"],
                "source_type": "manual",
            },
            headers={"Authorization": "Bearer test"},
        )
        assert resp.status_code == 201
        assert resp.json()["content"] == "דוגמה לסגנון בעברית"
