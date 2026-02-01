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

__all__ = [
    'TrendResponse',
    'TrendListResponse',
    'TrendCreate',
    'TrendUpdate',
    'SummaryGenerateRequest',
    'SummaryGenerateResponse',
    'BulkSummaryGenerateResponse'
]
