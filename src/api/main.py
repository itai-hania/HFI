"""
FastAPI main application for HFI.

Provides REST API endpoints for the Next.js frontend.
"""

import os
import time
import time as _time
import logging
from collections import defaultdict
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from common.env_utils import ensure_no_duplicate_env_keys, require_env_vars
from api.routes import (
    trends,
    summaries,
    auth,
    content,
    generation,
    inspiration,
    settings,
    notifications,
)

logger = logging.getLogger(__name__)

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_DOTENV_PATH = _PROJECT_ROOT / ".env"
API_REQUIRED_ENV_VARS = ("DASHBOARD_PASSWORD", "JWT_SECRET")
PRODUCTION_REQUIRED_ENV_VARS = ("APP_VERSION", "CORS_ORIGINS")

load_dotenv(_DOTENV_PATH)


def validate_api_startup_env() -> None:
    """Fail-fast API runtime validation."""
    if not os.getenv("PYTEST_CURRENT_TEST"):
        ensure_no_duplicate_env_keys(_DOTENV_PATH)
    require_env_vars(API_REQUIRED_ENV_VARS, scope="api")
    if IS_PRODUCTION:
        require_env_vars(PRODUCTION_REQUIRED_ENV_VARS, scope="api production")
        if not _validate_origins(os.getenv("CORS_ORIGINS", "")):
            raise RuntimeError("No valid HTTPS CORS_ORIGINS configured for production")

# Determine environment
IS_PRODUCTION = os.getenv('ENVIRONMENT', '').lower() == 'production'
APP_VERSION = (os.getenv("APP_VERSION") or "dev").strip() or "dev"
ENFORCE_HTTPS_REDIRECT = os.getenv("API_ENFORCE_HTTPS_REDIRECT", "false").strip().lower() == "true"

# Disable docs in production
docs_kwargs = {}
if IS_PRODUCTION:
    docs_kwargs = dict(docs_url=None, redoc_url=None, openapi_url=None)
else:
    docs_kwargs = dict(
        docs_url="/api/docs",
        redoc_url="/api/redoc",
        openapi_url="/api/openapi.json",
    )


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Per-IP rate limiting middleware using an in-memory sliding window."""

    def __init__(self, app, max_requests: int = 100, window_seconds: int = 60):
        super().__init__(app)
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.requests: dict[str, list[float]] = defaultdict(list)
        self._request_counter = 0
        self._cleanup_every = 500

    async def dispatch(self, request, call_next):
        client_ip = request.client.host if request.client else "unknown"
        now = time.time()
        self._request_counter += 1

        if self._request_counter % self._cleanup_every == 0 and self.requests:
            for ip in list(self.requests.keys()):
                self.requests[ip] = [t for t in self.requests[ip] if now - t < self.window_seconds]
                if not self.requests[ip]:
                    self.requests.pop(ip, None)

        timestamps = [t for t in self.requests[client_ip] if now - t < self.window_seconds]
        if not timestamps:
            self.requests.pop(client_ip, None)
        else:
            self.requests[client_ip] = timestamps
        if len(timestamps) >= self.max_requests:
            return JSONResponse(
                status_code=429, content={"detail": "Too many requests"}
            )
        self.requests[client_ip] = timestamps + [now]
        return await call_next(request)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Attach baseline security headers to all API responses."""

    async def dispatch(self, request, call_next):
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        if not request.url.path.startswith("/api/docs") and not request.url.path.startswith("/api/redoc"):
            response.headers.setdefault(
                "Content-Security-Policy",
                "default-src 'none'; frame-ancestors 'none'; base-uri 'none'",
            )
        if IS_PRODUCTION:
            response.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
        return response


