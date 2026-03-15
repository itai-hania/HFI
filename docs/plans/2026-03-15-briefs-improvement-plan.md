# Briefs Improvement Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Upgrade briefs with AI-powered themed sections, inline one-tap Hebrew drafts, and story feedback/personalization — mirrored on both Dashboard and Telegram.

**Architecture:** A new `BriefThemer` module sits between the news scraper and the API response, grouping stories into AI-generated themes. The `BriefResponse` schema gains a `themes` list alongside the existing flat `stories` list. A new `BriefFeedback` model stores thumbs-down signals that dynamically adjust keyword scoring. The frontend renders themed cards with inline draft panels; Telegram formats themes with inline keyboard buttons.

**Tech Stack:** Python/FastAPI, OpenAI GPT-4o, SQLAlchemy, Next.js/React/TypeScript, Telegram Bot API (python-telegram-bot)

**Design doc:** `docs/plans/2026-03-15-briefs-improvement-design.md`

---

## Task 1: Add `BriefFeedback` DB Model

**Files:**
- Modify: `src/common/models.py` (after `Notification` class, ~L768)
- Test: `tests/test_brief_feedback_model.py`

**Step 1: Write the failing test**

```python
# tests/test_brief_feedback_model.py
"""Tests for BriefFeedback model."""

import pytest
from datetime import datetime, timezone

from common.models import Base, BriefFeedback, SessionLocal, engine


@pytest.fixture(autouse=True)
def _setup_tables():
    Base.metadata.create_all(engine)
    yield
    db = SessionLocal()
    db.query(BriefFeedback).delete()
    db.commit()
    db.close()


def test_create_brief_feedback():
    db = SessionLocal()
    try:
        fb = BriefFeedback(
            story_title="NVIDIA beats earnings expectations",
            feedback_type="not_relevant",
            keywords=["nvidia", "earnings"],
            source="dashboard",
        )
        db.add(fb)
        db.commit()
        db.refresh(fb)

        assert fb.id is not None
        assert fb.story_title == "NVIDIA beats earnings expectations"
        assert fb.feedback_type == "not_relevant"
        assert fb.keywords == ["nvidia", "earnings"]
        assert fb.source == "dashboard"
        assert isinstance(fb.created_at, datetime)
    finally:
        db.close()


def test_query_feedback_by_type():
    db = SessionLocal()
    try:
        db.add(BriefFeedback(story_title="Story A", feedback_type="not_relevant", keywords=["a"], source="telegram"))
        db.add(BriefFeedback(story_title="Story B", feedback_type="not_relevant", keywords=["b"], source="dashboard"))
        db.commit()

        results = db.query(BriefFeedback).filter_by(feedback_type="not_relevant").all()
        assert len(results) == 2
    finally:
        db.close()
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_brief_feedback_model.py -v`
Expected: FAIL with `ImportError: cannot import name 'BriefFeedback'`

**Step 3: Write minimal implementation**

Add to `src/common/models.py` after the `Notification` class (after line ~768):

```python
class BriefFeedback(Base):
    __tablename__ = "brief_feedback"

    id = Column(Integer, primary_key=True, autoincrement=True)
    story_title = Column(String(500), nullable=False)
    feedback_type = Column(String(20), nullable=False, index=True)
    keywords = Column(JSON, nullable=True)
    source = Column(String(50), nullable=False)
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        index=True,
    )
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_brief_feedback_model.py -v`
Expected: PASS (2 tests)

**Step 5: Commit**

```bash
git add src/common/models.py tests/test_brief_feedback_model.py
git commit -m "feat: add BriefFeedback database model"
```

---

## Task 2: Add `BriefTheme` Schema and Update `BriefResponse`

**Files:**
- Modify: `src/api/schemas/notification.py`
- Modify: `frontend/src/lib/types.ts`
- Test: `tests/test_api_notifications.py` (extend existing)

**Step 1: Write the failing test**

Add to `tests/test_api_notifications.py`:

```python
def test_brief_response_with_themes(client):
    """POST /api/notifications/brief returns themes when available."""
    response = client.post("/api/notifications/brief", params={"force_refresh": True})
    assert response.status_code == 200
    data = response.json()
    # Must have both themes and stories
    assert "themes" in data
    assert "stories" in data
    assert "generated_at" in data
    # stories is still a flat list for backward compat
    assert isinstance(data["stories"], list)
    assert isinstance(data["themes"], list)
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_api_notifications.py::test_brief_response_with_themes -v`
Expected: FAIL — `"themes"` not in response, `"generated_at"` not in response

**Step 3: Update the schema**

In `src/api/schemas/notification.py`, update to:

```python
"""Schemas for notifications endpoints."""

from datetime import datetime
from typing import Any, Dict, List, Optional

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
```

Update `frontend/src/lib/types.ts` — add `BriefTheme` and update `BriefResponse`:

```typescript
export interface BriefTheme {
  name: string;
  emoji: string;
  takeaway: string;
  stories: BriefStory[];
}

export interface BriefResponse {
  themes: BriefTheme[];
  stories: BriefStory[];
  generated_at?: string | null;
}
```

**Step 4: Update `_to_brief_response` and `generate_brief` in `src/api/routes/notifications.py`**

Update `_to_brief_response` (~L30):

```python
def _to_brief_response(row: Notification | None) -> BriefResponse:
    if row is None:
        raise HTTPException(status_code=404, detail="No stored brief found")
    content = row.content or {}
    stories_payload = content.get("stories", [])
    stories = [BriefStory.model_validate(item) for item in stories_payload if isinstance(item, dict)]
    if not stories:
        raise HTTPException(status_code=404, detail="No stored brief found")
    themes_payload = content.get("themes", [])
    themes = [BriefTheme.model_validate(item) for item in themes_payload if isinstance(item, dict)]
    generated_at = content.get("generated_at")
    return BriefResponse(themes=themes, stories=stories, generated_at=generated_at)
```

Update the import at top of file to include `BriefTheme`.

Update `generate_brief` (~L98–103) to include `generated_at` in payload:

```python
    generated_at = now.isoformat()
    payload = {
        "stories": [s.model_dump(mode="json") for s in stories],
        "themes": [],  # Empty until BriefThemer is integrated in Task 3
        "generated_at": generated_at,
    }
    row = Notification(type="brief", content=payload, delivered=False, created_at=now)
    db.add(row)
    db.commit()
    return BriefResponse(themes=[], stories=stories, generated_at=now)
```

**Step 5: Run test to verify it passes**

Run: `pytest tests/test_api_notifications.py -v`
Expected: ALL PASS (existing + new test)

**Step 6: Commit**

```bash
git add src/api/schemas/notification.py src/api/routes/notifications.py frontend/src/lib/types.ts tests/test_api_notifications.py
git commit -m "feat: add BriefTheme schema and generated_at to BriefResponse"
```

