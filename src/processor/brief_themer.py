"""AI-powered brief story grouping into themes."""

import json
import logging
import os
from typing import Any, Dict, List

from openai import OpenAI

logger = logging.getLogger(__name__)

_SOURCE_CATEGORIES: Dict[str, str] = {
    "Yahoo Finance": "Finance",
    "CNBC": "Finance",
    "Bloomberg": "Finance",
    "MarketWatch": "Finance",
    "Seeking Alpha": "Finance",
    "TechCrunch": "Tech",
    "Investing.com": "Israel",
    "Google News Israel": "Israel",
    "Calcalist": "Israel",
    "Globes": "Israel",
    "Times of Israel": "Israel",
}

_CATEGORY_EMOJI: Dict[str, str] = {
    "Finance": "\U0001f4b0",
    "Tech": "\U0001f916",
    "Israel": "\U0001f1ee\U0001f1f1",
    "General": "\U0001f4ca",
}

_THEME_PROMPT = """You are a FinTech news editor. Group these stories into 2-4 coherent themes.

Stories:
{stories_text}

Return JSON with this exact structure:
{{
  "themes": [
    {{
      "name": "short punchy theme name (3-6 words)",
      "emoji": "single emoji",
      "takeaway": "one sentence insight — the 'so what'",
      "story_indices": [0, 2]
    }}
  ]
}}

Rules:
- Every story index (0 to {max_index}) must appear in exactly one theme
- 2-4 themes total
- Theme names should be engaging, not generic ("Chip War Heats Up", not "Technology")
- Takeaways should explain WHY this matters, not just restate the headline
- Return ONLY valid JSON, no markdown fences"""


class BriefThemer:
    def __init__(self):
        self._client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    def generate_themes(self, stories: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        if not stories:
            return []
        try:
            return self._ai_themes(stories)
        except Exception:
            logger.warning("AI theming failed, falling back to rule-based grouping", exc_info=True)
            return self._fallback_themes(stories)

    def _ai_themes(self, stories: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        stories_text = "\n".join(
            f"{i}. {s.get('title', '')} — {s.get('summary', '')[:100]}"
            for i, s in enumerate(stories)
        )
        prompt = _THEME_PROMPT.format(stories_text=stories_text, max_index=len(stories) - 1)

        response = self._client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            temperature=0.4,
            max_tokens=500,
            timeout=5,
        )

        raw = response.choices[0].message.content
        parsed = json.loads(raw)
        raw_themes = parsed.get("themes", [])
        if not raw_themes:
            raise ValueError("Empty themes array from API")
        return self._resolve_themes(raw_themes, stories)

    def _resolve_themes(self, raw_themes: List[Dict], stories: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        assigned: set[int] = set()
        themes: List[Dict[str, Any]] = []

        for rt in raw_themes:
            indices = rt.get("story_indices", [])
            valid_indices = [i for i in indices if isinstance(i, int) and 0 <= i < len(stories) and i not in assigned]
            if not valid_indices:
                continue
            assigned.update(valid_indices)
            themes.append({
                "name": str(rt.get("name", "News")),
                "emoji": str(rt.get("emoji", "\U0001f4ca")),
                "takeaway": str(rt.get("takeaway", "")),
                "stories": [stories[i] for i in valid_indices],
            })

        orphans = [i for i in range(len(stories)) if i not in assigned]
        if orphans:
            if themes:
                themes[-1]["stories"].extend(stories[i] for i in orphans)
            else:
                themes.append({
                    "name": "News",
                    "emoji": "\U0001f4ca",
                    "takeaway": "",
                    "stories": [stories[i] for i in orphans],
                })
        return themes

    def _fallback_themes(self, stories: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        groups: Dict[str, List[Dict[str, Any]]] = {}
        for story in stories:
            sources = story.get("sources", [])
            category = "General"
            for src in sources:
                if src in _SOURCE_CATEGORIES:
                    category = _SOURCE_CATEGORIES[src]
                    break
            groups.setdefault(category, []).append(story)

        themes = []
        for category in ["Finance", "Tech", "Israel", "General"]:
            cat_stories = groups.get(category, [])
            if not cat_stories:
                continue
            top_title = cat_stories[0].get("title", "")
            themes.append({
                "name": category,
                "emoji": _CATEGORY_EMOJI.get(category, "\U0001f4ca"),
                "takeaway": top_title[:80],
                "stories": cat_stories,
            })
        return themes
