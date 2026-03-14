"""
Tests for the Voice Analyzer module.

Tests cover:
1. analyze_voice() — schema validation, empty input, API errors
2. save_voice_profile() — file creation, metadata, Hebrew preservation
3. load_voice_profile() — valid file, missing file, invalid JSON, caching
4. build_voice_prompt_section() — full profile, empty profile, partial, never_list, signature phrases

Run with: pytest tests/test_voice_analyzer.py -v
"""

import json
import os
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch


SAMPLE_PROFILE = {
    "personality": ["authoritative", "witty", "provocative"],
    "tone_formality": 6,
    "sentence_patterns": [
        "Opens with a bold claim, then provides evidence",
        "Uses rhetorical questions to engage readers"
    ],
    "signature_phrases": ["בוא נדבר על זה", "השורה התחתונה"],
    "opening_hooks": ["Rhetorical question", "Bold statement"],
    "closing_patterns": ["Call to action", "Punchline"],
    "language_mixing": {
        "hebrew_primary": True,
        "english_terms_policy": "Keep fintech terms in English",
        "code_switching_examples": ["השוק עשה ATH היום"]
    },
    "never_list": [
        "Never uses formal academic language",
        "Never starts with greetings like שלום"
    ],
    "tweet_type_distribution": {
        "pattern_observation": 0.4,
        "contrarian": 0.2,
        "insider_insight": 0.3,
        "cultural_commentary": 0.1
    },
    "humanizer": {
        "enabled": True,
        "aggressiveness": "medium"
    }
}

GPT_RESPONSE_JSON = json.dumps(SAMPLE_PROFILE, ensure_ascii=False)


@pytest.fixture
def mock_openai_client():
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = GPT_RESPONSE_JSON
    mock_client.chat.completions.create.return_value = mock_response
    return mock_client


@pytest.fixture
def tmp_profile_path(tmp_path):
    return tmp_path / "voice_profile.json"


@pytest.fixture(autouse=True)
def clear_cache():
    """Clear the module-level cache before each test."""
    from processor.voice_analyzer import _clear_cache
    _clear_cache()
    yield
    _clear_cache()


# ==================== analyze_voice Tests ====================

class TestAnalyzeVoice:

    @patch("processor.voice_analyzer.get_openai_client")
    def test_analyze_voice_returns_expected_schema(self, mock_get_client, mock_openai_client):
        mock_get_client.return_value = mock_openai_client
        from processor.voice_analyzer import analyze_voice

        examples = [
            "ביטקוין הגיע לשיא חדש. בוא נדבר על זה.",
            "השורה התחתונה: השוק עשה ATH היום.",
            "מה זה אומר למשקיעים? הנה מה שאני חושב.",
        ]
        result = analyze_voice(examples, model="gpt-4o-test")

        assert isinstance(result, dict)
        assert "personality" in result
        assert isinstance(result["personality"], list)
        assert len(result["personality"]) >= 3

        assert "tone_formality" in result
        assert isinstance(result["tone_formality"], int)

        assert "sentence_patterns" in result
        assert "signature_phrases" in result
        assert "opening_hooks" in result
        assert "closing_patterns" in result
        assert "language_mixing" in result
        assert "never_list" in result
        assert "tweet_type_distribution" in result
        assert "humanizer" in result

        mock_openai_client.chat.completions.create.assert_called_once()

    @patch("processor.voice_analyzer.get_openai_client")
    def test_analyze_voice_empty_examples(self, mock_get_client):
        from processor.voice_analyzer import analyze_voice

        result = analyze_voice([])
        assert result == {}
        mock_get_client.assert_not_called()

    @patch("processor.voice_analyzer.get_openai_client")
    def test_analyze_voice_handles_api_error(self, mock_get_client):
        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = Exception("API rate limit")
        mock_get_client.return_value = mock_client
        from processor.voice_analyzer import analyze_voice

        result = analyze_voice(["בדיקה של טקסט בעברית"])
        assert result == {}


# ==================== save_voice_profile Tests ====================

