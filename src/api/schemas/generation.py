"""Schemas for generation and translation APIs."""

from typing import Optional, List
from urllib.parse import urlparse

from pydantic import BaseModel, Field, model_validator, field_validator


class GeneratePostRequest(BaseModel):
    source_text: str = Field(..., min_length=1)
    num_variants: int = Field(3, ge=1, le=3)
    angles: Optional[List[str]] = None


class GenerateThreadRequest(BaseModel):
    source_text: str = Field(..., min_length=1)
    num_tweets: int = Field(3, ge=2, le=5)
    angle: str = "educational"


class TranslateRequest(BaseModel):
    text: Optional[str] = None
    url: Optional[str] = None

    @field_validator("url")
    @classmethod
    def _validate_url(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        parsed = urlparse(value.strip())
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("url must be a valid http/https URL")
        if parsed.username or parsed.password:
            raise ValueError("url must not include credentials")
        return value.strip()

    @model_validator(mode="after")
    def _validate_source(self):
        if not self.text and not self.url:
            raise ValueError("Provide text or url")
        return self


class VariantResponse(BaseModel):
    angle: str
    label: str
    content: str
    char_count: int
    is_valid_hebrew: bool
    quality_score: int


class GeneratePostResponse(BaseModel):
    variants: List[VariantResponse]


class GenerateThreadResponse(BaseModel):
    tweets: List[dict]


class TranslateResponse(BaseModel):
    hebrew_text: str
    original_text: str
    source_type: Optional[str] = None
