"""
Content Generator for HFI Application

Generates ORIGINAL Hebrew content inspired by English source material.
Unlike translation, this creates new content in the user's voice with
distinct angles (educational, news-breaking, opinion/analysis).
"""

import json
import hashlib
import logging
import os
from pathlib import Path
from typing import Optional, List, Dict
from datetime import datetime, timezone

from openai import OpenAI
from common.models import StyleExample, engine
from common.openai_client import get_openai_client
from processor.prompt_builder import (
    KEEP_ENGLISH as _KEEP_ENGLISH,
    extract_topic_keywords,
    build_glossary_section,
    build_relevant_glossary_section,
    validate_hebrew_output as _validate_hebrew_output,
    score_hebrew_quality as _score_hebrew_quality,
    build_style_section,
    load_style_examples_from_db,
    get_completion_params,
    call_with_retry,
)

logger = logging.getLogger(__name__)


SOURCE_TYPE_INSTRUCTIONS = {
    'tweet': 'Source is a short social media post. Capture the core message and expand it with your own insight.',
    'headline': 'Source is a news headline. Expand it into a complete post with context and significance.',
    'earnings': 'Source is an earnings report. Focus on the key numbers, surprises, and market implications.',
    'funding': 'Source is a funding/investment announcement. Highlight the amount, company, and what it means for the sector.',
    'article': 'Source is a full article. Distill the main takeaway into a concise, engaging post.',
}


def _detect_source_type(source_text: str) -> str:
    """Detect the type of source content based on length and keywords."""
    if not source_text:
        return 'article'
    word_count = len(source_text.split())
    text_lower = source_text.lower()

    if word_count <= 50:
        return 'tweet'
    if word_count <= 20:
        return 'headline'

    earnings_signals = ['revenue', 'earnings', 'eps', 'quarter', 'q1', 'q2', 'q3', 'q4',
                        'profit', 'loss', 'guidance', 'beat', 'miss']
    if sum(1 for s in earnings_signals if s in text_lower) >= 3:
        return 'earnings'

    funding_signals = ['raised', 'funding', 'series', 'valuation', 'round',
                       'investment', 'seed', 'led by']
    if sum(1 for s in funding_signals if s in text_lower) >= 2:
        return 'funding'

    return 'article'


