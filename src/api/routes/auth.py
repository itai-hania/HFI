"""JWT authentication routes."""

import os
import secrets
import time
from collections import defaultdict

from fastapi import APIRouter, Depends, HTTPException, Request

from api.dependencies import create_access_token, require_jwt, JWT_EXPIRY_HOURS
from api.schemas.auth import LoginRequest, TokenResponse

router = APIRouter(prefix="/api/auth", tags=["auth"])
_LOGIN_WINDOW_SECONDS = 60
_LOGIN_MAX_ATTEMPTS = 10
_failed_attempts: dict[str, list[float]] = defaultdict(list)


def _check_login_rate_limit(client_ip: str):
    now = time.time()
    attempts = [ts for ts in _failed_attempts[client_ip] if now - ts < _LOGIN_WINDOW_SECONDS]
    _failed_attempts[client_ip] = attempts
    if len(attempts) >= _LOGIN_MAX_ATTEMPTS:
        raise HTTPException(status_code=429, detail="Too many login attempts")


def _record_failed_attempt(client_ip: str):
    _failed_attempts[client_ip].append(time.time())


@router.post("/login", response_model=TokenResponse)
def login(http_request: Request, request: LoginRequest):
    """Authenticate with dashboard password and return JWT token."""
    client_ip = http_request.client.host if http_request.client else "unknown"
    _check_login_rate_limit(client_ip)

    password = os.getenv("DASHBOARD_PASSWORD", "").strip()
    if not password:
        raise HTTPException(status_code=503, detail="Authentication is not configured")

    if not secrets.compare_digest(request.password, password):
        _record_failed_attempt(client_ip)
        raise HTTPException(status_code=401, detail="Invalid credentials")

    _failed_attempts.pop(client_ip, None)
    token = create_access_token(subject="hfi-user")
    return TokenResponse(access_token=token, expires_in=JWT_EXPIRY_HOURS * 3600)


@router.post("/refresh", response_model=TokenResponse)
def refresh(_: str = Depends(require_jwt)):
    """Issue a fresh token using a valid current token."""
    token = create_access_token(subject="hfi-user")
    return TokenResponse(access_token=token, expires_in=JWT_EXPIRY_HOURS * 3600)
