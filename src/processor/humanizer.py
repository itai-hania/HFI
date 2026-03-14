"""
Two-pass AI pattern detection and removal system for Hebrew FinTech content.

Adapted from NaBot's 24-pattern humanizer. Scans Hebrew/English text for
AI-writing tells, then uses a two-pass GPT pipeline (self-critique → revision)
to produce more natural-sounding output.

Pass 1 — Self-critique: GPT identifies specific AI patterns in the text.
Pass 2 — Revision: GPT rewrites the text removing identified patterns,
          guided by the user's voice profile.
"""

import json
import logging
import os
import re
from pathlib import Path
from typing import Dict, List, Optional

from common.openai_client import get_openai_client
from processor.prompt_builder import get_completion_params

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).parent.parent.parent
DEFAULT_VOICE_PROFILE_PATH = PROJECT_ROOT / "config" / "voice_profile.json"

# ==================== Pattern Definitions ====================

CONTENT_PATTERNS = {
    "significance_inflation": {
        "description": "Inflated importance claims that AI models default to",
        "hebrew": [
            r"מהפכני", r"חסר\s+תקדים", r"שינוי\s+פרדיגמה",
            r"ציון\s+דרך", r"נקודת\s+מפנה",
        ],
        "english": [
            r"\brevolutionary\b", r"\bunprecedented\b",
            r"\bparadigm\s+shift\b", r"\bgame[\s-]changing\b",
            r"\bpivotal\s+moment\b",
        ],
    },
    "promotional_language": {
        "description": "Over-enthusiastic announcements typical of AI output",
        "hebrew": [
            r"אנו\s+שמחים\s+להודיע", r"פריצת\s+דרך",
            r"מרהיב", r"מרשים\s+ביותר",
        ],
        "english": [
            r"\bexcited\s+to\s+announce\b", r"\bthrilled\s+to\s+share\b",
            r"\bgroundbreaking\b", r"\bbreathtaking\b",
        ],
    },
    "vague_attributions": {
        "description": "Sourceless authority claims used to pad AI text",
        "hebrew": [
            r"מומחים\s+אומרים", r"רבים\s+מאמינים",
            r"מחקרים\s+מראים", r"על\s+פי\s+דיווחים",
        ],
        "english": [
            r"\bexperts\s+say\b", r"\bmany\s+believe\b",
            r"\bstudies\s+show\b", r"\baccording\s+to\s+reports\b",
        ],
    },
    "generic_conclusions": {
        "description": "Hollow wrap-up phrases that add no substance",
        "hebrew": [
            r"בסופו\s+של\s+דבר", r"לסיכום\s+חשוב\s+ש",
            r"העתיד\s+יראה", r"הזמן\s+יגיד",
        ],
        "english": [
            r"\bat\s+the\s+end\s+of\s+the\s+day\b",
            r"\bonly\s+time\s+will\s+tell\b",
            r"\bthe\s+future\s+remains\s+to\s+be\s+seen\b",
        ],
    },
}

LANGUAGE_PATTERNS = {
    "ai_vocabulary": {
        "description": "Words disproportionately favored by language models",
        "hebrew": [
            r"לצלול\s+לעומק", r"ציר\s+מרכזי", r"שטיח\s+של",
            r"לנווט", r"מרכיב\s+מפתח", r"להעצים",
        ],
        "english": [
            r"\bdelve\b", r"\bpivotal\b", r"\btapestry\b",
            r"\bnavigate\b", r"\blandscape\b", r"\bcrucial\b",
            r"\btransformative\b", r"\bfoster\b", r"\bharness\b",
            r"\bleverage\b", r"\bspearhead\b", r"\belevate\b",
            r"\bunpack\b", r"\breimagine\b", r"\bgarner\b",
            r"\bunderscore\b",
        ],
    },
    "copula_avoidance": {
        "description": "Overly ornate substitutes for simple 'is/are'",
        "hebrew": [],
        "english": [
            r"\bserves\s+as\b", r"\bstands\s+as\b",
            r"\brepresents\b",
        ],
    },
    "rule_of_three": {
        "description": "Gratuitous triple-adjective/noun lists",
        "hebrew": [],
        "english": [],
        "regex": r"(\w+),\s+(\w+),?\s+(?:and|ו)\s+(\w+)",
    },
    "em_dash_overuse": {
        "description": "Excessive em-dash usage (more than 1 per post)",
        "hebrew": [],
        "english": [],
        "counter": r"—|(?<= ) - (?= )",
        "threshold": 2,
    },
    "boldface_artifacts": {
        "description": "Markdown bold formatting leaked into social text",
        "hebrew": [],
        "english": [],
        "regex": r"\*\*[^*]+\*\*",
    },
    "decorative_emoji": {
        "description": "Emoji overuse or structural emoji at line/bullet starts",
        "hebrew": [],
        "english": [],
    },
}

