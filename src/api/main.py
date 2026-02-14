"""
FastAPI main application for HFI.

Provides REST API endpoints for the Next.js frontend.
"""

import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routes import trends, summaries

# Determine environment
IS_PRODUCTION = os.getenv('ENVIRONMENT', '').lower() == 'production'

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

# Create FastAPI app
app = FastAPI(
    title="HFI API",
    description="Hebrew FinTech Informant REST API",
    version="1.0.0",
    **docs_kwargs,
)

# Configure CORS — locked down
allowed_origins = os.getenv(
    'CORS_ORIGINS',
    'http://localhost:3000'
).split(',')

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in allowed_origins],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "Authorization", "X-API-Key"],
)

# Include routers
app.include_router(trends.router)
app.include_router(summaries.router)


@app.get("/")
def root():
    """Root endpoint."""
    return {
        "name": "HFI API",
        "version": "1.0.0",
        "status": "running",
    }


@app.get("/health")
def health_check():
    """Health check endpoint for monitoring."""
    from common.models import health_check as db_health_check

    db_health = db_health_check()

    return {
        "status": "healthy" if db_health['status'] == 'healthy' else "unhealthy",
        "database": db_health,
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
