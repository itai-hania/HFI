"""UX contract tests for dashboard publish handoff and stats shape."""

from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from common.models import Base, Tweet, TweetStatus
from dashboard import db_helpers


@pytest.fixture
def ux_db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    session = Session()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(engine)


def _fresh_stats(session, monkeypatch):
    monkeypatch.setattr(db_helpers.st, "session_state", {}, raising=False)
    return db_helpers.get_stats(session)


def test_get_stats_includes_publish_handoff_keys(ux_db_session, monkeypatch):
    ux_db_session.add_all(
        [
            Tweet(source_url="https://x.com/test/status/1", original_text="one", status=TweetStatus.PENDING),
            Tweet(source_url="https://x.com/test/status/2", original_text="two", status=TweetStatus.APPROVED),
            Tweet(
                source_url="https://x.com/test/status/3",
                original_text="three",
                status=TweetStatus.APPROVED,
                scheduled_at=datetime.now(timezone.utc),
            ),
            Tweet(source_url="https://x.com/test/status/4", original_text="four", status=TweetStatus.PUBLISHED),
        ]
    )
    ux_db_session.commit()

    stats = _fresh_stats(ux_db_session, monkeypatch)

    assert "scheduled" in stats
    assert "ready_to_publish" in stats
    assert stats["approved"] == 2
    assert stats["scheduled"] == 1
    assert stats["ready_to_publish"] == 1


def test_publish_handoff_state_transitions(ux_db_session, monkeypatch):
    tweet = Tweet(
        source_url="https://x.com/test/status/100",
        original_text="publish target",
        status=TweetStatus.APPROVED,
    )
    ux_db_session.add(tweet)
    ux_db_session.commit()

    # Schedule approved content.
    tweet.scheduled_at = datetime.now(timezone.utc)
    ux_db_session.commit()
    stats = _fresh_stats(ux_db_session, monkeypatch)
    assert stats["scheduled"] == 1

    # Mark as published.
    tweet.status = TweetStatus.PUBLISHED
    tweet.scheduled_at = None
    ux_db_session.commit()
    stats = _fresh_stats(ux_db_session, monkeypatch)
    assert stats["published"] == 1
    assert stats["scheduled"] == 0

    # Return to review flow (processed).
    tweet.status = TweetStatus.PROCESSED
    ux_db_session.commit()
    stats = _fresh_stats(ux_db_session, monkeypatch)
    assert stats["processed"] == 1
    assert stats["ready_to_publish"] == 0
