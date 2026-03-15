"""Inspiration account and search endpoints."""

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from api.dependencies import get_db, require_jwt
from api.routes.scrape import get_scraper
from api.schemas.inspiration import (
    InspirationAccountCreate,
    InspirationAccountUpdate,
    InspirationAccountResponse,
    InspirationAccountListResponse,
    InspirationSearchRequest,
    InspirationSearchResponse,
)
from common.models import InspirationAccount, InspirationPost
from scraper.errors import SessionExpiredError

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/inspiration",
    tags=["inspiration"],
    dependencies=[Depends(require_jwt)],
)

_CACHE_TTL = timedelta(hours=1)


@router.get("/accounts", response_model=InspirationAccountListResponse)
def list_accounts(db: Session = Depends(get_db)):
    """List configured inspiration accounts."""
    accounts = db.query(InspirationAccount).order_by(InspirationAccount.username.asc()).all()
    return InspirationAccountListResponse(accounts=accounts)


@router.post("/accounts", response_model=InspirationAccountResponse, status_code=201)
def add_account(payload: InspirationAccountCreate, db: Session = Depends(get_db)):
    """Create a new inspiration account."""
    existing = db.query(InspirationAccount).filter(InspirationAccount.username == payload.username).first()
    if existing:
        raise HTTPException(status_code=409, detail="Account already exists")

    account = InspirationAccount(**payload.model_dump())
    db.add(account)
    db.commit()
    db.refresh(account)
    return account


@router.patch("/accounts/{account_id}", response_model=InspirationAccountResponse)
def update_account(account_id: int, payload: InspirationAccountUpdate, db: Session = Depends(get_db)):
    """Update inspiration account metadata."""
    account = db.get(InspirationAccount, account_id)
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(account, field, value)

    db.commit()
    db.refresh(account)
    return account


@router.delete("/accounts/{account_id}", status_code=204)
def remove_account(account_id: int, db: Session = Depends(get_db)):
    """Delete inspiration account."""
    account = db.get(InspirationAccount, account_id)
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")

    db.delete(account)
    db.commit()


def _build_query_key(username: str, min_likes: int, keyword: str, since: str = "", until: str = "", sort_by: str = "top") -> str:
    return f"{username.lower()}::{min_likes}::{keyword.strip().lower()}::{since}::{until}::{sort_by}"


def _parse_dt(value):
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            normalized = value.replace("Z", "+00:00")
            return datetime.fromisoformat(normalized)
        except ValueError:
            return None
    return None


def _safe_url(value):
    if not value:
        return None
    raw = str(value).strip()
    parsed = urlparse(raw)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return None
    if parsed.username or parsed.password:
        return None
    return raw


@router.post("/search", response_model=InspirationSearchResponse)
async def search_posts(payload: InspirationSearchRequest, db: Session = Depends(get_db)):
    """Search high-engagement posts for a user and cache results."""
    account = (
        db.query(InspirationAccount)
        .filter(InspirationAccount.username == payload.username)
        .first()
    )
    if not account:
        raise HTTPException(status_code=404, detail=f"Account @{payload.username} not tracked. Add it first.")

    query_key = _build_query_key(payload.username, payload.min_likes, payload.keyword, payload.since or "", payload.until or "", payload.sort_by)
    now = datetime.now(timezone.utc)
    cutoff = now - _CACHE_TTL

    cached = (
        db.query(InspirationPost)
        .filter(
            InspirationPost.account_id == account.id,
            InspirationPost.query_key == query_key,
            InspirationPost.fetched_at >= cutoff,
        )
        .order_by(InspirationPost.posted_at.desc() if payload.sort_by == "latest" else InspirationPost.likes.desc())
        .limit(payload.limit)
        .all()
    )
    if cached:
        return InspirationSearchResponse(posts=cached, cached=True, query=query_key)

    try:
        scraper = await get_scraper()
        posts = await asyncio.wait_for(
            scraper.search_by_user_engagement(
                username=payload.username,
                min_faves=payload.min_likes,
                keyword=payload.keyword,
                limit=payload.limit,
                since=payload.since,
                until=payload.until,
                sort_by=payload.sort_by,
            ),
            timeout=90,
        )
    except SessionExpiredError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except asyncio.TimeoutError:
        raise HTTPException(
            status_code=504,
            detail="X search timed out. The session may be expired or X may be slow.",
        )
    except Exception as exc:
        logger.error(f"Inspiration search failed for @{payload.username}: {type(exc).__name__}: {exc}")
        raise HTTPException(
            status_code=502,
            detail="Scraper encountered an internal error",
        ) from exc

    rows = []
    post_ids = []
    for raw in posts:
        post_id = str(raw.get("tweet_id") or raw.get("id") or raw.get("x_post_id") or "").strip()
        if post_id:
            post_ids.append(post_id)

    existing_map = {}
    if post_ids:
        existing_rows = (
            db.query(InspirationPost)
            .filter(InspirationPost.x_post_id.in_(set(post_ids)))
            .all()
        )
        existing_map = {row.x_post_id: row for row in existing_rows}

    for raw in posts:
        post_id = str(raw.get("tweet_id") or raw.get("id") or raw.get("x_post_id") or "").strip()
        if not post_id:
            continue

        existing = existing_map.get(post_id)
        if existing:
            existing.account_id = account.id
            existing.content = raw.get("text") or raw.get("content")
            existing.post_url = _safe_url(raw.get("url") or raw.get("permalink"))
            existing.likes = int(raw.get("likes") or 0)
            existing.retweets = int(raw.get("retweets") or raw.get("reposts") or 0)
            existing.views = int(raw.get("views") or 0)
            existing.posted_at = _parse_dt(raw.get("timestamp"))
            existing.fetched_at = now
            existing.query_key = query_key
            rows.append(existing)
            continue

        row = InspirationPost(
            account_id=account.id,
            x_post_id=post_id,
            content=raw.get("text") or raw.get("content"),
            post_url=_safe_url(raw.get("url") or raw.get("permalink")),
            likes=int(raw.get("likes") or 0),
            retweets=int(raw.get("retweets") or raw.get("reposts") or 0),
            views=int(raw.get("views") or 0),
            posted_at=_parse_dt(raw.get("timestamp")),
            fetched_at=now,
            query_key=query_key,
        )
        db.add(row)
        rows.append(row)

    db.flush()
    db.commit()
    if payload.sort_by == "latest":
        rows.sort(key=lambda item: item.posted_at or datetime.min.replace(tzinfo=timezone.utc), reverse=True)
    else:
        rows.sort(key=lambda item: item.likes, reverse=True)
    return InspirationSearchResponse(posts=rows[: payload.limit], cached=False, query=query_key)
