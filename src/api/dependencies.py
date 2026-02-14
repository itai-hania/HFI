"""
FastAPI dependencies for dependency injection.

Provides database sessions, authentication, and other shared dependencies.
"""

import os
import secrets
from typing import Generator
from fastapi import Header, HTTPException
from sqlalchemy.orm import Session

from common.models import SessionLocal


def get_db() -> Generator[Session, None, None]:
    """Dependency injection for database sessions."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def require_api_key(x_api_key: str = Header(default=None, alias="X-API-Key")):
    """Validate X-API-Key header against API_SECRET_KEY env var.

    If API_SECRET_KEY is not set, authentication is disabled (dev mode).
    """
    expected = os.getenv('API_SECRET_KEY')
    if not expected:
        return  # No key configured — skip auth (dev mode)

    if not x_api_key:
        raise HTTPException(status_code=401, detail="Missing X-API-Key header")

    if not secrets.compare_digest(x_api_key.encode('utf-8'), expected.encode('utf-8')):
        raise HTTPException(status_code=401, detail="Invalid API key")
