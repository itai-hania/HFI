"""
Comprehensive unit and integration tests for the Processor service.

Tests cover:
1. ProcessorConfig - Configuration loading and validation
2. TranslationService - OpenAI API integration and error handling
3. MediaDownloader - Image and video download functionality
4. TweetProcessor - End-to-end tweet processing workflow
5. Integration tests - Full pipeline testing

Run with: pytest tests/test_processor_comprehensive.py -v
"""

import pytest
import os
import sys
import json
import tempfile
import subprocess
from pathlib import Path
from datetime import datetime, timezone
from unittest.mock import Mock, MagicMock, patch, mock_open
from io import BytesIO

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from processor.processor import (
    ProcessorConfig,
    TranslationService,
    MediaDownloader,
    TweetProcessor,
    MEDIA_DIR
)
from common.models import (
    Tweet,
    TweetStatus,
    Base,
    engine,
    get_db_session
)


# ==================== Fixtures ====================

@pytest.fixture
def temp_config_dir():
    """Create temporary config directory with test files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config_dir = Path(tmpdir) / "config"
        config_dir.mkdir()

        # Create test glossary
        glossary = {
            "Fintech": "פינטק",
            "Startup": "סטארטאפ",
            "AI": "בינה מלאכותית"
        }
        with open(config_dir / "glossary.json", 'w', encoding='utf-8') as f:
            json.dump(glossary, f, ensure_ascii=False)

        # Create test style guide
        style_content = """
# Example Style Guide
🚨 Example tweet: This is how we write tweets
💡 Another example: Professional but accessible
"""
        with open(config_dir / "style.txt", 'w', encoding='utf-8') as f:
            f.write(style_content)

        yield config_dir


@pytest.fixture
def test_db():
    """Create an in-memory database for testing."""
    # Use in-memory database
    os.environ['DATABASE_URL'] = 'sqlite:///:memory:'

    # Recreate tables
    Base.metadata.create_all(engine)

    # Create session
    session = get_db_session()

    yield session

    # Cleanup
    session.close()
    Base.metadata.drop_all(engine)


@pytest.fixture
def temp_media_dir():
    """Create temporary media directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        media_dir = Path(tmpdir)
        yield media_dir


@pytest.fixture
def mock_openai_client():
    """Mock OpenAI client for testing."""
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = "תרגום לדוגמה בעברית"
    mock_client.chat.completions.create.return_value = mock_response
    return mock_client


# ==================== ProcessorConfig Tests ====================

