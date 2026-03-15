"""Schemas for notifications endpoints."""

from datetime import datetime
from typing import Any, Dict, List, Literal

from pydantic import BaseModel, ConfigDict, Field


class BriefStory(BaseModel):
    title: str
    summary: str
    sources: List[str]
    source_urls: List[str] = Field(default_factory=list)
    source_count: int
    published_at: datetime | None = None
    relevance_score: int = 0


class BriefTheme(BaseModel):
    name: str
    emoji: str
    takeaway: str
    stories: List[BriefStory]


class BriefResponse(BaseModel):
    themes: List[BriefTheme] = Field(default_factory=list)
    stories: List[BriefStory]
    generated_at: datetime | None = None


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


class BriefFeedbackRequest(BaseModel):
    story_title: str = Field(max_length=500)
    feedback_type: Literal["not_relevant"] = "not_relevant"
    keywords: List[str] = Field(default_factory=list)
    source: Literal["dashboard", "telegram"] = "dashboard"


class BriefFeedbackWeightsResponse(BaseModel):
    excluded_keywords: List[str]
    keyword_counts: Dict[str, int]
