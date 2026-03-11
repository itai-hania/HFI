"""JWT authentication routes."""

import os
import secrets
import time
import logging
from collections import defaultdict

from fastapi import APIRouter, Depends, HTTPException, Request

from api.dependencies import create_access_token, require_jwt, JWT_EXPIRY_HOURS
from api.schemas.auth import LoginRequest, TokenResponse

router = APIRouter(prefix="/api/auth", tags=["auth"])
logger = logging.getLogger(__name__)
_LOGIN_WINDOW_SECONDS = 60
_LOGIN_MAX_ATTEMPTS = 10
_failed_attempts: dict[str, list[float]] = defaultdict(list)
_failed_attempts_checks = 0
_FAILED_ATTEMPTS_CLEANUP_EVERY = 500


def _cleanup_failed_attempts(now: float):
    for ip in list(_failed_attempts.keys()):
        attempts = [ts for ts in _failed_attempts[ip] if now - ts < _LOGIN_WINDOW_SECONDS]
        if attempts:
            _failed_attempts[ip] = attempts
        else:
            _failed_attempts.pop(ip, None)


def _check_login_rate_limit(client_ip: str):
    global _failed_attempts_checks
    now = time.time()
    _failed_attempts_checks += 1
    if _failed_attempts_checks % _FAILED_ATTEMPTS_CLEANUP_EVERY == 0:
        _cleanup_failed_attempts(now)

    attempts = [ts for ts in _failed_attempts[client_ip] if now - ts < _LOGIN_WINDOW_SECONDS]
    if attempts:
        _failed_attempts[client_ip] = attempts
    else:
        _failed_attempts.pop(client_ip, None)
    if len(attempts) >= _LOGIN_MAX_ATTEMPTS:
        raise HTTPException(status_code=429, detail="Too many login attempts")


def _record_failed_attempt(client_ip: str):
    _failed_attempts[client_ip].append(time.time())


@router.post("/login", response_model=TokenResponse)
def login(http_request: Request, request: LoginRequest | None = None):
    """Authenticate and return JWT token.

    Password validation is optional to support passwordless web login.
    Legacy clients can still send password payloads.
    """
    client_ip = http_request.client.host if http_request.client else "unknown"
    provided_password = (request.password or "").strip() if request else ""
    configured_password = os.getenv("DASHBOARD_PASSWORD", "").strip()

    # Keep legacy password-based auth behavior when password is explicitly supplied.
    if provided_password:
        _check_login_rate_limit(client_ip)
        if configured_password and not secrets.compare_digest(
            provided_password.encode("utf-8"),
            configured_password.encode("utf-8"),
        ):
            _record_failed_attempt(client_ip)
            raise HTTPException(status_code=401, detail="Invalid credentials")
        _failed_attempts.pop(client_ip, None)
    elif configured_password:
        logger.warning("⚠️ Passwordless login used while DASHBOARD_PASSWORD is configured")

    token = create_access_token(subject="hfi-user")
    return TokenResponse(access_token=token, expires_in=JWT_EXPIRY_HOURS * 3600)


@router.post("/refresh", response_model=TokenResponse)
def refresh(_: str = Depends(require_jwt)):
    """Issue a fresh token using a valid current token."""
    token = create_access_token(subject="hfi-user")
    return TokenResponse(access_token=token, expires_in=JWT_EXPIRY_HOURS * 3600)
