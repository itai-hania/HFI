"""
Tests for the Humanizer module.

Tests cover:
1. detect_ai_patterns() — Hebrew/English pattern detection across all categories
2. is_humanizer_enabled() — env var, voice profile, default fallback
3. humanize_text() — disabled path, no-patterns path, two-pass GPT, error handling

Run with: pytest tests/test_humanizer.py -v
"""

import json
import os
import pytest
from unittest.mock import MagicMock, patch


# ==================== Fixtures ====================

@pytest.fixture
def mock_openai_client():
    mock_client = MagicMock()
    critique_response = MagicMock()
    critique_response.choices = [MagicMock()]
    critique_response.choices[0].message.content = (
        "1. Uses 'חסר תקדים' — inflated significance\n"
        "2. Opens with filler 'חשוב לציין ש'\n"
        "3. Generic conclusion 'הזמן יגיד'"
    )
    revision_response = MagicMock()
    revision_response.choices = [MagicMock()]
    revision_response.choices[0].message.content = (
        "ביטקוין שבר שיא חדש. השוק מגיב בהתלהבות — אבל מה באמת השתנה?"
    )
    mock_client.chat.completions.create.side_effect = [
        critique_response,
        revision_response,
    ]
    return mock_client


@pytest.fixture
def sample_voice_profile():
    return {
        "personality": ["authoritative", "witty"],
        "tone_formality": 6,
        "signature_phrases": ["בוא נדבר על זה", "השורה התחתונה"],
        "never_list": ["Never uses formal academic language"],
        "humanizer": {"enabled": True, "aggressiveness": "medium"},
    }


# ==================== Pattern Detection Tests ====================

class TestDetectAIPatterns:

    def test_detect_significance_inflation_hebrew(self):
        from processor.humanizer import detect_ai_patterns

        text = "זהו אירוע מהפכני שמהווה נקודת מפנה בתעשייה"
        results = detect_ai_patterns(text)

        names = [r["pattern_name"] for r in results]
        assert "significance_inflation" in names
        match = next(r for r in results if r["pattern_name"] == "significance_inflation")
        assert match["category"] == "content"
        assert any("מהפכני" in m for m in match["matches"])

    def test_detect_significance_inflation_english(self):
        from processor.humanizer import detect_ai_patterns

        text = "This is a revolutionary and unprecedented development in fintech"
        results = detect_ai_patterns(text)

        names = [r["pattern_name"] for r in results]
        assert "significance_inflation" in names
        match = next(r for r in results if r["pattern_name"] == "significance_inflation")
        assert any("revolutionary" in m.lower() for m in match["matches"])
        assert any("unprecedented" in m.lower() for m in match["matches"])

    def test_detect_ai_vocabulary_hebrew(self):
        from processor.humanizer import detect_ai_patterns

        text = "צריך לצלול לעומק הנושא ולהבין את הציר המרכזי של הבעיה"
        results = detect_ai_patterns(text)

        names = [r["pattern_name"] for r in results]
        assert "ai_vocabulary" in names

    def test_detect_ai_vocabulary_english(self):
        from processor.humanizer import detect_ai_patterns

        text = "Let's delve into the pivotal landscape of fintech and unpack these transformative trends"
        results = detect_ai_patterns(text)

        names = [r["pattern_name"] for r in results]
        assert "ai_vocabulary" in names
        match = next(r for r in results if r["pattern_name"] == "ai_vocabulary")
        lower_matches = [m.lower() for m in match["matches"]]
        assert "delve" in lower_matches
        assert "pivotal" in lower_matches

    def test_detect_promotional_language(self):
        from processor.humanizer import detect_ai_patterns

        text = "אנו שמחים להודיע על פריצת דרך מרשימה ביותר בתחום הפינטק"
        results = detect_ai_patterns(text)

        names = [r["pattern_name"] for r in results]
        assert "promotional_language" in names

    def test_detect_vague_attributions(self):
        from processor.humanizer import detect_ai_patterns

        text = "מומחים אומרים שהשוק צפוי לעלות ומחקרים מראים מגמה חיובית"
        results = detect_ai_patterns(text)

        names = [r["pattern_name"] for r in results]
        assert "vague_attributions" in names

    def test_detect_generic_conclusions(self):
        from processor.humanizer import detect_ai_patterns

        text = "בסופו של דבר, הזמן יגיד מה יקרה בשוק הקריפטו"
        results = detect_ai_patterns(text)

        names = [r["pattern_name"] for r in results]
        assert "generic_conclusions" in names

    def test_detect_em_dash_overuse(self):
        from processor.humanizer import detect_ai_patterns

        text = "Bitcoin — the king of crypto — is surging — again — to new highs"
        results = detect_ai_patterns(text)

        names = [r["pattern_name"] for r in results]
        assert "em_dash_overuse" in names

    def test_detect_em_dash_normal_count_ok(self):
        from processor.humanizer import detect_ai_patterns

        text = "Bitcoin — the king of crypto, is surging to new highs"
        results = detect_ai_patterns(text)

        names = [r["pattern_name"] for r in results]
        assert "em_dash_overuse" not in names

    def test_detect_boldface_artifacts(self):
        from processor.humanizer import detect_ai_patterns

        text = "This is **very important** news about **Bitcoin** reaching new highs"
        results = detect_ai_patterns(text)

        names = [r["pattern_name"] for r in results]
        assert "boldface_artifacts" in names

    def test_detect_chatbot_artifacts(self):
        from processor.humanizer import detect_ai_patterns

        text = "Great question! I'd be happy to explain the current market situation"
        results = detect_ai_patterns(text)

        names = [r["pattern_name"] for r in results]
        assert "chatbot_artifacts" in names

    def test_detect_filler_phrases(self):
        from processor.humanizer import detect_ai_patterns

        text = "חשוב לציין ש ביטקוין עלה וראוי להזכיר ש זה משפיע על כל השוק"
        results = detect_ai_patterns(text)

        names = [r["pattern_name"] for r in results]
        assert "filler_phrases" in names

    def test_detect_clean_text_no_patterns(self):
        from processor.humanizer import detect_ai_patterns

        text = "ביטקוין עלה ב-5% היום. סוחרים מדווחים על ביקוש גובר."
        results = detect_ai_patterns(text)

        assert results == []

    def test_detect_multiple_patterns(self):
        from processor.humanizer import detect_ai_patterns

        text = (
            "אנו שמחים להודיע על אירוע מהפכני חסר תקדים. "
            "מומחים אומרים שזו פריצת דרך. "
            "חשוב לציין ש הזמן יגיד."
        )
        results = detect_ai_patterns(text)

        names = [r["pattern_name"] for r in results]
        assert len(names) >= 3
        assert "significance_inflation" in names
        assert "promotional_language" in names
        assert "vague_attributions" in names


