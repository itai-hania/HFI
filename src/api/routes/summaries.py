"""
Summary generation API endpoints.

Provides endpoints for generating AI summaries for trends.

Author: HFI Development Team
Last Updated: 2026-02-01
"""

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session

from common.models import Trend
from api.dependencies import get_db, require_api_key
from api.schemas import (
    SummaryGenerateRequest,
    SummaryGenerateResponse,
    BulkSummaryGenerateResponse
)
from processor.summary_generator import SummaryGenerator

router = APIRouter(prefix="/api/trends", tags=["summaries"], dependencies=[Depends(require_api_key)])


_summary_generator_instance = None


def get_summary_generator() -> SummaryGenerator:
    """Dependency to get summary generator instance (cached singleton)."""
    global _summary_generator_instance
    if _summary_generator_instance is None:
        _summary_generator_instance = SummaryGenerator()
    return _summary_generator_instance


@router.post("/{trend_id}/generate-summary", response_model=SummaryGenerateResponse)
def generate_summary(
    trend_id: int,
    request: SummaryGenerateRequest = SummaryGenerateRequest(),
    db: Session = Depends(get_db),
    generator: SummaryGenerator = Depends(get_summary_generator)
):
    """
    Generate AI summary for a specific trend.

    Path Parameters:
    - trend_id: ID of the trend

    Request Body:
    - force: Force regeneration even if summary exists (default: false)

    Returns:
        Generated summary, keywords, source count, and related trends
    """
    trend = db.query(Trend).filter(Trend.id == trend_id).first()

    if not trend:
        raise HTTPException(status_code=404, detail=f"Trend {trend_id} not found")

    # Check if summary already exists
    if trend.summary and not request.force:
        raise HTTPException(
            status_code=400,
            detail=f"Trend {trend_id} already has a summary. Use force=true to regenerate."
        )

    # Generate summary
    success = generator.process_trend(db, trend_id)

    if not success:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate summary for trend {trend_id}"
        )

    # Refresh trend to get updated data
    db.refresh(trend)

    return SummaryGenerateResponse(
        trend_id=trend.id,
        summary=trend.summary or "",
        keywords=trend.keywords or [],
        source_count=trend.source_count or 1,
        related_trend_ids=trend.related_trend_ids or []
    )


def _backfill_summaries_task(limit: Optional[int], db_session):
    """Background task to generate summaries."""
    generator = SummaryGenerator()
    return generator.backfill_summaries(db_session, limit=limit)


@router.post("/generate-summaries", response_model=BulkSummaryGenerateResponse)
def generate_summaries_bulk(
    limit: Optional[int] = None,
    background_tasks: BackgroundTasks = None,
    db: Session = Depends(get_db),
    generator: SummaryGenerator = Depends(get_summary_generator)
):
    """
    Generate summaries for all trends missing them.

    Query Parameters:
    - limit: Maximum number of trends to process (optional)

    Returns:
        Statistics about the bulk generation process
    """
    # Run synchronously for now (can be made async with BackgroundTasks)
    stats = generator.backfill_summaries(db, limit=limit)

    return BulkSummaryGenerateResponse(
        success=stats['success'],
        failed=stats['failed'],
        skipped=stats['skipped']
    )


@router.delete("/{trend_id}/summary")
def delete_summary(
    trend_id: int,
    db: Session = Depends(get_db)
):
    """
    Delete the summary for a trend.

    Useful for regenerating summaries or removing incorrect ones.

    Path Parameters:
    - trend_id: ID of the trend

    Returns:
        Success message
    """
    trend = db.query(Trend).filter(Trend.id == trend_id).first()

    if not trend:
        raise HTTPException(status_code=404, detail=f"Trend {trend_id} not found")

    if not trend.summary:
        raise HTTPException(
            status_code=400,
            detail=f"Trend {trend_id} does not have a summary"
        )

    trend.summary = None
    trend.keywords = None
    trend.source_count = 1
    trend.related_trend_ids = None
    db.commit()

    return {"message": f"Summary deleted for trend {trend_id}"}
