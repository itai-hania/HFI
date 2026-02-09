"""
Shared test fixtures and configuration.
"""

import sys
from pathlib import Path

# Add src directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import pytest
from common.openai_client import reset_client


@pytest.fixture(autouse=True)
def _reset_openai_client():
    """Reset the shared OpenAI client cache before each test."""
    reset_client()
    yield
    reset_client()
