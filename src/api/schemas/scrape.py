"""Schemas for scrape and content-from-thread APIs."""

from typing import Any, Optional, List, Literal

from pydantic import BaseModel, Field, field_validator

from common.url_validation import URLValidationError, validate_https_url


class ScrapeUrlRequest(BaseModel):
    url: str = Field(..., min_length=1, max_length=1024)

    @field_validator("url")
    @classmethod
    def _validate_url(cls, value: str) -> str:
        try:
            return validate_https_url(value)
        except URLValidationError as exc:
            raise ValueError(str(exc)) from exc


class ScrapeTrendsRequest(BaseModel):
    limit: int = Field(default=10, ge=1, le=30)


class ScrapedTweetResponse(BaseModel):
    text: Optional[str] = None
    media_url: Optional[str] = None
    author: Optional[str] = None
    timestamp: Optional[str] = None
    source_url: Optional[str] = None
    scraped_at: Optional[str] = None


class ScrapedThreadResponse(BaseModel):
    source_url: str
    author_handle: Optional[str] = None
    author_name: Optional[str] = None
    tweet_count: int = 0
    tweets: List[dict[str, Any]] = []
    scraped_at: Optional[str] = None


class ScrapedTrendResponse(BaseModel):
    title: str
    description: str = ""
    category: str = "Trending"
    scraped_at: Optional[str] = None


class ScrapeTrendsResponse(BaseModel):
    trends: List[ScrapedTrendResponse]
    count: int


ContentFromThreadMode = Literal["consolidated", "separate"]


class ContentFromThreadRequest(BaseModel):
    url: str = Field(..., min_length=1, max_length=1024)
    mode: ContentFromThreadMode = "consolidated"
    auto_translate: bool = True
    download_media: bool = False

    @field_validator("url")
    @classmethod
    def _validate_url(cls, value: str) -> str:
        try:
            return validate_https_url(value)
        except URLValidationError as exc:
            raise ValueError(str(exc)) from exc


class ContentFromThreadResponse(BaseModel):
    mode: str
    thread_url: str
    tweet_count: int
    saved_items: List[dict[str, Any]]