---

## Task 3: Build `BriefThemer` Module

**Files:**
- Create: `src/processor/brief_themer.py`
- Test: `tests/test_brief_themer.py`

**Step 1: Write the failing tests**

```python
# tests/test_brief_themer.py
"""Tests for BriefThemer — AI-powered story grouping."""

import json
import pytest
from unittest.mock import patch, MagicMock

from processor.brief_themer import BriefThemer


@pytest.fixture
def sample_stories():
    return [
        {"title": "NVIDIA beats earnings expectations", "summary": "Revenue surged 122%", "sources": ["Bloomberg", "CNBC"], "source_urls": ["https://b.com", "https://c.com"], "source_count": 2, "published_at": "2026-03-15T08:00:00+00:00", "relevance_score": 87},
        {"title": "OpenAI launches enterprise agents", "summary": "New AI platform for business", "sources": ["TechCrunch"], "source_urls": ["https://tc.com"], "source_count": 1, "published_at": "2026-03-15T07:00:00+00:00", "relevance_score": 65},
        {"title": "Israeli FinTech raises $50M", "summary": "Series C led by Sequoia", "sources": ["Investing.com", "Google News Israel"], "source_urls": ["https://inv.com", "https://gn.com"], "source_count": 2, "published_at": "2026-03-15T06:00:00+00:00", "relevance_score": 72},
        {"title": "Fed holds rates steady", "summary": "Markets rally on decision", "sources": ["CNBC", "MarketWatch"], "source_urls": ["https://cnbc.com", "https://mw.com"], "source_count": 2, "published_at": "2026-03-15T05:00:00+00:00", "relevance_score": 80},
    ]


def test_themer_returns_valid_structure(sample_stories):
    """Themes must have name, emoji, takeaway, and story_indices."""
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = json.dumps({
        "themes": [
            {"name": "AI Spending Surge", "emoji": "\U0001f916", "takeaway": "AI investment accelerating", "story_indices": [0, 1]},
            {"name": "Markets Digest Fed", "emoji": "\U0001f4b0", "takeaway": "Rate decision lifts stocks", "story_indices": [3]},
            {"name": "Israeli Tech Boom", "emoji": "\U0001f1ee\U0001f1f1", "takeaway": "Funding hits new high", "story_indices": [2]},
        ]
    })

    with patch("processor.brief_themer.OpenAI") as mock_openai:
        mock_openai.return_value.chat.completions.create.return_value = mock_response
        themer = BriefThemer()
        themes = themer.generate_themes(sample_stories)

    assert len(themes) == 3
    for theme in themes:
        assert "name" in theme
        assert "emoji" in theme
        assert "takeaway" in theme
        assert "stories" in theme
        assert len(theme["stories"]) > 0


def test_themer_fallback_on_api_error(sample_stories):
    """On OpenAI error, falls back to rule-based grouping."""
    with patch("processor.brief_themer.OpenAI") as mock_openai:
        mock_openai.return_value.chat.completions.create.side_effect = Exception("API down")
        themer = BriefThemer()
        themes = themer.generate_themes(sample_stories)

    # Fallback should still produce themes
    assert len(themes) >= 1
    for theme in themes:
        assert "name" in theme
        assert "stories" in theme


def test_themer_all_stories_assigned(sample_stories):
    """Every story must appear in exactly one theme."""
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = json.dumps({
        "themes": [
            {"name": "Tech", "emoji": "\U0001f916", "takeaway": "AI is hot", "story_indices": [0, 1]},
            {"name": "Finance", "emoji": "\U0001f4b0", "takeaway": "Fed holds", "story_indices": [3]},
            {"name": "Israel", "emoji": "\U0001f1ee\U0001f1f1", "takeaway": "Funding up", "story_indices": [2]},
        ]
    })

    with patch("processor.brief_themer.OpenAI") as mock_openai:
        mock_openai.return_value.chat.completions.create.return_value = mock_response
        themer = BriefThemer()
        themes = themer.generate_themes(sample_stories)

    all_titles = {s["title"] for s in sample_stories}
    themed_titles = set()
    for theme in themes:
        for story in theme["stories"]:
            themed_titles.add(story["title"])
    assert themed_titles == all_titles


def test_themer_handles_invalid_json(sample_stories):
    """Invalid JSON response triggers fallback."""
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = "not json at all"

    with patch("processor.brief_themer.OpenAI") as mock_openai:
        mock_openai.return_value.chat.completions.create.return_value = mock_response
        themer = BriefThemer()
        themes = themer.generate_themes(sample_stories)

    assert len(themes) >= 1
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_brief_themer.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'processor.brief_themer'`

**Step 3: Write the implementation**

