"""
Pydantic schemas for Trend API endpoints.

Defines request/response models for FastAPI validation and documentation.

Author: HFI Development Team
Last Updated: 2026-02-01
"""

from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel, Field, HttpUrl, ConfigDict


class TrendBase(BaseModel):
    """Base schema for Trend attributes."""
    title: str = Field(..., max_length=256, description="Trend title or article headline")
    description: Optional[str] = Field(None, description="Article description or excerpt")
    article_url: Optional[HttpUrl] = Field(None, description="Original article URL")
    source: str = Field(..., description="Source platform (Yahoo Finance, WSJ, etc.)")


class TrendCreate(TrendBase):
    """Schema for creating a new trend."""
    pass


class TrendUpdate(BaseModel):
    """Schema for updating a trend."""
    title: Optional[str] = Field(None, max_length=256)
    description: Optional[str] = None
    article_url: Optional[HttpUrl] = None
    summary: Optional[str] = None
    keywords: Optional[List[str]] = None
    source_count: Optional[int] = None
    related_trend_ids: Optional[List[int]] = None


class TrendResponse(TrendBase):
    """Schema for trend response (includes all fields)."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    summary: Optional[str] = Field(None, description="AI-generated 1-2 sentence summary")
    keywords: Optional[List[str]] = Field(None, description="Extracted keywords from title")
    source_count: int = Field(1, description="Number of sources mentioning this trend")
    related_trend_ids: Optional[List[int]] = Field(None, description="IDs of related trends")
    discovered_at: datetime = Field(..., description="When trend was discovered")


class TrendListResponse(BaseModel):
    """Paginated list of trends."""
    trends: List[TrendResponse]
    total: int = Field(..., description="Total number of trends matching filters")
    page: int = Field(..., description="Current page number (1-indexed)")
    per_page: int = Field(..., description="Number of items per page")
    total_pages: int = Field(..., description="Total number of pages")


class SummaryGenerateRequest(BaseModel):
    """Request to generate summary for a trend."""
    force: bool = Field(False, description="Force regeneration even if summary exists")


class SummaryGenerateResponse(BaseModel):
    """Response from summary generation."""
    trend_id: int
    summary: str
    keywords: List[str]
    source_count: int
    related_trend_ids: List[int]


class BulkSummaryGenerateResponse(BaseModel):
    """Response from bulk summary generation."""
    success: int = Field(..., description="Number of trends processed successfully")
    failed: int = Field(..., description="Number of trends that failed processing")
    skipped: int = Field(..., description="Number of trends skipped (already have summaries)")
