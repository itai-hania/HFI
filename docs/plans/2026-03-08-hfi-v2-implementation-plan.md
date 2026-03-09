# HFI v2 — Content Studio Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace the Streamlit dashboard with a polished Next.js content studio + Telegram bot, keeping the existing Python scraping/translation/generation engine intact.

**Architecture:** Next.js frontend → FastAPI REST API (expanded from existing `src/api/`) → existing Python engine (scrapers, processors, generators). Telegram bot connects to the same API. All frontends access data through the API only — no direct DB access.

**Tech Stack:** Next.js 14 (App Router), Tailwind CSS, shadcn/ui, TanStack Query, FastAPI, python-telegram-bot, APScheduler, SQLAlchemy, SQLite, OpenAI GPT-4o, Playwright, feedparser.

**Design doc:** `docs/plans/2026-03-08-hfi-v2-content-studio-design.md`

---

## Phase 1: API Layer Expansion

> Expand the existing FastAPI app (`src/api/`) to cover all operations the Next.js frontend and Telegram bot will need. The existing trend + summary endpoints stay. We add content, inspiration, settings, and auth endpoints.

---

### Task 1.1: Database Model Additions

Add new tables for inspiration accounts, cached inspiration posts, notifications, and user preferences.

**Files:**
- Modify: `src/common/models.py`
- Create: `tests/test_models_v2.py`

**Step 1: Write failing tests for new models**

```python
# tests/test_models_v2.py
import pytest
from datetime import datetime, timezone
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from common.models import Base, InspirationAccount, InspirationPost, Notification, UserPreference

@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = Session(bind=engine)
    yield session
    session.close()

class TestInspirationAccount:
    def test_create_account(self, db):
        account = InspirationAccount(
            username="elikiris",
            display_name="Eli Kiris",
            category="fintech",
            is_active=True,
        )
        db.add(account)
        db.commit()
        assert account.id is not None
        assert account.username == "elikiris"
        assert account.is_active is True

    def test_unique_username(self, db):
        db.add(InspirationAccount(username="user1", display_name="User 1"))
        db.commit()
        db.add(InspirationAccount(username="user1", display_name="Duplicate"))
        with pytest.raises(Exception):
            db.commit()

class TestInspirationPost:
    def test_create_post(self, db):
        account = InspirationAccount(username="testuser", display_name="Test")
        db.add(account)
        db.commit()
        post = InspirationPost(
            account_id=account.id,
            x_post_id="1234567890",
            content="Test post content",
            likes=500,
            retweets=100,
            views=10000,
            posted_at=datetime.now(timezone.utc),
        )
        db.add(post)
        db.commit()
        assert post.id is not None
        assert post.account_id == account.id

    def test_unique_x_post_id(self, db):
        account = InspirationAccount(username="testuser", display_name="Test")
        db.add(account)
        db.commit()
        db.add(InspirationPost(account_id=account.id, x_post_id="same_id", content="a"))
        db.commit()
        db.add(InspirationPost(account_id=account.id, x_post_id="same_id", content="b"))
        with pytest.raises(Exception):
            db.commit()

class TestNotification:
    def test_create_notification(self, db):
        notif = Notification(
            type="brief",
            content={"stories": [{"title": "Test"}]},
            delivered=False,
        )
        db.add(notif)
        db.commit()
        assert notif.id is not None
        assert notif.delivered is False

class TestUserPreference:
    def test_create_preference(self, db):
        pref = UserPreference(key="default_angle", value="news")
        db.add(pref)
        db.commit()
        fetched = db.query(UserPreference).filter_by(key="default_angle").first()
        assert fetched.value == "news"

    def test_upsert_preference(self, db):
        pref = UserPreference(key="theme", value="dark")
        db.add(pref)
        db.commit()
        pref.value = "light"
        db.commit()
        fetched = db.query(UserPreference).filter_by(key="theme").first()
        assert fetched.value == "light"
```

**Step 2: Run tests to verify they fail**

```bash
pytest tests/test_models_v2.py -v
```

Expected: `ImportError` — models don't exist yet.

**Step 3: Implement the new models**

Add to `src/common/models.py` after the existing `StyleExample` class:

```python
class InspirationAccount(Base):
    __tablename__ = "inspiration_accounts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(256), unique=True, nullable=False, index=True)
    display_name = Column(String(256))
    category = Column(String(100))
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    posts = relationship("InspirationPost", back_populates="account", cascade="all, delete-orphan")

class InspirationPost(Base):
    __tablename__ = "inspiration_posts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    account_id = Column(Integer, ForeignKey("inspiration_accounts.id"), nullable=False, index=True)
    x_post_id = Column(String(64), unique=True, nullable=False)
    content = Column(Text)
    likes = Column(Integer, default=0)
    retweets = Column(Integer, default=0)
    views = Column(Integer, default=0)
    posted_at = Column(DateTime(timezone=True))
    fetched_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    account = relationship("InspirationAccount", back_populates="posts")

    __table_args__ = (
        Index("ix_inspiration_posts_likes", "likes"),
        Index("ix_inspiration_posts_account_likes", "account_id", "likes"),
    )

class Notification(Base):
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True, autoincrement=True)
    type = Column(String(20), nullable=False, index=True)  # "brief" or "alert"
    content = Column(JSON)
    delivered = Column(Boolean, default=False, index=True)
    delivered_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

class UserPreference(Base):
    __tablename__ = "user_preferences"

    key = Column(String(256), primary_key=True)
    value = Column(JSON)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
```

Also add `copy_count` column to existing `Tweet` model:

```python
copy_count = Column(Integer, default=0)
```

Update `create_tables()` to add new columns safely (same pattern as existing safe migrations).

**Step 4: Run tests to verify they pass**

```bash
pytest tests/test_models_v2.py -v
```

Expected: All PASS.

**Step 5: Run all existing tests to ensure no regressions**

```bash
pytest tests/ -v --timeout=60
```

Expected: All 468+ tests PASS.

**Step 6: Commit**

```bash
git add src/common/models.py tests/test_models_v2.py
git commit -m "feat: add inspiration, notification, and preference models for v2"
```

---

### Task 1.2: Auth Endpoints (JWT)

Replace the current password + session-based auth with JWT tokens for the API.

**Files:**
- Create: `src/api/routes/auth.py`
- Create: `src/api/schemas/auth.py`
- Modify: `src/api/main.py` (register router)
- Modify: `src/api/dependencies.py` (add JWT validation)
- Create: `tests/test_api_auth.py`

**Step 1: Write failing tests**

```python
# tests/test_api_auth.py
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch
import os

@pytest.fixture
def client():
    os.environ["DASHBOARD_PASSWORD"] = "testpass123"
    os.environ["JWT_SECRET"] = "test-jwt-secret-key"
    from api.main import app
    return TestClient(app)

class TestAuthEndpoints:
    def test_login_success(self, client):
        resp = client.post("/api/auth/login", json={"password": "testpass123"})
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"

    def test_login_wrong_password(self, client):
        resp = client.post("/api/auth/login", json={"password": "wrong"})
        assert resp.status_code == 401

    def test_protected_endpoint_without_token(self, client):
        resp = client.get("/api/content/drafts")
        assert resp.status_code == 401

    def test_protected_endpoint_with_token(self, client):
        login_resp = client.post("/api/auth/login", json={"password": "testpass123"})
        token = login_resp.json()["access_token"]
        resp = client.get(
            "/api/content/drafts",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code in (200, 404)  # endpoint may not exist yet

    def test_refresh_token(self, client):
        login_resp = client.post("/api/auth/login", json={"password": "testpass123"})
        token = login_resp.json()["access_token"]
        resp = client.post(
            "/api/auth/refresh",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        assert "access_token" in resp.json()
```

**Step 2: Run tests to verify they fail**

