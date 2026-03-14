"""Schemas for generation and translation APIs."""

from typing import Optional, List

from pydantic import BaseModel, Field, model_validator, field_validator

from common.url_validation import URLValidationError, validate_https_url


class GeneratePostRequest(BaseModel):
    source_text: str = Field(..., min_length=1)
    num_variants: int = Field(3, ge=1, le=3)
    angles: Optional[List[str]] = None
    use_tweet_types: bool = False
    tweet_types: Optional[List[str]] = None
    humanize: Optional[bool] = None
    quality_gate: bool = False


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
        try:
            return validate_https_url(value)
        except URLValidationError as exc:
            raise ValueError(str(exc)) from exc

    @model_validator(mode="after")
    def _validate_source(self):
        if not self.text and not self.url:
            raise ValueError("Provide text or url")
        return self


class SourceResolveRequest(BaseModel):
    text: Optional[str] = None
    url: Optional[str] = None

    @field_validator("url")
    @classmethod
    def _validate_url(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        try:
            return validate_https_url(value)
        except URLValidationError as exc:
            raise ValueError(str(exc)) from exc

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
    title: Optional[str] = None
    canonical_url: Optional[str] = None
    source_domain: Optional[str] = None
    preview_text: Optional[str] = None


class SourceResolveResponse(BaseModel):
    source_type: str
    original_text: str
    title: Optional[str] = None
    canonical_url: Optional[str] = None
    source_domain: Optional[str] = None
    preview_text: str
