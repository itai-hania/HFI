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
import sys
from pathlib import Path
from typing import Optional, List, Dict
from datetime import datetime, timezone

sys.path.append(str(Path(__file__).parent.parent))

from openai import OpenAI
from common.models import StyleExample, engine

logger = logging.getLogger(__name__)


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

    KEEP_ENGLISH = {
        'API', 'ML', 'AI', 'GPT', 'LLM', 'NFT', 'DeFi', 'ETF', 'IPO', 'VC',
        'CEO', 'CTO', 'CFO', 'COO', 'SaaS', 'B2B', 'B2C', 'ROI', 'KPI',
        'FOMO', 'HODL', 'DCA', 'ATH', 'FUD', 'DAO', 'DEX', 'CEX',
        'startup', 'fintech', 'blockchain', 'crypto', 'bitcoin', 'ethereum',
    }

    def __init__(self, openai_client=None, model: Optional[str] = None,
                 temperature: Optional[float] = None,
                 glossary: Optional[Dict[str, str]] = None):
        if openai_client:
            self.client = openai_client
        else:
            api_key = os.getenv('OPENAI_API_KEY')
            if not api_key:
                raise ValueError("OPENAI_API_KEY environment variable is required")
            self.client = OpenAI(api_key=api_key)

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
        except Exception:
            return {}

    def _load_style_examples(self, source_text: Optional[str] = None, limit: int = 5) -> List[str]:
        """Load style examples from DB, prioritizing topic-matched ones."""
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

            if source_text:
                source_tags = self._extract_keywords(source_text)
                scored = []
                for ex in all_examples:
                    ex_tags = ex.topic_tags or []
                    if isinstance(ex_tags, str):
                        try:
                            ex_tags = json.loads(ex_tags)
                        except Exception:
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
                step = len(sorted_by_length) / limit
                selected = [sorted_by_length[min(int(i * step), len(sorted_by_length) - 1)] for i in range(limit)]

            return [ex.content for ex in selected]
        except Exception as e:
            logger.warning(f"Could not load style examples: {e}")
            return []
        finally:
            db.close()

    def _extract_keywords(self, text: str) -> List[str]:
        keyword_map = {
            'fintech': ['fintech', 'financial technology', 'neobank'],
            'crypto': ['crypto', 'cryptocurrency', 'token'],
            'bitcoin': ['bitcoin', 'btc'],
            'ethereum': ['ethereum', 'eth'],
            'blockchain': ['blockchain', 'distributed ledger'],
            'banking': ['bank', 'banking', 'deposit', 'loan'],
            'payments': ['payment', 'transfer', 'paypal', 'stripe'],
            'investing': ['invest', 'portfolio', 'fund', 'asset'],
            'trading': ['trading', 'trade', 'exchange', 'broker'],
            'markets': ['market', 'stock', 'bond', 'equity', 'nasdaq'],
            'regulation': ['regulat', 'compliance', 'sec', 'fed'],
            'startups': ['startup', 'founder', 'seed', 'venture'],
            'AI': ['artificial intelligence', ' ai ', 'machine learning', 'llm'],
            'DeFi': ['defi', 'decentralized finance', 'yield'],
            'IPO': ['ipo', 'public offering', 'listing'],
        }
        text_lower = text.lower()
        found = []
        for tag, keywords in keyword_map.items():
            for kw in keywords:
                if kw in text_lower:
                    found.append(tag)
                    break
        return found

    def _build_style_section(self, source_text: Optional[str] = None) -> str:
        examples = self._load_style_examples(source_text=source_text, limit=5)
        if not examples:
            return "Write in a professional, engaging Hebrew style suitable for financial/tech content on social media."

        examples_text = ""
        for i, example in enumerate(examples, 1):
            truncated = example[:800] + "..." if len(example) > 800 else example
            examples_text += f"\n--- Example {i} ---\n{truncated}\n"

        return f"""STYLE EXAMPLES (match this writing style):
{examples_text}

Match the tone, vocabulary, and sentence structure from the examples above."""

    def _build_glossary_str(self) -> str:
        if not self.glossary:
            return ""
        return "\n".join(f"- {eng}: {heb}" for eng, heb in self.glossary.items())

    def _get_completion_params(self, system_prompt: str, user_content: str,
                                temperature_offset: float = 0.0) -> dict:
        params = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content}
            ]
        }
        if self.base_temperature is not None:
            params["temperature"] = min(self.base_temperature + temperature_offset, 2.0)
        return params

    def validate_hebrew_output(self, text: str) -> bool:
        if not text:
            return False
        hebrew_chars = sum(1 for c in text if '\u0590' <= c <= '\u05FF')
        alpha_chars = sum(1 for c in text if c.isalpha())
        if alpha_chars == 0:
            return False
        return (hebrew_chars / alpha_chars) >= 0.5

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

        glossary_str = self._build_glossary_str()
        keep_english_str = ", ".join(sorted(self.KEEP_ENGLISH))
        style_section = self._build_style_section(source_text=source_text)
        source_hash = hashlib.md5(source_text.encode()).hexdigest()[:12]

        variants = []
        for angle in selected_angles:
            system_prompt = f"""You are a Hebrew financial/tech content creator writing for social media (X/Twitter).

Your task: Write an ORIGINAL Hebrew post INSPIRED BY the source content below.
Do NOT translate. Create NEW content in Hebrew that captures the key insight.

ANGLE: {angle['instruction']}

RULES:
1. Write ORIGINAL Hebrew content (not a translation)
2. Keep these terms in English: {keep_english_str}
3. Use this glossary: {glossary_str}
4. {style_section}
5. Keep it concise (tweet-length, under 280 chars if possible, max 500 chars)
6. 1-2 emojis maximum
7. At least 50% of letters must be Hebrew
8. Output ONLY the Hebrew post content, nothing else"""

            user_content = f"Source content to be inspired by:\n\n{source_text}"

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

                variants.append({
                    'angle': angle['name'],
                    'label': angle['label'],
                    'content': content,
                    'char_count': len(content),
                    'is_valid_hebrew': self.validate_hebrew_output(content),
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

        glossary_str = self._build_glossary_str()
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

        user_content = f"Source content to be inspired by:\n\n{source_text}"

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
