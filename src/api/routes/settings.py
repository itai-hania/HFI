"""Settings endpoints for glossary, style examples, and user preferences."""

import json
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from api.dependencies import get_db, require_jwt
from api.schemas.settings import (
    GlossaryResponse,
    GlossaryUpdateRequest,
    PreferencesResponse,
    PreferencesUpdateRequest,
    StyleExampleCreate,
    StyleExampleUpdate,
    StyleExampleListResponse,
    StyleExampleResponse,
)
from common.models import StyleExample, UserPreference

router = APIRouter(
    prefix="/api/settings",
    tags=["settings"],
    dependencies=[Depends(require_jwt)],
)

_GLOSSARY_PATH = Path(__file__).resolve().parents[3] / "config" / "glossary.json"


@router.get("/glossary", response_model=GlossaryResponse)
def get_glossary():
    """Return glossary terms from config file."""
    if not _GLOSSARY_PATH.exists():
        return GlossaryResponse(terms={})

    try:
        with _GLOSSARY_PATH.open("r", encoding="utf-8") as file:
            payload = json.load(file)
    except (json.JSONDecodeError, OSError) as exc:
        raise HTTPException(status_code=500, detail=f"Failed to read glossary: {exc}") from exc

    if not isinstance(payload, dict):
        raise HTTPException(status_code=500, detail="Glossary must be a JSON object")

    return GlossaryResponse(terms=payload)


@router.put("/glossary", response_model=GlossaryResponse)
def update_glossary(request: GlossaryUpdateRequest):
    """Persist glossary terms to config file."""
    _GLOSSARY_PATH.parent.mkdir(parents=True, exist_ok=True)

    with _GLOSSARY_PATH.open("w", encoding="utf-8") as file:
        json.dump(request.terms, file, ensure_ascii=False, indent=2, sort_keys=True)

    return GlossaryResponse(terms=request.terms)


@router.get("/preferences", response_model=PreferencesResponse)
def get_preferences(db: Session = Depends(get_db)):
    """Fetch all user preferences as a single object."""
    rows = db.query(UserPreference).all()
    return PreferencesResponse(preferences={row.key: row.value for row in rows})


@router.put("/preferences", response_model=PreferencesResponse)
def update_preferences(request: PreferencesUpdateRequest, db: Session = Depends(get_db)):
    """Upsert preference keys."""
    if not request.preferences:
        return PreferencesResponse(preferences={})

    keys = list(request.preferences.keys())
    existing_rows = db.query(UserPreference).filter(UserPreference.key.in_(keys)).all()
    existing_map = {row.key: row for row in existing_rows}

    for key, value in request.preferences.items():
        row = existing_map.get(key)
        if row is not None:
            row.value = value
        else:
            db.add(UserPreference(key=key, value=value))

    db.commit()
    return PreferencesResponse(preferences=request.preferences)


@router.get("/style-examples", response_model=StyleExampleListResponse)
def list_style_examples(db: Session = Depends(get_db)):
    """List style examples used by generator/translator prompts."""
    rows = db.query(StyleExample).order_by(StyleExample.created_at.desc()).all()
    return StyleExampleListResponse(items=rows)


@router.post("/style-examples", response_model=StyleExampleResponse, status_code=201)
def add_style_example(request: StyleExampleCreate, db: Session = Depends(get_db)):
    """Create a new style example."""
    content = request.content.strip()
    word_count = len(content.split())

    row = StyleExample(
        content=content,
        topic_tags=request.topic_tags,
        source_type=request.source_type,
        source_url=request.source_url,
        word_count=word_count,
        is_active=request.is_active,
    )

    db.add(row)
    db.commit()
    db.refresh(row)
    return row


@router.patch("/style-examples/{example_id}", response_model=StyleExampleResponse)
def update_style_example(example_id: int, request: StyleExampleUpdate, db: Session = Depends(get_db)):
    """Update style example fields."""
    row = db.get(StyleExample, example_id)
    if not row:
        raise HTTPException(status_code=404, detail="Style example not found")

    payload = request.model_dump(exclude_unset=True)
    if "content" in payload and payload["content"] is not None:
        payload["content"] = payload["content"].strip()
        payload["word_count"] = len(payload["content"].split())

    for field, value in payload.items():
        setattr(row, field, value)

    db.commit()
    db.refresh(row)
    return row
