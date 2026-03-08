"""Tests for v2 database models."""

from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from common.models import (
    Base,
    Tweet,
    InspirationAccount,
    InspirationPost,
    Notification,
    UserPreference,
)


@pytest.fixture
def db():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session = Session(bind=engine)
    try:
        yield session
    finally:
        session.close()


class TestInspirationAccount:
    def test_create_account(self, db):
        account = InspirationAccount(
            username="elikiris",
            display_name="Eli Kiris",
            category="fintech",
            is_active=True,
        )
        db.add(account)
        db.commit()

        assert account.id is not None
        assert account.username == "elikiris"
        assert account.is_active is True

    def test_unique_username(self, db):
        db.add(InspirationAccount(username="user1", display_name="User 1"))
        db.commit()

        db.add(InspirationAccount(username="user1", display_name="Duplicate"))
        with pytest.raises(Exception):
            db.commit()


class TestInspirationPost:
    def test_create_post(self, db):
        account = InspirationAccount(username="testuser", display_name="Test")
        db.add(account)
        db.commit()

        post = InspirationPost(
            account_id=account.id,
            x_post_id="1234567890",
            content="Test post content",
            likes=500,
            retweets=100,
            views=10000,
            posted_at=datetime.now(timezone.utc),
        )
        db.add(post)
        db.commit()

        assert post.id is not None
        assert post.account_id == account.id

    def test_unique_x_post_id(self, db):
        account = InspirationAccount(username="testuser2", display_name="Test")
        db.add(account)
        db.commit()

        db.add(InspirationPost(account_id=account.id, x_post_id="same_id", content="a"))
        db.commit()

        db.add(InspirationPost(account_id=account.id, x_post_id="same_id", content="b"))
        with pytest.raises(Exception):
            db.commit()


class TestNotification:
    def test_create_notification(self, db):
        notif = Notification(
            type="brief",
            content={"stories": [{"title": "Test"}]},
            delivered=False,
        )
        db.add(notif)
        db.commit()

        assert notif.id is not None
        assert notif.delivered is False


class TestUserPreference:
    def test_create_preference(self, db):
        pref = UserPreference(key="default_angle", value="news")
        db.add(pref)
        db.commit()

        fetched = db.query(UserPreference).filter_by(key="default_angle").first()
        assert fetched.value == "news"

    def test_upsert_preference(self, db):
        pref = UserPreference(key="theme", value="dark")
        db.add(pref)
        db.commit()

        pref.value = "light"
        db.commit()

        fetched = db.query(UserPreference).filter_by(key="theme").first()
        assert fetched.value == "light"


class TestTweetCopyCount:
    def test_copy_count_default(self, db):
        tweet = Tweet(source_url="https://x.com/test/status/1", original_text="hello")
        db.add(tweet)
        db.commit()
        assert tweet.copy_count == 0