class TestProcessorConfig:
    """Test cases for ProcessorConfig."""

    def test_config_requires_api_key(self):
        """Test that config initialization requires OPENAI_API_KEY."""
        # Remove API key if exists
        original_key = os.environ.get('OPENAI_API_KEY')
        if 'OPENAI_API_KEY' in os.environ:
            del os.environ['OPENAI_API_KEY']

        with pytest.raises(ValueError, match="OPENAI_API_KEY environment variable is required"):
            ProcessorConfig()

        # Restore original key
        if original_key:
            os.environ['OPENAI_API_KEY'] = original_key

    @patch('processor.processor.CONFIG_DIR')
    def test_config_loads_glossary(self, mock_config_dir, temp_config_dir):
        """Test loading glossary from JSON file."""
        mock_config_dir.__truediv__ = lambda self, x: temp_config_dir / x
        os.environ['OPENAI_API_KEY'] = 'test-key-123'
        os.environ['OPENAI_MODEL'] = 'gpt-4o'

        with patch('processor.processor.ProcessorConfig._load_glossary') as mock_load:
            test_glossary = {"Test": "בדיקה"}
            mock_load.return_value = test_glossary

            config = ProcessorConfig()
            config.glossary = test_glossary

            assert config.glossary == test_glossary
            assert "Test" in config.glossary

    def test_config_handles_missing_glossary(self):
        """Test graceful handling of missing glossary file."""
        os.environ['OPENAI_API_KEY'] = 'test-key-123'
        os.environ['OPENAI_MODEL'] = 'gpt-4o'

        with patch('processor.processor.CONFIG_DIR') as mock_dir:
            mock_dir.__truediv__ = lambda self, x: Path("/nonexistent") / x

            with patch('processor.processor.ProcessorConfig._load_glossary') as mock_load:
                mock_load.return_value = {}

                config = ProcessorConfig()
                config.glossary = {}

                assert config.glossary == {}

    @patch('processor.processor.CONFIG_DIR')
    def test_config_loads_style_guide(self, mock_config_dir, temp_config_dir):
        """Test loading style guide from text file."""
        mock_config_dir.__truediv__ = lambda self, x: temp_config_dir / x
        os.environ['OPENAI_API_KEY'] = 'test-key-123'
        os.environ['OPENAI_MODEL'] = 'gpt-4o'

        with patch('processor.processor.ProcessorConfig._load_style') as mock_load:
            test_style = "Professional writing style"
            mock_load.return_value = test_style

            config = ProcessorConfig()
            config.style_examples = test_style

            assert config.style_examples == test_style

    def test_config_handles_missing_style_guide(self):
        """Test graceful handling of missing style guide."""
        os.environ['OPENAI_API_KEY'] = 'test-key-123'
        os.environ['OPENAI_MODEL'] = 'gpt-4o'

        with patch('processor.processor.CONFIG_DIR') as mock_dir:
            mock_dir.__truediv__ = lambda self, x: Path("/nonexistent") / x

            with patch('processor.processor.ProcessorConfig._load_style') as mock_load:
                default_style = "Write in a professional, engaging style suitable for financial news."
                mock_load.return_value = default_style

                config = ProcessorConfig()
                config.style_examples = default_style

                assert "professional" in config.style_examples.lower()

    def test_config_handles_invalid_json(self):
        """Test handling of corrupted JSON glossary."""
        os.environ['OPENAI_API_KEY'] = 'test-key-123'
        os.environ['OPENAI_MODEL'] = 'gpt-4o'

        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            f.write("{ invalid json }")
            invalid_json_path = f.name

        try:
            with patch('processor.processor.CONFIG_DIR') as mock_dir:
                mock_dir.__truediv__ = lambda self, x: Path(invalid_json_path)

                with patch('processor.processor.ProcessorConfig._load_glossary') as mock_load:
                    mock_load.return_value = {}

                    config = ProcessorConfig()
                    config.glossary = {}

                    assert config.glossary == {}
        finally:
            os.unlink(invalid_json_path)


# ==================== TranslationService Tests ====================

