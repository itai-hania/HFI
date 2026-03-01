"""
Style Manager for HFI Application

Handles CRUD operations for style examples and auto topic extraction.
Used by the Settings UI and TranslationService for few-shot prompting.
"""

import json
import os
import re
import logging
from typing import List, Optional, Dict
from datetime import datetime, timezone

from sqlalchemy import func
from sqlalchemy.orm import Session

from common.models import StyleExample
from common.openai_client import get_openai_client

logger = logging.getLogger(__name__)


def count_words(text: str) -> int:
    """Count words in text (handles Hebrew and English)."""
    if not text:
        return 0
    # Split on whitespace and filter empty strings
    words = [w for w in text.split() if w.strip()]
    return len(words)


def is_hebrew_content(text: str, min_ratio: float = 0.5) -> bool:
    """Check if text contains sufficient Hebrew characters."""
    if not text:
        return False
    hebrew_chars = sum(1 for c in text if '\u0590' <= c <= '\u05FF')
    alpha_chars = sum(1 for c in text if c.isalpha())
    if alpha_chars == 0:
        return False
    return (hebrew_chars / alpha_chars) >= min_ratio


def add_style_example(
    db: Session,
    content: str,
    source_type: str = 'manual',
    source_url: Optional[str] = None,
    topic_tags: Optional[List[str]] = None
) -> Optional[StyleExample]:
    """
    Add a new style example to the database.

    Args:
        db: Database session
        content: Hebrew text content
        source_type: 'x_thread', 'local_file', or 'manual'
        source_url: Original URL if from X
        topic_tags: List of topic tags

    Returns:
        Created StyleExample or None if failed
    """
    if not content or not content.strip():
        logger.warning("Cannot add empty content")
        return None

    content = content.strip()
    word_count = count_words(content)

    if word_count < 10:
        logger.warning(f"Content too short ({word_count} words), minimum 10 required")
        return None

    example = StyleExample(
        content=content,
        source_type=source_type,
        source_url=source_url,
        topic_tags=topic_tags or [],
        word_count=word_count,
        is_active=True
    )

    try:
        db.add(example)
        db.commit()
        db.refresh(example)
        logger.info(f"Added style example {example.id} ({word_count} words)")
        return example
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to add style example: {e}")
        return None


def get_all_examples(db: Session, include_inactive: bool = False) -> List[StyleExample]:
    """Get all style examples, optionally including soft-deleted ones."""
    query = db.query(StyleExample).order_by(StyleExample.created_at.desc())
    if not include_inactive:
        query = query.filter(StyleExample.is_active == True)
    return query.all()


def get_examples_by_tags(db: Session, tags: List[str], limit: int = 5) -> List[StyleExample]:
    """
    Get style examples that match any of the given topic tags.

    Args:
        db: Database session
        tags: List of topic tags to match
        limit: Maximum number of examples to return

    Returns:
        List of matching StyleExample objects
    """
    if not tags:
        return get_recent_examples(db, limit=limit)

    # Get all active examples
    all_examples = get_all_examples(db)

    # Pre-compute lowercase tag set once
    tags_lower = {t.lower() for t in tags}

    # Score examples by tag overlap
    scored = []
    for example in all_examples:
        example_tags = example.topic_tags or []
        if isinstance(example_tags, str):
            try:
                example_tags = json.loads(example_tags)
            except (json.JSONDecodeError, ValueError):
                example_tags = []
        example_tags_lower = {et.lower() for et in example_tags}
        matches = len(tags_lower & example_tags_lower)
        scored.append((example, matches))

    # Sort by matches (desc), then by word count (prefer varied lengths)
    scored.sort(key=lambda x: (-x[1], -x[0].word_count))

    return [ex for ex, _ in scored[:limit]]


def get_recent_examples(db: Session, limit: int = 5) -> List[StyleExample]:
    """Get most recent active style examples."""
    return (
        db.query(StyleExample)
        .filter(StyleExample.is_active == True)
        .order_by(StyleExample.created_at.desc())
        .limit(limit)
        .all()
    )


