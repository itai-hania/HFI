"""
HFI Common Module

Shared database models and utilities for the Hebrew FinTech Informant application.
"""

from .models import (
    # Database setup
    Base,
    engine,
    SessionLocal,
    DATABASE_URL,

    # Models
    Tweet,
    Trend,
    StyleExample,
    InspirationAccount,
    InspirationPost,
    Notification,
    UserPreference,

    # Enums
    TweetStatus,
    TrendSource,

    # Database utilities
    create_tables,
    init_db,
    get_db,
    get_db_session,

    # Health check
    health_check,
)

__all__ = [
    # Database setup
    'Base',
    'engine',
    'SessionLocal',
    'DATABASE_URL',

    # Models
    'Tweet',
    'Trend',
    'StyleExample',
    'InspirationAccount',
    'InspirationPost',
    'Notification',
    'UserPreference',

    # Enums
    'TweetStatus',
    'TrendSource',

    # Database utilities
    'create_tables',
    'init_db',
    'get_db',
    'get_db_session',

    # Health check
    'health_check',
]

__version__ = '1.0.0'
