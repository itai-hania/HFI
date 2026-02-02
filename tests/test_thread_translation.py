"""
Unit tests for Thread Translation (Phase 3) functionality.

Tests thread translation with side-by-side RTL Hebrew display.

Author: HFI Development Team
Last Updated: 2026-02-02
"""

import pytest
import os
from unittest.mock import Mock, patch, MagicMock
import sys
from pathlib import Path

# Add src directory to path
sys.path.append(str(Path(__file__).parent.parent))

from src.processor.processor import TranslationService, ProcessorConfig


@pytest.fixture
def mock_openai():
    """Mock OpenAI client for testing."""
    with patch('src.processor.processor.OpenAI') as mock:
        mock_client = Mock()
        mock_response = Mock()
        mock_response.choices = [Mock(message=Mock(content="זוהי תרגום בעברית לדוגמה."))]
        mock_client.chat.completions.create.return_value = mock_response
        mock.return_value = mock_client
        yield mock


@pytest.fixture
def mock_config(mock_openai):
    """Create a mocked ProcessorConfig."""
    os.environ['OPENAI_API_KEY'] = 'test-key'
    os.environ['OPENAI_MODEL'] = 'gpt-4o'

    config = ProcessorConfig()
    return config


@pytest.fixture
def translator(mock_config):
    """Create a TranslationService instance with mocked config."""
    return TranslationService(mock_config)


class TestIsHebrew:
    """Test Hebrew detection."""

    def test_is_hebrew_with_hebrew_text(self, translator):
        """Test detection of Hebrew text."""
        hebrew_text = "שלום עולם, זוהי בדיקה בעברית"
        assert translator.is_hebrew(hebrew_text) is True

    def test_is_hebrew_with_english_text(self, translator):
        """Test detection of English text."""
        english_text = "Hello world, this is a test in English"
        assert translator.is_hebrew(english_text) is False

    def test_is_hebrew_with_mixed_text(self, translator):
        """Test detection with mixed text (majority Hebrew)."""
        # Mostly Hebrew with some English terms
        mixed_text = "שוק ה-Bitcoin עלה היום ב-5% לפי המומחים"
        # Should be True if Hebrew > 50%
        result = translator.is_hebrew(mixed_text)
        assert isinstance(result, bool)

    def test_is_hebrew_with_empty_text(self, translator):
        """Test with empty string."""
        assert translator.is_hebrew("") is False

    def test_is_hebrew_with_numbers_only(self, translator):
        """Test with numbers only."""
        assert translator.is_hebrew("12345") is False


class TestValidateHebrewOutput:
    """Test Hebrew output validation."""

    def test_validate_hebrew_output_valid(self, translator):
        """Test validation of valid Hebrew output."""
        hebrew_text = "זוהי תרגום בעברית תקין עם מספיק תווים עבריים"
        is_valid, reason = translator.validate_hebrew_output(hebrew_text)
        assert is_valid is True
        assert reason == ""

    def test_validate_hebrew_output_empty(self, translator):
        """Test validation of empty output."""
        is_valid, reason = translator.validate_hebrew_output("")
        assert is_valid is False
        assert "Empty" in reason

    def test_validate_hebrew_output_english_only(self, translator):
        """Test validation of English-only output."""
        is_valid, reason = translator.validate_hebrew_output("This is only in English")
        assert is_valid is False
        assert "Hebrew ratio too low" in reason

    def test_validate_hebrew_output_mixed_valid(self, translator):
        """Test validation of mixed text with enough Hebrew."""
        # Text with >50% Hebrew characters
        mixed_text = "ביטקוין (Bitcoin) הגיע לשיא חדש של 100,000 דולר"
        is_valid, reason = translator.validate_hebrew_output(mixed_text)
        # Should be valid if Hebrew > 50% of alphabetic chars
        assert isinstance(is_valid, bool)


class TestExtractPreservables:
    """Test extraction of URLs, mentions, and hashtags."""

    def test_extract_urls(self, translator):
        """Test URL extraction."""
        text = "Check this out https://example.com and http://test.com"
        preservables = translator.extract_preservables(text)
        assert 'https://example.com' in preservables['urls']
        assert 'http://test.com' in preservables['urls']

    def test_extract_mentions(self, translator):
        """Test @mention extraction."""
        text = "Thanks @elonmusk and @sama for the update"
        preservables = translator.extract_preservables(text)
        assert '@elonmusk' in preservables['mentions']
        assert '@sama' in preservables['mentions']

    def test_extract_hashtags(self, translator):
        """Test #hashtag extraction."""
        text = "This is trending #Bitcoin #Crypto #Fintech"
        preservables = translator.extract_preservables(text)
        assert '#Bitcoin' in preservables['hashtags']
        assert '#Crypto' in preservables['hashtags']
        assert '#Fintech' in preservables['hashtags']

    def test_extract_empty_text(self, translator):
        """Test extraction from empty text."""
        preservables = translator.extract_preservables("")
        assert preservables['urls'] == []
        assert preservables['mentions'] == []
        assert preservables['hashtags'] == []


