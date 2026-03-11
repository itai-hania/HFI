"""Schemas for content CRUD APIs."""

from datetime import datetime
from typing import Any, Optional, List, Literal

from pydantic import BaseModel, Field, ConfigDict, field_validator

from common.url_validation import URLValidationError, validate_https_url


ContentStatus = Literal["pending", "processed", "approved", "published", "failed"]


class ContentCreate(BaseModel):
    source_url: str = Field(..., min_length=1, max_length=1024)
    original_text: str = Field(..., min_length=1)
    hebrew_draft: Optional[str] = None
    content_type: str = "translation"
    trend_topic: Optional[str] = None
    scheduled_at: Optional[datetime] = None
    status: Optional[ContentStatus] = None
    generation_metadata: Optional[dict[str, Any]] = None

    @field_validator("source_url")
    @classmethod
    def _validate_source_url(cls, value: str) -> str:
        try:
            return validate_https_url(value)
        except URLValidationError as exc:
            raise ValueError(str(exc)) from exc


class ContentUpdate(BaseModel):
    hebrew_draft: Optional[str] = None
    status: Optional[ContentStatus] = None
    scheduled_at: Optional[datetime] = None
    trend_topic: Optional[str] = None
    generation_metadata: Optional[dict[str, Any]] = None


class ContentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    source_url: str
    source_domain: Optional[str] = None
    original_text: str
    hebrew_draft: Optional[str] = None
    content_type: str
    status: str
    trend_topic: Optional[str] = None
    copy_count: int
    scheduled_at: Optional[datetime] = None
    generation_metadata: Optional[dict[str, Any]] = None
    created_at: datetime
    updated_at: Optional[datetime] = None


class ContentListResponse(BaseModel):
    items: List[ContentResponse]
    total: int
    page: int
    per_page: int