```bash
pytest tests/test_api_auth.py -v
```

**Step 3: Implement auth**

`src/api/schemas/auth.py`:
```python
from pydantic import BaseModel

class LoginRequest(BaseModel):
    password: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
```

`src/api/routes/auth.py`:
```python
import os
import secrets
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, HTTPException
import jwt
from api.schemas.auth import LoginRequest, TokenResponse

router = APIRouter(prefix="/api/auth", tags=["auth"])

JWT_SECRET = os.getenv("JWT_SECRET", secrets.token_hex(32))
JWT_ALGORITHM = "HS256"
JWT_EXPIRY_HOURS = 24

@router.post("/login", response_model=TokenResponse)
def login(request: LoginRequest):
    password = os.getenv("DASHBOARD_PASSWORD", "")
    if not password or not secrets.compare_digest(request.password, password):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = _create_token()
    return TokenResponse(access_token=token, expires_in=JWT_EXPIRY_HOURS * 3600)

@router.post("/refresh", response_model=TokenResponse)
def refresh(current_user: str = Depends(require_jwt)):
    token = _create_token()
    return TokenResponse(access_token=token, expires_in=JWT_EXPIRY_HOURS * 3600)

def _create_token() -> str:
    payload = {
        "sub": "user",
        "exp": datetime.now(timezone.utc) + timedelta(hours=JWT_EXPIRY_HOURS),
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)
```

Update `src/api/dependencies.py` — add `require_jwt` dependency:
```python
from fastapi import Depends, Header, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import jwt

security = HTTPBearer(auto_error=False)

def require_jwt(credentials: HTTPAuthorizationCredentials = Depends(security)):
    if not credentials:
        raise HTTPException(status_code=401, detail="Missing token")
    try:
        payload = jwt.decode(credentials.credentials, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return payload["sub"]
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")
```

Register router in `src/api/main.py`.

**Step 4: Run tests**

```bash
pytest tests/test_api_auth.py -v
```

**Step 5: Commit**

```bash
git add src/api/routes/auth.py src/api/schemas/auth.py src/api/dependencies.py src/api/main.py tests/test_api_auth.py
git commit -m "feat: add JWT auth endpoints for API"
```

---

### Task 1.3: Content CRUD Endpoints

Endpoints for creating, reading, updating, deleting content (tweets/drafts).

**Files:**
- Create: `src/api/routes/content.py`
- Create: `src/api/schemas/content.py`
- Modify: `src/api/main.py` (register router)
- Create: `tests/test_api_content.py`

**Step 1: Write failing tests**

```python
# tests/test_api_content.py
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from common.models import Base, Tweet
from datetime import datetime, timezone

@pytest.fixture
def db_and_client():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = Session(bind=engine)
    # Setup test client with DB override
    from api.main import app
    from api.dependencies import get_db
    def override_get_db():
        try:
            yield session
        finally:
            pass
    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)
    yield session, client
    app.dependency_overrides.clear()
    session.close()

class TestContentEndpoints:
    def _auth_header(self, client):
        # Helper to get auth token (skip auth in tests or mock it)
        return {"Authorization": "Bearer test"}

    def test_list_drafts_empty(self, db_and_client):
        db, client = db_and_client
        resp = client.get("/api/content/drafts", headers=self._auth_header(client))
        assert resp.status_code == 200
        assert resp.json()["items"] == []

    def test_create_content(self, db_and_client):
        db, client = db_and_client
        resp = client.post("/api/content", json={
            "source_url": "https://x.com/test/status/123",
            "original_text": "Test fintech news",
            "hebrew_draft": "חדשות פינטק",
            "content_type": "translation",
        }, headers=self._auth_header(client))
        assert resp.status_code == 201
        data = resp.json()
        assert data["original_text"] == "Test fintech news"
        assert data["hebrew_draft"] == "חדשות פינטק"

    def test_get_content_by_id(self, db_and_client):
        db, client = db_and_client
        tweet = Tweet(source_url="https://x.com/t/1", original_text="Hello", status="pending")
        db.add(tweet)
        db.commit()
        resp = client.get(f"/api/content/{tweet.id}", headers=self._auth_header(client))
        assert resp.status_code == 200
        assert resp.json()["original_text"] == "Hello"

    def test_update_content(self, db_and_client):
        db, client = db_and_client
        tweet = Tweet(source_url="https://x.com/t/2", original_text="Hello", status="pending")
        db.add(tweet)
        db.commit()
        resp = client.patch(f"/api/content/{tweet.id}", json={
            "hebrew_draft": "שלום",
            "status": "processed",
        }, headers=self._auth_header(client))
        assert resp.status_code == 200
        assert resp.json()["hebrew_draft"] == "שלום"

    def test_delete_content(self, db_and_client):
        db, client = db_and_client
        tweet = Tweet(source_url="https://x.com/t/3", original_text="Delete me", status="pending")
        db.add(tweet)
        db.commit()
        resp = client.delete(f"/api/content/{tweet.id}", headers=self._auth_header(client))
        assert resp.status_code == 204

    def test_list_by_status(self, db_and_client):
        db, client = db_and_client
        db.add(Tweet(source_url="https://x.com/t/4", original_text="a", status="pending"))
        db.add(Tweet(source_url="https://x.com/t/5", original_text="b", status="approved"))
        db.commit()
        resp = client.get("/api/content/drafts?status=approved", headers=self._auth_header(client))
        assert resp.status_code == 200
        assert len(resp.json()["items"]) == 1

    def test_increment_copy_count(self, db_and_client):
        db, client = db_and_client
        tweet = Tweet(source_url="https://x.com/t/6", original_text="Copy me", status="approved")
        db.add(tweet)
        db.commit()
        resp = client.post(f"/api/content/{tweet.id}/copy", headers=self._auth_header(client))
        assert resp.status_code == 200
        assert resp.json()["copy_count"] == 1
```

**Step 2: Run tests to verify they fail**

```bash
pytest tests/test_api_content.py -v
```

**Step 3: Implement content endpoints**

`src/api/schemas/content.py`:
```python
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

class ContentCreate(BaseModel):
    source_url: str
    original_text: str
    hebrew_draft: Optional[str] = None
    content_type: str = "translation"
    trend_topic: Optional[str] = None

class ContentUpdate(BaseModel):
    hebrew_draft: Optional[str] = None
    status: Optional[str] = None
    scheduled_at: Optional[datetime] = None
    trend_topic: Optional[str] = None

class ContentResponse(BaseModel):
    id: int
    source_url: str
    original_text: str
    hebrew_draft: Optional[str]
    content_type: str
    status: str
    trend_topic: Optional[str]
    copy_count: int
    scheduled_at: Optional[datetime]
    created_at: datetime
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True

class ContentListResponse(BaseModel):
    items: List[ContentResponse]
    total: int
    page: int
    per_page: int
```

