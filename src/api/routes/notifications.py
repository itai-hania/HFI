"""Brief and alert notification endpoints."""

import os
from datetime import datetime, timezone, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from api.dependencies import get_db, require_jwt
from api.schemas.notification import (
    BriefResponse,
    BriefStory,
    NotificationListResponse,
    NotificationResponse,
    NotificationDeliveredResponse,
)
from common.models import Notification
from processor.alert_detector import AlertDetector
from scraper.news_scraper import NewsScraper

router = APIRouter(
    prefix="/api/notifications",
    tags=["notifications"],
    dependencies=[Depends(require_jwt)],
)

_BRIEF_CACHE_TTL = timedelta(minutes=10)


def _get_translation_service():
    """Initialize translator once per request (if configured)."""
    if not os.getenv("OPENAI_API_KEY"):
        return None
    try:
        from processor.processor import ProcessorConfig, TranslationService

        return TranslationService(ProcessorConfig())
    except Exception:
        return None


def _summarize_to_hebrew(title: str, description: str, service=None) -> str:
    """Best-effort short Hebrew summary with graceful fallback."""
    source_text = f"{title}. {description or ''}".strip()

    if service is None:
        return source_text[:280]

    try:
        translated = service.translate_and_rewrite(source_text)
        return translated[:280]
    except Exception:
        return source_text[:280]


@router.post("/brief", response_model=BriefResponse)
def generate_brief(force_refresh: bool = Query(False), db: Session = Depends(get_db)):
    """Generate brief stories from latest news and store notification."""
    now = datetime.now(timezone.utc)
    if not force_refresh:
        latest = (
            db.query(Notification)
            .filter(Notification.type == "brief")
            .order_by(Notification.created_at.desc())
            .first()
        )
        latest_created_at = latest.created_at if latest else None
        if latest_created_at and latest_created_at.tzinfo is None:
            # SQLite often returns naive datetimes even for timezone-aware columns.
            latest_created_at = latest_created_at.replace(tzinfo=timezone.utc)
        if latest_created_at and latest_created_at >= now - _BRIEF_CACHE_TTL:
            stories_payload = (latest.content or {}).get("stories", [])
            stories = [BriefStory.model_validate(item) for item in stories_payload if isinstance(item, dict)]
            if stories:
                return BriefResponse(stories=stories)

    scraper = NewsScraper()
    articles = scraper.get_latest_news(limit_per_source=10, total_limit=8)
    translator = _get_translation_service()

    stories = []
    for article in articles:
        title = article.get("title") or ""
        if not title:
            continue

        source = article.get("source") or "Unknown"
        source_count = int(article.get("source_count") or 1)
        summary = _summarize_to_hebrew(
            title=title,
            description=article.get("description") or "",
            service=translator,
        )

        stories.append(
            BriefStory(
                title=title,
                summary=summary,
                sources=[source],
                source_count=source_count,
            )
        )

    payload = {"stories": [s.model_dump() for s in stories]}
    row = Notification(type="brief", content=payload, delivered=False, created_at=now)
    db.add(row)
    db.commit()

    return BriefResponse(stories=stories)


@router.get("/alerts", response_model=NotificationListResponse)
def get_alerts(
    delivered: Optional[bool] = Query(None),
    refresh: bool = Query(False, description="Run alert detection before listing alerts"),
    db: Session = Depends(get_db),
):
    """List alert notifications, optionally filtered by delivery state."""
    if refresh:
        detector = AlertDetector(news_scraper=NewsScraper(), db_session=db)
        detector.check_for_alerts(min_sources=3)

    query = db.query(Notification).filter(Notification.type == "alert")
    if delivered is not None:
        query = query.filter(Notification.delivered == delivered)

    alerts = query.order_by(Notification.created_at.desc()).all()
    return NotificationListResponse(alerts=alerts)


@router.post("/alerts/check")
def check_alerts(
    min_sources: int = Query(3, ge=2, le=10),
    db: Session = Depends(get_db),
):
    """Run cross-source alert detection and persist new notifications."""
    detector = AlertDetector(news_scraper=NewsScraper(), db_session=db)
    created = detector.check_for_alerts(min_sources=min_sources)
    return {"created": created, "count": len(created)}


@router.patch("/{notification_id}/delivered", response_model=NotificationDeliveredResponse)
def mark_delivered(notification_id: int, db: Session = Depends(get_db)):
    """Mark a notification as delivered."""
    row = db.get(Notification, notification_id)
    if not row:
        raise HTTPException(status_code=404, detail="Notification not found")

    row.delivered = True
    row.delivered_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(row)

    return NotificationDeliveredResponse(
        id=row.id,
        delivered=row.delivered,
        delivered_at=row.delivered_at,
    )
