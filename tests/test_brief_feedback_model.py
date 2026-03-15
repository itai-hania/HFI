"""Tests for BriefFeedback model."""

import pytest
from datetime import datetime, timezone

from common.models import Base, BriefFeedback, SessionLocal, engine


@pytest.fixture(autouse=True)
def _setup_tables():
    Base.metadata.create_all(engine)
    yield
    db = SessionLocal()
    db.query(BriefFeedback).delete()
    db.commit()
    db.close()


def test_create_brief_feedback():
    db = SessionLocal()
    try:
        fb = BriefFeedback(
            story_title="NVIDIA beats earnings expectations",
            feedback_type="not_relevant",
            keywords=["nvidia", "earnings"],
            source="dashboard",
        )
        db.add(fb)
        db.commit()
        db.refresh(fb)

        assert fb.id is not None
        assert fb.story_title == "NVIDIA beats earnings expectations"
        assert fb.feedback_type == "not_relevant"
        assert fb.keywords == ["nvidia", "earnings"]
        assert fb.source == "dashboard"
        assert isinstance(fb.created_at, datetime)
    finally:
        db.close()


def test_query_feedback_by_type():
    db = SessionLocal()
    try:
        db.add(BriefFeedback(story_title="Story A", feedback_type="not_relevant", keywords=["a"], source="telegram"))
        db.add(BriefFeedback(story_title="Story B", feedback_type="not_relevant", keywords=["b"], source="dashboard"))
        db.commit()

        results = db.query(BriefFeedback).filter_by(feedback_type="not_relevant").all()
        assert len(results) == 2
    finally:
        db.close()