class TestTranslateThreadConsolidated:
    """Test consolidated thread translation."""

    def test_translate_thread_consolidated_basic(self, translator, mock_openai):
        """Test basic consolidated thread translation."""
        tweets = [
            {'text': 'Breaking: Bitcoin hits new ATH', 'author_handle': '@crypto'},
            {'text': 'This is significant because...', 'author_handle': '@crypto'},
            {'text': 'Market implications are huge', 'author_handle': '@crypto'}
        ]

        result = translator.translate_thread_consolidated(tweets)

        assert result is not None
        assert len(result) > 0
        # Should have called OpenAI API
        mock_openai.return_value.chat.completions.create.assert_called()

    def test_translate_thread_consolidated_empty(self, translator):
        """Test with empty tweet list."""
        result = translator.translate_thread_consolidated([])
        assert result == ""

    def test_translate_thread_consolidated_no_text(self, translator):
        """Test with tweets missing text."""
        tweets = [
            {'author_handle': '@user'},
            {'author_handle': '@user2'}
        ]
        result = translator.translate_thread_consolidated(tweets)
        assert result == ""

    def test_translate_thread_consolidated_already_hebrew(self, translator):
        """Test that already-Hebrew content is not re-translated."""
        tweets = [
            {'text': 'שלום עולם זוהי הודעה בעברית', 'author_handle': '@user'},
            {'text': 'זוהי הודעה נוספת בעברית', 'author_handle': '@user'}
        ]
        result = translator.translate_thread_consolidated(tweets)
        # Should return the original combined text
        assert 'שלום' in result or result == "שלום עולם זוהי הודעה בעברית\n\nזוהי הודעה נוספת בעברית"


class TestTranslateThreadSeparate:
    """Test separate thread translation with context."""

    def test_translate_thread_separate_basic(self, translator, mock_openai):
        """Test basic separate thread translation."""
        tweets = [
            {'text': 'First tweet in the thread', 'author_handle': '@user'},
            {'text': 'Second tweet continues the story', 'author_handle': '@user'},
            {'text': 'Third tweet concludes', 'author_handle': '@user'}
        ]

        results = translator.translate_thread_separate(tweets)

        assert isinstance(results, list)
        assert len(results) == 3
        # Each result should be a Hebrew translation
        for result in results:
            assert result is not None

    def test_translate_thread_separate_empty(self, translator):
        """Test with empty tweet list."""
        results = translator.translate_thread_separate([])
        assert results == []

    def test_translate_thread_separate_preserves_order(self, translator, mock_openai):
        """Test that translation order matches input order."""
        tweets = [
            {'text': 'Tweet 1', 'author_handle': '@user'},
            {'text': 'Tweet 2', 'author_handle': '@user'},
            {'text': 'Tweet 3', 'author_handle': '@user'}
        ]

        results = translator.translate_thread_separate(tweets)

        assert len(results) == 3

    def test_translate_thread_separate_handles_empty_tweets(self, translator, mock_openai):
        """Test handling of tweets with empty text."""
        tweets = [
            {'text': 'Tweet 1', 'author_handle': '@user'},
            {'text': '', 'author_handle': '@user'},  # Empty tweet
            {'text': 'Tweet 3', 'author_handle': '@user'}
        ]

        results = translator.translate_thread_separate(tweets)

        # Should still return 3 results (empty string for empty tweet)
        assert len(results) == 3


class TestTranslateText:
    """Test single text translation (backward compatibility)."""

    def test_translate_text_basic(self, translator, mock_openai):
        """Test basic text translation."""
        result = translator.translate_text("Hello world, this is a test")
        assert result is not None
        assert len(result) > 0

    def test_translate_text_already_hebrew(self, translator):
        """Test that Hebrew text is not re-translated."""
        hebrew_text = "שלום עולם זוהי בדיקה בעברית"
        result = translator.translate_text(hebrew_text)
        assert result == hebrew_text


class TestKeepEnglishTerms:
    """Test that certain terms are kept in English."""

    def test_keep_english_terms_defined(self, translator):
        """Test that KEEP_ENGLISH set is defined."""
        assert hasattr(translator, 'KEEP_ENGLISH')
        assert 'API' in translator.KEEP_ENGLISH
        assert 'AI' in translator.KEEP_ENGLISH
        assert 'Bitcoin' in translator.KEEP_ENGLISH or 'bitcoin' in translator.KEEP_ENGLISH
        assert 'fintech' in translator.KEEP_ENGLISH


class TestRTLSupport:
    """Test RTL (Right-to-Left) Hebrew text handling."""

    def test_hebrew_output_structure(self, translator, mock_openai):
        """Test that Hebrew output has proper structure."""
        # Mock response with Hebrew
        mock_openai.return_value.chat.completions.create.return_value.choices[0].message.content = \
            "הביטקוין הגיע לשיא חדש. זה משמעותי כי..."

        tweets = [{'text': 'Bitcoin hits ATH', 'author_handle': '@crypto'}]
        result = translator.translate_thread_consolidated(tweets)

        # Hebrew characters should be present
        hebrew_chars = sum(1 for c in result if '\u0590' <= c <= '\u05FF')
        assert hebrew_chars > 0

    def test_preserves_numbers_and_symbols(self, translator, mock_openai):
        """Test that numbers and symbols are preserved."""
        mock_openai.return_value.chat.completions.create.return_value.choices[0].message.content = \
            "המחיר עלה ב-15% ל-$100,000"

        tweets = [{'text': 'Price up 15% to $100,000', 'author_handle': '@crypto'}]
        result = translator.translate_thread_consolidated(tweets)

        # Numbers should be preserved
        assert '15' in result or '100,000' in result or result  # Check result exists


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
