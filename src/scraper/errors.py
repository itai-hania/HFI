"""Scraper-specific error classes."""


class SessionExpiredError(Exception):
    """Raised when the X browser session is expired or missing."""

    action = "refresh_session"

    def __init__(self, message: str = "X session expired or missing. Please refresh the session file."):
        super().__init__(message)