```python
# src/processor/brief_themer.py
"""AI-powered brief story grouping into themes."""

import json
import logging
import os
from typing import Any, Dict, List

from openai import OpenAI

logger = logging.getLogger(__name__)

# Source → category mapping for fallback grouping
_SOURCE_CATEGORIES: Dict[str, str] = {
    "Yahoo Finance": "Finance",
    "CNBC": "Finance",
    "Bloomberg": "Finance",
    "MarketWatch": "Finance",
    "Seeking Alpha": "Finance",
    "TechCrunch": "Tech",
    "Investing.com": "Israel",
    "Google News Israel": "Israel",
    "Calcalist": "Israel",
    "Globes": "Israel",
    "Times of Israel": "Israel",
}

_CATEGORY_EMOJI: Dict[str, str] = {
    "Finance": "\U0001f4b0",
    "Tech": "\U0001f916",
    "Israel": "\U0001f1ee\U0001f1f1",
    "General": "\U0001f4ca",
}

_THEME_PROMPT = """You are a FinTech news editor. Group these stories into 2-4 coherent themes.

Stories:
{stories_text}

Return JSON with this exact structure:
{{
  "themes": [
    {{
      "name": "short punchy theme name (3-6 words)",
      "emoji": "single emoji",
      "takeaway": "one sentence insight — the 'so what'",
      "story_indices": [0, 2]
    }}
  ]
}}

Rules:
- Every story index (0 to {max_index}) must appear in exactly one theme
- 2-4 themes total
- Theme names should be engaging, not generic ("Chip War Heats Up", not "Technology")
- Takeaways should explain WHY this matters, not just restate the headline
- Return ONLY valid JSON, no markdown fences"""


class BriefThemer:
    def __init__(self):
        self._client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    def generate_themes(self, stories: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Group stories into AI-generated themes with names and takeaways.

        Falls back to rule-based grouping if the API call fails.
        """
        if not stories:
            return []

        try:
            return self._ai_themes(stories)
        except Exception:
            logger.warning("⚠️ AI theming failed, falling back to rule-based grouping", exc_info=True)
            return self._fallback_themes(stories)

    def _ai_themes(self, stories: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        stories_text = "\n".join(
            f"{i}. {s.get('title', '')} — {s.get('summary', '')[:100]}"
            for i, s in enumerate(stories)
        )
        prompt = _THEME_PROMPT.format(stories_text=stories_text, max_index=len(stories) - 1)

        response = self._client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            temperature=0.4,
            max_tokens=500,
            timeout=5,
        )

        raw = response.choices[0].message.content
        parsed = json.loads(raw)
        raw_themes = parsed.get("themes", [])

        if not raw_themes:
            raise ValueError("Empty themes array from API")

        return self._resolve_themes(raw_themes, stories)

    def _resolve_themes(
        self, raw_themes: List[Dict], stories: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Convert story_indices to actual story dicts, ensure all stories assigned."""
        assigned: set[int] = set()
        themes: List[Dict[str, Any]] = []

        for rt in raw_themes:
            indices = rt.get("story_indices", [])
            valid_indices = [i for i in indices if isinstance(i, int) and 0 <= i < len(stories) and i not in assigned]
            if not valid_indices:
                continue
            assigned.update(valid_indices)
            themes.append({
                "name": str(rt.get("name", "News")),
                "emoji": str(rt.get("emoji", "\U0001f4ca")),
                "takeaway": str(rt.get("takeaway", "")),
                "stories": [stories[i] for i in valid_indices],
            })

        # Assign any orphaned stories to the last theme
        orphans = [i for i in range(len(stories)) if i not in assigned]
        if orphans:
            if themes:
                themes[-1]["stories"].extend(stories[i] for i in orphans)
            else:
                themes.append({
                    "name": "News",
                    "emoji": "\U0001f4ca",
                    "takeaway": "",
                    "stories": [stories[i] for i in orphans],
                })

        return themes

    def _fallback_themes(self, stories: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Group stories by source category (Finance/Tech/Israel)."""
        groups: Dict[str, List[Dict[str, Any]]] = {}

        for story in stories:
            sources = story.get("sources", [])
            category = "General"
            for src in sources:
                if src in _SOURCE_CATEGORIES:
                    category = _SOURCE_CATEGORIES[src]
                    break
            groups.setdefault(category, []).append(story)

        themes = []
        for category in ["Finance", "Tech", "Israel", "General"]:
            cat_stories = groups.get(category, [])
            if not cat_stories:
                continue
            top_title = cat_stories[0].get("title", "")
            themes.append({
                "name": category,
                "emoji": _CATEGORY_EMOJI.get(category, "\U0001f4ca"),
                "takeaway": top_title[:80],
                "stories": cat_stories,
            })

        return themes
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_brief_themer.py -v`
Expected: PASS (4 tests)

**Step 5: Commit**

```bash
git add src/processor/brief_themer.py tests/test_brief_themer.py
git commit -m "feat: add BriefThemer for AI-powered story grouping"
```

---

## Task 4: Integrate `BriefThemer` into Brief Generation Route

**Files:**
- Modify: `src/api/routes/notifications.py` (~L63–103)
- Test: `tests/test_api_notifications.py` (extend)

**Step 1: Write the failing test**

Add to `tests/test_api_notifications.py`:

```python
def test_brief_themes_populated(client, monkeypatch):
    """Generated brief must contain non-empty themes."""
    import processor.brief_themer as bt

    def fake_themes(self, stories):
        return [
            {"name": "Test Theme", "emoji": "\U0001f4ca", "takeaway": "Test takeaway", "stories": stories}
        ]

    monkeypatch.setattr(bt.BriefThemer, "generate_themes", fake_themes)

    response = client.post("/api/notifications/brief", params={"force_refresh": True})
    assert response.status_code == 200
    data = response.json()
    assert len(data["themes"]) > 0
    assert data["themes"][0]["name"] == "Test Theme"
    assert data["themes"][0]["takeaway"] == "Test takeaway"
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_api_notifications.py::test_brief_themes_populated -v`
Expected: FAIL — themes is empty `[]`

**Step 3: Integrate BriefThemer into `generate_brief`**

In `src/api/routes/notifications.py`, update the `generate_brief` function. After building the `stories` list (~L96), add theming:

```python
    # Add import at top of file:
    from processor.brief_themer import BriefThemer

    # After stories list is built (after the for loop), add:
    themer = BriefThemer()
    story_dicts = [s.model_dump(mode="json") for s in stories]
    raw_themes = themer.generate_themes(story_dicts)

    themes = [
        BriefTheme(
            name=t["name"],
            emoji=t["emoji"],
            takeaway=t["takeaway"],
            stories=[BriefStory.model_validate(s) for s in t["stories"]],
        )
        for t in raw_themes
    ]

    generated_at = now.isoformat()
    payload = {
        "stories": story_dicts,
        "themes": [t.model_dump(mode="json") for t in themes],
        "generated_at": generated_at,
    }
    row = Notification(type="brief", content=payload, delivered=False, created_at=now)
    db.add(row)
    db.commit()
    return BriefResponse(themes=themes, stories=stories, generated_at=now)
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_api_notifications.py -v`
Expected: ALL PASS

**Step 5: Commit**

```bash
git add src/api/routes/notifications.py tests/test_api_notifications.py
git commit -m "feat: integrate BriefThemer into brief generation route"
```

---

## Task 5: Add Brief Feedback API Endpoints

**Files:**
- Modify: `src/api/routes/notifications.py`
- Modify: `src/api/schemas/notification.py`
- Test: `tests/test_api_notifications.py` (extend)

**Step 1: Write the failing tests**

Add to `tests/test_api_notifications.py`:

