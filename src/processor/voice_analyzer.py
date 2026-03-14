"""
Voice Analyzer for HFI Application

Analyzes scraped Hebrew tweets to extract a voice fingerprint and generate
a voice profile (config/voice_profile.json). The profile captures writing
patterns, tone, signature phrases, and anti-patterns for consistent
content generation.
"""

import json
import logging
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

from common.openai_client import get_openai_client

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).parent.parent.parent
DEFAULT_VOICE_PROFILE_PATH = PROJECT_ROOT / "config" / "voice_profile.json"

VOICE_ANALYSIS_PROMPT = """You are a writing-style analyst specializing in Hebrew social media content.

Analyze the following corpus of Hebrew tweets written by the SAME author.
Extract a detailed voice fingerprint capturing their unique writing patterns.

TWEETS:
{tweets_block}

---

Analyze the corpus above and return a JSON object with EXACTLY these fields:

{{
  "personality": ["adj1", "adj2", ...],
  // 3-5 adjectives describing the writer's persona (e.g. "authoritative", "witty", "provocative")

  "tone_formality": <int 1-10>,
  // 1 = very casual/slang, 10 = very formal/academic

  "sentence_patterns": ["pattern1", "pattern2", ...],
  // Describe recurring sentence structures (e.g. "Opens with a bold claim, then provides evidence")

  "signature_phrases": ["phrase1", "phrase2", ...],
  // Recurring Hebrew words, expressions, or idioms the writer uses often

  "opening_hooks": ["hook1", "hook2", ...],
  // How tweets typically begin (e.g. "Rhetorical question", "Bold statement", "News reference")

  "closing_patterns": ["pattern1", "pattern2", ...],
  // How tweets typically end (e.g. "Call to action", "Punchline", "Thought-provoking question")

  "language_mixing": {{
    "hebrew_primary": true/false,
    "english_terms_policy": "description of when/how English terms are used",
    "code_switching_examples": ["example1", "example2", ...]
  }},

  "never_list": ["anti-pattern1", "anti-pattern2", ...],
  // What does this writer NEVER do? Anti-patterns to avoid.
  // e.g. "Never uses formal academic language", "Never starts with greetings"

  "tweet_type_distribution": {{
    "pattern_observation": <float 0-1>,
    "contrarian": <float 0-1>,
    "insider_insight": <float 0-1>,
    "cultural_commentary": <float 0-1>
  }},
  // Inferred distribution of tweet types. Weights should sum to ~1.0

  "humanizer": {{
    "enabled": true,
    "aggressiveness": "medium"
  }}
}}

IMPORTANT:
- Return ONLY valid JSON, no markdown code fences, no explanation text
- All string values may contain Hebrew characters
- The "signature_phrases" should be actual Hebrew phrases found in the tweets
- The "never_list" should describe things the writer clearly avoids
- For "tweet_type_distribution", infer from the examples what proportion of tweets fall into each category
"""

# Module-level cache for voice profile
_voice_profile_cache: Dict = {}
_voice_profile_cache_time: float = 0.0
_CACHE_TTL_SECONDS: float = 300.0


def analyze_voice(examples: List[str], model: str = None) -> Dict:
    """
    Analyze Hebrew tweet examples to extract a voice fingerprint.

    Args:
        examples: List of Hebrew tweet texts (the user's own writing)
        model: OpenAI model to use (defaults to OPENAI_MODEL env or gpt-4o)

    Returns:
        Dict with voice profile fields (personality, tone, patterns, etc.)
        Returns empty dict if examples list is empty or API call fails.
    """
    if not examples:
        logger.warning("No examples provided for voice analysis")
        return {}

    model = model or os.getenv('OPENAI_MODEL', 'gpt-4o')
    client = get_openai_client()

    tweets_block = "\n".join(
        f"{i}. {text.strip()}" for i, text in enumerate(examples, 1) if text.strip()
    )

    if not tweets_block.strip():
        logger.warning("All provided examples were empty")
        return {}

    prompt = VOICE_ANALYSIS_PROMPT.format(tweets_block=tweets_block)

    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {
                    "role": "system",
                    "content": "You are a writing-style analyst. Return ONLY valid JSON."
                },
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,
        )

        raw = response.choices[0].message.content.strip()

        if raw.startswith("```"):
            lines = raw.split("\n")
            lines = [l for l in lines if not l.strip().startswith("```")]
            raw = "\n".join(lines)

        profile = json.loads(raw)
        logger.info(
            f"Voice analysis complete: {len(profile.get('personality', []))} personality traits, "
            f"{len(profile.get('signature_phrases', []))} signature phrases"
        )
        return profile

    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse voice analysis JSON: {e}")
        return {}
    except Exception as e:
        logger.error(f"Voice analysis failed: {e}")
        return {}


