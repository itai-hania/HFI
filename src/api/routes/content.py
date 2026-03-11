"""Content CRUD endpoints for drafts, queue, and library."""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from fastapi.responses import JSONResponse
from sqlalchemy import func, or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from api.dependencies import get_db, require_jwt
from api.schemas.content import (
    ContentCreate,
    ContentUpdate,
    ContentResponse,
    ContentListResponse,
)
from common.models import Tweet, TweetStatus

router = APIRouter(
    prefix="/api/content",
    tags=["content"],
    dependencies=[Depends(require_jwt)],
)


def _parse_status(status: Optional[str]) -> Optional[TweetStatus]:
    if not status:
        return None
    try:
        return TweetStatus(status)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"Invalid status: {status}") from exc


def _queue_summary_payload(db: Session) -> dict[str, int]:
    """Build queue counts by workflow status and scheduled flag."""
    counts = {status.value: 0 for status in TweetStatus}
    rows = db.query(Tweet.status, func.count(Tweet.id)).group_by(Tweet.status).all()
    for status, count in rows:
        if status is not None:
            counts[str(status.value)] = int(count)

    scheduled_count = int(
        db.query(func.count(Tweet.id))
        .filter(Tweet.scheduled_at.isnot(None))
        .scalar()
        or 0
    )

    return {
        "pending": counts[TweetStatus.PENDING.value],
        "processed": counts[TweetStatus.PROCESSED.value],
        "approved": counts[TweetStatus.APPROVED.value],
        "scheduled": scheduled_count,
        "published": counts[TweetStatus.PUBLISHED.value],
        "failed": counts[TweetStatus.FAILED.value],
    }


@router.get("/drafts", response_model=ContentListResponse)
def list_content(
    status: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    search: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    """List content items with filtering, search, and pagination."""
    query = db.query(Tweet)

    parsed_status = _parse_status(status)
    if parsed_status:
        query = query.filter(Tweet.status == parsed_status)

    if search:
        pattern = f"%{search}%"
        query = query.filter(
            or_(
                Tweet.original_text.ilike(pattern),
                Tweet.hebrew_draft.ilike(pattern),
                Tweet.trend_topic.ilike(pattern),
                Tweet.source_url.ilike(pattern),
            )
        )

    total = query.count()
    items = (
        query.order_by(Tweet.created_at.desc())
        .offset((page - 1) * limit)
        .limit(limit)
        .all()
    )
    return ContentListResponse(items=items, total=total, page=page, per_page=limit)


@router.get("/scheduled", response_model=ContentListResponse)
def list_scheduled(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """List approved content that has a schedule."""
    query = db.query(Tweet).filter(
        Tweet.status == TweetStatus.APPROVED,
        Tweet.scheduled_at.isnot(None),
    )
    total = query.count()
    items = (
        query.order_by(Tweet.scheduled_at.asc())
        .offset((page - 1) * limit)
        .limit(limit)
        .all()
    )
    return ContentListResponse(items=items, total=total, page=page, per_page=limit)


@router.get("/published", response_model=ContentListResponse)
def list_published(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """List published content."""
    query = db.query(Tweet).filter(Tweet.status == TweetStatus.PUBLISHED)
    total = query.count()
    items = (
        query.order_by(Tweet.created_at.desc())
        .offset((page - 1) * limit)
        .limit(limit)
        .all()
    )
    return ContentListResponse(items=items, total=total, page=page, per_page=limit)


@router.get("/queue/summary")
def queue_summary(db: Session = Depends(get_db)):
    """Return compact queue counters for Telegram and dashboard widgets."""
    return _queue_summary_payload(db)


@router.get("/{content_id}", response_model=ContentResponse)
def get_content(content_id: int, db: Session = Depends(get_db)):
    """Get a single content item by id."""
    tweet = db.get(Tweet, content_id)
    if not tweet:
        raise HTTPException(status_code=404, detail="Content not found")
    return tweet


@router.post("", response_model=ContentResponse, status_code=201)
def create_content(data: ContentCreate, db: Session = Depends(get_db)):
    """Create a new content record."""
    requested_status = _parse_status(data.status)
    status = requested_status or (TweetStatus.PROCESSED if data.hebrew_draft else TweetStatus.PENDING)

    tweet = Tweet(
        source_url=data.source_url,
        original_text=data.original_text,
        hebrew_draft=data.hebrew_draft,
        content_type=data.content_type,
        generation_metadata=data.generation_metadata,
        trend_topic=data.trend_topic,
        scheduled_at=data.scheduled_at,
        status=status,
    )

    db.add(tweet)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        if "source_url" in str(exc).lower():
            existing = db.query(Tweet.id).filter(Tweet.source_url == data.source_url).first()
            detail: dict[str, object] = {"detail": "Content with this source_url already exists"}
            if existing:
                detail["existing_id"] = int(existing[0])
            return JSONResponse(status_code=409, content=detail)
        raise HTTPException(status_code=500, detail="Failed to create content") from exc
    db.refresh(tweet)
    return tweet


@router.patch("/{content_id}", response_model=ContentResponse)
def update_content(content_id: int, data: ContentUpdate, db: Session = Depends(get_db)):
    """Update content fields and status."""
    tweet = db.get(Tweet, content_id)
    if not tweet:
        raise HTTPException(status_code=404, detail="Content not found")

    payload = data.model_dump(exclude_unset=True)
    if "status" in payload and payload["status"] is not None:
        payload["status"] = _parse_status(payload["status"])

    for field, value in payload.items():
        setattr(tweet, field, value)

    db.commit()
    db.refresh(tweet)
    return tweet


@router.delete("/{content_id}", status_code=204)
def delete_content(content_id: int, db: Session = Depends(get_db)):
    """Delete content by id."""
    tweet = db.get(Tweet, content_id)
    if not tweet:
        raise HTTPException(status_code=404, detail="Content not found")

    db.delete(tweet)
    db.commit()
    return Response(status_code=204)


@router.post("/{content_id}/approve", response_model=ContentResponse)
def approve_content(content_id: int, db: Session = Depends(get_db)):
    """Approve a draft when Hebrew content exists."""
    tweet = db.get(Tweet, content_id)
    if not tweet:
        raise HTTPException(status_code=404, detail="Content not found")

    if tweet.status in {TweetStatus.PUBLISHED, TweetStatus.FAILED}:
        raise HTTPException(status_code=400, detail=f"Cannot approve content in status: {tweet.status.value}")

    if not (tweet.hebrew_draft or "").strip():
        raise HTTPException(status_code=400, detail="Cannot approve content without hebrew_draft")

    tweet.status = TweetStatus.APPROVED
    db.commit()
    db.refresh(tweet)
    return tweet


@router.post("/{content_id}/copy", response_model=ContentResponse)
def increment_copy(content_id: int, db: Session = Depends(get_db)):
    """Increment copy counter for analytics and UX metrics."""
    tweet = db.get(Tweet, content_id)
    if not tweet:
        raise HTTPException(status_code=404, detail="Content not found")

    tweet.copy_count = int(tweet.copy_count or 0) + 1
    db.commit()
    db.refresh(tweet)
    return tweet