def get_diverse_examples(db: Session, limit: int = 5) -> List[StyleExample]:
    """
    Get a diverse set of examples with varied word counts.

    Selects examples to cover different lengths (short, medium, long)
    using SQL OFFSET to avoid loading the full table.
    """
    total = db.query(func.count(StyleExample.id)).filter(StyleExample.is_active == True).scalar() or 0
    if total <= limit:
        return get_all_examples(db)

    base_query = db.query(StyleExample).filter(
        StyleExample.is_active == True
    ).order_by(StyleExample.word_count)

    result = []
    seen_ids = set()
    for i in range(limit):
        offset = i * total // limit
        row = base_query.offset(offset).limit(1).first()
        if row and row.id not in seen_ids:
            result.append(row)
            seen_ids.add(row.id)

    return result


def delete_example(db: Session, example_id: int, hard_delete: bool = False) -> bool:
    """
    Delete a style example (soft delete by default).

    Args:
        db: Database session
        example_id: ID of example to delete
        hard_delete: If True, permanently remove from database

    Returns:
        True if deleted, False if not found
    """
    example = db.query(StyleExample).filter(StyleExample.id == example_id).first()
    if not example:
        return False

    if hard_delete:
        db.delete(example)
    else:
        example.is_active = False

    db.commit()
    logger.info(f"Deleted style example {example_id} (hard={hard_delete})")
    return True


def update_example(
    db: Session,
    example_id: int,
    content: Optional[str] = None,
    topic_tags: Optional[List[str]] = None
) -> Optional[StyleExample]:
    """Update an existing style example."""
    example = db.query(StyleExample).filter(StyleExample.id == example_id).first()
    if not example:
        return None

    if content is not None:
        example.content = content.strip()
        example.word_count = count_words(content)

    if topic_tags is not None:
        example.topic_tags = topic_tags

    db.commit()
    db.refresh(example)
    logger.info(f"Updated style example {example_id}")
    return example


def get_example_stats(db: Session) -> Dict:
    """Get statistics about style examples using SQL aggregation."""
    count = db.query(func.count(StyleExample.id)).filter(StyleExample.is_active == True).scalar() or 0
    if count == 0:
        return {'count': 0, 'total_words': 0, 'topics': [], 'avg_words': 0, 'sources': {}}

    total_words = db.query(func.sum(StyleExample.word_count)).filter(StyleExample.is_active == True).scalar() or 0

    # Source counts via GROUP BY
    source_rows = db.query(StyleExample.source_type, func.count(StyleExample.id)).filter(
        StyleExample.is_active == True
    ).group_by(StyleExample.source_type).all()
    sources = {st: cnt for st, cnt in source_rows}

    # Topics still need loading since they're JSON arrays, but only fetch needed columns
    tag_rows = db.query(StyleExample.topic_tags).filter(
        StyleExample.is_active == True, StyleExample.topic_tags.isnot(None)
    ).all()
    all_topics = set()
    for (tags,) in tag_rows:
        if isinstance(tags, list):
            all_topics.update(tags)
        elif isinstance(tags, str):
            try:
                all_topics.update(json.loads(tags))
            except (json.JSONDecodeError, ValueError):
                pass

    return {
        'count': count,
        'total_words': total_words,
        'topics': list(all_topics),
        'avg_words': total_words // count if count else 0,
        'sources': sources
    }


def record_feedback(db: Session, example_id: int, approved: bool) -> bool:
    """Record approval/rejection feedback on a style example.

    Args:
        db: Database session
        example_id: ID of the style example
        approved: True for approval, False for rejection

    Returns:
        True if feedback recorded, False if example not found
    """
    example = db.query(StyleExample).filter(StyleExample.id == example_id).first()
    if not example:
        return False

    if approved:
        example.approval_count = (example.approval_count or 0) + 1
    else:
        example.rejection_count = (example.rejection_count or 0) + 1

    db.commit()
    logger.info(f"Recorded {'approval' if approved else 'rejection'} for style example {example_id}")
    return True