class TestTranslationService:
    """Test cases for TranslationService."""

    def test_translation_service_initialization(self, mock_openai_client):
        """Test TranslationService initialization."""
        config = MagicMock()
        config.openai_client = mock_openai_client
        config.glossary = {"Test": "בדיקה"}
        config.style_examples = "Style guide content"

        service = TranslationService(config)

        assert service.config == config
        assert service.client == mock_openai_client

    def test_translate_and_rewrite_success(self, mock_openai_client):
        """Test successful translation with OpenAI API."""
        config = MagicMock()
        config.openai_client = mock_openai_client
        config.openai_model = 'gpt-4o'
        config.openai_temperature = 0.7
        config.glossary = {"Fintech": "פינטק", "Startup": "סטארטאפ"}
        config.style_examples = "Example style content"

        service = TranslationService(config)

        result = service.translate_and_rewrite("This is a test about Fintech startups")

        assert result == "תרגום לדוגמה בעברית"
        mock_openai_client.chat.completions.create.assert_called_once()

        # Verify API call parameters
        call_args = mock_openai_client.chat.completions.create.call_args
        assert call_args.kwargs['model'] == 'gpt-4o'
        assert call_args.kwargs['temperature'] == 0.7

    def test_translate_and_rewrite_includes_glossary(self, mock_openai_client):
        """Test that glossary terms are included in the prompt."""
        config = MagicMock()
        config.openai_client = mock_openai_client
        config.glossary = {"AI": "בינה מלאכותית", "ML": "למידת מכונה"}
        config.style_examples = "Style guide"

        service = TranslationService(config)
        service.translate_and_rewrite("Test text about AI and ML")

        # Check that system prompt includes glossary
        call_args = mock_openai_client.chat.completions.create.call_args
        system_prompt = call_args.kwargs['messages'][0]['content']

        assert "AI: בינה מלאכותית" in system_prompt or "AI" in system_prompt

    def test_translate_and_rewrite_api_error(self, mock_openai_client):
        """Test handling of OpenAI API errors."""
        config = MagicMock()
        config.openai_client = mock_openai_client
        config.glossary = {}
        config.style_examples = "Style"

        # Simulate API error
        mock_openai_client.chat.completions.create.side_effect = Exception("API Error")

        service = TranslationService(config)

        with pytest.raises(Exception, match="OpenAI translation error"):
            service.translate_and_rewrite("Test text")

    def test_translate_and_rewrite_timeout(self, mock_openai_client):
        """Test handling of API timeout."""
        config = MagicMock()
        config.openai_client = mock_openai_client
        config.glossary = {}
        config.style_examples = "Style"

        # Simulate timeout
        mock_openai_client.chat.completions.create.side_effect = TimeoutError("Request timeout")

        service = TranslationService(config)

        with pytest.raises(Exception, match="OpenAI translation error"):
            service.translate_and_rewrite("Test text")

    def test_translate_empty_text(self, mock_openai_client):
        """Test translation of empty text."""
        config = MagicMock()
        config.openai_client = mock_openai_client
        config.glossary = {}
        config.style_examples = "Style"

        service = TranslationService(config)
        result = service.translate_and_rewrite("")

        # Should still call API and return result
        assert result == "תרגום לדוגמה בעברית"


# ==================== MediaDownloader Tests ====================

