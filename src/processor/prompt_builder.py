"""
Shared prompt-building utilities for translation and content generation.

Extracts duplicated logic from TranslationService and ContentGenerator
into reusable functions: glossary/style sections, Hebrew validation,
OpenAI completion params, retry logic, and topic keyword extraction.
"""

import json
import logging
from typing import Optional, Dict, Tuple, List

logger = logging.getLogger(__name__)

# Tech terms to keep in English (not translate)
KEEP_ENGLISH = {
    'API', 'ML', 'AI', 'GPT', 'LLM', 'NFT', 'DeFi', 'ETF', 'IPO', 'VC',
    'CEO', 'CTO', 'CFO', 'COO', 'SaaS', 'B2B', 'B2C', 'ROI', 'KPI',
    'FOMO', 'HODL', 'DCA', 'ATH', 'FUD', 'DAO', 'DEX', 'CEX',
    'startup', 'fintech', 'blockchain', 'crypto', 'bitcoin', 'ethereum',
    'tweet', 'thread', 'retweet', 'like', 'follower'
}

# Topic keyword map for tag matching
KEYWORD_MAP = {
    'fintech': ['fintech', 'financial technology', 'neobank', 'digital bank'],
    'crypto': ['crypto', 'cryptocurrency', 'token', 'coin'],
    'bitcoin': ['bitcoin', 'btc'],
    'ethereum': ['ethereum', 'eth'],
    'blockchain': ['blockchain', 'distributed ledger'],
    'banking': ['bank', 'banking', 'deposit', 'loan', 'mortgage'],
    'payments': ['payment', 'transfer', 'remittance', 'paypal', 'stripe'],
    'investing': ['invest', 'portfolio', 'fund', 'asset', 'wealth'],
    'trading': ['trading', 'trade', 'exchange', 'broker'],
    'markets': ['market', 'stock', 'bond', 'equity', 'dow', 'nasdaq', 's&p'],
    'regulation': ['regulat', 'compliance', 'sec', 'fed', 'central bank'],
    'startups': ['startup', 'founder', 'seed', 'series a', 'venture'],
    'AI': ['artificial intelligence', ' ai ', 'machine learning', 'llm', 'gpt'],
    'technology': ['tech', 'software', 'platform', 'saas', 'cloud'],
    'DeFi': ['defi', 'decentralized finance', 'yield', 'liquidity pool'],
    'IPO': ['ipo', 'public offering', 'listing'],
}


def extract_topic_keywords(text: str) -> List[str]:
    """Extract topic keywords from text for tag matching."""
    text_lower = text.lower()
    found = []
    for tag, keywords in KEYWORD_MAP.items():
        for kw in keywords:
            if kw in text_lower:
                found.append(tag)
                break
    return found


def build_glossary_section(glossary: Dict[str, str]) -> str:
    """Build glossary string for prompts (all terms)."""
    if not glossary:
        return ""
    return "\n".join(f"- {eng}: {heb}" for eng, heb in glossary.items())


# Common finance defaults when no source-text matches found
_COMMON_FINANCE_TERMS = {
    'Bitcoin', 'Ethereum', 'blockchain', 'crypto', 'fintech',
    'IPO', 'ETF', 'stock', 'market', 'investor',
}


def build_relevant_glossary_section(glossary: Dict[str, str],
                                     source_text: str,
                                     max_terms: int = 20) -> str:
    """Build glossary section with only terms relevant to the source text.

    Scores each glossary term by presence in source_text:
      - Exact case-insensitive match of English key: +10
      - Partial word boundary match: +5
    Returns top max_terms terms. Falls back to common finance defaults
    if fewer than 5 matches found.
    """
    if not glossary:
        return ""
    if not source_text:
        return build_glossary_section(glossary)

    source_lower = source_text.lower()

    scored: List[Tuple[str, str, int]] = []
    for eng, heb in glossary.items():
        eng_lower = eng.lower()
        score = 0
        if eng_lower in source_lower:
            score += 10
        elif any(word.startswith(eng_lower) or eng_lower.startswith(word)
                 for word in source_lower.split()
                 if len(word) > 2):
            score += 5
        scored.append((eng, heb, score))

    # Sort by score desc, keep only those with score > 0
    matched = [(e, h, s) for e, h, s in scored if s > 0]
    matched.sort(key=lambda x: -x[2])

    if len(matched) < 5:
        # Fill with common finance defaults
        for eng, heb, _ in scored:
            if eng in _COMMON_FINANCE_TERMS and (eng, heb, 0) not in [(e, h, 0) for e, h, _ in matched]:
                matched.append((eng, heb, 0))
            if len(matched) >= max_terms:
                break

    selected = matched[:max_terms]
    if not selected:
        return build_glossary_section(glossary)

    return "\n".join(f"- {eng}: {heb}" for eng, heb, _ in selected)