`src/api/routes/content.py`:
```python
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from api.dependencies import get_db, require_jwt
from api.schemas.content import ContentCreate, ContentUpdate, ContentResponse, ContentListResponse
from common.models import Tweet

router = APIRouter(prefix="/api/content", tags=["content"], dependencies=[Depends(require_jwt)])

@router.get("/drafts", response_model=ContentListResponse)
def list_content(
    status: str = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    search: str = Query(None),
    db: Session = Depends(get_db),
):
    query = db.query(Tweet)
    if status:
        query = query.filter(Tweet.status == status)
    if search:
        query = query.filter(
            Tweet.original_text.ilike(f"%{search}%") |
            Tweet.hebrew_draft.ilike(f"%{search}%") |
            Tweet.trend_topic.ilike(f"%{search}%")
        )
    total = query.count()
    items = query.order_by(Tweet.created_at.desc()).offset((page - 1) * limit).limit(limit).all()
    return ContentListResponse(items=items, total=total, page=page, per_page=limit)

@router.get("/scheduled", response_model=ContentListResponse)
def list_scheduled(db: Session = Depends(get_db)):
    items = db.query(Tweet).filter(
        Tweet.status == "approved",
        Tweet.scheduled_at.isnot(None),
    ).order_by(Tweet.scheduled_at.asc()).all()
    return ContentListResponse(items=items, total=len(items), page=1, per_page=len(items))

@router.get("/published", response_model=ContentListResponse)
def list_published(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    query = db.query(Tweet).filter(Tweet.status == "published")
    total = query.count()
    items = query.order_by(Tweet.created_at.desc()).offset((page - 1) * limit).limit(limit).all()
    return ContentListResponse(items=items, total=total, page=page, per_page=limit)

@router.get("/{content_id}", response_model=ContentResponse)
def get_content(content_id: int, db: Session = Depends(get_db)):
    tweet = db.query(Tweet).get(content_id)
    if not tweet:
        raise HTTPException(status_code=404, detail="Content not found")
    return tweet

@router.post("", response_model=ContentResponse, status_code=201)
def create_content(data: ContentCreate, db: Session = Depends(get_db)):
    tweet = Tweet(
        source_url=data.source_url,
        original_text=data.original_text,
        hebrew_draft=data.hebrew_draft,
        content_type=data.content_type,
        trend_topic=data.trend_topic,
        status="pending" if not data.hebrew_draft else "processed",
    )
    db.add(tweet)
    db.commit()
    db.refresh(tweet)
    return tweet

@router.patch("/{content_id}", response_model=ContentResponse)
def update_content(content_id: int, data: ContentUpdate, db: Session = Depends(get_db)):
    tweet = db.query(Tweet).get(content_id)
    if not tweet:
        raise HTTPException(status_code=404, detail="Content not found")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(tweet, field, value)
    db.commit()
    db.refresh(tweet)
    return tweet

@router.delete("/{content_id}", status_code=204)
def delete_content(content_id: int, db: Session = Depends(get_db)):
    tweet = db.query(Tweet).get(content_id)
    if not tweet:
        raise HTTPException(status_code=404, detail="Content not found")
    db.delete(tweet)
    db.commit()

@router.post("/{content_id}/copy", response_model=ContentResponse)
def increment_copy(content_id: int, db: Session = Depends(get_db)):
    tweet = db.query(Tweet).get(content_id)
    if not tweet:
        raise HTTPException(status_code=404, detail="Content not found")
    tweet.copy_count = (tweet.copy_count or 0) + 1
    db.commit()
    db.refresh(tweet)
    return tweet
```

**Step 4: Run tests**

```bash
pytest tests/test_api_content.py -v
```

**Step 5: Commit**

```bash
git add src/api/routes/content.py src/api/schemas/content.py src/api/main.py tests/test_api_content.py
git commit -m "feat: add content CRUD endpoints"
```

---

### Task 1.4: Generation & Translation Endpoints

Expose the existing ContentGenerator and TranslationService through the API.

**Files:**
- Create: `src/api/routes/generation.py`
- Create: `src/api/schemas/generation.py`
- Modify: `src/api/main.py`
- Create: `tests/test_api_generation.py`

**Step 1: Write failing tests**

```python
# tests/test_api_generation.py
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock

class TestGenerationEndpoints:
    def test_generate_post_returns_variants(self, client):
        with patch("api.routes.generation.get_content_generator") as mock_gen:
            mock_gen.return_value.generate_post.return_value = [
                {"angle": "news", "label": "News/Breaking", "content": "תוכן בעברית", "char_count": 15, "is_valid_hebrew": True, "quality_score": 85},
            ]
            resp = client.post("/api/generation/post", json={
                "source_text": "SEC approves new Bitcoin ETF",
                "num_variants": 1,
                "angles": ["news"],
            })
            assert resp.status_code == 200
            variants = resp.json()["variants"]
            assert len(variants) == 1
            assert variants[0]["angle"] == "news"

    def test_translate_text(self, client):
        with patch("api.routes.generation.get_translation_service") as mock_ts:
            mock_ts.return_value.translate_and_rewrite.return_value = "תרגום בעברית"
            resp = client.post("/api/generation/translate", json={
                "text": "Fintech is disrupting traditional banking",
            })
            assert resp.status_code == 200
            assert resp.json()["hebrew_text"] == "תרגום בעברית"

    def test_translate_url(self, client):
        with patch("api.routes.generation.get_translation_service") as mock_ts:
            with patch("api.routes.generation.get_scraper") as mock_scraper:
                mock_scraper.return_value.get_tweet_content.return_value = {
                    "text": "Original tweet text",
                    "author": "fintech_guru",
                }
                mock_ts.return_value.translate_and_rewrite.return_value = "תוכן מתורגם"
                resp = client.post("/api/generation/translate", json={
                    "url": "https://x.com/fintech_guru/status/123",
                })
                assert resp.status_code == 200
```

**Step 2: Run tests to verify they fail**

```bash
pytest tests/test_api_generation.py -v
```

**Step 3: Implement generation endpoints**

`src/api/schemas/generation.py`:
```python
from pydantic import BaseModel
from typing import Optional, List

class GeneratePostRequest(BaseModel):
    source_text: str
    num_variants: int = 3
    angles: Optional[List[str]] = None

class GenerateThreadRequest(BaseModel):
    source_text: str
    num_tweets: int = 3
    angle: str = "educational"

class TranslateRequest(BaseModel):
    text: Optional[str] = None
    url: Optional[str] = None

class VariantResponse(BaseModel):
    angle: str
    label: str
    content: str
    char_count: int
    is_valid_hebrew: bool
    quality_score: int

class GeneratePostResponse(BaseModel):
    variants: List[VariantResponse]

class TranslateResponse(BaseModel):
    hebrew_text: str
    original_text: str
    source_type: Optional[str] = None
```

`src/api/routes/generation.py`:
```python
from fastapi import APIRouter, Depends, HTTPException
from api.dependencies import require_jwt
from api.schemas.generation import *

router = APIRouter(prefix="/api/generation", tags=["generation"], dependencies=[Depends(require_jwt)])

def get_content_generator():
    from processor.content_generator import ContentGenerator
    return ContentGenerator()

def get_translation_service():
    from processor.processor import ProcessorConfig, TranslationService
    config = ProcessorConfig()
    return TranslationService(config)

@router.post("/post", response_model=GeneratePostResponse)
def generate_post(request: GeneratePostRequest):
    generator = get_content_generator()
    variants = generator.generate_post(
        source_text=request.source_text,
        num_variants=request.num_variants,
        angles=request.angles,
    )
    return GeneratePostResponse(variants=variants)

@router.post("/thread")
def generate_thread(request: GenerateThreadRequest):
    generator = get_content_generator()
    tweets = generator.generate_thread(
        source_text=request.source_text,
        num_tweets=request.num_tweets,
        angle=request.angle,
    )
    return {"tweets": tweets}

@router.post("/translate", response_model=TranslateResponse)
async def translate(request: TranslateRequest):
    if not request.text and not request.url:
        raise HTTPException(status_code=400, detail="Provide text or url")
    service = get_translation_service()
    original = request.text
    source_type = "text"
    if request.url:
        source_type = "url"
        # Scrape content from URL
        from scraper.scraper import TwitterScraper
        scraper = TwitterScraper(headless=True)
        try:
            await scraper.ensure_logged_in()
            tweet_data = await scraper.get_tweet_content(request.url)
            original = tweet_data.get("text", "")
        finally:
            await scraper.close()
    hebrew = service.translate_and_rewrite(original)
    return TranslateResponse(hebrew_text=hebrew, original_text=original, source_type=source_type)
```

**Step 4: Run tests**

```bash
pytest tests/test_api_generation.py -v
```

