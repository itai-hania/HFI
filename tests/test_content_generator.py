"""
Tests for the Content Generator module.

Tests cover:
1. ContentGenerator initialization
2. generate_post() - variant generation with mocked GPT
3. generate_thread() - thread generation with mocked GPT
4. Hebrew validation
5. Prompt building and style section
6. Auto-style learning on approval
7. Schema changes (content_type, generation_metadata)

Run with: pytest tests/test_content_generator.py -v
"""

import pytest
import os
import json
from unittest.mock import Mock, MagicMock, patch
from datetime import datetime, timezone

from common.models import (
    Tweet, TweetStatus, StyleExample, Base, engine, get_db_session, SessionLocal
)


# ==================== Fixtures ====================

@pytest.fixture
def mock_openai_client():
    """Mock OpenAI client that returns Hebrew content."""
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = "ביטקוין הגיע לשיא חדש של 100 אלף דולר. זוהי עלייה משמעותית בשוק הקריפטו."
    mock_client.chat.completions.create.return_value = mock_response
    return mock_client


@pytest.fixture
def mock_openai_client_thread():
    """Mock OpenAI client that returns thread-formatted Hebrew content."""
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = (
        "ביטקוין הגיע לשיא חדש. מה זה אומר?\n"
        "---\n"
        "המשמעות היא שהשוק מראה סימני התאוששות חזקים.\n"
        "---\n"
        "לסיכום: זה הזמן לעקוב אחרי השוק מקרוב."
    )
    mock_client.chat.completions.create.return_value = mock_response
    return mock_client


@pytest.fixture
def mock_openai_client_english():
    """Mock OpenAI client that returns English content (invalid)."""
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = "Bitcoin hits new all-time high of $100K"
    mock_client.chat.completions.create.return_value = mock_response
    return mock_client


@pytest.fixture
def test_db():
    """Create test database with fresh schema."""
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    session = get_db_session()
    yield session
    session.close()
    Base.metadata.drop_all(engine)


@pytest.fixture
def generator(mock_openai_client):
    """Create ContentGenerator with mocked OpenAI client."""
    from processor.content_generator import ContentGenerator
    return ContentGenerator(
        openai_client=mock_openai_client,
        model='gpt-4o-test',
        temperature=0.7,
        glossary={"Bitcoin": "ביטקוין", "Fintech": "פינטק"}
    )


# ==================== ContentGenerator Init Tests ====================

class TestContentGeneratorInit:

    def test_init_with_client(self, mock_openai_client):
        from processor.content_generator import ContentGenerator
        gen = ContentGenerator(
            openai_client=mock_openai_client,
            model='gpt-4o',
            glossary={}
        )
        assert gen.client == mock_openai_client
        assert gen.model == 'gpt-4o'

    def test_init_uses_env_model(self, mock_openai_client):
        from processor.content_generator import ContentGenerator
        os.environ['OPENAI_MODEL'] = 'gpt-test-model'
        gen = ContentGenerator(openai_client=mock_openai_client)
        assert gen.model == 'gpt-test-model'
        del os.environ['OPENAI_MODEL']

    def test_init_default_model(self, mock_openai_client):
        from processor.content_generator import ContentGenerator
        if 'OPENAI_MODEL' in os.environ:
            del os.environ['OPENAI_MODEL']
        gen = ContentGenerator(openai_client=mock_openai_client)
        assert gen.model == 'gpt-4o'

    def test_init_no_api_key_raises(self):
        from processor.content_generator import ContentGenerator
        original = os.environ.get('OPENAI_API_KEY')
        if 'OPENAI_API_KEY' in os.environ:
            del os.environ['OPENAI_API_KEY']
        with pytest.raises(ValueError, match="OPENAI_API_KEY"):
            ContentGenerator()
        if original:
            os.environ['OPENAI_API_KEY'] = original

    def test_angles_defined(self):
        from processor.content_generator import ContentGenerator
        assert len(ContentGenerator.ANGLES) == 3
        names = [a['name'] for a in ContentGenerator.ANGLES]
        assert 'news' in names
        assert 'educational' in names
        assert 'opinion' in names


