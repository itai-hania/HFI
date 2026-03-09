"""Pydantic schemas for API validation."""

from .trend import (
    TrendResponse,
    TrendListResponse,
    TrendCreate,
    TrendUpdate,
    SummaryGenerateRequest,
    SummaryGenerateResponse,
    BulkSummaryGenerateResponse
)
from .auth import LoginRequest, TokenResponse
from .content import (
    ContentCreate,
    ContentUpdate,
    ContentResponse,
    ContentListResponse,
)
from .generation import (
    GeneratePostRequest,
    GenerateThreadRequest,
    TranslateRequest,
    VariantResponse,
    GeneratePostResponse,
    GenerateThreadResponse,
    TranslateResponse,
)
from .inspiration import (
    InspirationAccountCreate,
    InspirationAccountUpdate,
    InspirationAccountResponse,
    InspirationAccountListResponse,
    InspirationSearchRequest,
    InspirationPostResponse,
    InspirationSearchResponse,
)
from .settings import (
    GlossaryResponse,
    GlossaryUpdateRequest,
    PreferencesResponse,
    PreferencesUpdateRequest,
    StyleExampleCreate,
    StyleExampleUpdate,
    StyleExampleResponse,
    StyleExampleListResponse,
)
from .notification import (
    BriefStory,
    BriefResponse,
    NotificationResponse,
    NotificationListResponse,
    NotificationDeliveredResponse,
)

__all__ = [
    'TrendResponse',
    'TrendListResponse',
    'TrendCreate',
    'TrendUpdate',
    'SummaryGenerateRequest',
    'SummaryGenerateResponse',
    'BulkSummaryGenerateResponse',
    'LoginRequest',
    'TokenResponse',
    'ContentCreate',
    'ContentUpdate',
    'ContentResponse',
    'ContentListResponse',
    'GeneratePostRequest',
    'GenerateThreadRequest',
    'TranslateRequest',
    'VariantResponse',
    'GeneratePostResponse',
    'GenerateThreadResponse',
    'TranslateResponse',
    'InspirationAccountCreate',
    'InspirationAccountUpdate',
    'InspirationAccountResponse',
    'InspirationAccountListResponse',
    'InspirationSearchRequest',
    'InspirationPostResponse',
    'InspirationSearchResponse',
    'GlossaryResponse',
    'GlossaryUpdateRequest',
    'PreferencesResponse',
    'PreferencesUpdateRequest',
    'StyleExampleCreate',
    'StyleExampleUpdate',
    'StyleExampleResponse',
    'StyleExampleListResponse',
    'BriefStory',
    'BriefResponse',
    'NotificationResponse',
    'NotificationListResponse',
    'NotificationDeliveredResponse',
]