**Step 5: Commit**

```bash
git add src/api/routes/generation.py src/api/schemas/generation.py src/api/main.py tests/test_api_generation.py
git commit -m "feat: add generation and translation API endpoints"
```

---

### Task 1.5: Inspiration Endpoints

CRUD for inspiration accounts + search for high-engagement posts.

**Files:**
- Create: `src/api/routes/inspiration.py`
- Create: `src/api/schemas/inspiration.py`
- Modify: `src/api/main.py`
- Create: `tests/test_api_inspiration.py`

**Step 1: Write failing tests**

```python
# tests/test_api_inspiration.py
import pytest

class TestInspirationEndpoints:
    def test_add_account(self, db_and_client):
        db, client = db_and_client
        resp = client.post("/api/inspiration/accounts", json={
            "username": "fintech_guru",
            "display_name": "FinTech Guru",
            "category": "fintech",
        }, headers=self._auth_header(client))
        assert resp.status_code == 201
        assert resp.json()["username"] == "fintech_guru"

    def test_list_accounts(self, db_and_client):
        db, client = db_and_client
        client.post("/api/inspiration/accounts", json={"username": "user1", "display_name": "U1"}, headers=self._auth_header(client))
        client.post("/api/inspiration/accounts", json={"username": "user2", "display_name": "U2"}, headers=self._auth_header(client))
        resp = client.get("/api/inspiration/accounts", headers=self._auth_header(client))
        assert resp.status_code == 200
        assert len(resp.json()["accounts"]) == 2

    def test_remove_account(self, db_and_client):
        db, client = db_and_client
        create_resp = client.post("/api/inspiration/accounts", json={"username": "to_delete", "display_name": "D"}, headers=self._auth_header(client))
        account_id = create_resp.json()["id"]
        resp = client.delete(f"/api/inspiration/accounts/{account_id}", headers=self._auth_header(client))
        assert resp.status_code == 204

    def test_search_posts(self, db_and_client):
        # This will use Playwright to search X — mock in tests
        db, client = db_and_client
        resp = client.post("/api/inspiration/search", json={
            "username": "fintech_guru",
            "min_likes": 100,
            "keyword": "bitcoin",
        }, headers=self._auth_header(client))
        assert resp.status_code == 200
```

**Step 2: Run tests, verify fail**

**Step 3: Implement**

`src/api/routes/inspiration.py`:
- CRUD for InspirationAccount model
- `POST /api/inspiration/search` — uses TwitterScraper to search `from:username min_faves:N keyword`, caches results in InspirationPost table
- Returns cached results if recent (<1 hour), otherwise re-scrapes

**Step 4: Run tests, verify pass**

**Step 5: Commit**

```bash
git add src/api/routes/inspiration.py src/api/schemas/inspiration.py tests/test_api_inspiration.py src/api/main.py
git commit -m "feat: add inspiration accounts and search endpoints"
```

---

### Task 1.6: Settings Endpoints

Glossary, style examples, and user preferences.

**Files:**
- Create: `src/api/routes/settings.py`
- Create: `src/api/schemas/settings.py`
- Modify: `src/api/main.py`
- Create: `tests/test_api_settings.py`

**Step 1: Write failing tests**

```python
# tests/test_api_settings.py
class TestSettingsEndpoints:
    def test_get_glossary(self, db_and_client):
        resp = client.get("/api/settings/glossary", headers=auth)
        assert resp.status_code == 200
        assert isinstance(resp.json()["terms"], dict)

    def test_update_glossary(self, db_and_client):
        resp = client.put("/api/settings/glossary", json={
            "terms": {"fintech": "פינטק", "blockchain": "בלוקצ'יין"},
        }, headers=auth)
        assert resp.status_code == 200

    def test_get_preferences(self, db_and_client):
        resp = client.get("/api/settings/preferences", headers=auth)
        assert resp.status_code == 200

    def test_update_preferences(self, db_and_client):
        resp = client.put("/api/settings/preferences", json={
            "default_angle": "news",
            "posts_per_day": 5,
            "brief_times": ["08:00", "19:00"],
        }, headers=auth)
        assert resp.status_code == 200

    def test_list_style_examples(self, db_and_client):
        resp = client.get("/api/settings/style-examples", headers=auth)
        assert resp.status_code == 200

    def test_add_style_example(self, db_and_client):
        resp = client.post("/api/settings/style-examples", json={
            "content": "דוגמה לסגנון בעברית",
            "topic_tags": ["fintech", "crypto"],
            "source_type": "manual",
        }, headers=auth)
        assert resp.status_code == 201
```

**Step 2–5:** Implement, test, commit.

```bash
git commit -m "feat: add settings endpoints for glossary, style, preferences"
```

---

### Task 1.7: Brief & Alert Endpoints (for Telegram bot)

Endpoints the Telegram bot will poll for briefs and alerts.

**Files:**
- Create: `src/api/routes/notifications.py`
- Create: `src/api/schemas/notification.py`
- Modify: `src/api/main.py`
- Create: `tests/test_api_notifications.py`

**Step 1: Write failing tests**

```python
# tests/test_api_notifications.py
class TestNotificationEndpoints:
    def test_generate_brief(self, db_and_client):
        resp = client.post("/api/notifications/brief", headers=auth)
        assert resp.status_code == 200
        data = resp.json()
        assert "stories" in data
        assert isinstance(data["stories"], list)

    def test_get_pending_alerts(self, db_and_client):
        resp = client.get("/api/notifications/alerts?delivered=false", headers=auth)
        assert resp.status_code == 200

    def test_mark_alert_delivered(self, db_and_client):
        # Create a notification first
        notif = Notification(type="alert", content={"title": "test"}, delivered=False)
        db.add(notif)
        db.commit()
        resp = client.patch(f"/api/notifications/{notif.id}/delivered", headers=auth)
        assert resp.status_code == 200
        assert resp.json()["delivered"] is True
```

**Step 2–5:** Implement, test, commit.

`POST /api/notifications/brief` — calls NewsScraper.get_latest_news(), generates one-line Hebrew summaries, creates Notification record, returns stories.

```bash
git commit -m "feat: add notification endpoints for briefs and alerts"
```

---

## Phase 2: Next.js Frontend

> Build the web app page by page. Each task is a complete page with API integration.

---

### Task 2.1: Next.js Project Setup

**Files:**
- Create: `frontend/` directory (Next.js project)

**Step 1: Initialize Next.js project**

```bash
cd /Users/itayy16/CursorProjects/HFI
npx create-next-app@latest frontend --typescript --tailwind --eslint --app --src-dir --no-import-alias
```

**Step 2: Install dependencies**

```bash
cd frontend
npm install @tanstack/react-query axios
npx shadcn@latest init  # Choose: dark theme, zinc palette, CSS variables
npx shadcn@latest add button card input textarea badge tabs dialog select dropdown-menu separator toast
npm install @fontsource/heebo
```

**Step 3: Configure RTL + dark theme**

`frontend/tailwind.config.ts`:
```typescript
import type { Config } from "tailwindcss";

const config: Config = {
  darkMode: "class",
  content: ["./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        heebo: ["Heebo", "Arial Hebrew", "system-ui", "sans-serif"],
      },
    },
  },
  plugins: [require("tailwindcss-rtl")],
};

export default config;
```

`frontend/src/app/layout.tsx`:
```tsx
import type { Metadata } from "next";
import "@fontsource/heebo/400.css";
import "@fontsource/heebo/500.css";
import "@fontsource/heebo/700.css";
import "./globals.css";
import { Providers } from "./providers";

export const metadata: Metadata = {
  title: "HFI Content Studio",
  description: "Hebrew FinTech content creation tool",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="he" dir="rtl" className="dark">
      <body className="font-heebo bg-zinc-950 text-zinc-50 min-h-screen">
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
```