def validate_hebrew_output(text: str) -> Tuple[bool, str]:
    """
    Validate that output is primarily Hebrew.

    Returns:
        Tuple of (is_valid, reason)
    """
    if not text:
        return False, "Empty output"

    hebrew_chars = sum(1 for c in text if '\u0590' <= c <= '\u05FF')
    alpha_chars = sum(1 for c in text if c.isalpha())

    if alpha_chars == 0:
        return False, "No alphabetic characters"

    ratio = hebrew_chars / alpha_chars

    if ratio < 0.5:
        return False, f"Hebrew ratio too low: {ratio:.1%}"

    return True, ""


import re as _re


def score_hebrew_quality(text: str) -> Dict:
    """Score Hebrew text quality on a 0-100 scale.

    Components:
      - hebrew_ratio (0-50): How much of the text is Hebrew
      - length (0-25): Optimal tweet length
      - structure (0-25): Proper ending, emoji count, no artifacts

    Returns dict with 'total', 'hebrew_ratio', 'length', 'structure' scores.
    """
    if not text:
        return {'total': 0, 'hebrew_ratio': 0, 'length': 0, 'structure': 0}

    # Hebrew ratio score (0-50)
    hebrew_chars = sum(1 for c in text if '\u0590' <= c <= '\u05FF')
    alpha_chars = sum(1 for c in text if c.isalpha())
    ratio = hebrew_chars / alpha_chars if alpha_chars > 0 else 0

    if ratio >= 0.8:
        ratio_score = 50
    elif ratio >= 0.6:
        ratio_score = 35
    elif ratio >= 0.5:
        ratio_score = 20
    else:
        ratio_score = 0

    # Length score (0-25)
    char_count = len(text)
    if 100 <= char_count <= 280:
        length_score = 25
    elif 50 <= char_count < 100 or 280 < char_count <= 500:
        length_score = 15
    else:
        length_score = 5

    # Structure score (0-25)
    structure_score = 0

    # Proper ending: period, exclamation, question, or emoji at end
    stripped = text.rstrip()
    if stripped and stripped[-1] in '.!?…':
        structure_score += 10
    elif stripped and ord(stripped[-1]) > 0x1F000:  # emoji
        structure_score += 10

    # Reasonable emoji count (0-3 is good)
    emoji_count = sum(1 for c in text if ord(c) > 0x1F000)
    if 0 <= emoji_count <= 3:
        structure_score += 10

    # No markdown artifacts
    if not _re.search(r'[*_#`\[\]]', text):
        structure_score += 5

    total = ratio_score + length_score + structure_score
    return {
        'total': total,
        'hebrew_ratio': ratio_score,
        'length': length_score,
        'structure': structure_score,
    }


def _recency_bonus(created_at) -> int:
    """Calculate recency bonus for style example scoring."""
    from datetime import datetime, timezone
    if not created_at:
        return 0
    now = datetime.now(timezone.utc)
    # Handle naive datetimes
    if created_at.tzinfo is None:
        from datetime import timezone as _tz
        created_at = created_at.replace(tzinfo=_tz.utc)
    age_days = (now - created_at).days
    if age_days <= 7:
        return 3
    if age_days <= 30:
        return 2
    if age_days <= 90:
        return 1
    return 0


