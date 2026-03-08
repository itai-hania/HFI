"""Schemas for settings endpoints."""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, ConfigDict, field_validator


class GlossaryResponse(BaseModel):
    terms: Dict[str, str]


class GlossaryUpdateRequest(BaseModel):
    terms: Dict[str, str]

    @field_validator("terms")
    @classmethod
    def _validate_terms(cls, terms: Dict[str, str]) -> Dict[str, str]:
        if len(terms) > 2000:
            raise ValueError("Too many glossary terms")
        normalized: Dict[str, str] = {}
        for key, value in terms.items():
            clean_key = key.strip()
            clean_value = value.strip()
            if not clean_key:
                continue
            if len(clean_key) > 128:
                raise ValueError("Glossary key too long")
            if len(clean_value) > 256:
                raise ValueError("Glossary value too long")
            normalized[clean_key] = clean_value
        return normalized


class PreferencesResponse(BaseModel):
    preferences: Dict[str, Any]


class PreferencesUpdateRequest(BaseModel):
    preferences: Dict[str, Any]

    @field_validator("preferences")
    @classmethod
    def _validate_preferences(cls, preferences: Dict[str, Any]) -> Dict[str, Any]:
        if len(preferences) > 100:
            raise ValueError("Too many preference keys")
        for key in preferences:
            if len(str(key).strip()) > 128:
                raise ValueError("Preference key too long")
        return preferences


class StyleExampleCreate(BaseModel):
    content: str = Field(..., min_length=1, max_length=5000)
    topic_tags: Optional[List[str]] = None
    source_type: str = "manual"
    source_url: Optional[str] = None
    is_active: bool = True


class StyleExampleUpdate(BaseModel):
    content: Optional[str] = Field(None, min_length=1, max_length=5000)
    topic_tags: Optional[List[str]] = None
    source_type: Optional[str] = None
    source_url: Optional[str] = None
    is_active: Optional[bool] = None


class StyleExampleResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    content: str
    source_type: str
    source_url: Optional[str] = None
    topic_tags: Optional[List[str]] = None
    word_count: int
    is_active: bool
    approval_count: int
    rejection_count: int
    created_at: datetime


class StyleExampleListResponse(BaseModel):
    items: List[StyleExampleResponse]