**Step 4: Set up API client**

`frontend/src/lib/api.ts`:
```typescript
import axios from "axios";

const api = axios.create({
  baseURL: process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000",
});

api.interceptors.request.use((config) => {
  const token = localStorage.getItem("hfi_token");
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem("hfi_token");
      window.location.href = "/login";
    }
    return Promise.reject(error);
  },
);

export default api;
```

**Step 5: Set up TanStack Query provider**

`frontend/src/app/providers.tsx`:
```tsx
"use client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useState } from "react";

export function Providers({ children }: { children: React.ReactNode }) {
  const [queryClient] = useState(() => new QueryClient({
    defaultOptions: {
      queries: { staleTime: 30_000, retry: 1 },
    },
  }));
  return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
}
```

**Step 6: Verify dev server runs**

```bash
cd frontend && npm run dev
```

Visit `http://localhost:3000` — should show blank dark page.

**Step 7: Commit**

```bash
git add frontend/
git commit -m "feat: initialize Next.js frontend with Tailwind, shadcn, RTL support"
```

---

### Task 2.2: Login Page

**Files:**
- Create: `frontend/src/app/login/page.tsx`
- Create: `frontend/src/hooks/useAuth.ts`

**Implementation:**
- Simple centered card with password input
- Calls `POST /api/auth/login`
- Stores JWT in localStorage
- Redirects to `/` on success
- Shows error toast on failure

**Step 1: Build login page**

```tsx
// frontend/src/app/login/page.tsx
"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import api from "@/lib/api";

export default function LoginPage() {
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const router = useRouter();

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError("");
    try {
      const { data } = await api.post("/api/auth/login", { password });
      localStorage.setItem("hfi_token", data.access_token);
      router.push("/");
    } catch {
      setError("Wrong password");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center">
      <Card className="w-full max-w-sm">
        <CardHeader>
          <CardTitle className="text-center">HFI Content Studio</CardTitle>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleLogin} className="space-y-4">
            <Input
              type="password"
              placeholder="Password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              dir="ltr"
            />
            {error && <p className="text-red-400 text-sm">{error}</p>}
            <Button type="submit" className="w-full" disabled={loading}>
              {loading ? "..." : "Login"}
            </Button>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
```

**Step 2: Verify in browser**

**Step 3: Commit**

```bash
git add frontend/src/app/login/ frontend/src/hooks/
git commit -m "feat: add login page with JWT auth"
```

---

### Task 2.3: App Shell (Sidebar + Layout)

**Files:**
- Create: `frontend/src/components/layout/Sidebar.tsx`
- Create: `frontend/src/components/layout/AppShell.tsx`
- Modify: `frontend/src/app/(app)/layout.tsx` (protected layout)

**Implementation:**
- Left sidebar (fixed) with navigation links: Dashboard, Create, Queue, Inspiration, Library, Settings
- Icons for each nav item (use lucide-react icons, included with shadcn)
- Active state highlighting
- Responsive: collapsible on mobile
- All (app) routes protected — redirect to /login if no token

```bash
npm install lucide-react  # already included with shadcn usually
```

Sidebar links:
```
Dashboard    → /
Create       → /create
Queue        → /queue
Inspiration  → /inspiration
Library      → /library
Settings     → /settings
```

**Step 1: Build Sidebar component**

```tsx
// frontend/src/components/layout/Sidebar.tsx
"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { LayoutDashboard, PenSquare, ListTodo, Sparkles, Library, Settings } from "lucide-react";
import { cn } from "@/lib/utils";

const NAV_ITEMS = [
  { href: "/", label: "Dashboard", icon: LayoutDashboard },
  { href: "/create", label: "Create", icon: PenSquare },
  { href: "/queue", label: "Queue", icon: ListTodo },
  { href: "/inspiration", label: "Inspiration", icon: Sparkles },
  { href: "/library", label: "Library", icon: Library },
  { href: "/settings", label: "Settings", icon: Settings },
];

export function Sidebar() {
  const pathname = usePathname();
  return (
    <aside className="fixed right-0 top-0 h-full w-56 bg-zinc-900 border-l border-zinc-800 p-4 flex flex-col gap-1">
      <h1 className="text-lg font-bold mb-6 px-3">HFI Studio</h1>
      {NAV_ITEMS.map(({ href, label, icon: Icon }) => (
        <Link
          key={href}
          href={href}
          className={cn(
            "flex items-center gap-3 px-3 py-2 rounded-lg text-sm transition-colors",
            pathname === href
              ? "bg-zinc-800 text-white"
              : "text-zinc-400 hover:text-white hover:bg-zinc-800/50",
          )}
        >
          <Icon size={18} />
          {label}
        </Link>
      ))}
    </aside>
  );
}
```

Note: sidebar on the **right** side because RTL layout.

**Step 2: Build AppShell**

```tsx
// frontend/src/app/(app)/layout.tsx
"use client";
import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { Sidebar } from "@/components/layout/Sidebar";

export default function AppLayout({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  useEffect(() => {
    if (!localStorage.getItem("hfi_token")) router.push("/login");
  }, [router]);

  return (
    <div className="flex min-h-screen">
      <Sidebar />
      <main className="flex-1 mr-56 p-6">{children}</main>
    </div>
  );
}
```

**Step 3: Commit**

```bash
git add frontend/src/components/layout/ frontend/src/app/\(app\)/
git commit -m "feat: add app shell with sidebar navigation"
```

---

### Task 2.4: Dashboard Page

**Files:**
- Create: `frontend/src/app/(app)/page.tsx`
- Create: `frontend/src/hooks/useBrief.ts`
- Create: `frontend/src/hooks/useStats.ts`
- Create: `frontend/src/components/dashboard/BriefCard.tsx`
- Create: `frontend/src/components/dashboard/ScheduleTimeline.tsx`
- Create: `frontend/src/components/dashboard/StatsBar.tsx`

**Implementation:**

1. **StatsBar** — 4 stat cards: Drafts | Scheduled Today | Published Today | Total
   - Calls `GET /api/content/drafts?status=pending` (count), etc.

2. **Today's Brief** — list of top stories
   - Calls `POST /api/notifications/brief` on page load (or `GET /api/trends/brief`)
   - Each story card shows: title, sources, one-line summary
   - Actions: "Write" (→ /create?source=trend_id), "Translate", "Skip"

3. **ScheduleTimeline** — horizontal timeline for today's posts
   - Calls `GET /api/content/scheduled`
   - Shows time slots with scheduled post previews

**Key interaction:** Clicking "Write" on a brief story navigates to `/create?source=trend&id=123`

**Step 1: Implement page and components**

**Step 2: Verify API integration in browser**

**Step 3: Commit**

```bash
git commit -m "feat: add dashboard page with brief, stats, and schedule timeline"
```

---

### Task 2.5: Create Page

The core content creation flow.

**Files:**
- Create: `frontend/src/app/(app)/create/page.tsx`
- Create: `frontend/src/components/create/SourceInput.tsx`
- Create: `frontend/src/components/create/AngleSelector.tsx`
- Create: `frontend/src/components/create/VariantCards.tsx`
- Create: `frontend/src/components/create/HebrewEditor.tsx`
- Create: `frontend/src/hooks/useGenerate.ts`
- Create: `frontend/src/hooks/useTranslate.ts`

**Implementation:**

1. **SourceInput** — text area or URL input with auto-detect
   - Accepts: paste URL (tweet/article/thread), raw text, or pre-filled from query params
   - Auto-detects: URL → shows "Tweet" or "Article" badge; text → shows char count
   - Reads `?source=trend&id=123` from URL params to pre-fill from a trend

2. **AngleSelector** — 3 radio buttons: News | Educational | Opinion
   - Persists last choice in localStorage

