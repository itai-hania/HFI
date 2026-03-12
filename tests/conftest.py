"""
Shared test fixtures and configuration.
"""

import os

import pytest
from common.openai_client import reset_client

os.environ.setdefault("DASHBOARD_PASSWORD", "testpass123")
os.environ.setdefault("JWT_SECRET", "test-jwt-secret-key-with-at-least-32-chars")
os.environ.setdefault("API_BASE_URL", "http://localhost:8000")
os.environ.setdefault("API_RATE_LIMIT_MAX_REQUESTS", "10000")


@pytest.fixture(autouse=True)
def _reset_openai_client():
    """Reset the shared OpenAI client cache before each test."""
    reset_client()
    yield
    reset_client()


@pytest.fixture(autouse=True)
def _default_required_env():
    """Provide baseline env required by API and bot startup checks."""
    required_defaults = {
        "DASHBOARD_PASSWORD": "testpass123",
        "JWT_SECRET": "test-jwt-secret-key-with-at-least-32-chars",
        "API_BASE_URL": "http://localhost:8000",
        "API_RATE_LIMIT_MAX_REQUESTS": "10000",
    }
    previous = {key: os.environ.get(key) for key in required_defaults}
    for key, value in required_defaults.items():
        os.environ.setdefault(key, value)
    try:
        yield
    finally:
        for key, old_value in previous.items():
            if old_value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = old_value
