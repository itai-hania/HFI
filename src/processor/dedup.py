"""
Topic deduplication for content generation.

Tracks recently generated topics and angles to prevent repetitive content.
Uses keyword-based Jaccard similarity to detect near-duplicate topics across
a configurable lookback window.
"""

import hashlib
import json
import logging
import re
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Set, Tuple

from sqlalchemy.orm import Session

from common.models import Tweet, TweetStatus
from common.stopwords import STOPWORDS

logger = logging.getLogger(__name__)

_COMMON_WORDS: Set[str] = {
    'said', 'says', 'new', 'year', 'time', 'way', 'day', 'made', 'make',
    'like', 'long', 'look', 'come', 'over', 'such', 'take', 'last', 'first',
    'after', 'back', 'only', 'other', 'into', 'even', 'well', 'because',
    'good', 'give', 'most', 'tell', 'need', 'want',
}

_WORD_RE = re.compile(r'[a-zA-Z]+')


def _extract_keywords(text: str) -> Set[str]:
    """Extract significant words from text, removing stopwords and short words."""
    words = _WORD_RE.findall(text.lower())
    return {
        w for w in words
        if len(w) > 3 and w not in STOPWORDS and w not in _COMMON_WORDS
    }


def _extract_entities(text: str) -> Set[str]:
    """Extract likely named entities (capitalized words that aren't sentence starters)."""
    words = text.split()
    entities: Set[str] = set()
    for i, word in enumerate(words):
        cleaned = re.sub(r'[^a-zA-Z]', '', word)
        if not cleaned or len(cleaned) <= 2:
            continue
        if cleaned[0].isupper() and cleaned.lower() not in STOPWORDS:
            if i > 0 and not words[i - 1].endswith(('.', '!', '?', ':')):
                entities.add(cleaned)
    return entities


def _jaccard_similarity(set_a: Set[str], set_b: Set[str]) -> float:
    """Compute Jaccard similarity between two sets."""
    if not set_a and not set_b:
        return 1.0
    if not set_a or not set_b:
        return 0.0
    intersection = set_a & set_b
    union = set_a | set_b
    return len(intersection) / len(union)


def get_recent_topics(
    db: Session,
    lookback_hours: int = 72,
    statuses: Optional[List[TweetStatus]] = None,
) -> List[dict]:
    """Fetch generation_metadata from recently generated tweets.

    Queries Tweet model for records with:
    - created_at within lookback window
    - status in provided statuses (default: PROCESSED, APPROVED, PUBLISHED)
    - generation_metadata is not None
    """
    if statuses is None:
        statuses = [TweetStatus.PROCESSED, TweetStatus.APPROVED, TweetStatus.PUBLISHED]

    cutoff = datetime.now(timezone.utc) - timedelta(hours=lookback_hours)

    rows = (
        db.query(Tweet.generation_metadata)
        .filter(
            Tweet.created_at >= cutoff,
            Tweet.status.in_(statuses),
            Tweet.generation_metadata.isnot(None),
        )
        .all()
    )

    results: List[dict] = []
    for (meta,) in rows:
        if meta is None:
            continue
        if isinstance(meta, str):
            try:
                meta = json.loads(meta)
            except (json.JSONDecodeError, ValueError):
                continue
        if isinstance(meta, dict):
            results.append(meta)

    logger.info(f"Fetched {len(results)} recent topic(s) within {lookback_hours}h window")
    return results


def extract_topic_fingerprint(source_text: str) -> dict:
    """Extract a topic fingerprint from source text.

    Returns dict with:
    - 'keywords': set of significant words (lowercase, >3 chars, excluding stopwords)
    - 'source_hash': MD5 hex prefix (12 chars)
    - 'entities': extracted names (capitalized words that aren't common)
    """
    if not source_text:
        return {
            'keywords': set(),
            'source_hash': hashlib.md5(b'').hexdigest()[:12],
            'entities': set(),
        }

    keywords = _extract_keywords(source_text)
    source_hash = hashlib.md5(source_text.encode('utf-8')).hexdigest()[:12]
    entities = _extract_entities(source_text)

    return {
        'keywords': keywords,
        'source_hash': source_hash,
        'entities': entities,
    }


def is_duplicate_topic(
    fingerprint: dict,
    recent_topics: List[dict],
    threshold: float = 0.6,
) -> Tuple[bool, Optional[str]]:
    """Check if a topic fingerprint is too similar to recent content.

    Computes Jaccard similarity between fingerprint keywords and
    each recent topic's keywords.

    Returns (is_duplicate, reason_string_or_None)
    """
    if not recent_topics:
        return False, None

    fp_keywords = fingerprint.get('keywords', set())
    if isinstance(fp_keywords, list):
        fp_keywords = set(fp_keywords)

    if not fp_keywords:
        return False, None

    for topic in recent_topics:
        topic_keywords = topic.get('keywords', set())
        if isinstance(topic_keywords, list):
            topic_keywords = set(topic_keywords)
        if not topic_keywords:
            continue

        similarity = _jaccard_similarity(fp_keywords, topic_keywords)
        if similarity >= threshold:
            overlap = fp_keywords & topic_keywords
            return True, (
                f"Topic similarity {similarity:.0%} >= {threshold:.0%} threshold. "
                f"Overlapping keywords: {', '.join(sorted(overlap)[:5])}"
            )

    return False, None


def build_dedup_metadata(
    source_text: str,
    angle: str,
    tweet_type: str = None,
) -> dict:
    """Build generation_metadata dict for storage on the Tweet.

    Returns dict with:
    - 'angle': str
    - 'tweet_type': str or None
    - 'source_hash': str (12 chars)
    - 'keywords': list of keywords
    - 'generated_at': ISO timestamp
    """
    fingerprint = extract_topic_fingerprint(source_text)

    return {
        'angle': angle,
        'tweet_type': tweet_type,
        'source_hash': fingerprint['source_hash'],
        'keywords': sorted(fingerprint['keywords']),
        'generated_at': datetime.now(timezone.utc).isoformat(),
    }
