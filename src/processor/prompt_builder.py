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
    """Build glossary string for prompts."""
    if not glossary:
        return ""
    return "\n".join(f"- {eng}: {heb}" for eng, heb in glossary.items())


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


def load_style_examples_from_db(limit: int = 5, source_tags: Optional[List[str]] = None) -> List[str]:
    """
    Load style examples from database for few-shot prompting.

    Prioritizes examples matching source_tags if provided,
    then fills remaining slots with diverse word count examples.
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
                matches = sum(1 for t in source_tags if t.lower() in [et.lower() for et in ex_tags])
                scored.append((ex, matches))
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
            truncated = example[:800] + "..." if len(example) > 800 else example
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
    for attempt in range(max_retries + 1):
        try:
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
