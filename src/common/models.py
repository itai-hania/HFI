"""
Database models for Hebrew FinTech Informant (HFI) application.

This module provides SQLAlchemy ORM models for managing tweets, trends, and related
data. Optimized for SQLite with proper indexing for common query patterns.

Author: HFI Development Team
Last Updated: 2026-01-17
"""

import os
import enum
import logging
from datetime import datetime, timezone
from typing import Generator, Optional
from contextlib import contextmanager
from pathlib import Path

from sqlalchemy import (
    create_engine,
    Column,
    Integer,
    String,
    Text,
    DateTime,
    Enum as SQLEnum,
    Index,
    event,
    Engine,
)
from sqlalchemy.orm import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ==================== Configuration ====================

# Ensure data directory exists
data_dir = Path(__file__).parent.parent.parent / "data"
data_dir.mkdir(parents=True, exist_ok=True)

# Get database URL from environment, default to SQLite in data directory
DATABASE_URL = os.getenv('DATABASE_URL', f'sqlite:///{data_dir}/hfi.db')

logger.info(f"Database configured: {DATABASE_URL}")

# ==================== SQLAlchemy Setup ====================

Base = declarative_base()

# Engine configuration optimized for SQLite
# - check_same_thread: False allows multiple threads (safe with proper session management)
# - connect_args: SQLite-specific optimizations
# - pool_pre_ping: Verify connections before using them
# - echo: Set to True for SQL debugging (disabled in production)
engine = create_engine(
    DATABASE_URL,
    echo=False,  # Set to True for SQL query debugging
    connect_args={
        "check_same_thread": False,  # Allow multi-threaded access
        "timeout": 30,  # 30 second timeout for locks
    },
    pool_pre_ping=True,  # Verify connection health
    # For SQLite, use StaticPool to maintain single connection in memory databases
    poolclass=StaticPool if DATABASE_URL == 'sqlite:///:memory:' else None,
)

# Enable SQLite WAL mode for better concurrent access
@event.listens_for(Engine, "connect")
def set_sqlite_pragma(dbapi_conn, connection_record):
    """
    Configure SQLite connection for optimal performance.

    - WAL mode: Write-Ahead Logging for better concurrency
    - Foreign keys: Enable referential integrity
    - Synchronous: NORMAL is safe for most cases (faster than FULL)
    - Cache size: 10MB cache for better performance
    """
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")  # Better concurrency
    cursor.execute("PRAGMA foreign_keys=ON")  # Enable foreign keys
    cursor.execute("PRAGMA synchronous=NORMAL")  # Balance between safety and speed
    cursor.execute("PRAGMA cache_size=-10000")  # 10MB cache
    cursor.execute("PRAGMA temp_store=MEMORY")  # Use memory for temp tables
    cursor.close()

# Session factory for creating database sessions
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
    expire_on_commit=False,  # Prevent expired object issues after commit
)

# ==================== Enums ====================

class TweetStatus(enum.Enum):
    """
    Tweet processing status workflow.

    Lifecycle:
    1. pending: Tweet scraped, awaiting translation
    2. processed: Translation complete, ready for review
    3. approved: Human-approved, ready to publish
    4. published: Posted to X (Twitter)
    5. failed: Processing failed, requires attention
    """
    PENDING = "pending"
    PROCESSED = "processed"
    APPROVED = "approved"
    PUBLISHED = "published"
    FAILED = "failed"

    def __str__(self):
        return self.value


class TrendSource(enum.Enum):
    """Supported sources for trend discovery."""
    X_TWITTER = "X"
    REUTERS = "Reuters"
    WSJ = "WSJ"
    TECHCRUNCH = "TechCrunch"
    BLOOMBERG = "Bloomberg"
    MANUAL = "Manual"

    def __str__(self):
        return self.value


# ==================== Models ====================