def _validate_origins(raw: str) -> list[str]:
    """Validate and filter CORS origins.

    Ensures each origin has a proper scheme and enforces HTTPS in production.
    Falls back to ['http://localhost:3000'] if no valid origins remain.
    """
    origins = [o.strip() for o in raw.split(',') if o.strip()]
    validated = []
    for origin in origins:
        if not origin.startswith(('http://', 'https://')):
            logger.warning(f"Invalid CORS origin (missing scheme): {origin}")
            continue
        if IS_PRODUCTION and origin.startswith('http://'):
            logger.warning(f"Non-HTTPS CORS origin in production: {origin}")
            continue
        validated.append(origin)
    if not validated:
        if IS_PRODUCTION:
            logger.error("No valid CORS origins configured for production")
            return []
        return ['http://localhost:3000']
    return validated


# Lifespan hook for startup schema readiness.
@asynccontextmanager
async def _lifespan(_app: FastAPI):
    from common.models import create_tables

    validate_api_startup_env()
    create_tables()
    yield


# Create FastAPI app
app = FastAPI(
    title="HFI API",
    description="Hebrew FinTech Informant REST API",
    version="1.0.0",
    lifespan=_lifespan,
    **docs_kwargs,
)

# HTTPS enforcement (optional). Keep disabled behind internal reverse proxies.
if IS_PRODUCTION and ENFORCE_HTTPS_REDIRECT:
    from starlette.middleware.httpsredirect import HTTPSRedirectMiddleware
    app.add_middleware(HTTPSRedirectMiddleware)

# Configure CORS — locked down with validated origins
allowed_origins = _validate_origins(
    os.getenv('CORS_ORIGINS', 'http://localhost:3000,http://127.0.0.1:13000,http://localhost:13000')
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "X-API-Key"],
)

app.add_middleware(SecurityHeadersMiddleware)

# Per-IP rate limiting (added last = outermost, runs first)
app.add_middleware(
    RateLimitMiddleware,
    max_requests=max(1, int(os.getenv("API_RATE_LIMIT_MAX_REQUESTS", "100"))),
    window_seconds=max(1, int(os.getenv("API_RATE_LIMIT_WINDOW_SECONDS", "60"))),
)

# Include routers
app.include_router(trends.router)
app.include_router(summaries.router)
app.include_router(auth.router)
app.include_router(content.router)
app.include_router(generation.router)
app.include_router(inspiration.router)
app.include_router(settings.router)
app.include_router(notifications.router)


@app.get("/")
def root():
    """Root endpoint."""
    return {
        "name": "HFI API",
        "version": "1.0.0",
        "build_version": APP_VERSION,
        "status": "running",
    }


@app.get("/health")
def health_check():
    """Health check endpoint for monitoring."""
    from common.models import health_check as db_health_check

    db_health = db_health_check()
    db_status = db_health.get('status', 'unhealthy')

    response = {
        "status": "healthy" if db_status == 'healthy' else "unhealthy",
        "database": {"status": db_status},
        "build_version": APP_VERSION,
    }

    if db_status == 'healthy':
        response["database"].update({
            "tweet_count": db_health.get("tweet_count", 0),
            "trend_count": db_health.get("trend_count", 0),
        })

    return response


def _get_session_path() -> Path:
    return Path(__file__).parent.parent / "data" / "session" / "storage_state.json"


@app.get("/health/scraper-session")
def scraper_session_health():
    """Check X scraper session file status without launching a browser."""
    session_path = _get_session_path()
    if not session_path.exists():
        return {
            "status": "missing",
            "file_exists": False,
            "age_hours": None,
            "message": "No session file found. Run tools/refresh_session.py locally.",
        }
    mtime = os.path.getmtime(session_path)
    age_hours = round((_time.time() - mtime) / 3600, 1)
    if age_hours > 168:
        status = "expired"
        message = "Session is over 7 days old and likely expired."
    elif age_hours > 120:
        status = "warning"
        message = "Session is over 5 days old and may expire soon."
    else:
        status = "valid"
        message = "Session file looks fresh."
    return {
        "status": status,
        "file_exists": True,
        "age_hours": age_hours,
        "message": message,
    }


if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv('PORT', 8000))

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=port,
        reload=not IS_PRODUCTION,
        log_level="info"
    )
