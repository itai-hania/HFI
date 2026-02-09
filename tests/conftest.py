"""
Shared test fixtures and configuration.
"""

import pytest
from common.openai_client import reset_client


@pytest.fixture(autouse=True)
def _reset_openai_client():
    """Reset the shared OpenAI client cache before each test."""
    reset_client()
    yield
    reset_client()