class Tweet(Base):
    """
    Stores scraped tweets with translation and publication status.

    Workflow:
    1. Scraper creates tweet with original_text and status=PENDING
    2. Processor translates to hebrew_draft, downloads media, sets status=PROCESSED
    3. Dashboard user approves, sets status=APPROVED
    4. Publisher posts to X, sets status=PUBLISHED

    Indexes:
    - status: Fast filtering by status (dashboard main query)
    - created_at: Date range queries and sorting
    - trend_topic: Group tweets by trend
    - composite (status, created_at): Optimized for dashboard pagination
    """
    __tablename__ = 'tweets'

    # Primary key
    id = Column(Integer, primary_key=True, autoincrement=True)

    # Source information
    source_url = Column(
        String(512),
        nullable=False,
        unique=True,  # Prevent duplicate tweets
        comment="Original X (Twitter) post URL"
    )

    # Content
    original_text = Column(
        Text,
        nullable=False,
        comment="Original English tweet content"
    )
    hebrew_draft = Column(
        Text,
        nullable=True,
        comment="Translated Hebrew content (populated by processor)"
    )

    # Media handling
    media_url = Column(
        String(1024),
        nullable=True,
        comment="Source URL for video/image (if exists)"
    )
    media_path = Column(
        String(512),
        nullable=True,
        comment="Local filesystem path to downloaded media (relative to data/media/)"
    )

    # Classification
    trend_topic = Column(
        String(256),
        nullable=True,
        index=True,  # NOTE: This standalone index may be redundant with the composite index 'ix_tweets_trend_status' (line 230).
                     # The composite index (trend_topic, status) can efficiently serve queries filtering by trend_topic alone (leftmost prefix).
                     # Consider removing this index if query patterns show the composite index covers all trend_topic lookups.
        comment="Associated trending topic"
    )

    # Status tracking
    status = Column(
        SQLEnum(TweetStatus),
        nullable=False,
        default=TweetStatus.PENDING,
        index=True,  # Critical index for dashboard filtering
        comment="Processing status in workflow"
    )
    error_message = Column(
        Text,
        nullable=True,
        comment="Error message if processing failed"
    )

    # Timestamps
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        index=True,  # Index for date range queries and sorting
        comment="When tweet was scraped"
    )
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        comment="Last modification timestamp"
    )

    # Composite indexes for optimized queries
    __table_args__ = (
        # Dashboard query: Filter by status + sort by date
        Index('ix_tweets_status_created', 'status', 'created_at'),
        # Trend analysis: Group by trend + filter by status
        Index('ix_tweets_trend_status', 'trend_topic', 'status'),
    )

    def __repr__(self):
        return (
            f"<Tweet(id={self.id}, status={self.status.value}, "
            f"trend='{self.trend_topic}', created={self.created_at})>"
        )

    def to_dict(self):
        """Convert model to dictionary for API responses."""
        return {
            'id': self.id,
            'source_url': self.source_url,
            'original_text': self.original_text,
            'hebrew_draft': self.hebrew_draft,
            'media_url': self.media_url,
            'media_path': self.media_path,
            'trend_topic': self.trend_topic,
            'status': self.status.value,
            'error_message': self.error_message,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }


class Trend(Base):
    """
    Stores discovered trending topics from various sources.

    Used to:
    - Track which topics are currently trending
    - Associate tweets with trends
    - Analyze trend patterns over time

    Indexes:
    - discovered_at: Sort by discovery time
    - source: Filter by source platform
    - composite (source, discovered_at): Latest trends per source
    """
    __tablename__ = 'trends'

    # Primary key
    id = Column(Integer, primary_key=True, autoincrement=True)

    # Trend information
    title = Column(
        String(256),
        nullable=False,
        index=True,  # Fast lookup by trend name
        comment="Trend name/hashtag"
    )
    description = Column(
        Text,
        nullable=True,
        comment="Description of what's trending (if available)"
    )

    # Source tracking
    source = Column(
        SQLEnum(TrendSource),
        nullable=False,
        default=TrendSource.X_TWITTER,
        index=True,  # Filter by source
        comment="Platform where trend was discovered"
    )

    # Timestamp
    discovered_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        index=True,  # Sort by discovery time
        comment="When trend was first detected"
    )

    # Composite indexes
    __table_args__ = (
        # Query latest trends per source
        Index('ix_trends_source_discovered', 'source', 'discovered_at'),
        # Prevent duplicate trends from same source on same day
        Index('ix_trends_unique_title_source', 'title', 'source', 'discovered_at'),
    )

    def __repr__(self):
        return (
            f"<Trend(id={self.id}, title='{self.title}', "
            f"source={self.source.value}, discovered={self.discovered_at})>"
        )

    def to_dict(self):
        """Convert model to dictionary for API responses."""
        return {
            'id': self.id,
            'title': self.title,
            'description': self.description,
            'source': self.source.value,
            'discovered_at': self.discovered_at.isoformat() if self.discovered_at else None,
        }


