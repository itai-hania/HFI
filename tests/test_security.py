"""
Security hardening tests for HFI.

Tests for:
- Rate limiting (OpenAI calls)
- Media download security
- Database URL masking
- CORS / API security
"""

import os
import time
import json
import secrets
import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path


# ==================== Rate Limiter Tests ====================

class TestRateLimiter:
    """Tests for OpenAI rate limiting."""

    def test_limiter_allows_under_limit(self):
        from common.rate_limiter import RateLimiter
        limiter = RateLimiter(max_calls=10, window_seconds=60)
        assert limiter.check() is True

    def test_limiter_blocks_at_limit(self):
        from common.rate_limiter import RateLimiter
        limiter = RateLimiter(max_calls=3, window_seconds=60)
        for _ in range(3):
            limiter.record()
        assert limiter.check() is False

    def test_limiter_acquire_raises(self):
        from common.rate_limiter import RateLimiter, RateLimitExceeded
        limiter = RateLimiter(max_calls=2, window_seconds=60)
        limiter.acquire()
        limiter.acquire()
        with pytest.raises(RateLimitExceeded):
            limiter.acquire()

    def test_limiter_calls_remaining(self):
        from common.rate_limiter import RateLimiter
        limiter = RateLimiter(max_calls=5, window_seconds=60)
        assert limiter.calls_remaining == 5
        limiter.record()
        assert limiter.calls_remaining == 4

    def test_limiter_calls_made(self):
        from common.rate_limiter import RateLimiter
        limiter = RateLimiter(max_calls=10, window_seconds=60)
        assert limiter.calls_made == 0
        limiter.record()
        limiter.record()
        assert limiter.calls_made == 2

    def test_limiter_window_expiry(self):
        from common.rate_limiter import RateLimiter
        limiter = RateLimiter(max_calls=2, window_seconds=1)
        limiter.record()
        limiter.record()
        assert limiter.check() is False
        # Wait for window to expire
        time.sleep(1.1)
        assert limiter.check() is True

    def test_limiter_env_config(self):
        from common.rate_limiter import RateLimiter
        with patch.dict(os.environ, {'OPENAI_RATE_LIMIT': '50'}):
            limiter = RateLimiter()
            assert limiter.max_calls == 50

    def test_singleton_returns_same(self):
        import common.rate_limiter as rl
        # Reset singleton for test
        rl._limiter = None
        limiter1 = rl.get_rate_limiter()
        limiter2 = rl.get_rate_limiter()
        assert limiter1 is limiter2
        # Clean up
        rl._limiter = None


# ==================== Media Downloader Security Tests ====================

class TestMediaDownloaderSecurity:
    """Tests for media download security features."""

    def test_domain_whitelist_blocks_unknown(self):
        from processor.processor import MediaDownloader
        downloader = MediaDownloader()
        result = downloader.download_media("https://evil.com/malware.exe")
        assert result is None

    def test_domain_whitelist_allows_twimg(self):
        from processor.processor import MediaDownloader
        downloader = MediaDownloader()
        assert downloader._is_allowed_domain("https://pbs.twimg.com/media/test.jpg") is True

    def test_domain_whitelist_allows_video_twimg(self):
        from processor.processor import MediaDownloader
        downloader = MediaDownloader()
        assert downloader._is_allowed_domain("https://video.twimg.com/video.mp4") is True

    def test_domain_whitelist_blocks_evil(self):
        from processor.processor import MediaDownloader
        downloader = MediaDownloader()
        assert downloader._is_allowed_domain("https://evil.com/file") is False

    def test_size_limits_defined(self):
        from processor.processor import MediaDownloader
        assert MediaDownloader.MAX_IMAGE_SIZE == 10 * 1024 * 1024
        assert MediaDownloader.MAX_VIDEO_SIZE == 100 * 1024 * 1024

    def test_extension_whitelist(self):
        from processor.processor import MediaDownloader
        allowed = MediaDownloader.ALLOWED_IMAGE_EXTENSIONS
        assert 'jpg' in allowed
        assert 'png' in allowed
        assert 'gif' in allowed
        assert 'webp' in allowed
        assert 'exe' not in allowed


# ==================== DB URL Logging Tests ====================

class TestDBLogSecurity:
    """Tests for database URL not leaking in logs."""

    def test_db_url_masked_in_health_check(self):
        from common.models import health_check
        with patch('common.models.SessionLocal') as mock_session:
            mock_db = MagicMock()
            mock_db.query.return_value.count.return_value = 0
            mock_db.query.return_value.filter.return_value.count.return_value = 0
            mock_session.return_value = mock_db

            result = health_check()
            if 'database_url' in result:
                assert '***' in result['database_url']
                # Should not contain actual path
                assert 'hfi.db' not in result['database_url']


# ==================== CORS / API Security Tests ====================

class TestAPISecurity:
    """Tests for API security configuration."""

    def test_cors_methods_locked(self):
        """CORS should only allow GET and POST."""
        import importlib
        import api.main
        importlib.reload(api.main)
        app = api.main.app
        for middleware in app.user_middleware:
            if hasattr(middleware, 'kwargs'):
                methods = middleware.kwargs.get('allow_methods', [])
                if methods:
                    assert '*' not in methods

    def test_api_key_dependency_exists(self):
        """require_api_key dependency should exist."""
        from api.dependencies import require_api_key
        assert callable(require_api_key)

    def test_api_key_rejects_missing(self):
        """Missing API key should raise 401 when API_SECRET_KEY is set."""
        from api.dependencies import require_api_key
        from fastapi import HTTPException
        with patch.dict(os.environ, {'API_SECRET_KEY': 'test-secret-key'}):
            with pytest.raises(HTTPException) as exc_info:
                require_api_key(x_api_key=None)
            assert exc_info.value.status_code == 401

    def test_api_key_rejects_invalid(self):
        """Invalid API key should raise 401."""
        from api.dependencies import require_api_key
        from fastapi import HTTPException
        with patch.dict(os.environ, {'API_SECRET_KEY': 'correct-key'}):
            with pytest.raises(HTTPException) as exc_info:
                require_api_key(x_api_key="wrong-key")
            assert exc_info.value.status_code == 401

    def test_api_key_accepts_valid(self):
        """Valid API key should not raise."""
        from api.dependencies import require_api_key
        with patch.dict(os.environ, {'API_SECRET_KEY': 'my-secret'}):
            # Should not raise
            require_api_key(x_api_key="my-secret")

    def test_api_key_skips_when_unset(self):
        """When API_SECRET_KEY is unset, auth should be skipped."""
        from api.dependencies import require_api_key
        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop('API_SECRET_KEY', None)
            # Should not raise
            require_api_key(x_api_key=None)

    def test_api_key_missing_secret_blocks_in_production(self):
        """In production, missing API_SECRET_KEY must fail closed."""
        from api.dependencies import require_api_key
        from fastapi import HTTPException
        with patch.dict(os.environ, {'ENVIRONMENT': 'production'}, clear=True):
            with pytest.raises(HTTPException) as exc_info:
                require_api_key(x_api_key=None)
            assert exc_info.value.status_code == 503

    def test_production_docs_disabled(self):
        """Docs should be disabled in production."""
        with patch.dict(os.environ, {'ENVIRONMENT': 'production'}):
            import importlib
            import api.main
            importlib.reload(api.main)
            app = api.main.app
            assert app.docs_url is None
            assert app.redoc_url is None
            # Clean up
            os.environ.pop('ENVIRONMENT', None)
            importlib.reload(api.main)