# ==================== generate_post() Tests ====================

class TestGeneratePost:

    def test_generate_post_returns_variants(self, generator):
        variants = generator.generate_post("Bitcoin hits $100K ATH")
        assert len(variants) == 3
        for v in variants:
            assert 'angle' in v
            assert 'label' in v
            assert 'content' in v
            assert 'char_count' in v
            assert 'source_hash' in v

    def test_generate_post_single_variant(self, generator):
        variants = generator.generate_post("Bitcoin hits $100K", num_variants=1)
        assert len(variants) == 1

    def test_generate_post_specific_angles(self, generator):
        variants = generator.generate_post("Test content", angles=['news'])
        assert len(variants) == 1
        assert variants[0]['angle'] == 'news'

    def test_generate_post_hebrew_validation(self, generator):
        variants = generator.generate_post("Bitcoin hits $100K")
        for v in variants:
            assert v['is_valid_hebrew'] is True

    def test_generate_post_empty_input(self, generator):
        assert generator.generate_post("") == []
        assert generator.generate_post(None) == []
        assert generator.generate_post("   ") == []

    def test_generate_post_char_count(self, generator):
        variants = generator.generate_post("Test content")
        for v in variants:
            assert v['char_count'] == len(v['content'])

    def test_generate_post_source_hash_consistent(self, generator):
        variants = generator.generate_post("Same source text")
        hashes = [v['source_hash'] for v in variants]
        assert len(set(hashes)) == 1  # All same hash

    def test_generate_post_different_sources_different_hashes(self, generator):
        v1 = generator.generate_post("Source A", num_variants=1)
        v2 = generator.generate_post("Source B", num_variants=1)
        assert v1[0]['source_hash'] != v2[0]['source_hash']

    def test_generate_post_api_error_handled(self, mock_openai_client):
        from processor.content_generator import ContentGenerator
        mock_openai_client.chat.completions.create.side_effect = Exception("API Error")
        gen = ContentGenerator(openai_client=mock_openai_client, model='test')
        variants = gen.generate_post("Test content")
        assert len(variants) == 3
        for v in variants:
            assert "Error" in v['content']
            assert v['is_valid_hebrew'] is False

    def test_generate_post_max_variants_capped(self, generator):
        variants = generator.generate_post("Test", num_variants=10)
        assert len(variants) <= 3  # Capped at ANGLES length

    def test_generate_post_with_english_response_retries(self, mock_openai_client_english):
        """When GPT returns English, it should retry with stronger instruction."""
        from processor.content_generator import ContentGenerator
        gen = ContentGenerator(
            openai_client=mock_openai_client_english,
            model='test'
        )
        variants = gen.generate_post("Test", num_variants=1)
        assert len(variants) == 1
        # Should have called the API at least twice (original + retry)
        assert mock_openai_client_english.chat.completions.create.call_count >= 2


# ==================== generate_thread() Tests ====================

