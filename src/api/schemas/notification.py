"""Schemas for notifications endpoints."""

from datetime import datetime
from typing import Any, Dict, List

from pydantic import BaseModel, ConfigDict, Field


class BriefStory(BaseModel):
    title: str
    summary: str
    sources: List[str]
    source_urls: List[str] = Field(default_factory=list)
    source_count: int
    published_at: datetime | None = None
    relevance_score: int = 0


class BriefResponse(BaseModel):
    stories: List[BriefStory]


class NotificationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    type: str
    content: Dict[str, Any]
    delivered: bool
    delivered_at: datetime | None = None
    created_at: datetime


class NotificationListResponse(BaseModel):
    alerts: List[NotificationResponse]


class NotificationDeliveredResponse(BaseModel):
    id: int
    delivered: bool
    delivered_at: datetime | None = None