# ==================== Configuration Tests ====================

class TestIsHumanizerEnabled:

    def test_is_humanizer_enabled_env_var_true(self, monkeypatch):
        monkeypatch.setenv("HFI_HUMANIZER_ENABLED", "true")
        from processor.humanizer import is_humanizer_enabled

        assert is_humanizer_enabled() is True

    def test_is_humanizer_enabled_env_var_false(self, monkeypatch):
        monkeypatch.setenv("HFI_HUMANIZER_ENABLED", "false")
        from processor.humanizer import is_humanizer_enabled

        assert is_humanizer_enabled() is False

    @patch("processor.humanizer.os.environ.get", return_value=None)
    @patch("processor.voice_analyzer.load_voice_profile")
    def test_is_humanizer_enabled_voice_profile(self, mock_load, mock_env_get):
        mock_load.return_value = {
            "humanizer": {"enabled": True, "aggressiveness": "medium"}
        }
        from processor.humanizer import is_humanizer_enabled

        assert is_humanizer_enabled() is True

    def test_is_humanizer_enabled_default_false(self, monkeypatch):
        monkeypatch.delenv("HFI_HUMANIZER_ENABLED", raising=False)

        with patch("processor.voice_analyzer.load_voice_profile", return_value={}):
            from processor.humanizer import is_humanizer_enabled
            assert is_humanizer_enabled() is False


# ==================== Humanization Tests ====================