3. **Generate button** → calls `POST /api/generation/post`

4. **VariantCards** — 2-3 side-by-side RTL cards showing generated Hebrew
   - Each variant shows: angle label, Hebrew text (RTL), char count, quality score badge
   - "Select" button on each → opens in editor

5. **HebrewEditor** — RTL textarea with:
   - `dir="rtl"` and `font-family: Heebo`
   - Character counter (X limit: 280)
   - Copy button (calls `POST /api/content/{id}/copy`)
   - Save as Draft button (calls `POST /api/content`)
   - Schedule button (date/time picker + save)

**Key UX:** Source → Angle → Generate → Pick Variant → Edit → Copy/Save. Minimum clicks.

**Step 1: Implement components**

**Step 2: Test full flow in browser**

**Step 3: Commit**

```bash
git commit -m "feat: add create page with generation flow and RTL editor"
```

---

### Task 2.6: Queue Page

**Files:**
- Create: `frontend/src/app/(app)/queue/page.tsx`
- Create: `frontend/src/components/queue/ContentCard.tsx`
- Create: `frontend/src/hooks/useContent.ts`

**Implementation:**

1. **Tabs:** Drafts | Scheduled | Published
2. **ContentCard** — RTL card with:
   - Hebrew text (right-aligned, Heebo font)
   - Source reference (small, linked)
   - Status badge (color-coded)
   - Scheduled time (if applicable)
   - Actions: Edit (→ /create?edit=id) | Copy | Delete | Reschedule
3. **Pagination** — Load more button
4. **Search** — filter by keyword across original + hebrew text

Calls: `GET /api/content/drafts`, `GET /api/content/scheduled`, `GET /api/content/published`

**Step 1: Implement page and components**

**Step 2: Test in browser**

**Step 3: Commit**

```bash
git commit -m "feat: add queue page with drafts, scheduled, and published tabs"
```

---

### Task 2.7: Inspiration Page

**Files:**
- Create: `frontend/src/app/(app)/inspiration/page.tsx`
- Create: `frontend/src/components/inspiration/SearchForm.tsx`
- Create: `frontend/src/components/inspiration/PostCard.tsx`
- Create: `frontend/src/hooks/useInspiration.ts`

**Implementation:**

1. **SearchForm** — account dropdown + min likes input + keyword input + date range
   - Account dropdown populated from `GET /api/inspiration/accounts`
   - "Search" button → `POST /api/inspiration/search`

2. **PostCard** — shows X post content with engagement stats
   - Engagement bar: likes, retweets, views
   - "Use as Source" button → navigates to `/create?source=inspiration&text=...`
   - Content shown in LTR (English source content)

3. **Results grid** — cards sorted by likes (default)

**Step 1: Implement page**

**Step 2: Test with mock data, then real search**

**Step 3: Commit**

```bash
git commit -m "feat: add inspiration page with account search and post cards"
```

---

### Task 2.8: Content Library Page

**Files:**
- Create: `frontend/src/app/(app)/library/page.tsx`
- Create: `frontend/src/hooks/useLibrary.ts`

**Implementation:**

1. **Search bar** — full-text search across hebrew_draft and original_text
2. **Filters** — status, content_type, date range
3. **Results** — RTL content cards with "Reuse" action
4. Reuses `ContentCard` component from Queue page

Calls: `GET /api/content/drafts?search=...&status=...`

**Step 1: Implement page**

**Step 2: Test in browser**

**Step 3: Commit**

```bash
git commit -m "feat: add content library page with search and filters"
```

---

### Task 2.9: Settings Page

**Files:**
- Create: `frontend/src/app/(app)/settings/page.tsx`
- Create: `frontend/src/components/settings/GlossaryEditor.tsx`
- Create: `frontend/src/components/settings/AccountManager.tsx`
- Create: `frontend/src/components/settings/StyleExampleManager.tsx`
- Create: `frontend/src/components/settings/PreferencesForm.tsx`

**Implementation:**

Sections (collapsible):

1. **Inspiration Accounts** — add/remove X accounts with category tags
2. **Glossary** — key-value editor for EN→HE terms (add, edit, delete rows)
3. **Style Examples** — list examples, add new, edit topic tags, toggle active
4. **Telegram** — show connection status, link to bot
5. **Preferences** — default angle, posts-per-day target, brief times

**Step 1: Implement page and all sections**

**Step 2: Test each section**

**Step 3: Commit**

```bash
git commit -m "feat: add settings page with glossary, accounts, style, and preferences"
```

---

### Task 2.10: Polish & Responsive

**Files:**
- Modify: various component files

**Steps:**

1. **RTL audit** — verify all Hebrew text renders correctly right-to-left
2. **Mobile responsive** — sidebar collapses to hamburger menu below `md` breakpoint
3. **Toast notifications** — add success/error toasts for all actions (copy, save, delete)
4. **Loading states** — add skeleton loaders for all API calls
5. **Error states** — graceful error messages when API is unreachable
6. **Keyboard shortcuts** — Ctrl+Enter to generate, Ctrl+C to copy

```bash
git commit -m "feat: polish UI with responsive layout, toasts, and loading states"
```

---

## Phase 3: Telegram Bot

> Python-based Telegram bot that sends briefs and alerts, accepts commands.

---

### Task 3.1: Bot Setup

**Files:**
- Create: `src/telegram_bot/__init__.py`
- Create: `src/telegram_bot/bot.py`
- Create: `src/telegram_bot/config.py`
- Create: `src/telegram_bot/main.py`
- Create: `tests/test_telegram_bot.py`

**Step 1: Write failing tests**

```python
# tests/test_telegram_bot.py
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

class TestTelegramBot:
    def test_format_brief_message(self):
        from telegram_bot.bot import format_brief_message
        stories = [
            {"title": "SEC approves Bitcoin ETF", "sources": ["Bloomberg", "WSJ"], "summary": "רגולציה חדשה"},
            {"title": "Stripe acquires startup", "sources": ["TechCrunch"], "summary": "רכישה"},
        ]
        msg = format_brief_message(stories, "morning")
        assert "SEC approves Bitcoin ETF" in msg
        assert "Bloomberg" in msg
        assert "/write_1" in msg
        assert "/write_2" in msg

    def test_format_alert_message(self):
        from telegram_bot.bot import format_alert_message
        alert = {"title": "CBDC pilot program", "sources": ["Bloomberg", "WSJ", "Yahoo"], "summary": "בנק מרכזי"}
        msg = format_alert_message(alert)
        assert "CBDC pilot program" in msg
        assert "/write" in msg
```

**Step 2: Run tests, verify fail**

**Step 3: Implement bot**

`src/telegram_bot/config.py`:
```python
import os

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")  # Your personal chat ID
API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")
API_PASSWORD = os.getenv("DASHBOARD_PASSWORD", "")
BRIEF_TIMES = ["08:00", "19:00"]
ALERT_CHECK_INTERVAL_MINUTES = 15
```