COMMUNICATION_PATTERNS = {
    "chatbot_artifacts": {
        "description": "Phrases revealing chatbot interaction patterns",
        "hebrew": [
            r"שאלה\s+מצוינת", r"בהחלט", r"ללא\s+ספק",
        ],
        "english": [
            r"\bGreat\s+question\s*!", r"\bAbsolutely\s*!",
            r"\bI'?d\s+be\s+happy\s+to\b", r"\bLet\s+me\s+explain\b",
        ],
    },
    "sycophantic_tone": {
        "description": "Excessive agreement / flattery patterns",
        "hebrew": [
            r"בוודאי", r"אכן", r"אין\s+ספק\s+ש",
        ],
        "english": [
            r"\bYou'?re\s+absolutely\s+right\b",
            r"\bThat'?s\s+a\s+great\s+point\b",
        ],
    },
    "filler_phrases": {
        "description": "Padding phrases that add no information",
        "hebrew": [
            r"חשוב\s+לציין\s+ש", r"ראוי\s+להזכיר\s+ש",
            r"כדאי\s+לשים\s+לב\s+ש",
        ],
        "english": [
            r"\bIt\s+is\s+important\s+to\s+note\s+that\b",
            r"\bIt\s+is\s+worth\s+mentioning\b",
        ],
    },
    "excessive_hedging": {
        "description": "Stacked hedge words that weaken every claim",
        "hebrew": [
            r"ייתכן\s+שאולי", r"אפשר\s+לטעון\s+ש",
        ],
        "english": [
            r"\bIt\s+could\s+potentially\s+possibly\b",
        ],
    },
}

# Pre-compile emoji pattern (surrogate-safe, covers common emoji ranges)
_EMOJI_RE = re.compile(
    "["
    "\U0001F600-\U0001F64F"  # emoticons
    "\U0001F300-\U0001F5FF"  # misc symbols
    "\U0001F680-\U0001F6FF"  # transport
    "\U0001F1E0-\U0001F1FF"  # flags
    "\U00002702-\U000027B0"  # dingbats
    "\U0001F900-\U0001F9FF"  # supplemental
    "\U0001FA00-\U0001FA6F"  # chess
    "\U0001FA70-\U0001FAFF"  # extended-A
    "\U00002600-\U000026FF"  # misc
    "]+",
    re.UNICODE,
)

_LINE_START_EMOJI_RE = re.compile(
    r"(?:^|[\n•\-\*])\s*["
    "\U0001F600-\U0001F64F"
    "\U0001F300-\U0001F5FF"
    "\U0001F680-\U0001F6FF"
    "\U0001F1E0-\U0001F1FF"
    "\U00002702-\U000027B0"
    "\U0001F900-\U0001F9FF"
    "\U0001FA00-\U0001FA6F"
    "\U0001FA70-\U0001FAFF"
    "\U00002600-\U000026FF"
    "]",
    re.UNICODE | re.MULTILINE,
)


# ==================== Pattern Detection ====================

def _find_matches(text: str, patterns: List[str]) -> List[str]:
    """Find all regex matches in text, case-insensitive with Unicode support."""
    matches = []
    for pattern in patterns:
        found = re.findall(pattern, text, re.IGNORECASE | re.UNICODE)
        matches.extend(found)
    return matches


def _count_emojis(text: str) -> int:
    """Count total emoji characters in text."""
    return sum(len(m) for m in _EMOJI_RE.findall(text))


def detect_ai_patterns(text: str) -> List[Dict]:
    """
    Scan Hebrew/English text for AI-writing tells.

    Each detected pattern is returned with its category, name, description,
    and the specific matches found.

    Args:
        text: Input text (Hebrew, English, or mixed)

    Returns:
        List of dicts: {category, pattern_name, description, matches}
    """
    if not text or not text.strip():
        return []

    detected = []

    # Content patterns
    for name, cfg in CONTENT_PATTERNS.items():
        all_markers = cfg.get("hebrew", []) + cfg.get("english", [])
        matches = _find_matches(text, all_markers)
        if matches:
            detected.append({
                "category": "content",
                "pattern_name": name,
                "description": cfg["description"],
                "matches": matches,
            })

    # Language patterns
    for name, cfg in LANGUAGE_PATTERNS.items():
        # Standard marker-based detection
        all_markers = cfg.get("hebrew", []) + cfg.get("english", [])
        matches = _find_matches(text, all_markers)

        # Standalone regex pattern (rule_of_three, boldface_artifacts)
        regex = cfg.get("regex")
        if regex:
            found = re.findall(regex, text, re.IGNORECASE | re.UNICODE)
            if found:
                # findall with groups returns tuples; flatten
                for item in found:
                    if isinstance(item, tuple):
                        matches.append(", ".join(item))
                    else:
                        matches.append(item)

        # Counter-based detection (em_dash_overuse)
        counter_re = cfg.get("counter")
        if counter_re:
            count = len(re.findall(counter_re, text))
            threshold = cfg.get("threshold", 2)
            if count >= threshold:
                matches.append(f"count={count}")

        # Decorative emoji detection
        if name == "decorative_emoji":
            emoji_count = _count_emojis(text)
            line_start_emojis = _LINE_START_EMOJI_RE.findall(text)
            if emoji_count > 3:
                matches.append(f"emoji_count={emoji_count}")
            if line_start_emojis:
                matches.extend(line_start_emojis)

        if matches:
            detected.append({
                "category": "language",
                "pattern_name": name,
                "description": cfg["description"],
                "matches": matches,
            })

    # Communication patterns
    for name, cfg in COMMUNICATION_PATTERNS.items():
        all_markers = cfg.get("hebrew", []) + cfg.get("english", [])
        matches = _find_matches(text, all_markers)
        if matches:
            detected.append({
                "category": "communication",
                "pattern_name": name,
                "description": cfg["description"],
                "matches": matches,
            })

    return detected


