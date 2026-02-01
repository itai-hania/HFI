"""
FastAPI main application for HFI.

Provides REST API endpoints for the Next.js frontend.

Author: HFI Development Team
Last Updated: 2026-02-01
"""

import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import sys
from pathlib import Path

# Add parent directory to path for common modules
sys.path.append(str(Path(__file__).parent.parent))

from api.routes import trends, summaries

# Create FastAPI app
app = FastAPI(
    title="HFI API",
    description="Hebrew FinTech Informant REST API",
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json"
)

# Configure CORS for frontend
# Get allowed origins from environment or use defaults
allowed_origins = os.getenv(
    'CORS_ORIGINS',
    'https://your-vercel-app.vercel.app,http://localhost:3000'
).split(',')

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(trends.router)
app.include_router(summaries.router)


@app.get("/")
def root():
    """Root endpoint - API health check."""
    return {
        "name": "HFI API",
        "version": "1.0.0",
        "status": "running",
        "docs": "/api/docs"
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

    # Get port from environment or use default
    port = int(os.getenv('PORT', 8000))

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=port,
        reload=True,  # Enable auto-reload for development
        log_level="info"
    )