def save_voice_profile(profile: Dict, path: Path = None) -> None:
    """
    Save a voice profile to JSON file.

    Adds metadata fields (_version, _generated_at, _source_count).
    Pretty-prints with ensure_ascii=False for Hebrew characters.

    Args:
        profile: Voice profile dict from analyze_voice()
        path: Output path (defaults to config/voice_profile.json)
    """
    path = Path(path) if path else DEFAULT_VOICE_PROFILE_PATH
    path.parent.mkdir(parents=True, exist_ok=True)

    profile_with_meta = dict(profile)
    profile_with_meta["_version"] = "1.0"
    profile_with_meta["_generated_at"] = datetime.now(timezone.utc).isoformat()

    source_count = profile_with_meta.get("_source_count")
    if source_count is None:
        profile_with_meta["_source_count"] = 0

    with open(path, 'w', encoding='utf-8') as f:
        json.dump(profile_with_meta, f, ensure_ascii=False, indent=2)

    logger.info(f"Voice profile saved to {path}")

    _clear_cache()


def load_voice_profile(path: Path = None) -> Dict:
    """
    Load a voice profile from JSON file.

    Uses a module-level cache with TTL to avoid repeated disk reads.
    Returns empty dict if file is missing or invalid JSON.

    Args:
        path: Path to voice profile JSON (defaults to config/voice_profile.json)

    Returns:
        Voice profile dict, or empty dict on any error.
    """
    global _voice_profile_cache, _voice_profile_cache_time

    path = Path(path) if path else DEFAULT_VOICE_PROFILE_PATH
    cache_key = str(path)

    now = time.time()
    if (
        cache_key in _voice_profile_cache
        and (now - _voice_profile_cache_time) < _CACHE_TTL_SECONDS
    ):
        return _voice_profile_cache[cache_key]

    try:
        if not path.exists():
            logger.debug(f"Voice profile not found at {path}")
            return {}

        with open(path, 'r', encoding='utf-8') as f:
            profile = json.load(f)

        if not isinstance(profile, dict):
            logger.warning(f"Voice profile is not a dict: {type(profile)}")
            return {}

        _voice_profile_cache[cache_key] = profile
        _voice_profile_cache_time = now
        logger.debug(f"Loaded voice profile from {path}")
        return profile

    except json.JSONDecodeError as e:
        logger.warning(f"Invalid JSON in voice profile {path}: {e}")
        return {}
    except Exception as e:
        logger.warning(f"Failed to load voice profile from {path}: {e}")
        return {}


def _clear_cache() -> None:
    """Clear the voice profile cache (used after saving and in tests)."""
    global _voice_profile_cache, _voice_profile_cache_time
    _voice_profile_cache.clear()
    _voice_profile_cache_time = 0.0


def _build_ai_patterns_avoid_section() -> str:
    """Build a prompt section listing AI writing patterns to avoid.

    Extracts human-readable forbidden words/phrases from the humanizer's
    pattern definitions and formats them as prompt rules. This gets injected
    into EVERY prompt (translation + generation) so GPT avoids AI tells
    from the start, rather than needing post-processing to fix them.
    """
    try:
        from processor.humanizer import (
            CONTENT_PATTERNS, LANGUAGE_PATTERNS, COMMUNICATION_PATTERNS,
        )
    except ImportError:
        return ""

    import re

    def _clean_regex(pattern: str) -> str:
        """Strip regex syntax to get human-readable phrase."""
        cleaned = pattern
        cleaned = re.sub(r'\\b', '', cleaned)
        cleaned = re.sub(r'\\s\+', ' ', cleaned)
        cleaned = re.sub(r'\\s\*', '', cleaned)
        cleaned = re.sub(r'\[\s*\\s-\s*\]', ' ', cleaned)
        cleaned = re.sub(r"\\'\?", "'", cleaned)
        cleaned = re.sub(r"'\?", "'", cleaned)
        cleaned = cleaned.strip()
        return cleaned

    hebrew_words = []
    english_words = []

    all_patterns = {}
    all_patterns.update(CONTENT_PATTERNS)
    all_patterns.update(LANGUAGE_PATTERNS)
    all_patterns.update(COMMUNICATION_PATTERNS)

    for name, cfg in all_patterns.items():
        for marker in cfg.get("hebrew", []):
            cleaned = _clean_regex(marker)
            if cleaned and len(cleaned) > 1:
                hebrew_words.append(cleaned)
        for marker in cfg.get("english", []):
            cleaned = _clean_regex(marker)
            if cleaned and len(cleaned) > 1:
                english_words.append(cleaned)

    if not hebrew_words and not english_words:
        return ""

    lines = ["AI WRITING PATTERNS TO AVOID (these phrases sound AI-generated):"]
    if hebrew_words:
        lines.append(f"  Hebrew — DO NOT use: {', '.join(hebrew_words)}")
    if english_words:
        lines.append(f"  English — DO NOT use: {', '.join(english_words)}")
    lines.append("  Also avoid: em-dash overuse (max 1 per post), markdown bold (**text**), decorative emojis, rule-of-three filler lists")

    return "\n".join(lines)


