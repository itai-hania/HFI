"""Tests for scraper error classes."""

from scraper.errors import SessionExpiredError


class TestSessionExpiredError:
    def test_is_exception(self):
        err = SessionExpiredError("Session expired")
        assert isinstance(err, Exception)
        assert str(err) == "Session expired"

    def test_default_message(self):
        err = SessionExpiredError()
        assert "session" in str(err).lower()

    def test_has_action_hint(self):
        err = SessionExpiredError("gone")
        assert err.action == "refresh_session"
