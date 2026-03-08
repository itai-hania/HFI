"""Schemas for content CRUD APIs."""

from datetime import datetime
from typing import Optional, List, Literal
from urllib.parse import urlparse

from pydantic import BaseModel, Field, ConfigDict, field_validator


ContentStatus = Literal["pending", "processed", "approved", "published", "failed"]


class ContentCreate(BaseModel):
    source_url: str = Field(..., min_length=1, max_length=1024)
    original_text: str = Field(..., min_length=1)
    hebrew_draft: Optional[str] = None
    content_type: str = "translation"
    trend_topic: Optional[str] = None
    scheduled_at: Optional[datetime] = None
    status: Optional[ContentStatus] = None

    @field_validator("source_url")
    @classmethod
    def _validate_source_url(cls, value: str) -> str:
        parsed = urlparse(value.strip())
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("source_url must be a valid http/https URL")
        if parsed.username or parsed.password:
            raise ValueError("source_url must not include credentials")
        return value.strip()


class ContentUpdate(BaseModel):
    hebrew_draft: Optional[str] = None
    status: Optional[ContentStatus] = None
    scheduled_at: Optional[datetime] = None
    trend_topic: Optional[str] = None


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
    created_at: datetime
    updated_at: Optional[datetime] = None


class ContentListResponse(BaseModel):
    items: List[ContentResponse]
    total: int
    page: int
    per_page: int