```python
def test_submit_brief_feedback(client):
    """POST /api/notifications/brief/feedback stores feedback."""
    response = client.post("/api/notifications/brief/feedback", json={
        "story_title": "NVIDIA beats earnings",
        "feedback_type": "not_relevant",
        "keywords": ["nvidia", "earnings"],
        "source": "dashboard",
    })
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"


def test_get_feedback_weights(client):
    """GET /api/notifications/brief/feedback/weights returns learned adjustments."""
    # Submit 3 feedbacks for same keyword to cross threshold
    for _ in range(3):
        client.post("/api/notifications/brief/feedback", json={
            "story_title": "Tariff news story",
            "feedback_type": "not_relevant",
            "keywords": ["tariff"],
            "source": "dashboard",
        })

    response = client.get("/api/notifications/brief/feedback/weights")
    assert response.status_code == 200
    data = response.json()
    assert "tariff" in data["excluded_keywords"]


def test_reset_feedback(client):
    """DELETE /api/notifications/brief/feedback resets all feedback."""
    client.post("/api/notifications/brief/feedback", json={
        "story_title": "Some story",
        "feedback_type": "not_relevant",
        "keywords": ["test"],
        "source": "dashboard",
    })
    response = client.delete("/api/notifications/brief/feedback")
    assert response.status_code == 200

    weights = client.get("/api/notifications/brief/feedback/weights")
    assert len(weights.json()["excluded_keywords"]) == 0
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/test_api_notifications.py::test_submit_brief_feedback -v`
Expected: FAIL — 404 (route doesn't exist)

**Step 3: Add schemas**

Add to `src/api/schemas/notification.py`:

```python
class BriefFeedbackRequest(BaseModel):
    story_title: str
    feedback_type: str = "not_relevant"
    keywords: List[str] = Field(default_factory=list)
    source: str = "dashboard"


class BriefFeedbackWeightsResponse(BaseModel):
    excluded_keywords: List[str]
    keyword_counts: Dict[str, int]
```

**Step 4: Add routes**

Add to `src/api/routes/notifications.py`:

```python
from common.models import BriefFeedback
from api.schemas.notification import BriefFeedbackRequest, BriefFeedbackWeightsResponse
from sqlalchemy import func


@router.post("/brief/feedback")
def submit_brief_feedback(request: BriefFeedbackRequest, db: Session = Depends(get_db)):
    """Store story feedback for personalization."""
    fb = BriefFeedback(
        story_title=request.story_title,
        feedback_type=request.feedback_type,
        keywords=request.keywords,
        source=request.source,
    )
    db.add(fb)
    db.commit()
    return {"status": "ok"}


@router.get("/brief/feedback/weights", response_model=BriefFeedbackWeightsResponse)
def get_feedback_weights(db: Session = Depends(get_db)):
    """Return learned keyword exclusions based on accumulated feedback."""
    rows = db.query(BriefFeedback).filter_by(feedback_type="not_relevant").all()
    keyword_counts: Dict[str, int] = {}
    for row in rows:
        for kw in (row.keywords or []):
            keyword_counts[kw] = keyword_counts.get(kw, 0) + 1
    excluded = [kw for kw, count in keyword_counts.items() if count >= 3]
    return BriefFeedbackWeightsResponse(excluded_keywords=excluded, keyword_counts=keyword_counts)


@router.delete("/brief/feedback")
def reset_feedback(db: Session = Depends(get_db)):
    """Clear all feedback data."""
    db.query(BriefFeedback).delete()
    db.commit()
    return {"status": "ok"}
```

**Step 5: Run tests to verify they pass**

Run: `pytest tests/test_api_notifications.py -v`
Expected: ALL PASS

**Step 6: Commit**

```bash
git add src/api/routes/notifications.py src/api/schemas/notification.py tests/test_api_notifications.py
git commit -m "feat: add brief feedback API endpoints"
```

---

## Task 6: Integrate Feedback into News Scraper Scoring

**Files:**
- Modify: `src/scraper/news_scraper.py` (~`_score_brief_cluster` and `get_brief_news`)
- Test: `tests/test_news_scraper_brief.py` (extend)

**Step 1: Write the failing test**

Add to `tests/test_news_scraper_brief.py`:

```python
def test_feedback_keywords_penalize_score():
    """Keywords with >= 3 'not_relevant' feedback get penalized in scoring."""
    from common.models import Base, BriefFeedback, SessionLocal, engine

    Base.metadata.create_all(engine)
    db = SessionLocal()
    try:
        # Add 3 feedbacks for "tariff"
        for _ in range(3):
            db.add(BriefFeedback(
                story_title="Tariff story",
                feedback_type="not_relevant",
                keywords=["tariff"],
                source="dashboard",
            ))
        db.commit()

        scraper = NewsScraper()
        feedback_excludes = scraper._load_feedback_excludes()
        assert "tariff" in feedback_excludes
    finally:
        db.query(BriefFeedback).delete()
        db.commit()
        db.close()
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_news_scraper_brief.py::test_feedback_keywords_penalize_score -v`
Expected: FAIL — `AttributeError: 'NewsScraper' object has no attribute '_load_feedback_excludes'`

**Step 3: Add feedback loading to NewsScraper**

Add to `src/scraper/news_scraper.py`:

```python
# Add import at top:
from common.models import BriefFeedback, SessionLocal

# Add method to NewsScraper class:
def _load_feedback_excludes(self) -> set[str]:
    """Load keywords that users have marked as not relevant (>= 3 times)."""
    db = SessionLocal()
    try:
        rows = db.query(BriefFeedback).filter_by(feedback_type="not_relevant").all()
        keyword_counts: dict[str, int] = {}
        for row in rows:
            for kw in (row.keywords or []):
                keyword_counts[kw] = keyword_counts.get(kw, 0) + 1
        return {kw for kw, count in keyword_counts.items() if count >= 3}
    finally:
        db.close()
```

In `get_brief_news`, before the scoring loop (~L316), load and merge feedback:

```python
    feedback_excludes = self._load_feedback_excludes()
    if feedback_excludes:
        logger.info(f"📊 Applying {len(feedback_excludes)} feedback-based keyword exclusions")
```

In `_score_brief_cluster`, accept an optional `extra_excludes: set[str]` parameter and add its penalty alongside existing `EXCLUDE_KEYWORDS`:

```python
@classmethod
def _score_brief_cluster(cls, cluster: Dict[str, Any], extra_excludes: set[str] | None = None) -> Dict[str, Any]:
```

In the relevance scoring section, merge `extra_excludes` with `EXCLUDE_KEYWORDS`:

```python
    all_excludes = cls.EXCLUDE_KEYWORDS | (extra_excludes or set())
    # Use all_excludes instead of cls.EXCLUDE_KEYWORDS in _cluster_relevance_score
```

Pass `feedback_excludes` through to scoring in `get_brief_news`:

```python
    ranked_clusters = [self._score_brief_cluster(cluster, extra_excludes=feedback_excludes) for cluster in clusters]
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_news_scraper_brief.py -v`
Expected: ALL PASS

**Step 5: Commit**

```bash
git add src/scraper/news_scraper.py tests/test_news_scraper_brief.py
git commit -m "feat: integrate feedback keyword exclusions into brief scoring"
```

---

## Task 7: Update Telegram Brief Format with Themed Sections

**Files:**
- Modify: `src/telegram_bot/bot.py` — `format_brief_message()` and `send_scheduled_brief()`
- Test: `tests/test_brief_telegram_format.py` (new)

**Step 1: Write the failing test**

```python
# tests/test_brief_telegram_format.py
"""Tests for themed Telegram brief formatting."""

from telegram_bot.bot import format_brief_message


def _make_themed_response():
    return {
        "themes": [
            {
                "name": "Chip War Heats Up",
                "emoji": "\U0001f916",
                "takeaway": "AI spending is accelerating",
                "stories": [
                    {"title": "NVIDIA beats earnings", "summary": "Revenue surged", "sources": ["Bloomberg"], "source_urls": ["https://b.com"], "source_count": 1, "published_at": "2026-03-15T08:00:00+00:00", "relevance_score": 87},
                ],
            },
            {
                "name": "Israeli Tech Boom",
                "emoji": "\U0001f1ee\U0001f1f1",
                "takeaway": "Funding hits new high",
                "stories": [
                    {"title": "FinTech raises $50M", "summary": "Series C led by Sequoia", "sources": ["Investing.com"], "source_urls": ["https://inv.com"], "source_count": 1, "published_at": "2026-03-15T06:00:00+00:00", "relevance_score": 72},
                ],
            },
        ],
        "stories": [
            {"title": "NVIDIA beats earnings", "summary": "Revenue surged", "sources": ["Bloomberg"], "source_urls": ["https://b.com"], "source_count": 1, "published_at": "2026-03-15T08:00:00+00:00", "relevance_score": 87},
            {"title": "FinTech raises $50M", "summary": "Series C led by Sequoia", "sources": ["Investing.com"], "source_urls": ["https://inv.com"], "source_count": 1, "published_at": "2026-03-15T06:00:00+00:00", "relevance_score": 72},
        ],
    }


def test_themed_format_contains_theme_headers():
    data = _make_themed_response()
    msg = format_brief_message(data["stories"], "morning", themes=data["themes"])
    assert "Chip War Heats Up" in msg
    assert "Israeli Tech Boom" in msg
    assert "AI spending is accelerating" in msg


def test_themed_format_continuous_numbering():
    data = _make_themed_response()
    msg = format_brief_message(data["stories"], "morning", themes=data["themes"])
    assert "<b>1.</b>" in msg
    assert "<b>2.</b>" in msg


def test_themed_format_footer():
    data = _make_themed_response()
    msg = format_brief_message(data["stories"], "morning", themes=data["themes"])
    assert "/write N" in msg
    assert "/skip N" in msg


def test_legacy_format_without_themes():
    """When themes is empty/None, falls back to flat list."""
    stories = [
        {"title": "Test story", "summary": "Summary", "sources": ["CNBC"], "source_urls": ["https://cnbc.com"], "source_count": 1, "relevance_score": 50},
    ]
    msg = format_brief_message(stories, "morning", themes=[])
    assert "<b>1.</b>" in msg
    assert "Test story" in msg
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_brief_telegram_format.py -v`
Expected: FAIL — `format_brief_message() got an unexpected keyword argument 'themes'`

**Step 3: Update `format_brief_message`**

In `src/telegram_bot/bot.py`, update the function signature and body:

```python
def format_brief_message(stories: List[dict], brief_type: str, themes: List[dict] | None = None) -> str:
    """Render stories as rich HTML for Telegram — themed if themes provided."""
    from datetime import datetime, timezone, timedelta

    if brief_type == "morning":
        header = "Morning Brief"
    elif brief_type == "evening":
        header = "Evening Brief"
    else:
        header = "Brief"

    now = datetime.now(timezone.utc)
    ist_now = now + timedelta(hours=2)
    timestamp = ist_now.strftime("%H:%M")

    lines = [f"\U0001f4ca <b>{header}</b> \u00b7 {len(stories)} stories \u00b7 {timestamp} IST", ""]

    israel_sources = {"calcalist", "globes", "times of israel"}

    if themes:
        story_index = 1
        for theme in themes:
            lines.append(f"{theme.get('emoji', '\U0001f4ca')} <b>{html.escape(theme.get('name', 'News'))}</b>")
            takeaway = theme.get("takeaway", "")
            if takeaway:
                lines.append(f"   {html.escape(takeaway)}")
            lines.append("")

            for story in theme.get("stories", []):
                lines.extend(_format_story_lines(story, story_index, now, israel_sources))
                story_index += 1
    else:
        for index, story in enumerate(stories, 1):
            lines.extend(_format_story_lines(story, index, now, israel_sources))

    lines.append("/write N \u00b7 /story N \u00b7 /skip N")
    return "\n".join(lines).strip()
```

Extract the per-story formatting into a helper `_format_story_lines()` to avoid duplication:

```python
def _format_story_lines(story: dict, index: int, now, israel_sources: set) -> List[str]:
    """Format a single story as HTML lines."""
    from datetime import datetime

    title = html.escape(str(story.get("title", "Untitled")))
    summary = html.escape(_safe_preview(str(story.get("summary", "")), max_chars=280))
    source_count = story.get("source_count", len(story.get("sources", [])))
    relevance = story.get("relevance_score", 0)
    sources = story.get("sources", [])
    source_urls = story.get("source_urls", [])

    age_str = ""
    published = story.get("published_at")
    if published:
        if isinstance(published, str):
            try:
                pub_dt = datetime.fromisoformat(published.replace("Z", "+00:00"))
                age_hours = (now - pub_dt).total_seconds() / 3600
                if age_hours < 1:
                    age_str = f"{int(age_hours * 60)}m ago"
                elif age_hours < 24:
                    age_str = f"{int(age_hours)}h ago"
                else:
                    age_str = f"{int(age_hours / 24)}d ago"
            except (ValueError, TypeError):
                pass

    is_israel = any(s.lower() in israel_sources for s in sources)
    badge = "\U0001f535 Israel" if is_israel else f"\U0001f3af {relevance}"

    source_names = [html.escape(s) for s in sources]

    lines = [f"<b>{index}.</b> <b>{title}</b>"]
    if summary:
        lines.append(f"   {summary}")
    meta_parts = []
    if age_str:
        meta_parts.append(f"\u23f1 {age_str}")
    meta_parts.append(f"\U0001f4e1 {source_count} sources")
    meta_parts.append(badge)
    lines.append("   " + " \u00b7 ".join(meta_parts))
    if source_names:
        lines.append("   " + " \u00b7 ".join(source_names))
    lines.append("")
    return lines
```

Update `send_scheduled_brief()` to pass themes:

```python
async def send_scheduled_brief(self):
    response = await self._request("POST", "/api/notifications/brief")
    data = response.json()
    stories = data.get("stories", [])
    themes = data.get("themes", [])
    if not stories:
        return

    self._state_for_chat_key(str(self.chat_id)).last_brief = stories
    msg = format_brief_message(stories, "scheduled", themes=themes)
    # ... rest unchanged
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_brief_telegram_format.py -v`
Expected: PASS (4 tests)

**Step 5: Commit**

```bash
git add src/telegram_bot/bot.py tests/test_brief_telegram_format.py
git commit -m "feat: themed brief format for Telegram with continuous numbering"
```

---

## Task 8: Add Telegram `/skip` Command for Feedback

**Files:**
- Modify: `src/telegram_bot/bot.py` — add `cmd_skip` handler
- Test: `tests/test_brief_telegram_format.py` (extend)

**Step 1: Write the failing test**

Add to `tests/test_brief_telegram_format.py`:

```python
def test_skip_extracts_keywords():
    """_extract_story_keywords should extract meaningful keywords."""
    from telegram_bot.bot import _extract_story_keywords

    keywords = _extract_story_keywords("NVIDIA beats earnings expectations with record revenue")
    assert "nvidia" in keywords
    assert "earnings" in keywords
    assert "the" not in keywords  # stopword removed
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_brief_telegram_format.py::test_skip_extracts_keywords -v`
Expected: FAIL — `ImportError: cannot import name '_extract_story_keywords'`

**Step 3: Add keyword extraction helper and `/skip` command**

Add to `src/telegram_bot/bot.py`:

```python
from common.stopwords import STOPWORDS


def _extract_story_keywords(title: str) -> list[str]:
    """Extract meaningful keywords from a story title for feedback."""
    words = title.lower().split()
    return [w.strip(".,!?:;\"'()") for w in words if w.strip(".,!?:;\"'()") not in STOPWORDS and len(w) > 2]
```

Add the `/skip` command handler to the `HFIBot` class:

```python
async def cmd_skip(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Mark a brief story as not relevant — /skip N."""
    if await self._reject_if_unauthorized(update, "skip"):
        return

    args = context.args or []
    if not args or not args[0].isdigit():
        await self._reply_text(update, "Usage: /skip N (story number from last brief)")
        return

    index = int(args[0]) - 1
    state = self._state_for(update)
    stories = state.last_brief or []

    if index < 0 or index >= len(stories):
        await self._reply_text(update, f"Invalid story number. Last brief had {len(stories)} stories.")
        return

    story = stories[index]
    title = story.get("title", "")
    keywords = _extract_story_keywords(title)

    try:
        await self._request("POST", "/api/notifications/brief/feedback", json={
            "story_title": title,
            "feedback_type": "not_relevant",
            "keywords": keywords,
            "source": "telegram",
        })
        await self._reply_text(update, f"Got it, less stories like \"{title[:50]}...\"")
    except Exception as err:
        await self._reply_error(update, err)
```

Register the handler in `_register_handlers` (alongside other command handlers):

```python
self.app.add_handler(CommandHandler("skip", self.cmd_skip))
```

Add `/skip` to the bot's command list in `_set_bot_commands` (if it exists).

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_brief_telegram_format.py -v`
Expected: ALL PASS

**Step 5: Commit**

```bash
git add src/telegram_bot/bot.py tests/test_brief_telegram_format.py
git commit -m "feat: add /skip command for brief story feedback in Telegram"
```

---

## Task 9: Update Dashboard — Themed Brief Layout

**Files:**
- Modify: `frontend/src/app/(app)/page.tsx`
- Modify: `frontend/src/components/dashboard/BriefCard.tsx`
- Create: `frontend/src/components/dashboard/BriefThemeSection.tsx`

**Step 1: Create `BriefThemeSection` component**

```typescript
// frontend/src/components/dashboard/BriefThemeSection.tsx
"use client";

import type { BriefTheme, BriefStory } from "@/lib/types";
import { BriefCard } from "./BriefCard";

export function BriefThemeSection({
  theme,
  startIndex,
  onTranslate,
  onWrite,
  onSkip,
}: {
  theme: BriefTheme;
  startIndex: number;
  onTranslate: (story: BriefStory) => void | Promise<void>;
  onWrite: (story: BriefStory, index: number) => void;
  onSkip: (story: BriefStory, index: number) => void;
}) {
  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2">
        <span className="text-xl">{theme.emoji}</span>
        <h4 className="font-display text-base font-semibold">{theme.name}</h4>
      </div>
      <p className="text-sm text-[var(--muted)] -mt-1">{theme.takeaway}</p>
      <div className="grid gap-3 md:grid-cols-2">
        {theme.stories.map((story, i) => (
          <BriefCard
            key={`${story.title}-${startIndex + i}`}
            story={story}
            index={startIndex + i}
            onTranslate={onTranslate}
            onWrite={onWrite}
            onSkip={onSkip}
          />
        ))}
      </div>
    </div>
  );
}
```

**Step 2: Update `BriefCard` to accept `onWrite` and `onSkip` callbacks**

In `frontend/src/components/dashboard/BriefCard.tsx`, update the props:

```typescript
export function BriefCard({
  story,
  index,
  onTranslate,
  onWrite,
  onSkip,
}: {
  story: BriefStory;
  index: number;
  onTranslate: (story: BriefStory) => void | Promise<void>;
  onWrite: (story: BriefStory, index: number) => void;
  onSkip: (story: BriefStory, index: number) => void;
}) {
```

Replace the Write button's `router.push(...)` with `onWrite(story, index)`.

Add a 👎 button next to Write/Translate:

```tsx
<Button
  variant="ghost"
  className="h-8 w-8 p-0 text-[var(--muted)] hover:text-red-400"
  onClick={(e) => {
    e.stopPropagation();
    onSkip(story, index);
  }}
  title="Not relevant"
>
  👎
</Button>
```

**Step 3: Update Dashboard page to render themes**

In `frontend/src/app/(app)/page.tsx`, update the brief section (~L96–108):

```tsx
import { BriefThemeSection } from "@/components/dashboard/BriefThemeSection";

// Inside the component, add skip handler:
const handleSkip = async (story: BriefStory, index: number) => {
  try {
    const keywords = story.title.toLowerCase().split(/\s+/).filter(w => w.length > 2);
    await api.post("/api/notifications/brief/feedback", {
      story_title: story.title,
      feedback_type: "not_relevant",
      keywords,
      source: "dashboard",
    });
    toast.success("Noted", { description: "We'll show less stories like this" });
  } catch {
    toast.error("Failed to submit feedback");
  }
};

// Replace the stories grid with themed rendering:
{briefQuery.data?.themes && briefQuery.data.themes.length > 0 ? (
  <div className="space-y-6">
    {briefQuery.data.themes.reduce<{ sections: React.ReactNode[]; runningIndex: number }>(
      (acc, theme, themeIdx) => {
        acc.sections.push(
          <BriefThemeSection
            key={theme.name + themeIdx}
            theme={theme}
            startIndex={acc.runningIndex}
            onTranslate={handleTranslate}
            onWrite={handleWrite}
            onSkip={handleSkip}
          />
        );
        acc.runningIndex += theme.stories.length;
        return acc;
      },
      { sections: [], runningIndex: 0 }
    ).sections}
  </div>
) : (
  <div className="grid gap-4 md:grid-cols-2">
    {(briefQuery.data?.stories || []).map((story, index) => (
      <BriefCard
        key={`${story.title}-${index}`}
        story={story}
        index={index}
        onTranslate={handleTranslate}
        onWrite={handleWrite}
        onSkip={handleSkip}
      />
    ))}
  </div>
)}
```

The `handleWrite` function is needed — initially it navigates to `/create` like the old behavior (this gets replaced in Task 10):

```tsx
const handleWrite = (story: BriefStory, index: number) => {
  const text = `${story.title}\n\n${story.summary || ""}`;
  const sources = (story.source_urls || []).join(",");
  router.push(`/create?source=trend&id=${index + 1}&text=${encodeURIComponent(text)}&sources=${encodeURIComponent(sources)}`);
};
```

**Step 4: Verify in browser**

Run: `cd frontend && npm run dev`
Navigate to `http://localhost:3000` — verify themed sections render.

**Step 5: Commit**

```bash
git add frontend/src/components/dashboard/BriefThemeSection.tsx frontend/src/components/dashboard/BriefCard.tsx frontend/src/app/\(app\)/page.tsx
git commit -m "feat: themed brief layout on Dashboard with skip feedback button"
```

---

## Task 10: Add Inline Draft Panel to Dashboard

**Files:**
- Create: `frontend/src/hooks/useInlineDraft.ts`
- Modify: `frontend/src/components/dashboard/BriefCard.tsx`
- Modify: `frontend/src/app/(app)/page.tsx`

**Step 1: Create the `useInlineDraft` hook**

```typescript
// frontend/src/hooks/useInlineDraft.ts
"use client";

import { useState, useCallback } from "react";
import { useMutation } from "@tanstack/react-query";
import { toast } from "sonner";

import api from "@/lib/api";
import type { BriefStory } from "@/lib/types";

interface DraftState {
  storyIndex: number;
  hebrewText: string;
  isGenerating: boolean;
  isSaving: boolean;
}

export function useInlineDraft() {
  const [activeDraft, setActiveDraft] = useState<DraftState | null>(null);

  const generateMutation = useMutation({
    mutationFn: async (story: BriefStory) => {
      const sourceText = `${story.title}\n\n${story.summary || ""}`;
      const { data } = await api.post("/api/generation/post", {
        source_text: sourceText,
        num_variants: 1,
      });
      return data.variants?.[0]?.content || "";
    },
  });

  const saveMutation = useMutation({
    mutationFn: async ({ hebrewText, story, status }: { hebrewText: string; story: BriefStory; status: string }) => {
      const sourceText = `${story.title}\n\n${story.summary || ""}`;
      const sourceUrl = story.source_urls?.[0] || "";
      const { data } = await api.post("/api/content", {
        source_url: sourceUrl || `brief://${Date.now()}`,
        original_text: sourceText,
        hebrew_draft: hebrewText,
        content_type: "generation",
        status,
        generation_metadata: { origin: "brief_inline" },
      });
      return data;
    },
  });

  const openDraft = useCallback(async (story: BriefStory, index: number) => {
    setActiveDraft({ storyIndex: index, hebrewText: "", isGenerating: true, isSaving: false });
    try {
      const content = await generateMutation.mutateAsync(story);
      setActiveDraft((prev) => prev ? { ...prev, hebrewText: content, isGenerating: false } : null);
    } catch {
      toast.error("Failed to generate draft");
      setActiveDraft(null);
    }
  }, [generateMutation]);

  const updateText = useCallback((text: string) => {
    setActiveDraft((prev) => prev ? { ...prev, hebrewText: text } : null);
  }, []);

  const saveDraft = useCallback(async (story: BriefStory, status: "processed" | "approved") => {
    if (!activeDraft) return;
    setActiveDraft((prev) => prev ? { ...prev, isSaving: true } : null);
    try {
      await saveMutation.mutateAsync({ hebrewText: activeDraft.hebrewText, story, status });
      toast.success(status === "approved" ? "Added to queue" : "Draft saved");
      setActiveDraft(null);
    } catch {
      toast.error("Failed to save");
      setActiveDraft((prev) => prev ? { ...prev, isSaving: false } : null);
    }
  }, [activeDraft, saveMutation]);

  const closeDraft = useCallback(() => {
    setActiveDraft(null);
  }, []);

  return { activeDraft, openDraft, updateText, saveDraft, closeDraft };
}
```

**Step 2: Add inline draft panel to `BriefCard`**

In `frontend/src/components/dashboard/BriefCard.tsx`, add an optional `draftPanel` prop:

```tsx
export function BriefCard({
  story,
  index,
  onTranslate,
  onWrite,
  onSkip,
  draftPanel,
}: {
  story: BriefStory;
  index: number;
  onTranslate: (story: BriefStory) => void | Promise<void>;
  onWrite: (story: BriefStory, index: number) => void;
  onSkip: (story: BriefStory, index: number) => void;
  draftPanel?: React.ReactNode;
}) {
```

After the button row (after the `</div>` closing the `flex gap-2`), add:

```tsx
{draftPanel}
```

**Step 3: Wire inline draft in Dashboard page**

In `frontend/src/app/(app)/page.tsx`:

```tsx
import { useInlineDraft } from "@/hooks/useInlineDraft";

// Inside DashboardPage:
const { activeDraft, openDraft, updateText, saveDraft, closeDraft } = useInlineDraft();

const handleWrite = (story: BriefStory, index: number) => {
  openDraft(story, index);
};

// Build the draft panel for a given story/index:
const buildDraftPanel = (story: BriefStory, index: number) => {
  if (!activeDraft || activeDraft.storyIndex !== index) return undefined;
  return (
    <div className="mt-3 rounded-2xl border border-[var(--border)] bg-[var(--surface)] p-4 space-y-3">
      <p className="text-xs font-medium text-[var(--muted)]">Hebrew Draft</p>
      {activeDraft.isGenerating ? (
        <div className="flex items-center gap-2 text-sm text-[var(--muted)]">
          <Loader2 size={14} className="animate-spin" /> Generating...
        </div>
      ) : (
        <>
          <textarea
            className="w-full min-h-[100px] rounded-xl border border-[var(--border)] bg-[var(--background)] p-3 text-sm leading-6 resize-y focus:outline-none focus:ring-2 focus:ring-[var(--ring)]"
            dir="rtl"
            value={activeDraft.hebrewText}
            onChange={(e) => updateText(e.target.value)}
          />
          <div className="flex gap-2">
            <Button
              size="sm"
              variant="secondary"
              disabled={activeDraft.isSaving}
              onClick={() => saveDraft(story, "processed")}
            >
              Save Draft
            </Button>
            <Button
              size="sm"
              disabled={activeDraft.isSaving}
              onClick={() => saveDraft(story, "approved")}
            >
              Queue
            </Button>
            <Button size="sm" variant="ghost" onClick={closeDraft}>
              Close
            </Button>
          </div>
        </>
      )}
    </div>
  );
};
```

Pass `draftPanel={buildDraftPanel(story, startIndex + i)}` to each `BriefCard`.

**Step 4: Verify in browser**

Run: `cd frontend && npm run dev`
Navigate to `http://localhost:3000`, click "Write" on a story — verify inline draft panel opens with Hebrew text, editable, saveable.

**Step 5: Commit**

```bash
git add frontend/src/hooks/useInlineDraft.ts frontend/src/components/dashboard/BriefCard.tsx frontend/src/app/\(app\)/page.tsx
git commit -m "feat: inline one-tap Hebrew draft panel on Dashboard brief cards"
```

---

## Task 11: Add Telegram Inline Keyboard Buttons for `/write`

**Files:**
- Modify: `src/telegram_bot/bot.py` — `cmd_write` handler

**Step 1: Update `/write` to use inline keyboard buttons**

In the `cmd_write` handler, after generating variants, instead of showing "Use /save N to persist", add inline keyboard buttons:

```python
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

# After generating variants, for each variant:
keyboard = InlineKeyboardMarkup([
    [
        InlineKeyboardButton("Save Draft", callback_data=f"write_save_{session.session_id}_{idx}"),
        InlineKeyboardButton("Queue", callback_data=f"write_queue_{session.session_id}_{idx}"),
    ]
])

await self._send_chunked_reply(update, msg, reply_markup=keyboard)
```

Add a callback query handler for the buttons:

```python
async def handle_write_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    data = query.data  # e.g. "write_save_{session_id}_{variant_idx}"
    parts = data.split("_", 3)
    action = parts[1]  # "save" or "queue"
    variant_idx = int(parts[3]) - 1

    state = self._state_for_chat_key(str(query.message.chat_id))
    session = state.last_write_session
    if not session:
        await query.edit_message_text("Session expired. Use /write again.")
        return

    status = "processed" if action == "save" else "approved"
    variant = session.variants[variant_idx]

    # Save via API (reuse existing save logic)
    try:
        await self._request("POST", "/api/content", json={
            "source_url": session.canonical_url or f"telegram://{session.session_id}",
            "original_text": session.original_text,
            "hebrew_draft": variant.get("content", ""),
            "content_type": "generation",
            "status": status,
            "generation_metadata": {"origin": "telegram", "write_session_id": session.session_id},
        })
        label = "Saved as draft" if action == "save" else "Added to queue"
        await query.edit_message_text(f"{label} \u2705")
    except Exception as err:
        await query.edit_message_text(f"Failed: {err}")
```

Register the callback handler:

```python
from telegram.ext import CallbackQueryHandler

self.app.add_handler(CallbackQueryHandler(self.handle_write_callback, pattern=r"^write_"))
```

**Step 2: Verify manually**

Start the Telegram bot, send `/write 1` after a `/brief`, verify inline buttons appear and work.

**Step 3: Commit**

```bash
git add src/telegram_bot/bot.py
git commit -m "feat: inline keyboard buttons for Telegram /write flow"
```

---

## Task 12: Add Feedback Weights to Settings Page

**Files:**
- Create: `frontend/src/components/settings/FeedbackWeights.tsx`
- Modify: `frontend/src/app/(app)/settings/page.tsx`

**Step 1: Create the `FeedbackWeights` component**

```typescript
// frontend/src/components/settings/FeedbackWeights.tsx
"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";

import api from "@/lib/api";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";

interface FeedbackWeightsData {
  excluded_keywords: string[];
  keyword_counts: Record<string, number>;
}

export function FeedbackWeights() {
  const queryClient = useQueryClient();

  const { data, isLoading } = useQuery({
    queryKey: ["feedback-weights"],
    queryFn: async () => {
      const { data } = await api.get<FeedbackWeightsData>("/api/notifications/brief/feedback/weights");
      return data;
    },
  });

  const resetMutation = useMutation({
    mutationFn: () => api.delete("/api/notifications/brief/feedback"),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["feedback-weights"] });
      toast.success("Feedback reset");
    },
  });

  if (isLoading) return <p className="text-sm text-[var(--muted)]">Loading...</p>;

  const counts = data?.keyword_counts || {};
  const sorted = Object.entries(counts).sort(([, a], [, b]) => b - a);

  return (
    <div className="space-y-3">
      {sorted.length === 0 ? (
        <p className="text-sm text-[var(--muted)]">No feedback yet. Use the 👎 button on brief stories to train your preferences.</p>
      ) : (
        <>
          <div className="flex flex-wrap gap-2">
            {sorted.map(([keyword, count]) => (
              <Badge
                key={keyword}
                className={count >= 3 ? "bg-red-900/40 text-red-300" : "bg-zinc-800 text-zinc-300"}
              >
                {keyword} ({count}){count >= 3 ? " — excluded" : ""}
              </Badge>
            ))}
          </div>
          <p className="text-xs text-[var(--muted)]">Keywords with 3+ downvotes are excluded from future briefs.</p>
          <Button variant="secondary" size="sm" onClick={() => resetMutation.mutate()} disabled={resetMutation.isPending}>
            {resetMutation.isPending ? "Resetting..." : "Reset All Feedback"}
          </Button>
        </>
      )}
    </div>
  );
}
```

**Step 2: Add to Settings page**

In `frontend/src/app/(app)/settings/page.tsx`, add after the Telegram section:

```tsx
import { FeedbackWeights } from "@/components/settings/FeedbackWeights";

// Add new details section:
<details className="rounded-3xl border border-[var(--border)] bg-[var(--card)]/75">
  <summary className="cursor-pointer px-5 py-4 font-medium">Brief Preferences</summary>
  <div className="px-5 pb-5">
    <FeedbackWeights />
  </div>
</details>
```

**Step 3: Verify in browser**

Run: `cd frontend && npm run dev`
Navigate to `http://localhost:3000/settings` — verify the Brief Preferences section appears.

**Step 4: Commit**

```bash
git add frontend/src/components/settings/FeedbackWeights.tsx frontend/src/app/\(app\)/settings/page.tsx
git commit -m "feat: add Brief Preferences section to Settings with feedback weights"
```

---

## Task 13: End-to-End Verification

**Step 1: Run all backend tests**

```bash
pytest tests/ -v --tb=short
```

Expected: ALL PASS

**Step 2: Run frontend build check**

```bash
cd frontend && npm run build
```

Expected: Build succeeds with no errors

**Step 3: Manual E2E verification**

1. Start all services: `docker-compose up -d`
2. Open Dashboard — verify themed brief renders with sections
3. Click "Write" — verify inline Hebrew draft panel opens
4. Edit draft → "Save Draft" — verify toast + appears in Queue
5. Click 👎 — verify toast "Noted"
6. Check Settings → Brief Preferences — verify keyword appears
7. In Telegram: `/brief` — verify themed format
8. In Telegram: `/write 1` — verify inline buttons
9. In Telegram: `/skip 1` — verify feedback stored

**Step 4: Final commit**

```bash
git add -A
git commit -m "test: verify briefs improvement end-to-end"
```