class TestHumanizeText:

    def test_humanize_text_disabled_returns_original(self):
        from processor.humanizer import humanize_text

        text = "מהפכני חסר תקדים — אירוע שמשנה את כל התמונה"
        result = humanize_text(text, enabled=False)

        assert result["original"] == text
        assert result["humanized"] == text
        assert result["was_humanized"] is False
        assert result["critique"] == ""

    def test_humanize_text_no_patterns_returns_original(self):
        from processor.humanizer import humanize_text

        text = "ביטקוין עלה ב-5% היום. סוחרים מדווחים על ביקוש גובר."
        result = humanize_text(text, enabled=True)

        assert result["original"] == text
        assert result["humanized"] == text
        assert result["was_humanized"] is False
        assert result["patterns_detected"] == []

    @patch("processor.humanizer.get_openai_client")
    @patch("processor.voice_analyzer.load_voice_profile")
    @patch("processor.voice_analyzer.build_voice_prompt_section")
    def test_humanize_text_two_pass_mock_gpt(
        self, mock_build_voice, mock_load_profile, mock_get_client, mock_openai_client
    ):
        mock_get_client.return_value = mock_openai_client
        mock_load_profile.return_value = {"personality": ["bold"]}
        mock_build_voice.return_value = "VOICE IDENTITY:\nPersonality: bold"

        from processor.humanizer import humanize_text

        text = "מהפכני חסר תקדים — אירוע שמשנה את כל התמונה. חשוב לציין ש הזמן יגיד."
        result = humanize_text(text, enabled=True)

        assert result["was_humanized"] is True
        assert result["humanized"] != text
        assert result["critique"] != ""
        assert len(result["patterns_detected"]) > 0
        assert mock_openai_client.chat.completions.create.call_count == 2

    @patch("processor.humanizer.get_openai_client")
    @patch("processor.voice_analyzer.load_voice_profile")
    @patch("processor.voice_analyzer.build_voice_prompt_section")
    def test_humanize_text_result_structure(
        self, mock_build_voice, mock_load_profile, mock_get_client, mock_openai_client
    ):
        mock_get_client.return_value = mock_openai_client
        mock_load_profile.return_value = {}
        mock_build_voice.return_value = ""

        from processor.humanizer import humanize_text

        text = "אנו שמחים להודיע על פריצת דרך מהפכני. הזמן יגיד."
        result = humanize_text(text, enabled=True)

        assert "original" in result
        assert "humanized" in result
        assert "was_humanized" in result
        assert "patterns_detected" in result
        assert "critique" in result
        assert "changes_made" in result
        assert isinstance(result["patterns_detected"], list)
        assert isinstance(result["changes_made"], list)

    @patch("processor.humanizer.get_openai_client")
    @patch("processor.voice_analyzer.load_voice_profile")
    @patch("processor.voice_analyzer.build_voice_prompt_section")
    def test_humanize_text_preserves_hebrew_validation(
        self, mock_build_voice, mock_load_profile, mock_get_client, mock_openai_client
    ):
        mock_get_client.return_value = mock_openai_client
        mock_load_profile.return_value = {}
        mock_build_voice.return_value = ""

        from processor.humanizer import humanize_text

        text = "מהפכני חסר תקדים — אירוע ענק. חשוב לציין ש הזמן יגיד."
        result = humanize_text(text, enabled=True)

        # Humanized output should contain Hebrew characters
        hebrew_chars = sum(1 for c in result["humanized"] if '\u0590' <= c <= '\u05FF')
        assert hebrew_chars > 0

    def test_humanize_text_override_enabled_param(self):
        from processor.humanizer import humanize_text

        text = "ביטקוין עלה ב-5% היום. סוחרים מדווחים על ביקוש גובר."

        # enabled=True but no patterns → still returns original
        result = humanize_text(text, enabled=True)
        assert result["was_humanized"] is False

        # enabled=False with AI patterns → skips GPT, returns original
        ai_text = "מהפכני חסר תקדים — אירוע שמשנה הכל. הזמן יגיד."
        result = humanize_text(ai_text, enabled=False)
        assert result["was_humanized"] is False
        assert result["humanized"] == ai_text

    @patch("processor.humanizer.get_openai_client")
    @patch("processor.voice_analyzer.load_voice_profile")
    def test_humanize_text_api_error_returns_original(
        self, mock_load_profile, mock_get_client
    ):
        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = Exception("API rate limit exceeded")
        mock_get_client.return_value = mock_client
        mock_load_profile.return_value = {}

        from processor.humanizer import humanize_text

        text = "מהפכני חסר תקדים — אירוע שמשנה הכל. חשוב לציין ש הזמן יגיד."
        result = humanize_text(text, enabled=True)

        assert result["humanized"] == text
        assert result["was_humanized"] is False
        assert len(result["patterns_detected"]) > 0
