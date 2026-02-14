"""Rate limiter for OpenAI API calls to prevent runaway costs."""

import os
import time
import logging
import threading

logger = logging.getLogger(__name__)

# Default: 100 calls per hour
DEFAULT_RATE_LIMIT = 100
WINDOW_SECONDS = 3600


class RateLimiter:
    """Thread-safe sliding window rate limiter."""

    def __init__(self, max_calls: int = None, window_seconds: int = WINDOW_SECONDS):
        self.max_calls = max_calls or int(os.getenv('OPENAI_RATE_LIMIT', DEFAULT_RATE_LIMIT))
        self.window_seconds = window_seconds
        self._timestamps: list[float] = []
        self._lock = threading.Lock()

    def check(self) -> bool:
        """Check if a call is allowed. Returns True if under limit."""
        with self._lock:
            now = time.time()
            cutoff = now - self.window_seconds
            self._timestamps = [t for t in self._timestamps if t > cutoff]
            return len(self._timestamps) < self.max_calls

    def record(self):
        """Record a call."""
        with self._lock:
            self._timestamps.append(time.time())

    def acquire(self):
        """Check and record. Raises RateLimitExceeded if over limit."""
        if not self.check():
            raise RateLimitExceeded(
                f"OpenAI rate limit exceeded: {self.max_calls} calls per "
                f"{self.window_seconds // 60} minutes. Try again later."
            )
        self.record()

    @property
    def calls_remaining(self) -> int:
        with self._lock:
            now = time.time()
            cutoff = now - self.window_seconds
            recent = sum(1 for t in self._timestamps if t > cutoff)
            return max(0, self.max_calls - recent)

    @property
    def calls_made(self) -> int:
        with self._lock:
            now = time.time()
            cutoff = now - self.window_seconds
            return sum(1 for t in self._timestamps if t > cutoff)


class RateLimitExceeded(Exception):
    """Raised when rate limit is exceeded."""
    pass


# Module-level singleton
_limiter = None
_limiter_lock = threading.Lock()


def get_rate_limiter() -> RateLimiter:
    """Get or create the global rate limiter singleton."""
    global _limiter
    if _limiter is None:
        with _limiter_lock:
            if _limiter is None:
                _limiter = RateLimiter()
                logger.info(f"Rate limiter initialized: {_limiter.max_calls} calls/hour")
    return _limiter
