"""Tests for alert detection."""

from datetime import datetime, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from common.models import Base, Notification
from processor.alert_detector import AlertDetector


class _FakeScraper:
    def __init__(self, articles):
        self._articles = articles

    def get_latest_news(self, limit_per_source=10, total_limit=20):
        return self._articles


def _db_session() -> Session:
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    return Session(bind=engine)


def test_check_for_alerts_creates_notifications():
    db = _db_session()
    scraper = _FakeScraper(
        [
            {"title": "SEC approves Bitcoin ETF framework", "source": "Bloomberg", "description": "a"},
            {"title": "Bitcoin ETF framework approved by SEC", "source": "WSJ", "description": "b"},
            {"title": "SEC greenlights new Bitcoin ETF framework", "source": "Yahoo Finance", "description": "c"},
        ]
    )

    detector = AlertDetector(scraper, db)
    created = detector.check_for_alerts(min_sources=3)

    assert len(created) >= 1
    alerts = db.query(Notification).filter(Notification.type == "alert").all()
    assert len(alerts) >= 1


def test_check_for_alerts_deduplicates_recent():
    db = _db_session()
    db.add(
        Notification(
            type="alert",
            content={"title": "SEC approves Bitcoin ETF framework"},
            delivered=False,
            created_at=datetime.now(timezone.utc),
        )
    )
    db.commit()

    scraper = _FakeScraper(
        [
            {"title": "SEC approves Bitcoin ETF framework", "source": "Bloomberg", "description": "a"},
            {"title": "Bitcoin ETF framework approved by SEC", "source": "WSJ", "description": "b"},
            {"title": "SEC greenlights new Bitcoin ETF framework", "source": "Yahoo Finance", "description": "c"},
        ]
    )

    detector = AlertDetector(scraper, db)
    created = detector.check_for_alerts(min_sources=3)

    assert created == []