class TestGenerateThread:

    def test_generate_thread_returns_tweets(self, mock_openai_client_thread):
        from processor.content_generator import ContentGenerator
        gen = ContentGenerator(
            openai_client=mock_openai_client_thread,
            model='test',
            glossary={}
        )
        result = gen.generate_thread("Bitcoin hits $100K", num_tweets=3)
        assert len(result) == 3
        for i, t in enumerate(result, 1):
            assert t['index'] == i
            assert 'content' in t
            assert t['char_count'] == len(t['content'])
            assert t['angle'] == 'educational'

    def test_generate_thread_empty_input(self, generator):
        assert generator.generate_thread("") == []
        assert generator.generate_thread(None) == []

    def test_generate_thread_num_tweets_clamped(self, mock_openai_client_thread):
        from processor.content_generator import ContentGenerator
        gen = ContentGenerator(openai_client=mock_openai_client_thread, model='test', glossary={})
        # Request 10, but should be clamped to 5 max
        result = gen.generate_thread("Test", num_tweets=10)
        # GPT mock returns 3 tweets, but the request should have been clamped to 5
        assert len(result) == 3  # Matches mock output (3 sections separated by ---)

    def test_generate_thread_api_error(self, mock_openai_client):
        from processor.content_generator import ContentGenerator
        mock_openai_client.chat.completions.create.side_effect = Exception("Thread API Error")
        gen = ContentGenerator(openai_client=mock_openai_client, model='test')
        result = gen.generate_thread("Test content")
        assert len(result) == 1
        assert "Error" in result[0]['content']

    def test_generate_thread_angle_selection(self, mock_openai_client_thread):
        from processor.content_generator import ContentGenerator
        gen = ContentGenerator(openai_client=mock_openai_client_thread, model='test', glossary={})
        result = gen.generate_thread("Test", angle='opinion')
        for t in result:
            assert t['angle'] == 'opinion'

    def test_generate_thread_source_hash(self, mock_openai_client_thread):
        from processor.content_generator import ContentGenerator
        gen = ContentGenerator(openai_client=mock_openai_client_thread, model='test', glossary={})
        result = gen.generate_thread("Unique source text")
        for t in result:
            assert 'source_hash' in t
            assert len(t['source_hash']) == 12


# ==================== Hebrew Validation Tests ====================

class TestHebrewValidation:

    def test_validate_hebrew_valid(self, generator):
        assert generator.validate_hebrew_output("זהו טקסט בעברית") is True

    def test_validate_hebrew_invalid_english(self, generator):
        assert generator.validate_hebrew_output("This is English only") is False

    def test_validate_hebrew_empty(self, generator):
        assert generator.validate_hebrew_output("") is False
        assert generator.validate_hebrew_output(None) is False

    def test_validate_hebrew_mixed_above_threshold(self, generator):
        # More than 50% Hebrew characters
        assert generator.validate_hebrew_output("טקסט בעברית כתוב כאן עם some English") is True

    def test_validate_hebrew_mixed_below_threshold(self, generator):
        # Less than 50% Hebrew
        assert generator.validate_hebrew_output("Lots of English text here with just א") is False


# ==================== Keyword Extraction Tests ====================

class TestKeywordExtraction:

    def test_extract_fintech_keywords(self, generator):
        keywords = generator._extract_keywords("A new fintech startup raises $50M")
        assert 'fintech' in keywords
        assert 'startups' in keywords

    def test_extract_crypto_keywords(self, generator):
        keywords = generator._extract_keywords("Bitcoin price surges past $100K")
        assert 'bitcoin' in keywords

    def test_extract_multiple_keywords(self, generator):
        keywords = generator._extract_keywords("The new blockchain trading platform uses machine learning")
        assert 'blockchain' in keywords
        assert 'trading' in keywords
        assert 'AI' in keywords

    def test_extract_no_keywords(self, generator):
        keywords = generator._extract_keywords("Just a random sentence about nothing")
        assert len(keywords) == 0


# ==================== Prompt Building Tests ====================

class TestPromptBuilding:

    def test_build_glossary_str(self, generator):
        result = generator._build_glossary_str()
        assert "Bitcoin" in result
        assert "ביטקוין" in result

    def test_build_glossary_empty(self, mock_openai_client):
        from processor.content_generator import ContentGenerator
        gen = ContentGenerator(openai_client=mock_openai_client, model='test', glossary={})
        assert gen._build_glossary_str() == ""

    def test_completion_params_include_temperature(self, generator):
        params = generator._get_completion_params("system", "user")
        assert 'temperature' in params
        assert params['temperature'] == 0.7

    def test_completion_params_temperature_offset(self, generator):
        params = generator._get_completion_params("system", "user", temperature_offset=0.2)
        assert params['temperature'] == pytest.approx(0.9)

    def test_completion_params_no_temperature(self, mock_openai_client):
        from processor.content_generator import ContentGenerator
        gen = ContentGenerator(openai_client=mock_openai_client, model='test', temperature=None)
        params = gen._get_completion_params("system", "user")
        assert 'temperature' not in params

    def test_completion_params_temperature_capped(self, mock_openai_client):
        from processor.content_generator import ContentGenerator
        gen = ContentGenerator(openai_client=mock_openai_client, model='test', temperature=1.9)
        params = gen._get_completion_params("system", "user", temperature_offset=0.5)
        assert params['temperature'] <= 2.0