# ==================== Configuration ====================

def is_humanizer_enabled() -> bool:
    """
    Check whether the humanizer is enabled.

    Priority:
    1. Env var HFI_HUMANIZER_ENABLED (if set)
    2. voice_profile.json → humanizer.enabled (if present)
    3. Default: False
    """
    env_val = os.environ.get("HFI_HUMANIZER_ENABLED")
    if env_val is not None:
        return env_val.lower() in ("true", "1", "yes")

    try:
        from processor.voice_analyzer import load_voice_profile
        profile = load_voice_profile()
        humanizer_cfg = profile.get("humanizer", {})
        if isinstance(humanizer_cfg, dict) and "enabled" in humanizer_cfg:
            return bool(humanizer_cfg["enabled"])
    except Exception:
        pass

    return False


# ==================== Two-Pass Humanization ====================

_CRITIQUE_SYSTEM_PROMPT = (
    "You are an expert at detecting AI-generated text. "
    "Analyze this Hebrew text and list 3-5 specific things that make it "
    "sound AI-generated. Quote exact phrases. Be specific."
)

_REVISION_SYSTEM_PROMPT = (
    "You are a Hebrew content editor. Rewrite this text removing the AI "
    "patterns identified below. Inject natural personality matching the "
    "voice profile. Keep all factual content identical. "
    "Output ONLY the revised Hebrew text."
)


def humanize_text(
    text: str,
    enabled: Optional[bool] = None,
    model: Optional[str] = None,
    voice_profile: Optional[Dict] = None,
) -> Dict:
    """
    Two-pass humanization: self-critique then revision.

    If disabled (via param, config, or env) or no AI patterns are detected,
    skips GPT calls and returns the original text unchanged.

    Args:
        text: Input Hebrew text to humanize
        enabled: Override for humanizer enabled flag (None = use config)
        model: OpenAI model name (defaults to OPENAI_MODEL env or gpt-4o)
        voice_profile: Voice profile dict (None = load from disk)

    Returns:
        Dict with keys: original, humanized, was_humanized,
        patterns_detected, critique, changes_made
    """
    result = {
        "original": text,
        "humanized": text,
        "was_humanized": False,
        "patterns_detected": [],
        "critique": "",
        "changes_made": [],
    }

    if not text or not text.strip():
        return result

    # Determine enabled state
    is_enabled = enabled if enabled is not None else is_humanizer_enabled()
    if not is_enabled:
        return result

    # Detect patterns
    patterns = detect_ai_patterns(text)
    result["patterns_detected"] = patterns

    if not patterns:
        return result

    # Load model
    model = model or os.getenv("OPENAI_MODEL", "gpt-4o")

    # Load voice profile
    if voice_profile is None:
        try:
            from processor.voice_analyzer import load_voice_profile
            voice_profile = load_voice_profile()
        except Exception:
            voice_profile = {}

    try:
        client = get_openai_client()

        # Pass 1 — Self-critique
        critique_params = get_completion_params(
            model=model,
            system_prompt=_CRITIQUE_SYSTEM_PROMPT,
            user_content=text,
            temperature=0.3,
        )
        critique_response = client.chat.completions.create(**critique_params)
        critique = critique_response.choices[0].message.content.strip()
        result["critique"] = critique

        # Build voice section for pass 2
        voice_section = ""
        try:
            from processor.voice_analyzer import build_voice_prompt_section
            voice_section = build_voice_prompt_section(voice_profile)
        except Exception:
            pass

        # Pass 2 — Revision
        revision_user_content = (
            f"ORIGINAL TEXT:\n{text}\n\n"
            f"AI PATTERNS FOUND:\n{critique}"
        )
        if voice_section:
            revision_user_content += f"\n\nVOICE PROFILE:\n{voice_section}"

        revision_params = get_completion_params(
            model=model,
            system_prompt=_REVISION_SYSTEM_PROMPT,
            user_content=revision_user_content,
            temperature=0.7,
        )
        revision_response = client.chat.completions.create(**revision_params)
        humanized = revision_response.choices[0].message.content.strip()

        result["humanized"] = humanized
        result["was_humanized"] = True
        result["changes_made"] = [
            p["pattern_name"] for p in patterns
        ]

        logger.info(
            f"Humanized text: {len(patterns)} patterns detected, "
            f"{len(result['changes_made'])} addressed"
        )

    except Exception as e:
        logger.error(f"Humanization failed, returning original: {e}")
        result["humanized"] = text
        result["was_humanized"] = False

    return result