# ==================== Database Utilities ====================

def create_tables(drop_existing: bool = False):
    """
    Initialize database schema.

    Args:
        drop_existing: If True, drop all existing tables before creating.
                      USE WITH CAUTION - will delete all data!

    Raises:
        Exception: If table creation fails

    Example:
        >>> create_tables()
        Database tables created successfully
    """
    try:
        if drop_existing:
            logger.warning("Dropping all existing tables...")
            Base.metadata.drop_all(bind=engine)

        logger.info("Creating database tables...")
        Base.metadata.create_all(bind=engine)
        logger.info(f"Database tables created successfully at: {DATABASE_URL}")

    except Exception as e:
        logger.error(f"Failed to create database tables: {e}")
        raise


@contextmanager
def get_db() -> Generator[Session, None, None]:
    """
    Dependency injection pattern for database sessions.

    Provides a context-managed database session with automatic
    cleanup and error handling.

    Yields:
        Session: SQLAlchemy database session

    Example:
        >>> with get_db() as db:
        ...     tweets = db.query(Tweet).filter_by(status=TweetStatus.PENDING).all()
        ...     print(f"Found {len(tweets)} pending tweets")

    Note:
        - Automatically commits on success
        - Automatically rolls back on error
        - Always closes session in finally block
    """
    db = SessionLocal()
    try:
        yield db
        db.commit()  # Commit if no exceptions
    except Exception as e:
        db.rollback()  # Rollback on error
        logger.error(f"Database session error: {e}")
        raise
    finally:
        db.close()  # Always close session


def get_db_session() -> Session:
    """
    Create a new database session.

    Returns:
        Session: SQLAlchemy database session

    Note:
        Caller is responsible for closing the session.
        Consider using get_db() context manager instead.

    Example:
        >>> db = get_db_session()
        >>> try:
        ...     tweets = db.query(Tweet).all()
        >>> finally:
        ...     db.close()
    """
    return SessionLocal()


def init_db():
    """
    Initialize database with default configuration.

    This is the main entry point for database initialization.
    Call this once during application startup.

    Example:
        >>> if __name__ == "__main__":
        ...     init_db()
        ...     print("Database ready!")
    """
    logger.info(f"Initializing database: {DATABASE_URL}")
    create_tables()
    logger.info("Database initialization complete")


# ==================== Query Helpers ====================

def get_tweets_by_status(
    db: Session,
    status: TweetStatus,
    limit: Optional[int] = None,
    offset: int = 0
) -> list[Tweet]:
    """
    Retrieve tweets filtered by status.

    Args:
        db: Database session
        status: Tweet status to filter by
        limit: Maximum number of tweets to return (None = all)
        offset: Number of tweets to skip (for pagination)

    Returns:
        List of Tweet objects matching the status

    Example:
        >>> with get_db() as db:
        ...     pending = get_tweets_by_status(db, TweetStatus.PENDING, limit=10)
        ...     for tweet in pending:
        ...         print(f"Tweet {tweet.id}: {tweet.original_text[:50]}...")
    """
    query = db.query(Tweet).filter(Tweet.status == status).order_by(Tweet.created_at.desc())

    if limit:
        query = query.limit(limit)

    if offset:
        query = query.offset(offset)

    return query.all()