class ContentGenerator:
    """Generates original Hebrew content from English source material."""

    ANGLES = [
        {
            'name': 'news',
            'label': 'News/Breaking',
            'instruction': 'Write as a breaking news update. Be concise, factual, and urgent. Lead with the most important fact.',
            'temperature_offset': 0.0,
        },
        {
            'name': 'educational',
            'label': 'Educational',
            'instruction': 'Write as an educational explainer. Break down the topic for your audience. Use simple language to explain complex concepts.',
            'temperature_offset': 0.1,
        },
        {
            'name': 'opinion',
            'label': 'Opinion/Analysis',
            'instruction': 'Write as a personal opinion/analysis piece. Share your perspective, add context, and give your take on why this matters.',
            'temperature_offset': 0.2,
        },
    ]

    KEEP_ENGLISH = _KEEP_ENGLISH

    def __init__(self, openai_client=None, model: Optional[str] = None,
                 temperature: Optional[float] = None,
                 glossary: Optional[Dict[str, str]] = None):
        if openai_client:
            self.client = openai_client
        else:
            self.client = get_openai_client()

        self.model = model or os.getenv('OPENAI_MODEL', 'gpt-4o')
        self.base_temperature = temperature
        self.glossary = glossary if glossary is not None else self._load_glossary()

    def _load_glossary(self) -> Dict[str, str]:
        glossary_path = Path(__file__).parent.parent.parent / "config" / "glossary.json"
        if not glossary_path.exists():
            return {}
        try:
            with open(glossary_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            logger.warning(f"Failed to load glossary: {e}")
            return {}

    def _extract_keywords(self, text: str) -> List[str]:
        """Extract topic keywords from text. Delegates to prompt_builder."""
        return extract_topic_keywords(text)

    def _build_style_section(self, source_text: Optional[str] = None) -> str:
        """Build style section for prompts. Delegates to prompt_builder."""
        return build_style_section(source_text=source_text)

    @staticmethod
    def _preprocess_source(source_text: str, max_chars: int = 2000) -> str:
        """Preprocess source text for prompts.

        Short texts are returned as-is. Long texts get first 3 sentences
        + last 2 sentences with labels for focused generation.
        """
        if not source_text or len(source_text) <= max_chars:
            return source_text

        import re
        sentences = re.split(r'(?<=[.!?])\s+', source_text.strip())
        if len(sentences) <= 5:
            return source_text[:max_chars]

        opening = ' '.join(sentences[:3])
        closing = ' '.join(sentences[-2:])
        return f"[OPENING]\n{opening}\n\n[CLOSING]\n{closing}"

    def _build_glossary_str(self, source_text: str = None) -> str:
        """Build glossary string. Uses context-aware filtering when source_text provided."""
        if source_text:
            return build_relevant_glossary_section(self.glossary, source_text)
        return build_glossary_section(self.glossary)

    def _get_completion_params(self, system_prompt: str, user_content: str,
                                temperature_offset: float = 0.0) -> dict:
        """Build completion params with optional temperature offset."""
        temp = None
        if self.base_temperature is not None:
            temp = min(self.base_temperature + temperature_offset, 2.0)
        return get_completion_params(self.model, system_prompt, user_content, temperature=temp)

    def validate_hebrew_output(self, text: str) -> bool:
        """Validate Hebrew output. Returns bool (wraps prompt_builder's tuple return)."""
        is_valid, _ = _validate_hebrew_output(text)
        return is_valid

    def generate_post(self, source_text: str, num_variants: int = 3,
                       angles: Optional[List[str]] = None) -> List[Dict]:
        """
        Generate original Hebrew post variants from English source.

        Args:
            source_text: English source content to inspire the post
            num_variants: Number of variants to generate (max 3)
            angles: Optional list of angle names to use ('news', 'educational', 'opinion')

        Returns:
            List of dicts: [{'angle': str, 'label': str, 'content': str, 'char_count': int}]
        """
        if not source_text or not source_text.strip():
            return []

        num_variants = min(num_variants, len(self.ANGLES))

        if angles:
            selected_angles = [a for a in self.ANGLES if a['name'] in angles][:num_variants]
        else:
            selected_angles = self.ANGLES[:num_variants]

        glossary_str = self._build_glossary_str(source_text=source_text)
        keep_english_str = ", ".join(sorted(self.KEEP_ENGLISH))
        style_section = self._build_style_section(source_text=source_text)
        source_hash = hashlib.md5(source_text.encode()).hexdigest()[:12]
        source_type = _detect_source_type(source_text)
        source_type_instruction = SOURCE_TYPE_INSTRUCTIONS.get(source_type, '')

        variants = []
        for angle in selected_angles:
            system_prompt = f"""You are a Hebrew financial/tech content creator writing for social media (X/Twitter).

Your task: Write an ORIGINAL Hebrew post INSPIRED BY the source content below.
Do NOT translate. Create NEW content in Hebrew that captures the key insight.

ANGLE: {angle['instruction']}
SOURCE TYPE: {source_type_instruction}

RULES:
1. Write ORIGINAL Hebrew content (not a translation)
2. Keep these terms in English: {keep_english_str}
3. Use this glossary: {glossary_str}
4. {style_section}
5. Keep it concise (tweet-length, under 280 chars if possible, max 500 chars)
6. 1-2 emojis maximum
7. At least 50% of letters must be Hebrew
8. Output ONLY the Hebrew post content, nothing else"""

            processed_source = self._preprocess_source(source_text)
            user_content = f"Source content to be inspired by:\n\n{processed_source}"

            try:
                params = self._get_completion_params(
                    system_prompt, user_content,
                    temperature_offset=angle['temperature_offset']
                )
                response = self.client.chat.completions.create(**params)
                content = response.choices[0].message.content.strip()

                if not self.validate_hebrew_output(content):
                    # Retry once with stronger instruction
                    params['messages'][0]['content'] += "\n\nCRITICAL: Your output MUST be in Hebrew. Previous attempt was not Hebrew enough."
                    response = self.client.chat.completions.create(**params)
                    content = response.choices[0].message.content.strip()

                quality = _score_hebrew_quality(content)
                variants.append({
                    'angle': angle['name'],
                    'label': angle['label'],
                    'content': content,
                    'char_count': len(content),
                    'is_valid_hebrew': self.validate_hebrew_output(content),
                    'quality_score': quality['total'],
                    'quality_breakdown': quality,
                    'source_hash': source_hash,
                })

            except Exception as e:
                logger.error(f"Failed to generate {angle['name']} variant: {e}")
                variants.append({
                    'angle': angle['name'],
                    'label': angle['label'],
                    'content': f"Error: {str(e)}",
                    'char_count': 0,
                    'is_valid_hebrew': False,
                    'quality_score': 0,
                    'quality_breakdown': {'total': 0, 'hebrew_ratio': 0, 'length': 0, 'structure': 0},
                    'source_hash': source_hash,
                })

        return variants

    def generate_thread(self, source_text: str, num_tweets: int = 3,
                         angle: str = 'educational') -> List[Dict]:
        """
        Generate an original Hebrew thread (multiple tweets) from English source.

        Args:
            source_text: English source content
            num_tweets: Number of tweets in the thread (2-5)
            angle: Which angle to use

        Returns:
            List of dicts: [{'index': int, 'content': str, 'char_count': int}]
        """
        if not source_text or not source_text.strip():
            return []

        num_tweets = max(2, min(num_tweets, 5))

        angle_info = next((a for a in self.ANGLES if a['name'] == angle), self.ANGLES[0])

        glossary_str = self._build_glossary_str(source_text=source_text)
        keep_english_str = ", ".join(sorted(self.KEEP_ENGLISH))
        style_section = self._build_style_section(source_text=source_text)
        source_hash = hashlib.md5(source_text.encode()).hexdigest()[:12]

        system_prompt = f"""You are a Hebrew financial/tech content creator writing a Twitter thread.

Write an ORIGINAL Hebrew thread of exactly {num_tweets} tweets inspired by the source content.
Do NOT translate. Create NEW content.

ANGLE: {angle_info['instruction']}

RULES:
1. Write exactly {num_tweets} tweets, each under 280 characters
2. Separate tweets with "---" on its own line
3. First tweet should hook the reader
4. Last tweet should have a takeaway or call to action
5. Keep these terms in English: {keep_english_str}
6. Use this glossary: {glossary_str}
7. {style_section}
8. At least 50% Hebrew characters per tweet
9. Output ONLY the thread content separated by ---, nothing else"""

        processed_source = self._preprocess_source(source_text)
        user_content = f"Source content to be inspired by:\n\n{processed_source}"

        try:
            params = self._get_completion_params(
                system_prompt, user_content,
                temperature_offset=angle_info['temperature_offset']
            )
            response = self.client.chat.completions.create(**params)
            raw_content = response.choices[0].message.content.strip()

            # Parse tweets from response
            tweets = [t.strip() for t in raw_content.split('---') if t.strip()]

            results = []
            for i, tweet_text in enumerate(tweets):
                results.append({
                    'index': i + 1,
                    'content': tweet_text,
                    'char_count': len(tweet_text),
                    'is_valid_hebrew': self.validate_hebrew_output(tweet_text),
                    'source_hash': source_hash,
                    'angle': angle,
                })

            return results

        except Exception as e:
            logger.error(f"Failed to generate thread: {e}")
            return [{
                'index': 1,
                'content': f"Error: {str(e)}",
                'char_count': 0,
                'is_valid_hebrew': False,
                'source_hash': source_hash,
                'angle': angle,
            }]
