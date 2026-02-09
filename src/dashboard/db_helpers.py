import streamlit as st
from datetime import datetime, timezone
from sqlalchemy import func
from common.models import get_db_session, Tweet, Trend, TweetStatus


def get_db():
    if 'db' not in st.session_state:
        st.session_state.db = get_db_session()
    return st.session_state.db


def get_stats(db):
    return {
        'total': db.query(func.count(Tweet.id)).scalar() or 0,
        'pending': db.query(func.count(Tweet.id)).filter(Tweet.status == TweetStatus.PENDING).scalar() or 0,
        'processed': db.query(func.count(Tweet.id)).filter(Tweet.status == TweetStatus.PROCESSED).scalar() or 0,
        'approved': db.query(func.count(Tweet.id)).filter(Tweet.status == TweetStatus.APPROVED).scalar() or 0,
        'published': db.query(func.count(Tweet.id)).filter(Tweet.status == TweetStatus.PUBLISHED).scalar() or 0,
        'failed': db.query(func.count(Tweet.id)).filter(Tweet.status == TweetStatus.FAILED).scalar() or 0,
    }


def get_tweets(db, status_filter='all', limit=50):
    query = db.query(Tweet).order_by(Tweet.created_at.desc())
    if status_filter != 'all':
        status_enum = getattr(TweetStatus, status_filter.upper(), None)
        if status_enum:
            query = query.filter(Tweet.status == status_enum)
    return query.limit(limit).all()


def update_tweet(db, tweet_id, **kwargs):
    tweet = db.query(Tweet).filter(Tweet.id == tweet_id).first()
    if tweet:
        for key, value in kwargs.items():
            if key == 'status' and isinstance(value, str):
                value = getattr(TweetStatus, value.upper(), value)
            setattr(tweet, key, value)
        tweet.updated_at = datetime.now(timezone.utc)
        db.commit()
        return True
    return False


def delete_tweet(db, tweet_id):
    tweet = db.query(Tweet).filter(Tweet.id == tweet_id).first()
    if tweet:
        db.delete(tweet)
        db.commit()
        return True
    return False


def delete_trend(db, trend_id):
    """Delete a trend from the database."""
    trend = db.query(Trend).filter(Trend.id == trend_id).first()
    if trend:
        db.delete(trend)
        db.commit()
        return True
    return False