`src/telegram_bot/bot.py`:
```python
import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from apscheduler.schedulers.asyncio import AsyncIOScheduler
import httpx

logger = logging.getLogger(__name__)

class HFIBot:
    def __init__(self, token: str, chat_id: str, api_url: str, api_password: str):
        self.chat_id = chat_id
        self.api_url = api_url
        self.api_password = api_password
        self.app = Application.builder().token(token).build()
        self.http = httpx.AsyncClient(base_url=api_url)
        self.jwt_token = None
        self._register_handlers()

    def _register_handlers(self):
        self.app.add_handler(CommandHandler("start", self.cmd_start))
        self.app.add_handler(CommandHandler("status", self.cmd_status))
        self.app.add_handler(CommandHandler("brief", self.cmd_brief))
        self.app.add_handler(CommandHandler("schedule", self.cmd_schedule))
        # /write_1, /write_2, etc. handled via regex
        self.app.add_handler(CommandHandler("write", self.cmd_write))

    async def _ensure_auth(self):
        if not self.jwt_token:
            resp = await self.http.post("/api/auth/login", json={"password": self.api_password})
            self.jwt_token = resp.json()["access_token"]
        return {"Authorization": f"Bearer {self.jwt_token}"}

    async def cmd_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text("HFI Content Studio Bot. Use /brief for latest topics.")

    async def cmd_brief(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        headers = await self._ensure_auth()
        resp = await self.http.post("/api/notifications/brief", headers=headers)
        stories = resp.json()["stories"]
        msg = format_brief_message(stories, "on-demand")
        await update.message.reply_text(msg, parse_mode="HTML")

    async def cmd_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        headers = await self._ensure_auth()
        drafts = await self.http.get("/api/content/drafts?status=pending", headers=headers)
        scheduled = await self.http.get("/api/content/scheduled", headers=headers)
        published = await self.http.get("/api/content/drafts?status=published", headers=headers)
        msg = (
            f"Drafts: {drafts.json()['total']}\n"
            f"Scheduled: {scheduled.json()['total']}\n"
            f"Published: {published.json()['total']}"
        )
        await update.message.reply_text(msg)

    async def cmd_write(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        # Extract trend from context (stored from latest brief)
        headers = await self._ensure_auth()
        source_text = " ".join(context.args) if context.args else ""
        if not source_text:
            await update.message.reply_text("Usage: /write <source text or URL>")
            return
        resp = await self.http.post("/api/generation/post", json={
            "source_text": source_text,
            "num_variants": 2,
        }, headers=headers)
        variants = resp.json()["variants"]
        for v in variants:
            await update.message.reply_text(
                f"<b>{v['label']}</b>\n\n{v['content']}\n\n({v['char_count']} chars)",
                parse_mode="HTML",
            )

    async def send_scheduled_brief(self):
        headers = await self._ensure_auth()
        resp = await self.http.post("/api/notifications/brief", headers=headers)
        stories = resp.json()["stories"]
        if stories:
            msg = format_brief_message(stories, "scheduled")
            await self.app.bot.send_message(chat_id=self.chat_id, text=msg, parse_mode="HTML")

    async def check_alerts(self):
        headers = await self._ensure_auth()
        resp = await self.http.get("/api/notifications/alerts?delivered=false", headers=headers)
        alerts = resp.json().get("alerts", [])
        for alert in alerts:
            msg = format_alert_message(alert["content"])
            await self.app.bot.send_message(chat_id=self.chat_id, text=msg, parse_mode="HTML")
            await self.http.patch(f"/api/notifications/{alert['id']}/delivered", headers=headers)


def format_brief_message(stories: list, brief_type: str) -> str:
    header = f"{'Morning' if brief_type == 'morning' else 'Evening'} Brief" if brief_type in ("morning", "evening") else "Brief"
    lines = [f"<b>{header} — {len(stories)} hot topics</b>\n"]
    for i, s in enumerate(stories, 1):
        sources = ", ".join(s.get("sources", []))
        lines.append(f"{i}. <b>{s['title']}</b>")
        if sources:
            lines.append(f"   Sources: {sources}")
        lines.append(f"   /write_{i}  /skip_{i}\n")
    return "\n".join(lines)


def format_alert_message(alert: dict) -> str:
    sources = ", ".join(alert.get("sources", []))
    return (
        f"Breaking: {alert['title']}\n"
        f"Sources: {sources}\n\n"
        f"/write  /translate  /skip"
    )
```

**Step 4: Run tests**

```bash
pytest tests/test_telegram_bot.py -v
```

**Step 5: Commit**

```bash
git add src/telegram_bot/ tests/test_telegram_bot.py
git commit -m "feat: add Telegram bot with briefs, alerts, and commands"
```

---

### Task 3.2: Scheduler Integration

**Files:**
- Modify: `src/telegram_bot/main.py`
- Create: `src/telegram_bot/scheduler.py`
- Create: `tests/test_telegram_scheduler.py`

**Implementation:**

- APScheduler runs inside the bot process
- Two cron jobs: 8:00 AM and 7:00 PM → `send_scheduled_brief()`
- One interval job: every 15 min → `check_alerts()`
- Alert detection: `POST /api/trends/fetch` → check if any trend has source_count >= 3 and was discovered in last 30 min → create Notification

`src/telegram_bot/scheduler.py`:
```python
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

def setup_scheduler(bot):
    scheduler = AsyncIOScheduler()
    # Morning brief at 8:00 AM
    scheduler.add_job(bot.send_scheduled_brief, CronTrigger(hour=8, minute=0))
    # Evening brief at 7:00 PM
    scheduler.add_job(bot.send_scheduled_brief, CronTrigger(hour=19, minute=0))
    # Check for alerts every 15 minutes
    scheduler.add_job(bot.check_alerts, IntervalTrigger(minutes=15))
    return scheduler
```

`src/telegram_bot/main.py`:
```python
import asyncio
from telegram_bot.bot import HFIBot
from telegram_bot.config import *
from telegram_bot.scheduler import setup_scheduler

async def main():
    bot = HFIBot(TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, API_BASE_URL, API_PASSWORD)
    scheduler = setup_scheduler(bot)
    scheduler.start()
    await bot.app.run_polling()

if __name__ == "__main__":
    asyncio.run(main())
```

**Step 1: Write tests, Step 2: Run, Step 3: Implement, Step 4: Verify, Step 5: Commit**

```bash
git commit -m "feat: add scheduler for twice-daily briefs and alert polling"
```

---

## Phase 4: Integration, Deployment & Cleanup

---

### Task 4.1: Inspiration Search Implementation

Implement actual X search via Playwright for the inspiration feed.

**Files:**
- Modify: `src/scraper/scraper.py` — add `search_by_user_engagement()` method
- Modify: `src/api/routes/inspiration.py` — wire up real scraper
- Create: `tests/test_inspiration_scraper.py`

**Implementation:**

Add to `TwitterScraper`:
```python
async def search_by_user_engagement(self, username: str, min_faves: int = 100, keyword: str = "", limit: int = 20) -> list:
    """Search X for posts from a user with minimum engagement."""
    query = f"from:{username} min_faves:{min_faves}"
    if keyword:
        query += f" {keyword}"
    await self.ensure_logged_in()
    # Navigate to X search
    await self.page.goto(f"https://x.com/search?q={quote(query)}&src=typed_query&f=top")
    await self.page.wait_for_timeout(3000)
    # Scroll and collect tweets
    tweets = await self._scroll_and_collect(limit=limit)
    return tweets
```

Cache results in `inspiration_posts` table (1-hour TTL).

```bash
git commit -m "feat: implement inspiration search via X scraper"
```

---

### Task 4.2: Alert Detection System

Implement the background system that detects cross-source trending topics and creates alert notifications.

**Files:**
- Create: `src/processor/alert_detector.py`
- Modify: `src/api/routes/notifications.py`
- Create: `tests/test_alert_detector.py`

**Implementation:**

```python
# src/processor/alert_detector.py
class AlertDetector:
    def __init__(self, news_scraper, db_session):
        self.news_scraper = news_scraper
        self.db = db_session

    def check_for_alerts(self, min_sources: int = 3) -> list:
        """Fetch latest news and check for cross-source stories."""
        articles = self.news_scraper.get_latest_news(limit_per_source=10, total_limit=20)
        alerts = []
        for article in articles:
            if article.get("source_count", 1) >= min_sources:
                # Check if we already alerted on this topic (dedup by title similarity)
                if not self._already_alerted(article["title"]):
                    alerts.append(article)
                    self._create_notification(article)
        return alerts
```

The Telegram bot's `check_alerts()` calls `GET /api/notifications/alerts?delivered=false` which returns undelivered alert notifications.