class TestSaveVoiceProfile:

    def test_save_voice_profile_creates_file(self, tmp_profile_path):
        from processor.voice_analyzer import save_voice_profile

        save_voice_profile(SAMPLE_PROFILE, path=tmp_profile_path)

        assert tmp_profile_path.exists()
        with open(tmp_profile_path, 'r', encoding='utf-8') as f:
            loaded = json.load(f)
        assert "personality" in loaded

    def test_save_voice_profile_adds_metadata(self, tmp_profile_path):
        from processor.voice_analyzer import save_voice_profile

        save_voice_profile({"personality": ["bold"]}, path=tmp_profile_path)

        with open(tmp_profile_path, 'r', encoding='utf-8') as f:
            loaded = json.load(f)
        assert "_version" in loaded
        assert loaded["_version"] == "1.0"
        assert "_generated_at" in loaded
        assert "_source_count" in loaded

    def test_save_voice_profile_preserves_hebrew(self, tmp_profile_path):
        from processor.voice_analyzer import save_voice_profile

        profile = {
            "signature_phrases": ["בוא נדבר על זה", "השורה התחתונה"],
        }
        save_voice_profile(profile, path=tmp_profile_path)

        raw = tmp_profile_path.read_text(encoding='utf-8')
        assert "בוא נדבר על זה" in raw
        assert "\\u" not in raw


# ==================== load_voice_profile Tests ====================

class TestLoadVoiceProfile:

    def test_load_voice_profile_valid_file(self, tmp_profile_path):
        from processor.voice_analyzer import load_voice_profile

        tmp_profile_path.write_text(
            json.dumps(SAMPLE_PROFILE, ensure_ascii=False),
            encoding='utf-8'
        )

        result = load_voice_profile(path=tmp_profile_path)
        assert result["personality"] == SAMPLE_PROFILE["personality"]
        assert result["tone_formality"] == 6

    def test_load_voice_profile_missing_file_returns_empty(self, tmp_path):
        from processor.voice_analyzer import load_voice_profile

        result = load_voice_profile(path=tmp_path / "nonexistent.json")
        assert result == {}

    def test_load_voice_profile_invalid_json_returns_empty(self, tmp_profile_path):
        from processor.voice_analyzer import load_voice_profile

        tmp_profile_path.write_text("not valid json {{{{", encoding='utf-8')

        result = load_voice_profile(path=tmp_profile_path)
        assert result == {}

    def test_load_voice_profile_caching(self, tmp_profile_path):
        from processor.voice_analyzer import load_voice_profile, _clear_cache

        tmp_profile_path.write_text(
            json.dumps({"personality": ["original"]}),
            encoding='utf-8'
        )

        result1 = load_voice_profile(path=tmp_profile_path)
        assert result1["personality"] == ["original"]

        # Overwrite file — cached value should be returned
        tmp_profile_path.write_text(
            json.dumps({"personality": ["modified"]}),
            encoding='utf-8'
        )

        result2 = load_voice_profile(path=tmp_profile_path)
        assert result2["personality"] == ["original"]  # cached

        # Clear cache and reload
        _clear_cache()
        result3 = load_voice_profile(path=tmp_profile_path)
        assert result3["personality"] == ["modified"]


# ==================== build_voice_prompt_section Tests ====================

class TestBuildVoicePromptSection:

    def test_build_voice_prompt_section_full_profile(self):
        from processor.voice_analyzer import build_voice_prompt_section

        result = build_voice_prompt_section(SAMPLE_PROFILE)

        assert "VOICE IDENTITY:" in result
        assert "authoritative" in result
        assert "6/10" in result

        assert "WRITING PATTERNS:" in result
        assert "Opens with a bold claim" in result

        assert "LANGUAGE MIXING:" in result
        assert "Hebrew" in result

        assert "NEVER:" in result
        assert "formal academic language" in result

    def test_build_voice_prompt_section_empty_profile_returns_empty(self):
        from processor.voice_analyzer import build_voice_prompt_section

        assert build_voice_prompt_section({}) == ""

    def test_build_voice_prompt_section_partial_profile(self):
        from processor.voice_analyzer import build_voice_prompt_section

        partial = {"personality": ["bold", "direct"]}
        result = build_voice_prompt_section(partial)

        assert "VOICE IDENTITY:" in result
        assert "bold" in result
        assert "direct" in result
        assert "NEVER:" not in result  # no never_list provided

    def test_build_voice_prompt_section_never_list(self):
        from processor.voice_analyzer import build_voice_prompt_section

        profile = {
            "never_list": [
                "Never uses emojis excessively",
                "Never writes in passive voice",
                "Never uses clickbait titles"
            ]
        }
        result = build_voice_prompt_section(profile)

        assert "NEVER:" in result
        assert "1. Never uses emojis excessively" in result
        assert "2. Never writes in passive voice" in result
        assert "3. Never uses clickbait titles" in result

    def test_build_voice_prompt_section_signature_phrases(self):
        from processor.voice_analyzer import build_voice_prompt_section

        profile = {
            "signature_phrases": ["בוא נדבר על זה", "השורה התחתונה"]
        }
        result = build_voice_prompt_section(profile)

        assert "WRITING PATTERNS:" in result
        assert "Signature phrases:" in result
        assert "בוא נדבר על זה" in result
        assert "השורה התחתונה" in result
