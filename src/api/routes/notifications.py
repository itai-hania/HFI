"""Brief and alert notification endpoints."""

from datetime import datetime, timezone, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from api.dependencies import get_db, require_jwt
from api.schemas.notification import (
    BriefFeedbackRequest,
    BriefFeedbackWeightsResponse,
    BriefResponse,
    BriefStory,
    BriefTheme,
    NotificationListResponse,
    NotificationResponse,
    NotificationDeliveredResponse,
)
from common.models import BriefFeedback, Notification
from processor.alert_detector import AlertDetector
from processor.brief_themer import BriefThemer
from scraper.news_scraper import NewsScraper

router = APIRouter(
    prefix="/api/notifications",
    tags=["notifications"],
    dependencies=[Depends(require_jwt)],
)

_BRIEF_CACHE_TTL = timedelta(minutes=10)


def _to_brief_response(row: Notification | None) -> BriefResponse:
    if row is None:
        raise HTTPException(status_code=404, detail="No stored brief found")

    content = row.content or {}
    stories_payload = content.get("stories", [])
    stories = [BriefStory.model_validate(item) for item in stories_payload if isinstance(item, dict)]
    if not stories:
        raise HTTPException(status_code=404, detail="No stored brief found")

    themes_payload = content.get("themes", [])
    themes = [BriefTheme.model_validate(item) for item in themes_payload if isinstance(item, dict)]
    generated_at = content.get("generated_at")
    return BriefResponse(themes=themes, stories=stories, generated_at=generated_at)


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
            try:
                return _to_brief_response(latest)
            except HTTPException as exc:
                if exc.status_code != 404:
                    raise

    scraper = NewsScraper()
    articles = scraper.get_brief_news(total_limit=8, max_age_hours=48)

    stories = []
    for article in articles:
        title = article.get("title") or ""
        if not title:
            continue

        source = article.get("source") or "Unknown"
        sources = article.get("sources") or [source]
        sources = [str(item) for item in sources if item]
        if not sources:
            sources = [source]
        source_count = int(article.get("source_count") or len(set(sources)) or 1)
        description = article.get("description") or ""
        summary = (description if description else title)[:280]
        source_urls = article.get("source_urls") or []
        if not source_urls:
            url = article.get("url") or ""
            source_urls = [url] if url else []
        source_urls = [str(item) for item in source_urls if item]
        relevance_score = int(article.get("relevance_score") or article.get("score") or 0)
        published_at = article.get("published_at")

        stories.append(
            BriefStory(
                title=title,
                summary=summary,
                sources=sources,
                source_urls=source_urls,
                source_count=source_count,
                published_at=published_at,
                relevance_score=relevance_score,
            )
        )

    # Persist JSON-safe values (e.g., datetimes as ISO strings) in the JSON column.
    themer = BriefThemer()
    story_dicts = [s.model_dump(mode="json") for s in stories]
    raw_themes = themer.generate_themes(story_dicts)

    themes = [
        BriefTheme(
            name=t["name"],
            emoji=t["emoji"],
            takeaway=t["takeaway"],
            stories=[BriefStory.model_validate(s) for s in t["stories"]],
        )
        for t in raw_themes
    ]

    generated_at = now.isoformat()
    payload = {
        "stories": story_dicts,
        "themes": [t.model_dump(mode="json") for t in themes],
        "generated_at": generated_at,
    }
    row = Notification(type="brief", content=payload, delivered=False, created_at=now)
    db.add(row)
    db.commit()

    return BriefResponse(themes=themes, stories=stories, generated_at=now)


@router.get("/brief/latest", response_model=BriefResponse)
def latest_brief(db: Session = Depends(get_db)):
    """Return latest persisted brief payload without regeneration."""
    latest = (
        db.query(Notification)
        .filter(Notification.type == "brief")
        .order_by(Notification.created_at.desc())
        .first()
    )
    return _to_brief_response(latest)


@router.post("/brief/feedback")
def submit_brief_feedback(request: BriefFeedbackRequest, db: Session = Depends(get_db)):
    """Store story feedback for personalization.

    Keywords are extracted server-side from the story title to ensure
    consistent extraction regardless of the client surface.
    """
    from common.stopwords import STOPWORDS

    # Server-side keyword extraction for consistency
    keywords = request.keywords
    if not keywords and request.story_title:
        words = request.story_title.lower().split()
        keywords = [
            w.strip(".,!?:;\"'()")
            for w in words
            if w.strip(".,!?:;\"'()") not in STOPWORDS and len(w.strip(".,!?:;\"'()")) > 2
        ]

    fb = BriefFeedback(
        story_title=request.story_title[:500],
        feedback_type=request.feedback_type,
        keywords=keywords,
        source=request.source,
    )
    db.add(fb)
    db.commit()
    return {"status": "ok"}


@router.get("/brief/feedback/weights", response_model=BriefFeedbackWeightsResponse)
def get_feedback_weights(db: Session = Depends(get_db)):
    """Return learned keyword exclusions based on accumulated feedback."""
    rows = db.query(BriefFeedback).filter_by(feedback_type="not_relevant").all()
    keyword_counts: dict[str, int] = {}
    for row in rows:
        for kw in (row.keywords or []):
            keyword_counts[kw] = keyword_counts.get(kw, 0) + 1
    excluded = [kw for kw, count in keyword_counts.items() if count >= 3]
    return BriefFeedbackWeightsResponse(excluded_keywords=excluded, keyword_counts=keyword_counts)


@router.delete("/brief/feedback")
def reset_feedback(db: Session = Depends(get_db)):
    """Clear all feedback data."""
    db.query(BriefFeedback).delete()
    db.commit()
    return {"status": "ok"}


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
    min_sources: int = Query(2, ge=2, le=10),
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