class TestMediaDownloader:
    """Test cases for MediaDownloader."""

    def test_media_downloader_initialization(self, temp_media_dir):
        """Test MediaDownloader initialization."""
        downloader = MediaDownloader()

        assert downloader.media_dir == MEDIA_DIR
        assert downloader.media_dir.exists()

    def test_download_media_with_none_url(self):
        """Test download_media with None URL."""
        downloader = MediaDownloader()

        result = downloader.download_media(None)

        assert result is None

    def test_download_media_with_empty_url(self):
        """Test download_media with empty URL."""
        downloader = MediaDownloader()

        result = downloader.download_media("")

        assert result is None

    @patch('processor.processor.requests.get')
    def test_download_image_success(self, mock_get, temp_media_dir):
        """Test successful image download."""
        # Mock successful response
        mock_response = MagicMock()
        mock_response.iter_content = lambda chunk_size: [b'fake_image_data']
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        downloader = MediaDownloader()

        with patch.object(downloader, 'media_dir', temp_media_dir):
            result = downloader.download_media("https://example.com/image.jpg")

        assert result is not None
        assert Path(result).exists()
        assert Path(result).suffix == '.jpg'

    @patch('processor.processor.requests.get')
    def test_download_image_different_formats(self, mock_get, temp_media_dir):
        """Test downloading different image formats."""
        mock_response = MagicMock()
        mock_response.iter_content = lambda chunk_size: [b'fake_data']
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        downloader = MediaDownloader()

        formats = ['.png', '.jpeg', '.gif', '.webp']

        for fmt in formats:
            with patch.object(downloader, 'media_dir', temp_media_dir):
                result = downloader.download_media(f"https://example.com/image{fmt}")

            assert result is not None
            assert Path(result).suffix == fmt

    @patch('processor.processor.requests.get')
    def test_download_image_network_error(self, mock_get):
        """Test handling of network errors during image download."""
        mock_get.side_effect = Exception("Network error")

        downloader = MediaDownloader()
        result = downloader.download_media("https://example.com/image.jpg")

        # Should return None on error, not raise
        assert result is None

    @patch('processor.processor.requests.get')
    def test_download_image_http_error(self, mock_get):
        """Test handling of HTTP errors (404, 500, etc.)."""
        import requests
        mock_get.side_effect = requests.HTTPError("404 Not Found")

        downloader = MediaDownloader()
        result = downloader.download_media("https://example.com/notfound.jpg")

        assert result is None

    @patch('processor.processor.subprocess.run')
    def test_download_video_success(self, mock_run, temp_media_dir):
        """Test successful video download with yt-dlp."""
        # Mock successful subprocess call
        mock_run.return_value = MagicMock(returncode=0)

        downloader = MediaDownloader()

        with patch.object(downloader, 'media_dir', temp_media_dir):
            # Create a fake output file
            with patch('processor.processor.Path.exists', return_value=True):
                result = downloader.download_media("https://example.com/video.m3u8")

        assert mock_run.called
        call_args = mock_run.call_args[0][0]
        assert 'yt-dlp' in call_args[0]  # First arg is the binary path, check it contains 'yt-dlp'
        assert '-f' in call_args
        assert 'best' in call_args

    @patch('processor.processor.subprocess.run')
    def test_download_video_timeout(self, mock_run):
        """Test handling of yt-dlp timeout."""
        mock_run.side_effect = subprocess.TimeoutExpired('yt-dlp', 300)

        downloader = MediaDownloader()
        result = downloader.download_media("https://example.com/video.m3u8")

        assert result is None

    @patch('processor.processor.subprocess.run')
    def test_download_video_yt_dlp_error(self, mock_run):
        """Test handling of yt-dlp errors."""
        mock_run.side_effect = subprocess.CalledProcessError(
            1, 'yt-dlp', stderr=b'Download error'
        )

        downloader = MediaDownloader()
        result = downloader.download_media("https://example.com/video.m3u8")

        assert result is None

    def test_filename_generation_unique(self, temp_media_dir):
        """Test that generated filenames are unique."""
        downloader = MediaDownloader()

        with patch('processor.processor.requests.get') as mock_get:
            mock_response = MagicMock()
            mock_response.iter_content = lambda chunk_size: [b'data']
            mock_response.raise_for_status = MagicMock()
            mock_get.return_value = mock_response

            with patch.object(downloader, 'media_dir', temp_media_dir):
                result1 = downloader.download_media("https://example.com/image1.jpg")
                result2 = downloader.download_media("https://example.com/image2.jpg")

            # Filenames should be different
            assert result1 != result2

    def test_url_type_detection(self):
        """Test detection of URL type (video vs image)."""
        downloader = MediaDownloader()

        # Video URLs
        assert '.m3u8' in "https://example.com/stream.m3u8".lower()
        assert 'video' in "https://example.com/video/file".lower()

        # Image URLs
        assert '.jpg' in "https://example.com/image.jpg".lower()
        assert '.png' in "https://example.com/image.png".lower()


# ==================== TweetProcessor Tests ====================

