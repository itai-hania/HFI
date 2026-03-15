"""Schemas for inspiration endpoints."""

from datetime import datetime
from typing import Optional, List

from pydantic import BaseModel, Field, ConfigDict, field_validator

_USERNAME_ALLOWED = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_")


def _normalize_username(value: str) -> str:
    username = value.strip().lstrip("@")
    if not username:
        raise ValueError("username is required")
    if len(username) > 256:
        raise ValueError("username too long")
    if any(ch not in _USERNAME_ALLOWED for ch in username):
        raise ValueError("username contains invalid characters")
    return username


class InspirationAccountCreate(BaseModel):
    username: str = Field(..., min_length=1, max_length=256)
    display_name: Optional[str] = Field(None, max_length=256)
    category: Optional[str] = Field(None, max_length=100)
    is_active: bool = True

    @field_validator("username")
    @classmethod
    def _validate_username(cls, value: str) -> str:
        return _normalize_username(value)


class InspirationAccountUpdate(BaseModel):
    display_name: Optional[str] = Field(None, max_length=256)
    category: Optional[str] = Field(None, max_length=100)
    is_active: Optional[bool] = None


class InspirationAccountResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    display_name: Optional[str] = None
    category: Optional[str] = None
    is_active: bool
    created_at: datetime


class InspirationAccountListResponse(BaseModel):
    accounts: List[InspirationAccountResponse]


class InspirationSearchRequest(BaseModel):
    username: str = Field(..., min_length=1)
    min_likes: int = Field(100, ge=0)
    keyword: str = ""
    limit: int = Field(20, ge=1, le=100)
    since: Optional[str] = Field(None, description="Date filter since YYYY-MM-DD")
    until: Optional[str] = Field(None, description="Date filter until YYYY-MM-DD")
    sort_by: str = Field("top", description="Sort mode: 'top' (engagement) or 'latest' (chronological)")

    @field_validator("username")
    @classmethod
    def _validate_username(cls, value: str) -> str:
        return _normalize_username(value)

    @field_validator("sort_by")
    @classmethod
    def _validate_sort_by(cls, value: str) -> str:
        if value not in ("top", "latest"):
            raise ValueError("sort_by must be 'top' or 'latest'")
        return value


class InspirationPostResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    account_id: int
    x_post_id: str
    content: Optional[str] = None
    post_url: Optional[str] = None
    likes: int
    retweets: int
    views: int
    posted_at: Optional[datetime] = None
    fetched_at: datetime


class InspirationSearchResponse(BaseModel):
    posts: List[InspirationPostResponse]
    cached: bool
    query: str
