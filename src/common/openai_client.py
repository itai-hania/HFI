"""
Shared OpenAI client factory.

Provides a module-level cached OpenAI client to avoid creating
multiple instances across services (ProcessorConfig, ContentGenerator,
SummaryGenerator, StyleManager).
"""

import os
import logging
from typing import Optional

from openai import OpenAI

logger = logging.getLogger(__name__)

_client: Optional[OpenAI] = None


def get_openai_client() -> OpenAI:
    """
    Get or create a shared OpenAI client.

    The client is cached at module level. Thread-safe (OpenAI client uses
    httpx which handles connection pooling internally).
    """
    global _client
    if _client is None:
        api_key = os.getenv('OPENAI_API_KEY')
        if not api_key:
            raise ValueError("OPENAI_API_KEY environment variable is required")
        _client = OpenAI(api_key=api_key)
        logger.info("Initialized shared OpenAI client")
    return _client


def reset_client():
    """Reset the cached client (useful for testing)."""
    global _client
    _client = None