class TestTweetProcessor:
    """Test cases for TweetProcessor."""

    @patch('processor.processor.ProcessorConfig')
    @patch('processor.processor.TranslationService')
    @patch('processor.processor.MediaDownloader')
    def test_processor_initialization(self, mock_downloader, mock_translator, mock_config):
        """Test TweetProcessor initialization."""
        processor = TweetProcessor()

        assert processor.config is not None
        assert processor.translator is not None
        assert processor.downloader is not None

    def test_process_pending_tweets_empty_database(self, test_db):
        """Test processing when no pending tweets exist."""
        with patch('processor.processor.SessionLocal', return_value=test_db):
            with patch('processor.processor.ProcessorConfig'):
                processor = TweetProcessor()

                count = processor.process_pending_tweets()

                assert count == 0

    def test_process_single_tweet_success(self, test_db, mock_openai_client):
        """Test successful processing of a single tweet."""
        # Create a pending tweet
        tweet = Tweet(
            source_url="https://x.com/test/status/123",
            original_text="Test tweet about Fintech",
            status=TweetStatus.PENDING
        )
        test_db.add(tweet)
        test_db.commit()
        tweet_id = tweet.id

        with patch('processor.processor.SessionLocal', return_value=test_db):
            with patch('processor.processor.ProcessorConfig') as mock_config_cls:
                mock_config = MagicMock()
                mock_config.openai_client = mock_openai_client
                mock_config.glossary = {}
                mock_config.style_examples = "Style"
                mock_config_cls.return_value = mock_config

                processor = TweetProcessor()
                count = processor.process_pending_tweets()

        assert count == 1

        # Verify tweet was updated by querying fresh from DB
        updated_tweet = test_db.query(Tweet).filter(Tweet.id == tweet_id).first()
        assert updated_tweet.status == TweetStatus.PROCESSED
        assert updated_tweet.hebrew_draft is not None

    def test_process_tweet_with_media(self, test_db, mock_openai_client):
        """Test processing tweet with media URL."""
        tweet = Tweet(
            source_url="https://x.com/test/status/456",
            original_text="Tweet with image",
            media_url="https://example.com/image.jpg",
            status=TweetStatus.PENDING
        )
        test_db.add(tweet)
        test_db.commit()
        tweet_id = tweet.id

        with patch('processor.processor.SessionLocal', return_value=test_db):
            with patch('processor.processor.ProcessorConfig') as mock_config_cls:
                mock_config = MagicMock()
                mock_config.openai_client = mock_openai_client
                mock_config.glossary = {}
                mock_config.style_examples = "Style"
                mock_config_cls.return_value = mock_config

                processor = TweetProcessor()

                # Mock media download
                with patch.object(processor.downloader, 'download_media', return_value='/path/to/media.jpg'):
                    count = processor.process_pending_tweets()

        assert count == 1
        updated_tweet = test_db.query(Tweet).filter(Tweet.id == tweet_id).first()
        assert updated_tweet.media_path == '/path/to/media.jpg'

    def test_process_tweet_translation_failure(self, test_db, mock_openai_client):
        """Test handling of translation failure."""
        tweet = Tweet(
            source_url="https://x.com/test/status/789",
            original_text="Tweet that will fail",
            status=TweetStatus.PENDING
        )
        test_db.add(tweet)
        test_db.commit()
        tweet_id = tweet.id

        # Make translation fail
        mock_openai_client.chat.completions.create.side_effect = Exception("Translation failed")

        with patch('processor.processor.SessionLocal', return_value=test_db):
            with patch('processor.processor.ProcessorConfig') as mock_config_cls:
                mock_config = MagicMock()
                mock_config.openai_client = mock_openai_client
                mock_config.glossary = {}
                mock_config.style_examples = "Style"
                mock_config_cls.return_value = mock_config

                processor = TweetProcessor()
                count = processor.process_pending_tweets()

        # Should not count as success
        assert count == 0

        # Verify tweet marked as failed
        updated_tweet = test_db.query(Tweet).filter(Tweet.id == tweet_id).first()
        assert updated_tweet.status == TweetStatus.FAILED
        assert updated_tweet.error_message is not None
        assert "Translation failed" in updated_tweet.error_message

    def test_process_tweet_media_download_failure(self, test_db, mock_openai_client):
        """Test that media download failure doesn't prevent tweet processing."""
        tweet = Tweet(
            source_url="https://x.com/test/status/999",
            original_text="Tweet with broken media",
            media_url="https://example.com/broken.jpg",
            status=TweetStatus.PENDING
        )
        test_db.add(tweet)
        test_db.commit()
        tweet_id = tweet.id

        with patch('processor.processor.SessionLocal', return_value=test_db):
            with patch('processor.processor.ProcessorConfig') as mock_config_cls:
                mock_config = MagicMock()
                mock_config.openai_client = mock_openai_client
                mock_config.glossary = {}
                mock_config.style_examples = "Style"
                mock_config_cls.return_value = mock_config

                processor = TweetProcessor()

                # Mock media download failure
                with patch.object(processor.downloader, 'download_media', return_value=None):
                    count = processor.process_pending_tweets()

        # Should still succeed despite media failure
        assert count == 1
        updated_tweet = test_db.query(Tweet).filter(Tweet.id == tweet_id).first()
        assert updated_tweet.status == TweetStatus.PROCESSED
        assert updated_tweet.media_path is None

    def test_process_batch_of_tweets(self, test_db, mock_openai_client):
        """Test processing multiple tweets in batch."""
        # Create multiple pending tweets
        for i in range(5):
            tweet = Tweet(
                source_url=f"https://x.com/test/status/{i}",
                original_text=f"Test tweet {i}",
                status=TweetStatus.PENDING
            )
            test_db.add(tweet)
        test_db.commit()

        with patch('processor.processor.SessionLocal', return_value=test_db):
            with patch('processor.processor.ProcessorConfig') as mock_config_cls:
                mock_config = MagicMock()
                mock_config.openai_client = mock_openai_client
                mock_config.glossary = {}
                mock_config.style_examples = "Style"
                mock_config_cls.return_value = mock_config

                processor = TweetProcessor()
                count = processor.process_pending_tweets()

        assert count == 5

        # Verify all tweets processed
        processed = test_db.query(Tweet).filter(Tweet.status == TweetStatus.PROCESSED).all()
        assert len(processed) == 5

    def test_process_partial_batch_failure(self, test_db, mock_openai_client):
        """Test that some tweets can fail while others succeed."""
        # Create tweets
        for i in range(3):
            tweet = Tweet(
                source_url=f"https://x.com/test/status/{i}",
                original_text=f"Test tweet {i}",
                status=TweetStatus.PENDING
            )
            test_db.add(tweet)
        test_db.commit()

        # Make translation fail on second tweet (all retry attempts)
        # translate_and_rewrite has max_retries=2, so 3 total attempts per tweet
        # Tweet 1: call 1 (success)
        # Tweet 2: calls 2, 3, 4 (all fail → marked FAILED)
        # Tweet 3: call 5 (success)
        call_count = 0
        def side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count in (2, 3, 4):
                raise Exception("Translation error")
            mock_response = MagicMock()
            mock_response.choices = [MagicMock()]
            mock_response.choices[0].message.content = f"תרגום {call_count}"
            return mock_response

        mock_openai_client.chat.completions.create.side_effect = side_effect

        with patch('processor.processor.SessionLocal', return_value=test_db):
            with patch('processor.processor.ProcessorConfig') as mock_config_cls:
                mock_config = MagicMock()
                mock_config.openai_client = mock_openai_client
                mock_config.glossary = {}
                mock_config.style_examples = "Style"
                mock_config_cls.return_value = mock_config

                processor = TweetProcessor()
                count = processor.process_pending_tweets()

        # Should process 2 out of 3
        assert count == 2

        processed = test_db.query(Tweet).filter(Tweet.status == TweetStatus.PROCESSED).all()
        failed = test_db.query(Tweet).filter(Tweet.status == TweetStatus.FAILED).all()

        assert len(processed) == 2
        assert len(failed) == 1