def get_recent_trends(
    db: Session,
    source: Optional[TrendSource] = None,
    limit: int = 10
) -> list[Trend]:
    """
    Retrieve recent trends, optionally filtered by source.

    Args:
        db: Database session
        source: Trend source to filter by (None = all sources)
        limit: Maximum number of trends to return

    Returns:
        List of Trend objects, newest first

    Example:
        >>> with get_db() as db:
        ...     trends = get_recent_trends(db, TrendSource.X_TWITTER, limit=5)
        ...     for trend in trends:
        ...         print(f"Trending: {trend.title}")
    """
    query = db.query(Trend).order_by(Trend.discovered_at.desc())

    if source:
        query = query.filter(Trend.source == source)

    return query.limit(limit).all()


def update_tweet_status(
    db: Session,
    tweet_id: int,
    new_status: TweetStatus,
    hebrew_draft: Optional[str] = None,
    media_path: Optional[str] = None
) -> Optional[Tweet]:
    """
    Update tweet status and optionally update content fields.

    Args:
        db: Database session
        tweet_id: ID of tweet to update
        new_status: New status to set
        hebrew_draft: Optional updated Hebrew translation
        media_path: Optional updated media file path

    Returns:
        Updated Tweet object, or None if not found

    Example:
        >>> with get_db() as db:
        ...     tweet = update_tweet_status(
        ...         db,
        ...         tweet_id=1,
        ...         new_status=TweetStatus.PROCESSED,
        ...         hebrew_draft="תרגום עברי כאן"
        ...     )
        ...     if tweet:
        ...         print(f"Updated tweet {tweet.id} to {tweet.status}")
    """
    tweet = db.query(Tweet).filter(Tweet.id == tweet_id).first()

    if not tweet:
        logger.warning(f"Tweet {tweet_id} not found")
        return None

    # Update status
    tweet.status = new_status

    # Update optional fields if provided
    if hebrew_draft is not None:
        tweet.hebrew_draft = hebrew_draft

    if media_path is not None:
        tweet.media_path = media_path

    # updated_at will be automatically updated by onupdate
    db.commit()
    db.refresh(tweet)

    logger.info(f"Updated tweet {tweet_id} to status {new_status}")
    return tweet


# ==================== Health Check ====================

def health_check() -> dict:
    """
    Verify database connectivity and return statistics.

    Returns:
        Dictionary with health check results

    Example:
        >>> health = health_check()
        >>> if health['status'] == 'healthy':
        ...     print(f"Database OK: {health['tweet_count']} tweets")
    """
    try:
        with get_db() as db:
            tweet_count = db.query(Tweet).count()
            trend_count = db.query(Trend).count()

            # Count tweets by status
            status_counts = {}
            for status in TweetStatus:
                count = db.query(Tweet).filter(Tweet.status == status).count()
                status_counts[status.value] = count

            return {
                'status': 'healthy',
                'database_url': DATABASE_URL.split('?')[0],  # Hide sensitive params
                'tweet_count': tweet_count,
                'trend_count': trend_count,
                'status_breakdown': status_counts,
            }
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return {
            'status': 'unhealthy',
            'error': str(e),
        }


# ==================== Script Execution ====================

if __name__ == "__main__":
    """
    Initialize database when run as a script.

    Usage:
        python models.py
    """
    print("=" * 60)
    print("Hebrew FinTech Informant - Database Initialization")
    print("=" * 60)

    # Initialize database
    init_db()

    # Run health check
    health = health_check()
    print("\nHealth Check Results:")
    print(f"  Status: {health['status']}")
    print(f"  Database: {health.get('database_url', 'N/A')}")
    print(f"  Tweets: {health.get('tweet_count', 0)}")
    print(f"  Trends: {health.get('trend_count', 0)}")

    if health.get('status_breakdown'):
        print("\n  Tweet Status Breakdown:")
        for status, count in health['status_breakdown'].items():
            print(f"    {status}: {count}")

    print("\n" + "=" * 60)
    print("Database ready for use!")
    print("=" * 60)
