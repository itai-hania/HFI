"""
FastAPI dependencies for dependency injection.

Provides database sessions, authentication, and other shared dependencies.

Author: HFI Development Team
Last Updated: 2026-02-01
"""

from typing import Generator
from sqlalchemy.orm import Session
import sys
from pathlib import Path

# Add parent directory to path for common modules
sys.path.append(str(Path(__file__).parent.parent))

from common.models import SessionLocal


def get_db() -> Generator[Session, None, None]:
    """
    Dependency injection for database sessions.

    Yields:
        Database session

    Usage:
        @app.get("/api/trends")
        def get_trends(db: Session = Depends(get_db)):
            return db.query(Trend).all()
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