def find_examples_by_tag_overlap(db: Session, tags: List[str], limit: int = 5) -> List[StyleExample]:
    """Find style examples with overlapping topic tags for feedback propagation."""
    if not tags:
        return []
    all_examples = get_all_examples(db)
    tags_lower = {t.lower() for t in tags}
    matched = []
    for ex in all_examples:
        ex_tags = ex.topic_tags or []
        if isinstance(ex_tags, str):
            try:
                ex_tags = json.loads(ex_tags)
            except (json.JSONDecodeError, ValueError):
                ex_tags = []
        ex_tags_lower = {et.lower() for et in ex_tags}
        overlap = len(tags_lower & ex_tags_lower)
        if overlap > 0:
            matched.append((ex, overlap))
    matched.sort(key=lambda x: -x[1])
    return [ex for ex, _ in matched[:limit]]


def export_to_json(db: Session) -> str:
    """Export all active style examples to JSON."""
    examples = get_all_examples(db)
    data = [ex.to_dict() for ex in examples]
    return json.dumps(data, indent=2, ensure_ascii=False)


def extract_topic_tags(content: str, openai_client=None) -> List[str]:
    """
    Extract topic tags from Hebrew content using GPT-4o.

    Args:
        content: Hebrew text to analyze
        openai_client: OpenAI client instance

    Returns:
        List of 2-5 topic tags
    """
    if not openai_client:
        try:
            openai_client = get_openai_client()
        except ValueError:
            logger.warning("No OpenAI API key, using fallback tagging")
            return _fallback_topic_tags(content)

    # Predefined tag vocabulary
    tag_vocabulary = [
        'fintech', 'crypto', 'bitcoin', 'ethereum', 'blockchain',
        'banking', 'payments', 'investing', 'trading', 'markets',
        'regulation', 'startups', 'AI', 'technology', 'economics',
        'inflation', 'interest_rates', 'stocks', 'IPO', 'VC',
        'DeFi', 'NFT', 'Web3', 'digital_assets', 'CBDC'
    ]

    prompt = f"""Analyze this Hebrew financial/tech content and select 2-5 relevant topic tags.

AVAILABLE TAGS:
{', '.join(tag_vocabulary)}

CONTENT:
{content[:1500]}

Return ONLY a JSON array of tags, e.g.: ["fintech", "crypto", "blockchain"]
Select the most specific and relevant tags."""

    try:
        model = os.getenv('OPENAI_MODEL', 'gpt-4o')
        response = openai_client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "You extract topic tags from Hebrew financial content. Return only a JSON array."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=100
        )

        result = response.choices[0].message.content.strip()

        # Parse JSON array
        if result.startswith('['):
            tags = json.loads(result)
            # Validate tags
            vocab_lower = {v.lower() for v in tag_vocabulary}
            valid_tags = [t for t in tags if t.lower() in vocab_lower]
            if valid_tags:
                logger.info(f"Extracted tags: {valid_tags}")
                return valid_tags[:5]

        logger.warning(f"Could not parse tags from: {result}")
        return _fallback_topic_tags(content)

    except Exception as e:
        logger.error(f"Tag extraction failed: {e}")
        return _fallback_topic_tags(content)


def _fallback_topic_tags(content: str) -> List[str]:
    """Fallback topic tagging based on keyword detection."""
    content_lower = content.lower()

    tag_keywords = {
        'fintech': ['פינטק', 'fintech', 'פיננסי', 'financial'],
        'crypto': ['קריפטו', 'crypto', 'מטבע דיגיטלי'],
        'bitcoin': ['ביטקוין', 'bitcoin', 'btc'],
        'blockchain': ['בלוקצ\'יין', 'blockchain'],
        'banking': ['בנק', 'bank', 'בנקאות'],
        'payments': ['תשלום', 'payment', 'העברה'],
        'investing': ['השקע', 'invest', 'תיק השקעות'],
        'AI': ['בינה מלאכותית', 'ai', 'למידת מכונה'],
        'startups': ['סטארטאפ', 'startup', 'יזמות'],
        'regulation': ['רגולציה', 'regulation', 'פיקוח'],
    }

    found_tags = []
    for tag, keywords in tag_keywords.items():
        for kw in keywords:
            if kw.lower() in content_lower:
                found_tags.append(tag)
                break

    return found_tags[:5] if found_tags else ['fintech']
