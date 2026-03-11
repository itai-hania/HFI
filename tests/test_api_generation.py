"""Tests for generation and translation APIs."""

import os
from unittest.mock import patch, AsyncMock

import pytest
from fastapi.testclient import TestClient

from common.source_resolver import SourceResolution


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
            "api.routes.generation.resolve_source_input",
            new_callable=AsyncMock,
        ) as mock_resolve, patch(
            "api.routes.generation.asyncio.to_thread",
            new_callable=AsyncMock,
        ) as mock_to_thread:
            mock_resolve.return_value = SourceResolution(
                source_type="text",
                original_text="Fintech is disrupting traditional banking",
                preview_text="Fintech is disrupting traditional banking",
            )
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
            "api.routes.generation.resolve_source_input",
            new_callable=AsyncMock,
        ) as mock_resolve, patch(
            "api.routes.generation.asyncio.to_thread",
            new_callable=AsyncMock,
        ) as mock_to_thread:
            mock_resolve.return_value = SourceResolution(
                source_type="x_url",
                original_text="Original tweet text",
                preview_text="Original tweet text",
                title="Original tweet text",
                canonical_url="https://x.com/fintech_guru/status/123",
                source_domain="x.com",
            )
            mock_to_thread.return_value = "תוכן מתורגם"

            resp = client.post(
                "/api/generation/translate",
                json={"url": "https://x.com/fintech_guru/status/123"},
            )

            assert resp.status_code == 200
            assert resp.json()["hebrew_text"] == "תוכן מתורגם"
            assert resp.json()["source_type"] == "x_url"
            assert resp.json()["canonical_url"] == "https://x.com/fintech_guru/status/123"

    def test_source_resolve_endpoint(self, client):
        with patch(
            "api.routes.generation.resolve_source_input",
            new_callable=AsyncMock,
        ) as mock_resolve:
            mock_resolve.return_value = SourceResolution(
                source_type="article_url",
                original_text="Full article text",
                preview_text="Full article text",
                title="Article title",
                canonical_url="https://example.com/article",
                source_domain="example.com",
            )
            resp = client.post(
                "/api/generation/source/resolve",
                json={"url": "https://example.com/article"},
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["source_type"] == "article_url"
        assert data["canonical_url"] == "https://example.com/article"
