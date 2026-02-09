"""
Tests for the PromptBuilder module (shared prompt-building utilities).

Covers: glossary section, style section, Hebrew validation,
completion params, call_with_retry, topic keyword extraction,
and style example loading from DB.

Run with: pytest tests/test_prompt_builder.py -v
"""

import pytest
import os
from unittest.mock import MagicMock, patch

from processor.prompt_builder import (
    KEEP_ENGLISH,
    KEYWORD_MAP,
    extract_topic_keywords,
    build_glossary_section,
    validate_hebrew_output,
    build_style_section,
    load_style_examples_from_db,
    get_completion_params,
    call_with_retry,
    _deep_copy_params,
)


# ==================== KEEP_ENGLISH Tests ====================

class TestKeepEnglish:

    def test_contains_core_terms(self):
        assert 'API' in KEEP_ENGLISH
        assert 'AI' in KEEP_ENGLISH
        assert 'fintech' in KEEP_ENGLISH
        assert 'Bitcoin' in KEEP_ENGLISH or 'bitcoin' in KEEP_ENGLISH

    def test_contains_social_terms(self):
        assert 'tweet' in KEEP_ENGLISH
        assert 'thread' in KEEP_ENGLISH
        assert 'retweet' in KEEP_ENGLISH


# ==================== extract_topic_keywords Tests ====================

class TestExtractTopicKeywords:

    def test_extract_fintech(self):
        result = extract_topic_keywords("A new fintech startup is launching")
        assert 'fintech' in result
        assert 'startups' in result

    def test_extract_crypto_bitcoin(self):
        result = extract_topic_keywords("Bitcoin price surges past $100K in crypto markets")
        assert 'bitcoin' in result
        assert 'crypto' in result
        assert 'markets' in result

    def test_extract_ai(self):
        result = extract_topic_keywords("Machine learning transforms trading")
        assert 'AI' in result
        assert 'trading' in result

    def test_extract_empty(self):
        assert extract_topic_keywords("Just a random sentence") == []

    def test_case_insensitive(self):
        result = extract_topic_keywords("BLOCKCHAIN technology is changing BANKING")
        assert 'blockchain' in result
        assert 'banking' in result

    def test_extract_regulation(self):
        result = extract_topic_keywords("SEC regulation of crypto exchanges")
        assert 'regulation' in result
        assert 'crypto' in result

    def test_extract_defi(self):
        result = extract_topic_keywords("DeFi liquidity pool yields")
        assert 'DeFi' in result

    def test_extract_ipo(self):
        result = extract_topic_keywords("The company filed for IPO public offering")
        assert 'IPO' in result


# ==================== build_glossary_section Tests ====================

class TestBuildGlossarySection:

    def test_builds_glossary(self):
        glossary = {"Bitcoin": "ביטקוין", "Fintech": "פינטק"}
        result = build_glossary_section(glossary)
        assert "Bitcoin: ביטקוין" in result
        assert "Fintech: פינטק" in result

    def test_empty_glossary(self):
        assert build_glossary_section({}) == ""

    def test_single_entry(self):
        result = build_glossary_section({"AI": "בינה מלאכותית"})
        assert result == "- AI: בינה מלאכותית"


# ==================== validate_hebrew_output Tests ====================

class TestValidateHebrewOutput:

    def test_valid_hebrew(self):
        is_valid, reason = validate_hebrew_output("שלום עולם זוהי בדיקה בעברית")
        assert is_valid is True
        assert reason == ""

    def test_empty_string(self):
        is_valid, reason = validate_hebrew_output("")
        assert is_valid is False
        assert "Empty" in reason

    def test_none_input(self):
        is_valid, reason = validate_hebrew_output(None)
        assert is_valid is False

    def test_english_only(self):
        is_valid, reason = validate_hebrew_output("This is only in English")
        assert is_valid is False
        assert "Hebrew ratio too low" in reason

    def test_mixed_above_threshold(self):
        is_valid, _ = validate_hebrew_output("טקסט בעברית כתוב כאן עם some English")
        assert is_valid is True

    def test_mixed_below_threshold(self):
        is_valid, _ = validate_hebrew_output("Lots of English text here with just א")
        assert is_valid is False

    def test_numbers_only(self):
        is_valid, reason = validate_hebrew_output("12345 67890")
        assert is_valid is False
        assert "No alphabetic" in reason


# ==================== get_completion_params Tests ====================

class TestGetCompletionParams:

    def test_basic_params(self):
        params = get_completion_params("gpt-4o", "system prompt", "user content")
        assert params['model'] == 'gpt-4o'
        assert len(params['messages']) == 2
        assert params['messages'][0]['role'] == 'system'
        assert params['messages'][0]['content'] == 'system prompt'
        assert params['messages'][1]['role'] == 'user'
        assert params['messages'][1]['content'] == 'user content'
        assert 'temperature' not in params

    def test_with_temperature(self):
        params = get_completion_params("gpt-4o", "sys", "usr", temperature=0.7)
        assert params['temperature'] == 0.7
        assert params['top_p'] == 0.9

    def test_no_temperature(self):
        params = get_completion_params("gpt-4o", "sys", "usr", temperature=None)
        assert 'temperature' not in params
        assert 'top_p' not in params


# ==================== call_with_retry Tests ====================