def load_style_examples_from_db(limit: int = 5, source_tags: Optional[List[str]] = None) -> List[str]:
    """
    Load style examples from database for few-shot prompting.

    Prioritizes examples matching source_tags if provided,
    with recency bonus, then fills remaining slots with diverse word count examples.
    Uses its own dedicated session to avoid interfering with caller's session.
    """
    from common.models import engine, StyleExample
    from sqlalchemy.orm import Session as _Session

    db = _Session(bind=engine, expire_on_commit=False)
    try:
        all_examples = (
            db.query(StyleExample)
            .filter(StyleExample.is_active == True)
            .order_by(StyleExample.created_at.desc())
            .all()
        )

        if not all_examples:
            return []

        if source_tags:
            scored = []
            for ex in all_examples:
                ex_tags = ex.topic_tags or []
                if isinstance(ex_tags, str):
                    try:
                        ex_tags = json.loads(ex_tags)
                    except (json.JSONDecodeError, ValueError):
                        ex_tags = []
                tag_matches = sum(1 for t in source_tags if t.lower() in [et.lower() for et in ex_tags])
                recency = _recency_bonus(ex.created_at)
                quality = (getattr(ex, 'approval_count', 0) or 0) - (getattr(ex, 'rejection_count', 0) or 0) * 2
                combined = tag_matches * 10 + recency + quality
                scored.append((ex, combined))
            scored.sort(key=lambda x: (-x[1], -x[0].word_count))
            candidates = [ex for ex, _ in scored]
        else:
            candidates = all_examples

        pool = candidates[:limit * 3]
        sorted_by_length = sorted(pool, key=lambda x: x.word_count)
        if len(sorted_by_length) <= limit:
            selected = sorted_by_length
        else:
            selected = [sorted_by_length[i * len(sorted_by_length) // limit] for i in range(limit)]

        result = [ex.content for ex in selected]
        logger.info(f"Loaded {len(result)} style examples from database (tags={source_tags})")
        return result

    except Exception as e:
        logger.warning(f"Could not load style examples from DB: {e}")
        return []
    finally:
        db.close()


def _smart_truncate(text: str, max_chars: int = 800) -> str:
    """Truncate text at the last sentence boundary before max_chars.

    Finds the last sentence ending (. ! ? or newline) before the limit.
    Falls back to last space if no sentence boundary found.
    Only truncates if we keep at least 50% of max_chars.
    """
    if len(text) <= max_chars:
        return text

    # Look for last sentence boundary before limit
    truncated = text[:max_chars]
    for sep in ['. ', '! ', '? ', '.\n', '!\n', '?\n', '\n']:
        pos = truncated.rfind(sep)
        if pos >= max_chars // 2:
            return text[:pos + 1].rstrip()

    # Fall back to last space
    space_pos = truncated.rfind(' ')
    if space_pos >= max_chars // 2:
        return text[:space_pos].rstrip() + "..."

    # Last resort: hard cut
    return truncated.rstrip() + "..."


def build_style_section(source_text: Optional[str] = None,
                        fallback_style: str = "") -> str:
    """
    Build the style section for prompts.

    Loads examples from DB (prioritizing topic-matched ones),
    falls back to fallback_style if no DB examples found.
    """
    source_tags = extract_topic_keywords(source_text) if source_text else None
    db_examples = load_style_examples_from_db(limit=5, source_tags=source_tags)

    if db_examples:
        examples_text = ""
        for i, example in enumerate(db_examples, 1):
            truncated = _smart_truncate(example, max_chars=800)
            examples_text += f"\n--- Example {i} ---\n{truncated}\n"

        return f"""STYLE EXAMPLES (match this writing style):
{examples_text}

KEY STYLE REQUIREMENTS:
- Match the tone, vocabulary, and sentence structure from the examples above
- Use similar expressions and phrasing patterns
- Maintain the same level of formality"""
    elif fallback_style:
        return f"STYLE GUIDE:\n{fallback_style}"
    else:
        return "Write in a professional, engaging Hebrew style suitable for financial/tech content on social media."


def get_completion_params(model: str, system_prompt: str, user_content: str,
                          temperature: Optional[float] = None) -> dict:
    """
    Build OpenAI API completion parameters.

    Only includes temperature if explicitly provided (some models don't support it).
    """
    params = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content}
        ]
    }

    if temperature is not None:
        params["temperature"] = temperature
        params["top_p"] = 0.9

    return params


def call_with_retry(client, params: dict, max_retries: int = 2,
                    validator_fn=None) -> str:
    """
    Call OpenAI with retry on validation failure.

    Args:
        client: OpenAI client instance
        params: Completion parameters (from get_completion_params)
        max_retries: Number of retry attempts if validation fails
        validator_fn: Optional callable(text) -> (is_valid, reason).
                     If None, no validation is performed.

    Returns:
        Response text from the API

    Raises:
        Exception: If API call fails after all retries
    """
    from common.rate_limiter import get_rate_limiter
    rate_limiter = get_rate_limiter()

    for attempt in range(max_retries + 1):
        try:
            rate_limiter.acquire()
            response = client.chat.completions.create(**params)
            text = response.choices[0].message.content.strip()

            if validator_fn is None:
                return text

            is_valid, reason = validator_fn(text)
            if is_valid:
                return text

            logger.warning(f"Validation failed (attempt {attempt + 1}): {reason}")
            if attempt < max_retries:
                # Append feedback to system prompt for retry
                params = _deep_copy_params(params)
                params['messages'][0]['content'] += (
                    f"\n\nPREVIOUS ATTEMPT FAILED: {reason}. "
                    "Please ensure output is primarily in Hebrew."
                )
            else:
                logger.warning(f"Returning unvalidated result after {max_retries + 1} attempts")
                return text

        except Exception as e:
            logger.error(f"API call failed (attempt {attempt + 1}): {e}")
            if attempt == max_retries:
                raise Exception(
                    f"OpenAI API error after {max_retries + 1} attempts: {str(e)}"
                )

    return ""  # Should not reach here


def _deep_copy_params(params: dict) -> dict:
    """Deep copy params dict to avoid mutating the original on retry."""
    new_params = dict(params)
    new_params['messages'] = [dict(m) for m in params['messages']]
    return new_params