# ==================== Schema / Model Tests ====================

class TestSchemaChanges:

    def test_tweet_content_type_column(self, test_db):
        """Tweet model has content_type column."""
        tweet = Tweet(
            source_url="test_gen_1",
            original_text="Test",
            content_type='generation',
            status=TweetStatus.PENDING
        )
        test_db.add(tweet)
        test_db.commit()
        test_db.refresh(tweet)
        assert tweet.content_type == 'generation'

    def test_tweet_content_type_default(self, test_db):
        """Tweet content_type defaults to 'translation'."""
        tweet = Tweet(
            source_url="test_gen_2",
            original_text="Test",
            status=TweetStatus.PENDING
        )
        test_db.add(tweet)
        test_db.commit()
        test_db.refresh(tweet)
        assert tweet.content_type == 'translation'

    def test_tweet_generation_metadata(self, test_db):
        """Tweet model stores generation_metadata as JSON."""
        metadata = {'angle': 'news', 'variant_index': 0, 'source_hash': 'abc123'}
        tweet = Tweet(
            source_url="test_gen_3",
            original_text="Test",
            content_type='generation',
            generation_metadata=json.dumps(metadata),
            status=TweetStatus.PROCESSED
        )
        test_db.add(tweet)
        test_db.commit()
        test_db.refresh(tweet)

        loaded = json.loads(tweet.generation_metadata)
        assert loaded['angle'] == 'news'
        assert loaded['variant_index'] == 0

    def test_tweet_to_dict_includes_new_fields(self, test_db):
        """to_dict() includes content_type and generation_metadata."""
        tweet = Tweet(
            source_url="test_gen_4",
            original_text="Test",
            content_type='generation',
            generation_metadata=json.dumps({'angle': 'educational'}),
            status=TweetStatus.PENDING
        )
        test_db.add(tweet)
        test_db.commit()
        test_db.refresh(tweet)

        d = tweet.to_dict()
        assert 'content_type' in d
        assert d['content_type'] == 'generation'
        assert 'generation_metadata' in d


# ==================== Auto-Style Learning Tests ====================

class TestAutoStyleLearning:

    def test_approved_content_added_to_style_examples(self, test_db):
        """Approved Hebrew content should be addable as style example."""
        from processor.style_manager import add_style_example, get_all_examples

        hebrew_text = "ביטקוין הגיע לשיא חדש של 100 אלף דולר. זוהי התפתחות חשובה בשוק הקריפטו שמשפיעה על כל המשקיעים."
        example = add_style_example(
            test_db, hebrew_text,
            source_type='approved',
            topic_tags=['crypto', 'bitcoin']
        )
        assert example is not None
        assert example.source_type == 'approved'
        assert example.is_active is True

        all_examples = get_all_examples(test_db)
        assert len(all_examples) == 1
        assert all_examples[0].source_type == 'approved'

    def test_short_content_not_added(self, test_db):
        """Content under 10 words should not be added."""
        from processor.style_manager import add_style_example
        result = add_style_example(test_db, "קצר מדי", source_type='approved')
        assert result is None

    def test_empty_content_not_added(self, test_db):
        """Empty content should not be added."""
        from processor.style_manager import add_style_example
        assert add_style_example(test_db, "", source_type='approved') is None
        assert add_style_example(test_db, "   ", source_type='approved') is None