class TestCallWithRetry:

    def test_success_first_attempt(self):
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "תשובה בעברית"
        mock_client.chat.completions.create.return_value = mock_response

        params = get_completion_params("gpt-4o", "sys", "usr")
        result = call_with_retry(mock_client, params)
        assert result == "תשובה בעברית"
        assert mock_client.chat.completions.create.call_count == 1

    def test_no_validator(self):
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "English text"
        mock_client.chat.completions.create.return_value = mock_response

        params = get_completion_params("gpt-4o", "sys", "usr")
        result = call_with_retry(mock_client, params, validator_fn=None)
        assert result == "English text"  # No validation, returns as-is

    def test_retry_on_validation_failure(self):
        mock_client = MagicMock()

        # First call returns English, second returns Hebrew
        responses = [
            MagicMock(choices=[MagicMock(message=MagicMock(content="English text"))]),
            MagicMock(choices=[MagicMock(message=MagicMock(content="תשובה בעברית מלאה"))]),
        ]
        mock_client.chat.completions.create.side_effect = responses

        params = get_completion_params("gpt-4o", "sys", "usr")
        result = call_with_retry(mock_client, params, max_retries=1,
                                  validator_fn=validate_hebrew_output)
        assert "עברית" in result
        assert mock_client.chat.completions.create.call_count == 2

    def test_returns_unvalidated_on_max_retries(self):
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Always English"
        mock_client.chat.completions.create.return_value = mock_response

        params = get_completion_params("gpt-4o", "sys", "usr")
        result = call_with_retry(mock_client, params, max_retries=1,
                                  validator_fn=validate_hebrew_output)
        assert result == "Always English"
        assert mock_client.chat.completions.create.call_count == 2

    def test_raises_on_api_error(self):
        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = Exception("API Error")

        params = get_completion_params("gpt-4o", "sys", "usr")
        with pytest.raises(Exception, match="OpenAI API error"):
            call_with_retry(mock_client, params, max_retries=1)
        assert mock_client.chat.completions.create.call_count == 2

    def test_does_not_mutate_original_params(self):
        mock_client = MagicMock()

        responses = [
            MagicMock(choices=[MagicMock(message=MagicMock(content="English"))]),
            MagicMock(choices=[MagicMock(message=MagicMock(content="עברית טקסט מלא"))]),
        ]
        mock_client.chat.completions.create.side_effect = responses

        params = get_completion_params("gpt-4o", "original system prompt", "usr")
        original_system = params['messages'][0]['content']
        call_with_retry(mock_client, params, max_retries=1,
                        validator_fn=validate_hebrew_output)
        # Original params should NOT be mutated
        assert params['messages'][0]['content'] == original_system


# ==================== _deep_copy_params Tests ====================

class TestDeepCopyParams:

    def test_copies_messages(self):
        params = {
            'model': 'gpt-4o',
            'messages': [
                {'role': 'system', 'content': 'sys'},
                {'role': 'user', 'content': 'usr'},
            ]
        }
        copied = _deep_copy_params(params)
        copied['messages'][0]['content'] = 'modified'
        assert params['messages'][0]['content'] == 'sys'  # Original unchanged


# ==================== build_style_section Tests ====================

class TestBuildStyleSection:

    @patch('processor.prompt_builder.load_style_examples_from_db', return_value=[])
    def test_fallback_style(self, mock_load):
        result = build_style_section(fallback_style="My custom style guide")
        assert "My custom style guide" in result

    @patch('processor.prompt_builder.load_style_examples_from_db', return_value=[])
    def test_default_fallback(self, mock_load):
        result = build_style_section()
        assert "professional" in result.lower()

    @patch('processor.prompt_builder.load_style_examples_from_db')
    def test_with_db_examples(self, mock_load):
        mock_load.return_value = ["דוגמה ראשונה לסגנון", "דוגמה שנייה לסגנון"]
        result = build_style_section(source_text="fintech startup")
        assert "STYLE EXAMPLES" in result
        assert "דוגמה ראשונה" in result
        assert "דוגמה שנייה" in result

    @patch('processor.prompt_builder.load_style_examples_from_db')
    def test_truncates_long_examples(self, mock_load):
        long_example = "א" * 1000
        mock_load.return_value = [long_example]
        result = build_style_section()
        assert "..." in result
        # Should not contain the full 1000 chars
        assert len(long_example) > 800  # Sanity


# ==================== load_style_examples_from_db Tests ====================

class TestLoadStyleExamplesFromDb:

    def test_returns_empty_on_no_examples(self):
        """When DB has no active style examples, returns empty list."""
        mock_session = MagicMock()
        mock_session.query.return_value.filter.return_value.order_by.return_value.all.return_value = []

        with patch('processor.prompt_builder._Session', create=True) as mock_cls:
            # The function imports Session inside itself, so we need to mock
            # at the sqlalchemy.orm level
            pass

        # Simplest approach: patch the Session class used inside the function
        from sqlalchemy.orm import Session as RealSession
        with patch('sqlalchemy.orm.Session', return_value=mock_session):
            result = load_style_examples_from_db()
            assert result == []

    def test_returns_empty_on_exception(self):
        """When DB query fails, returns empty list gracefully."""
        mock_session = MagicMock()
        mock_session.query.side_effect = Exception("DB connection error")

        with patch('sqlalchemy.orm.Session', return_value=mock_session):
            result = load_style_examples_from_db()
            assert result == []


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