def build_voice_prompt_section(profile: Dict = None) -> str:
    """
    Build a prompt section string from a voice profile.

    Combines all voice DNA fields into a formatted string ready
    for injection into system prompts.

    Args:
        profile: Voice profile dict. If None, loads via load_voice_profile().

    Returns:
        Formatted prompt section string, or empty string if profile is empty.
    """
    if profile is None:
        profile = load_voice_profile()

    if not profile:
        return ""

    sections = []

    # VOICE IDENTITY
    personality = profile.get("personality", [])
    tone = profile.get("tone_formality")
    if personality or tone:
        identity_parts = []
        if personality:
            identity_parts.append(f"Personality: {', '.join(personality)}")
        if tone is not None:
            identity_parts.append(f"Tone formality: {tone}/10")
        sections.append("VOICE IDENTITY:\n" + "\n".join(identity_parts))

    # WRITING PATTERNS
    patterns_parts = []
    sentence_patterns = profile.get("sentence_patterns", [])
    if sentence_patterns:
        patterns_parts.append("Sentence patterns:")
        for p in sentence_patterns:
            patterns_parts.append(f"  - {p}")

    signature_phrases = profile.get("signature_phrases", [])
    if signature_phrases:
        patterns_parts.append("Signature phrases:")
        for p in signature_phrases:
            patterns_parts.append(f"  - {p}")

    opening_hooks = profile.get("opening_hooks", [])
    if opening_hooks:
        patterns_parts.append("Opening hooks:")
        for h in opening_hooks:
            patterns_parts.append(f"  - {h}")

    closing_patterns = profile.get("closing_patterns", [])
    if closing_patterns:
        patterns_parts.append("Closing patterns:")
        for c in closing_patterns:
            patterns_parts.append(f"  - {c}")

    if patterns_parts:
        sections.append("WRITING PATTERNS:\n" + "\n".join(patterns_parts))

    # LANGUAGE MIXING
    lang_mixing = profile.get("language_mixing", {})
    if lang_mixing:
        mixing_parts = []
        if "hebrew_primary" in lang_mixing:
            mixing_parts.append(
                f"Primary language: {'Hebrew' if lang_mixing['hebrew_primary'] else 'Mixed'}"
            )
        if lang_mixing.get("english_terms_policy"):
            mixing_parts.append(f"English terms: {lang_mixing['english_terms_policy']}")
        code_examples = lang_mixing.get("code_switching_examples", [])
        if code_examples:
            mixing_parts.append("Code-switching examples:")
            for ex in code_examples:
                mixing_parts.append(f"  - {ex}")
        if mixing_parts:
            sections.append("LANGUAGE MIXING:\n" + "\n".join(mixing_parts))

    # NEVER
    never_list = profile.get("never_list", [])
    if never_list:
        never_items = []
        for i, item in enumerate(never_list, 1):
            never_items.append(f"  {i}. {item}")
        sections.append("NEVER:\n" + "\n".join(never_items))

    # AI WRITING PATTERNS TO AVOID (from humanizer pattern definitions)
    ai_avoid_section = _build_ai_patterns_avoid_section()
    if ai_avoid_section:
        sections.append(ai_avoid_section)

    if not sections:
        return ""

    return "\n\n".join(sections)


def main():
    """CLI entry point: analyze style examples from DB and save voice profile."""
    # Load .env file if present
    try:
        from dotenv import load_dotenv
        env_path = PROJECT_ROOT / ".env"
        if env_path.exists():
            load_dotenv(env_path)
    except ImportError:
        pass

    from common.models import SessionLocal, StyleExample

    print("=" * 60)
    print("HFI Voice Analyzer — Extracting voice fingerprint")
    print("=" * 60)

    db = SessionLocal()
    try:
        examples = (
            db.query(StyleExample)
            .filter(StyleExample.is_active == True)
            .order_by(StyleExample.created_at.desc())
            .all()
        )

        if not examples:
            print("\n⚠️  No active style examples found in database.")
            print("Add style examples via the dashboard first.")
            return

        texts = [ex.content for ex in examples if ex.content and ex.content.strip()]
        print(f"\nFound {len(texts)} active style examples.")

        if not texts:
            print("⚠️  All style examples are empty. Aborting.")
            return

        print("Analyzing voice patterns with GPT...")
        profile = analyze_voice(texts)

        if not profile:
            print("❌ Voice analysis returned empty result.")
            return

        profile["_source_count"] = len(texts)
        save_voice_profile(profile)

        print(f"\n✅ Voice profile saved to {DEFAULT_VOICE_PROFILE_PATH}")
        print("\nSummary:")
        print(f"  Personality: {', '.join(profile.get('personality', []))}")
        print(f"  Tone formality: {profile.get('tone_formality', 'N/A')}/10")
        print(f"  Signature phrases: {len(profile.get('signature_phrases', []))}")
        print(f"  Opening hooks: {len(profile.get('opening_hooks', []))}")
        print(f"  Never-do items: {len(profile.get('never_list', []))}")
        print(f"  Source examples: {len(texts)}")

    finally:
        db.close()

    print("\n" + "=" * 60)


if __name__ == "__main__":
    main()
