"""
Trend API endpoints.

Provides CRUD operations and filtering for trends.

Author: HFI Development Team
Last Updated: 2026-02-01
"""

from typing import Optional, List
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func

from common.models import Trend, TrendSource
from api.dependencies import get_db
from api.schemas import TrendResponse, TrendListResponse

router = APIRouter(prefix="/api/trends", tags=["trends"])


@router.get("", response_model=TrendListResponse)
def get_trends(
    source: Optional[str] = Query(None, description="Filter by source (Yahoo Finance, WSJ, etc.)"),
    date_from: Optional[datetime] = Query(None, description="Filter by discovered date (from)"),
    date_to: Optional[datetime] = Query(None, description="Filter by discovered date (to)"),
    has_summary: Optional[bool] = Query(None, description="Filter trends with/without summaries"),
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    limit: int = Query(12, ge=1, le=100, description="Items per page"),
    db: Session = Depends(get_db)
):
    """
    Get paginated list of trends with optional filters.

    Query Parameters:
    - source: Filter by source platform
    - date_from: Start date for filtering
    - date_to: End date for filtering
    - has_summary: Filter trends with/without AI summaries
    - page: Page number (default: 1)
    - limit: Items per page (default: 12, max: 100)

    Returns:
        Paginated list of trends with metadata
    """
    # Build query with filters
    query = db.query(Trend)

    if source:
        # Convert source string to enum
        try:
            source_enum = TrendSource(source)
            query = query.filter(Trend.source == source_enum)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid source: {source}")

    if date_from:
        query = query.filter(Trend.discovered_at >= date_from)

    if date_to:
        query = query.filter(Trend.discovered_at <= date_to)

    if has_summary is not None:
        if has_summary:
            query = query.filter(Trend.summary != None)
        else:
            query = query.filter(Trend.summary == None)

    # Get total count before pagination
    total = query.count()

    # Apply pagination
    offset = (page - 1) * limit
    trends = query.order_by(Trend.discovered_at.desc()).offset(offset).limit(limit).all()

    # Calculate total pages
    total_pages = (total + limit - 1) // limit  # Ceiling division

    return TrendListResponse(
        trends=[TrendResponse.model_validate(trend) for trend in trends],
        total=total,
        page=page,
        per_page=limit,
        total_pages=total_pages
    )


@router.get("/{trend_id}", response_model=TrendResponse)
def get_trend_detail(
    trend_id: int,
    db: Session = Depends(get_db)
):
    """
    Get detailed information about a specific trend.

    Path Parameters:
    - trend_id: ID of the trend

    Returns:
        Full trend details including summary, keywords, and related trends
    """
    trend = db.query(Trend).filter(Trend.id == trend_id).first()

    if not trend:
        raise HTTPException(status_code=404, detail=f"Trend {trend_id} not found")

    return TrendResponse.model_validate(trend)


@router.get("/stats/summary", response_model=dict)
def get_trends_stats(db: Session = Depends(get_db)):
    """
    Get statistics about trends.

    Returns:
        Dictionary with trend statistics:
        - total: Total number of trends
        - with_summaries: Number of trends with AI summaries
        - without_summaries: Number of trends needing summaries
        - by_source: Breakdown by source platform
    """
    total = db.query(Trend).count()
    with_summaries = db.query(Trend).filter(Trend.summary != None).count()
    without_summaries = total - with_summaries

    # Count by source
    by_source = {}
    for source in TrendSource:
        count = db.query(Trend).filter(Trend.source == source).count()
        if count > 0:
            by_source[source.value] = count

    return {
        "total": total,
        "with_summaries": with_summaries,
        "without_summaries": without_summaries,
        "by_source": by_source
    }
