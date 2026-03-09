"""Tests for generation and translation APIs."""

import os
from unittest.mock import patch, AsyncMock

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    os.environ["JWT_SECRET"] = "test-jwt-secret-with-at-least-32-characters"

    from api.main import app
    from api.dependencies import require_jwt

    app.dependency_overrides[require_jwt] = lambda: "test-user"
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


class TestGenerationEndpoints:
    def test_generate_post_returns_variants(self, client):
        with patch("api.routes.generation.get_content_generator") as mock_gen:
            mock_gen.return_value.generate_post.return_value = [
                {
                    "angle": "news",
                    "label": "News/Breaking",
                    "content": "תוכן בעברית",
                    "char_count": 15,
                    "is_valid_hebrew": True,
                    "quality_score": 85,
                },
            ]

            resp = client.post(
                "/api/generation/post",
                json={"source_text": "SEC approves new Bitcoin ETF", "num_variants": 1, "angles": ["news"]},
            )

            assert resp.status_code == 200
            variants = resp.json()["variants"]
            assert len(variants) == 1
            assert variants[0]["angle"] == "news"

    def test_translate_text(self, client):
        with patch("api.routes.generation.get_translation_service") as mock_ts, patch(
            "api.routes.generation.asyncio.to_thread",
            new_callable=AsyncMock,
        ) as mock_to_thread:
            mock_to_thread.return_value = "תרגום בעברית"

            resp = client.post(
                "/api/generation/translate",
                json={"text": "Fintech is disrupting traditional banking"},
            )

            assert resp.status_code == 200
            assert resp.json()["hebrew_text"] == "תרגום בעברית"
            mock_to_thread.assert_awaited_once_with(
                mock_ts.return_value.translate_and_rewrite,
                "Fintech is disrupting traditional banking",
            )

    def test_translate_url(self, client):
        with patch("api.routes.generation.get_translation_service") as mock_ts, patch(
            "api.routes.generation.get_scraper"
        ) as mock_scraper:
            scraper = mock_scraper.return_value
            scraper.ensure_logged_in = AsyncMock(return_value=None)
            scraper.get_tweet_content = AsyncMock(
                return_value={"text": "Original tweet text", "author": "fintech_guru"}
            )
            scraper.close = AsyncMock(return_value=None)

            mock_ts.return_value.translate_and_rewrite.return_value = "תוכן מתורגם"

            resp = client.post(
                "/api/generation/translate",
                json={"url": "https://x.com/fintech_guru/status/123"},
            )

            assert resp.status_code == 200
            assert resp.json()["hebrew_text"] == "תוכן מתורגם"
            assert resp.json()["source_type"] == "url"