```bash
git commit -m "feat: add alert detection for cross-source trending topics"
```

---

### Task 4.3: Docker & Deployment Updates

**Files:**
- Modify: `docker-compose.yml` — add frontend, telegram_bot services
- Create: `frontend/Dockerfile`
- Create: `src/telegram_bot/Dockerfile`
- Modify: existing Dockerfiles if needed

**Step 1: Frontend Dockerfile**

```dockerfile
FROM node:20-alpine AS builder
WORKDIR /app
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ .
RUN npm run build

FROM node:20-alpine
WORKDIR /app
COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static
COPY --from=builder /app/public ./public
EXPOSE 3000
CMD ["node", "server.js"]
```

**Step 2: Telegram bot Dockerfile**

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY src/ /app/src/
COPY config/ /app/config/
ENV PYTHONPATH=/app/src
RUN pip install python-telegram-bot apscheduler httpx
CMD ["python", "-m", "telegram_bot.main"]
```

**Step 3: Update docker-compose.yml**

Add:
```yaml
  frontend:
    build:
      context: .
      dockerfile: frontend/Dockerfile
    ports:
      - "3000:3000"
    environment:
      - NEXT_PUBLIC_API_URL=http://api:8000
    depends_on:
      - api

  telegram-bot:
    build:
      context: .
      dockerfile: src/telegram_bot/Dockerfile
    environment:
      - TELEGRAM_BOT_TOKEN=${TELEGRAM_BOT_TOKEN}
      - TELEGRAM_CHAT_ID=${TELEGRAM_CHAT_ID}
      - API_BASE_URL=http://api:8000
      - DASHBOARD_PASSWORD=${DASHBOARD_PASSWORD}
    depends_on:
      - api

  api:
    build:
      context: .
      dockerfile: src/api/Dockerfile
    ports:
      - "8000:8000"
    volumes:
      - ./data:/app/data
      - ./config:/app/config
    environment:
      - DATABASE_URL=sqlite:///data/hfi.db
      - OPENAI_API_KEY=${OPENAI_API_KEY}
      - DASHBOARD_PASSWORD=${DASHBOARD_PASSWORD}
      - JWT_SECRET=${JWT_SECRET}
```

**Step 4: Commit**

```bash
git commit -m "feat: add Docker setup for frontend, API, and Telegram bot"
```

---

### Task 4.4: Retire Streamlit Dashboard

**Files:**
- Remove or archive: `src/dashboard/` (move to `archive/dashboard-v1/` for reference)
- Modify: `docker-compose.yml` — remove dashboard service
- Update: `CLAUDE.md`, `README.md`

**Steps:**

1. Move `src/dashboard/` → `archive/dashboard-v1/`
2. Update docker-compose to remove old dashboard service
3. Update CLAUDE.md to reflect new architecture
4. Update README.md with new setup instructions

```bash
git commit -m "chore: archive Streamlit dashboard, replace with Next.js frontend"
```

---

### Task 4.5: Environment & Documentation Updates

**Files:**
- Modify: `.env.example` (add new variables)
- Modify: `README.md`
- Modify: `CLAUDE.md`

**New env vars needed:**
```bash
# Telegram
TELEGRAM_BOT_TOKEN=...
TELEGRAM_CHAT_ID=...

# JWT
JWT_SECRET=...

# API
API_BASE_URL=http://localhost:8000
NEXT_PUBLIC_API_URL=http://localhost:8000
```

**Update README with:**
- New architecture diagram
- Setup instructions for Next.js frontend
- Telegram bot setup guide (BotFather → get token → get chat ID)
- Updated Docker Compose instructions

```bash
git commit -m "docs: update README and env config for v2 architecture"
```

---

### Task 4.6: End-to-End Testing

**Files:**
- Create: `tests/test_e2e_flow.py`

**Test the full workflow:**
1. Login via API → get JWT
2. Fetch brief → get stories
3. Generate Hebrew post from story → get variants
4. Save as draft → verify in drafts list
5. Update status to approved → verify in scheduled
6. Copy → verify copy_count incremented
7. Search content → verify searchable

```python
# tests/test_e2e_flow.py
class TestE2EWorkflow:
    def test_full_content_creation_flow(self, client, db):
        # 1. Login
        resp = client.post("/api/auth/login", json={"password": "testpass"})
        token = resp.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # 2. Generate post
        resp = client.post("/api/generation/post", json={
            "source_text": "SEC approves new Bitcoin ETF framework for institutional investors",
            "num_variants": 2,
            "angles": ["news", "educational"],
        }, headers=headers)
        assert resp.status_code == 200
        variants = resp.json()["variants"]
        assert len(variants) == 2

        # 3. Save best variant as draft
        best = variants[0]
        resp = client.post("/api/content", json={
            "source_url": "https://example.com/article",
            "original_text": "SEC approves new Bitcoin ETF framework",
            "hebrew_draft": best["content"],
            "content_type": "generation",
        }, headers=headers)
        assert resp.status_code == 201
        content_id = resp.json()["id"]

        # 4. Approve
        resp = client.patch(f"/api/content/{content_id}", json={
            "status": "approved",
        }, headers=headers)
        assert resp.status_code == 200

        # 5. Copy
        resp = client.post(f"/api/content/{content_id}/copy", headers=headers)
        assert resp.json()["copy_count"] == 1

        # 6. Search
        resp = client.get("/api/content/drafts?search=Bitcoin", headers=headers)
        assert resp.json()["total"] >= 1
```

```bash
git commit -m "test: add end-to-end workflow tests"
```

---

## Task Summary

| Phase | Task | Description | Est. Complexity |
|-------|------|-------------|-----------------|
| 1.1 | DB Models | New tables: inspiration, notifications, preferences | Small |
| 1.2 | Auth (JWT) | Login + refresh + JWT middleware | Small |
| 1.3 | Content CRUD | Drafts, scheduled, published endpoints | Medium |
| 1.4 | Generation API | Expose translate + generate through API | Medium |
| 1.5 | Inspiration API | Account CRUD + search endpoints | Medium |
| 1.6 | Settings API | Glossary, style, preferences endpoints | Small |
| 1.7 | Notifications API | Brief generation + alert endpoints | Medium |
| 2.1 | Next.js Setup | Project init, Tailwind, shadcn, RTL | Small |
| 2.2 | Login Page | JWT login form | Small |
| 2.3 | App Shell | Sidebar navigation + protected layout | Small |
| 2.4 | Dashboard | Brief, stats, schedule timeline | Large |
| 2.5 | Create Page | Source → generate → edit → save flow | Large |
| 2.6 | Queue Page | Drafts/scheduled/published tabs | Medium |
| 2.7 | Inspiration | Search accounts + post cards | Medium |
| 2.8 | Library | Content search + reuse | Small |
| 2.9 | Settings | Glossary, accounts, style, preferences | Medium |
| 2.10 | Polish | RTL audit, responsive, toasts, loading | Medium |
| 3.1 | Telegram Bot | Commands + message formatting | Medium |
| 3.2 | Scheduler | APScheduler for briefs + alert checks | Small |
| 4.1 | Inspiration Scraper | X search by user + engagement | Medium |
| 4.2 | Alert Detector | Cross-source topic detection | Medium |
| 4.3 | Docker | Dockerfiles + compose for all services | Small |
| 4.4 | Retire Streamlit | Archive old dashboard | Small |
| 4.5 | Docs Update | README, CLAUDE.md, env config | Small |
| 4.6 | E2E Tests | Full workflow integration tests | Medium |

**Total: 25 tasks across 4 phases.**

**Recommended execution order:** Phase 1 (API) → Phase 2 (Frontend) → Phase 3 (Bot) → Phase 4 (Integration). Each phase builds on the previous.
