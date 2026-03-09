"""
FastAPI dependencies for dependency injection.

Provides database sessions, authentication, and other shared dependencies.
"""

import os
import secrets
import logging
from datetime import datetime, timedelta, timezone
from typing import Generator, Any
from fastapi import Header, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
import jwt

from common.models import SessionLocal

JWT_ALGORITHM = "HS256"
JWT_EXPIRY_HOURS = 24
_security = HTTPBearer(auto_error=False)
logger = logging.getLogger(__name__)
_DEV_JWT_SECRET = secrets.token_urlsafe(48)


def _is_production() -> bool:
    """Check if API is running in production mode."""
    return os.getenv('ENVIRONMENT', '').strip().lower() in {'production', 'prod'}


def _jwt_secret() -> str:
    """
    Resolve JWT secret with secure production behavior.

    Production fails closed when JWT_SECRET is missing.
    Development falls back to an explicit local-only default.
    """
    secret = os.getenv("JWT_SECRET", "").strip()
    if secret:
        if _is_production() and len(secret) < 32:
            raise HTTPException(status_code=503, detail="JWT_SECRET must be at least 32 characters")
        if len(secret) < 32:
            logger.warning("JWT_SECRET is shorter than recommended minimum (32 chars)")
        return secret
    if _is_production():
        raise HTTPException(status_code=503, detail="JWT authentication is not configured")
    return _DEV_JWT_SECRET


def get_db() -> Generator[Session, None, None]:
    """Dependency injection for database sessions."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def require_api_key(x_api_key: str = Header(default=None, alias="X-API-Key")):
    """Validate X-API-Key header against API_SECRET_KEY env var.

    Dev mode: if API_SECRET_KEY is unset, auth is skipped.
    Production: API_SECRET_KEY is required (fail closed).
    """
    expected = os.getenv('API_SECRET_KEY')
    if not expected:
        if _is_production():
            raise HTTPException(status_code=503, detail="API authentication is not configured")
        return  # No key configured — skip auth in non-production mode.

    if not x_api_key:
        raise HTTPException(status_code=401, detail="Missing X-API-Key header")

    if not secrets.compare_digest(x_api_key.encode('utf-8'), expected.encode('utf-8')):
        raise HTTPException(status_code=401, detail="Invalid API key")


def create_access_token(subject: str = "user", expires_hours: int = JWT_EXPIRY_HOURS) -> str:
    """Create JWT access token for API authentication."""
    now = datetime.now(timezone.utc)
    payload = {
        "sub": subject,
        "iat": now,
        "exp": now + timedelta(hours=expires_hours),
    }
    return jwt.encode(payload, _jwt_secret(), algorithm=JWT_ALGORITHM)


def decode_access_token(token: str) -> dict[str, Any]:
    """Decode and validate JWT token."""
    try:
        return jwt.decode(token, _jwt_secret(), algorithms=[JWT_ALGORITHM])
    except jwt.ExpiredSignatureError as exc:
        raise HTTPException(status_code=401, detail="Token expired") from exc
    except jwt.InvalidTokenError as exc:
        raise HTTPException(status_code=401, detail="Invalid token") from exc


def require_jwt(credentials: HTTPAuthorizationCredentials = Depends(_security)) -> str:
    """Validate bearer token and return subject."""
    if not credentials or credentials.scheme.lower() != "bearer":
        raise HTTPException(status_code=401, detail="Missing bearer token")

    payload = decode_access_token(credentials.credentials)
    subject = payload.get("sub")
    if not subject:
        raise HTTPException(status_code=401, detail="Invalid token payload")
    return str(subject)
