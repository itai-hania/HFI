"""
GPT-based quality evaluation for generated Hebrew content.

Scores content on four dimensions (authenticity, voice_match,
engagement_potential, technical_accuracy) and provides improvement
suggestions. Designed as a non-blocking gate: API errors default
to pass so the pipeline is not held up by transient failures.
"""

import json
import logging
import os
from typing import Dict, List, Optional

from common.openai_client import get_openai_client
from common.rate_limiter import get_rate_limiter
from processor.prompt_builder import get_completion_params

logger = logging.getLogger(__name__)

_EVALUATION_PROMPT = """You are a Hebrew social-media content quality evaluator.

Score the following generated content on these dimensions. Return ONLY valid JSON.

SCORING RUBRIC:
- authenticity (0-30): Does it sound like a real person wrote it? Penalize generic phrasing, filler words, and robotic patterns.
- voice_match (0-25): Does it match the voice profile patterns below? Look for consistent tone, vocabulary, and sentence structure.
- engagement_potential (0-25): Would you stop scrolling for this? Reward hooks, specificity, and emotional resonance.
- technical_accuracy (0-20): Are claims specific and verifiable? Penalize vague statements and unsupported superlatives.

{voice_section}

{source_section}

CONTENT TO EVALUATE:
{text}

Return ONLY this JSON structure (no markdown, no explanation):
{{
    "authenticity": <0-30>,
    "voice_match": <0-25>,
    "engagement_potential": <0-25>,
    "technical_accuracy": <0-20>,
    "suggestions": ["suggestion 1", "suggestion 2"],
    "verdict": "one-sentence summary"
}}"""


def _build_evaluation_prompt(text: str, source_text: str = None,
                              voice_profile: dict = None) -> str:
    """Build the full evaluation prompt with optional context sections."""
    voice_section = ""
    if voice_profile:
        try:
            from processor.voice_analyzer import build_voice_prompt_section
            voice_section = f"VOICE PROFILE:\n{build_voice_prompt_section(voice_profile)}"
        except Exception:
            voice_section = ""
    if not voice_section:
        voice_section = "VOICE PROFILE: Not available. Judge based on general authenticity."

    source_section = ""
    if source_text:
        truncated = source_text[:500] + ("..." if len(source_text) > 500 else "")
        source_section = f"ORIGINAL SOURCE (for accuracy check):\n{truncated}"
    else:
        source_section = "ORIGINAL SOURCE: Not provided. Skip technical_accuracy deep check."

    return _EVALUATION_PROMPT.format(
        text=text,
        voice_section=voice_section,
        source_section=source_section,
    )


def _parse_scores(raw: str) -> Optional[Dict]:
    """Parse GPT response into scores dict, handling markdown fences."""
    cleaned = raw.strip()
    if cleaned.startswith('```'):
        lines = cleaned.split('\n')
        lines = [l for l in lines if not l.strip().startswith('```')]
        cleaned = '\n'.join(lines)
    try:
        return json.loads(cleaned)
    except (json.JSONDecodeError, ValueError):
        return None


def evaluate_quality(
    text: str,
    source_text: str = None,
    voice_profile: dict = None,
    pass_threshold: int = 60,
    model: str = None,
) -> Dict:
    """Evaluate generated content quality via GPT.

    Sends the text to GPT with a structured evaluation prompt.
    Returns dict with 'passed', 'total_score', 'scores', 'suggestions', 'verdict'.
    On error, returns passed=True (don't block on gate failure).
    """
    if model is None:
        model = os.getenv('OPENAI_MODEL', 'gpt-4o')

    prompt = _build_evaluation_prompt(text, source_text, voice_profile)

    try:
        client = get_openai_client()
        params = get_completion_params(
            model=model,
            system_prompt="You are a content quality evaluator. Return only valid JSON.",
            user_content=prompt,
            temperature=0.2,
        )

        rate_limiter = get_rate_limiter()
        rate_limiter.acquire()

        response = client.chat.completions.create(**params)
        raw = response.choices[0].message.content.strip()

        scores = _parse_scores(raw)
        if scores is None:
            logger.warning(f"Could not parse quality evaluation response: {raw[:200]}")
            return {
                'passed': True,
                'total_score': 0,
                'scores': {},
                'suggestions': [],
                'verdict': 'Evaluation parse error — auto-passing',
            }

        total = sum(
            scores.get(dim, 0)
            for dim in ('authenticity', 'voice_match', 'engagement_potential', 'technical_accuracy')
        )

        return {
            'passed': total >= pass_threshold,
            'total_score': total,
            'scores': {
                'authenticity': scores.get('authenticity', 0),
                'voice_match': scores.get('voice_match', 0),
                'engagement_potential': scores.get('engagement_potential', 0),
                'technical_accuracy': scores.get('technical_accuracy', 0),
            },
            'suggestions': scores.get('suggestions', []),
            'verdict': scores.get('verdict', ''),
        }

    except Exception as e:
        logger.error(f"Quality evaluation failed: {e}")
        return {
            'passed': True,
            'total_score': 0,
            'scores': {},
            'suggestions': [],
            'verdict': f'Evaluation error — auto-passing: {str(e)}',
        }


def gate_content(
    variants: List[Dict],
    source_text: str = None,
    pass_threshold: int = 60,
) -> List[Dict]:
    """Run quality gate on a list of generated variants.

    Adds 'quality_evaluation' key to each variant dict.
    Does NOT remove failing variants — just marks them.
    """
    if not variants:
        return variants

    voice_profile = None
    try:
        from processor.voice_analyzer import load_voice_profile
        voice_profile = load_voice_profile()
    except Exception:
        pass

    for variant in variants:
        content = variant.get('hebrew_draft') or variant.get('content') or variant.get('text', '')
        evaluation = evaluate_quality(
            text=content,
            source_text=source_text,
            voice_profile=voice_profile,
            pass_threshold=pass_threshold,
        )
        variant['quality_evaluation'] = evaluation

    return variants