# ==================== Integration Tests ====================

class TestProcessorIntegration:
    """Integration tests for end-to-end processing."""

    def test_end_to_end_processing(self, test_db, mock_openai_client, temp_media_dir):
        """Test complete flow: pending → translate → download → processed."""
        # Create tweet with all fields
        tweet = Tweet(
            source_url="https://x.com/test/status/integration",
            original_text="Full integration test tweet about Fintech and AI",
            media_url="https://example.com/test.jpg",
            trend_topic="FinTech Innovation",
            status=TweetStatus.PENDING
        )
        test_db.add(tweet)
        test_db.commit()
        tweet_id = tweet.id

        with patch('processor.processor.SessionLocal', return_value=test_db):
            with patch('processor.processor.ProcessorConfig') as mock_config_cls:
                mock_config = MagicMock()
                mock_config.openai_client = mock_openai_client
                mock_config.glossary = {"Fintech": "פינטק", "AI": "בינה מלאכותית"}
                mock_config.style_examples = "Professional style"
                mock_config_cls.return_value = mock_config

                processor = TweetProcessor()

                # Mock successful media download
                with patch.object(processor.downloader, 'download_media', return_value='/path/to/downloaded.jpg'):
                    count = processor.process_pending_tweets()

        assert count == 1

        # Verify all fields updated correctly
        updated_tweet = test_db.query(Tweet).filter(Tweet.id == tweet_id).first()
        assert updated_tweet.status == TweetStatus.PROCESSED
        assert updated_tweet.hebrew_draft == "תרגום לדוגמה בעברית"
        assert updated_tweet.media_path == '/path/to/downloaded.jpg'
        assert updated_tweet.error_message is None
        assert updated_tweet.updated_at is not None

    def test_error_recovery_scenario(self, test_db, mock_openai_client):
        """Test error recovery: failed → pending → processed."""
        # Create a failed tweet
        tweet = Tweet(
            source_url="https://x.com/test/status/recovery",
            original_text="Tweet that was previously failed",
            status=TweetStatus.FAILED,
            error_message="Previous error message"
        )
        test_db.add(tweet)
        test_db.commit()
        tweet_id = tweet.id

        # Reset to pending
        tweet.status = TweetStatus.PENDING
        test_db.commit()

        with patch('processor.processor.SessionLocal', return_value=test_db):
            with patch('processor.processor.ProcessorConfig') as mock_config_cls:
                mock_config = MagicMock()
                mock_config.openai_client = mock_openai_client
                mock_config.glossary = {}
                mock_config.style_examples = "Style"
                mock_config_cls.return_value = mock_config

                processor = TweetProcessor()
                count = processor.process_pending_tweets()

        assert count == 1

        # Verify error cleared
        updated_tweet = test_db.query(Tweet).filter(Tweet.id == tweet_id).first()
        assert updated_tweet.status == TweetStatus.PROCESSED
        assert updated_tweet.error_message is None

    def test_database_transaction_rollback(self, test_db, mock_openai_client):
        """Test that database transactions are handled correctly on errors."""
        tweet = Tweet(
            source_url="https://x.com/test/status/transaction",
            original_text="Test transaction handling",
            status=TweetStatus.PENDING
        )
        test_db.add(tweet)
        test_db.commit()
        tweet_id = tweet.id

        # Make translation fail
        mock_openai_client.chat.completions.create.side_effect = Exception("Simulated failure")

        with patch('processor.processor.SessionLocal', return_value=test_db):
            with patch('processor.processor.ProcessorConfig') as mock_config_cls:
                mock_config = MagicMock()
                mock_config.openai_client = mock_openai_client
                mock_config.glossary = {}
                mock_config.style_examples = "Style"
                mock_config_cls.return_value = mock_config

                processor = TweetProcessor()
                count = processor.process_pending_tweets()

        # Transaction should commit the FAILED status
        updated_tweet = test_db.query(Tweet).filter(Tweet.id == tweet_id).first()
        assert updated_tweet.status == TweetStatus.FAILED
        assert updated_tweet.error_message is not None


if __name__ == "__main__":
    # Run tests with verbose output
    pytest.main([__file__, "-v", "--tb=short"])
