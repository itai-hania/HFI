import time as _time
import streamlit as st
from datetime import datetime, timezone
from sqlalchemy import func, case
from common.models import get_db_session, Tweet, Trend, TweetStatus

_STATS_TTL = 5  # seconds


def get_db():
    if 'db' not in st.session_state:
        st.session_state.db = get_db_session()
    return st.session_state.db


def get_stats(db):
    cached = st.session_state.get('_stats_cache')
    if cached and (_time.time() - cached['_ts']) < _STATS_TTL:
        return cached

    row = db.query(
        func.count(Tweet.id),
        func.sum(case((Tweet.status == TweetStatus.PENDING, 1), else_=0)),
        func.sum(case((Tweet.status == TweetStatus.PROCESSED, 1), else_=0)),
        func.sum(case((Tweet.status == TweetStatus.APPROVED, 1), else_=0)),
        func.sum(case((Tweet.status == TweetStatus.PUBLISHED, 1), else_=0)),
        func.sum(case((Tweet.status == TweetStatus.FAILED, 1), else_=0)),
        func.sum(case(((Tweet.status == TweetStatus.APPROVED) & Tweet.scheduled_at.isnot(None), 1), else_=0)),
        func.sum(case(((Tweet.status == TweetStatus.APPROVED) & Tweet.scheduled_at.is_(None), 1), else_=0)),
    ).one()

    stats = {
        'total': row[0] or 0,
        'pending': int(row[1] or 0),
        'processed': int(row[2] or 0),
        'approved': int(row[3] or 0),
        'published': int(row[4] or 0),
        'failed': int(row[5] or 0),
        'scheduled': int(row[6] or 0),
        'ready_to_publish': int(row[7] or 0),
        '_ts': _time.time(),
    }
    st.session_state['_stats_cache'] = stats
    return stats


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
