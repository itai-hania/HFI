"""
Security hardening tests for HFI.

Tests for:
- Authentication (brute force, session expiry, compare_digest)
- URL validation (X URLs, safe URLs, media domains)
- Rate limiting (OpenAI calls)
- Input validation (glossary, batch limits)
"""

import os
import time
import json
import secrets
import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path


class SessionStateDict(dict):
    """Dict that also supports attribute-style access (like Streamlit session_state)."""
    def __getattr__(self, key):
        try:
            return self[key]
        except KeyError:
            raise AttributeError(key)

    def __setattr__(self, key, value):
        self[key] = value

    def __delattr__(self, key):
        del self[key]


# ==================== Auth Tests ====================

class TestAuth:
    """Tests for dashboard authentication hardening."""

    def test_compare_digest_used(self):
        """Verify auth uses secrets.compare_digest (not ==)."""
        import inspect
        from dashboard.auth import check_auth
        source = inspect.getsource(check_auth)
        assert 'secrets.compare_digest' in source
        assert 'entered == password' not in source

    def test_password_required(self):
        """App should refuse to start without DASHBOARD_PASSWORD."""
        from dashboard.auth import _get_password
        with patch.dict(os.environ, {}, clear=True):
            # Remove DASHBOARD_PASSWORD
            os.environ.pop('DASHBOARD_PASSWORD', None)
            assert _get_password() == ""

    def test_brute_force_lockout_constants(self):
        """Verify brute force protection constants are set."""
        from dashboard.auth import MAX_ATTEMPTS, LOCKOUT_WINDOW
        assert MAX_ATTEMPTS == 5
        assert LOCKOUT_WINDOW == 120

    def test_session_expiry_constant(self):
        """Verify session expiry is 4 hours."""
        from dashboard.auth import SESSION_EXPIRY
        assert SESSION_EXPIRY == 4 * 60 * 60

    def test_is_session_expired_true(self):
        """Session should expire after SESSION_EXPIRY."""
        from dashboard.auth import _is_session_expired, SESSION_EXPIRY
        # Mock st.session_state
        with patch('dashboard.auth.st') as mock_st:
            mock_st.session_state = SessionStateDict({'authenticated_at': time.time() - SESSION_EXPIRY - 1})
            assert _is_session_expired() is True

    def test_is_session_expired_false(self):
        """Session should not expire before SESSION_EXPIRY."""
        from dashboard.auth import _is_session_expired
        with patch('dashboard.auth.st') as mock_st:
            mock_st.session_state = SessionStateDict({'authenticated_at': time.time() - 60})
            assert _is_session_expired() is False

    def test_is_session_expired_no_timestamp(self):
        """Missing authenticated_at should count as expired."""
        from dashboard.auth import _is_session_expired
        with patch('dashboard.auth.st') as mock_st:
            mock_st.session_state = SessionStateDict({})
            assert _is_session_expired() is True

    def test_lockout_check_no_attempts(self):
        """No attempts should not trigger lockout."""
        from dashboard.auth import _is_locked_out
        with patch('dashboard.auth.st') as mock_st:
            mock_st.session_state = SessionStateDict({'failed_attempts': []})
            assert _is_locked_out() is False

    def test_lockout_check_under_limit(self):
        """Under MAX_ATTEMPTS should not trigger lockout."""
        from dashboard.auth import _is_locked_out
        with patch('dashboard.auth.st') as mock_st:
            mock_st.session_state = SessionStateDict({'failed_attempts': [time.time()] * 4})
            assert _is_locked_out() is False

    def test_lockout_check_at_limit(self):
        """At MAX_ATTEMPTS should trigger lockout."""
        from dashboard.auth import _is_locked_out, MAX_ATTEMPTS
        with patch('dashboard.auth.st') as mock_st:
            mock_st.session_state = SessionStateDict({'failed_attempts': [time.time()] * MAX_ATTEMPTS})
            assert _is_locked_out() is True

    def test_lockout_old_attempts_expire(self):
        """Old attempts beyond LOCKOUT_WINDOW should be cleaned up."""
        from dashboard.auth import _is_locked_out, LOCKOUT_WINDOW
        with patch('dashboard.auth.st') as mock_st:
            old_time = time.time() - LOCKOUT_WINDOW - 10
            mock_st.session_state = SessionStateDict({'failed_attempts': [old_time] * 10})
            assert _is_locked_out() is False

    def test_record_failed_attempt(self):
        """Recording failed attempt should append timestamp."""
        from dashboard.auth import _record_failed_attempt
        with patch('dashboard.auth.st') as mock_st:
            mock_st.session_state = SessionStateDict({'failed_attempts': []})
            _record_failed_attempt()
            assert len(mock_st.session_state['failed_attempts']) == 1

    def test_lockout_remaining_seconds(self):
        """Lockout remaining should return seconds."""
        from dashboard.auth import _lockout_remaining, LOCKOUT_WINDOW
        with patch('dashboard.auth.st') as mock_st:
            mock_st.session_state = SessionStateDict({'failed_attempts': [time.time()]})
            remaining = _lockout_remaining()
            assert 0 < remaining <= LOCKOUT_WINDOW


# ==================== URL Validation Tests ====================

class TestURLValidation:
    """Tests for URL validators."""

    def test_valid_x_url(self):
        from dashboard.validators import validate_x_url
        valid, err = validate_x_url("https://x.com/user/status/123456")
        assert valid is True
        assert err == ""

    def test_valid_twitter_url(self):
        from dashboard.validators import validate_x_url
        valid, err = validate_x_url("https://twitter.com/user/status/123456")
        assert valid is True

    def test_reject_non_x_domain(self):
        from dashboard.validators import validate_x_url
        valid, err = validate_x_url("https://evil.com/user/status/123")
        assert valid is False
        assert "x.com or twitter.com" in err

    def test_reject_javascript_url(self):
        from dashboard.validators import validate_safe_url
        valid, err = validate_safe_url("javascript:alert(1)")
        assert valid is False
        assert "Dangerous" in err

    def test_reject_data_url(self):
        from dashboard.validators import validate_safe_url
        valid, err = validate_safe_url("data:text/html,<script>alert(1)</script>")
        assert valid is False

    def test_reject_vbscript_url(self):
        from dashboard.validators import validate_safe_url
        valid, err = validate_safe_url("vbscript:msgbox")
        assert valid is False

    def test_valid_https_url(self):
        from dashboard.validators import validate_safe_url
        valid, err = validate_safe_url("https://example.com/article")
        assert valid is True

    def test_reject_empty_url(self):
        from dashboard.validators import validate_x_url
        valid, err = validate_x_url("")
        assert valid is False

    def test_reject_long_url(self):
        from dashboard.validators import validate_x_url
        long_url = "https://x.com/" + "a" * 500
        valid, err = validate_x_url(long_url)
        assert valid is False
        assert "too long" in err

    def test_reject_http_for_x(self):
        from dashboard.validators import validate_x_url
        valid, err = validate_x_url("ftp://x.com/user/status/123")
        assert valid is False

    def test_media_domain_allowed(self):
        from dashboard.validators import validate_media_domain
        valid, err = validate_media_domain("https://pbs.twimg.com/media/test.jpg")
        assert valid is True

    def test_media_domain_subdomain_allowed(self):
        from dashboard.validators import validate_media_domain
        valid, err = validate_media_domain("https://video.twimg.com/amp/video.mp4")
        assert valid is True

    def test_media_domain_blocked(self):
        from dashboard.validators import validate_media_domain
        valid, err = validate_media_domain("https://evil.com/malware.exe")
        assert valid is False
        assert "not allowed" in err


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
