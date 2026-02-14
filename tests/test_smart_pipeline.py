"""
Tests for Smart Pipeline upgrades: trend selection, translation, style matching.

Covers:
1.1 Description keywords in news_scraper
1.2 Topic diversity in auto_pipeline
1.3 Recency weighting in news_scraper
2.1 Context-aware glossary in prompt_builder
2.2 Source text preprocessing in content_generator
2.3 Source-type detection in content_generator
2.4 Graduated quality scoring in prompt_builder
3.1 Recency-weighted example selection in prompt_builder
3.2 Engagement-based scoring (model, style_manager, prompt_builder)
3.3 Smart truncation in prompt_builder

Run with: pytest tests/test_smart_pipeline.py -v
"""

import pytest
import json
from unittest.mock import MagicMock, patch
from datetime import datetime, timezone, timedelta

from common.models import (
    Base, engine, get_db_session, StyleExample,
    Tweet, Trend, TweetStatus, TrendSource,
)


# ==================== Fixtures ====================

@pytest.fixture
def test_db():
    """Create test database with fresh schema."""
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    session = get_db_session()
    yield session
    session.close()
    Base.metadata.drop_all(engine)


# ==================== Step 1.1: Description Keywords ====================

class TestDescriptionKeywords:

    def test_extract_article_keywords_combines_title_and_desc(self):
        from scraper.news_scraper import NewsScraper
        article = {
            'title': 'Bitcoin Surges Past $100K',
            'description': 'Institutional investors drive cryptocurrency rally to new heights.',
        }
        kws = NewsScraper._extract_article_keywords(article)
        # Title keywords appear twice (2x weight)
        assert kws.count('bitcoin') == 2
        assert kws.count('surges') == 2
        # Description keywords appear once
        assert 'institutional' in kws
        assert 'cryptocurrency' in kws

    def test_extract_article_keywords_empty_desc(self):
        from scraper.news_scraper import NewsScraper
        article = {'title': 'Bitcoin Surges', 'description': ''}
        kws = NewsScraper._extract_article_keywords(article)
        assert kws.count('bitcoin') == 2

    def test_extract_article_keywords_no_title(self):
        from scraper.news_scraper import NewsScraper
        article = {'description': 'Major market rally today'}
        kws = NewsScraper._extract_article_keywords(article)
        assert 'major' in kws
        assert 'market' in kws

    def test_ranking_uses_description_keywords(self):
        from scraper.news_scraper import NewsScraper
        scraper = NewsScraper()
        articles = [
            {
                'title': 'Stock Update',
                'description': 'NASDAQ hits all-time high as tech stocks rally on earnings.',
                'source': 'WSJ',
                'category': 'Finance',
                'discovered_at': datetime.utcnow(),
            },
            {
                'title': 'Stock Update',
                'description': 'Minor changes in markets.',
                'source': 'Bloomberg',
                'category': 'Finance',
                'discovered_at': datetime.utcnow(),
            },
        ]
        ranked = scraper._rank_articles(articles)
        # Article with richer description should score higher
        assert ranked[0]['description'].startswith('NASDAQ')


# ==================== Step 1.2: Topic Diversity ====================

class TestTopicDiversity:

    def test_diversify_removes_duplicates(self):
        from processor.auto_pipeline import AutoPipeline
        # Use very similar titles that share most keywords (high Jaccard)
        candidates = [
            {'title': 'Bitcoin surges past new record high', 'score': 90},
            {'title': 'Bitcoin surges past record high milestone', 'score': 85},
            {'title': 'Bitcoin surges record high again', 'score': 80},
            {'title': 'Stripe Launches New Fintech API', 'score': 70},
            {'title': 'Fed Raises Interest Rates', 'score': 60},
        ]
        result = AutoPipeline._diversify_candidates(candidates, top_n=3)
        titles = [c['title'] for c in result]
        # Should get at most 1 Bitcoin article due to high overlap
        bitcoin_count = sum(1 for t in titles if 'bitcoin' in t.lower())
        assert bitcoin_count <= 1
        assert len(result) == 3

    def test_diversify_all_unique_passes_through(self):
        from processor.auto_pipeline import AutoPipeline
        candidates = [
            {'title': 'Bitcoin price surges', 'score': 90},
            {'title': 'Stripe launches API', 'score': 70},
            {'title': 'Fed raises rates', 'score': 60},
        ]
        result = AutoPipeline._diversify_candidates(candidates, top_n=3)
        assert len(result) == 3

    def test_diversify_fewer_than_topn(self):
        from processor.auto_pipeline import AutoPipeline
        candidates = [{'title': 'Test', 'score': 50}]
        result = AutoPipeline._diversify_candidates(candidates, top_n=3)
        assert len(result) == 1

    def test_title_keywords_extraction(self):
        from processor.auto_pipeline import AutoPipeline
        kws = AutoPipeline._title_keywords('Bitcoin Surges Past $100K')
        assert 'bitcoin' in kws
        assert 'surges' in kws
        assert '100k' in kws


# ==================== Step 1.3: Recency Weighting ====================

class TestRecencyWeighting:

    def test_recent_article_gets_bonus(self):
        from scraper.news_scraper import NewsScraper
        scraper = NewsScraper()
        articles = [
            {
                'title': 'Old News Story',
                'description': 'Description here.',
                'source': 'WSJ',
                'category': 'Finance',
                'discovered_at': datetime.utcnow() - timedelta(days=5),
            },
            {
                'title': 'Fresh Breaking News',
                'description': 'Description here.',
                'source': 'Bloomberg',
                'category': 'Finance',
                'discovered_at': datetime.utcnow(),
            },
        ]
        ranked = scraper._rank_articles(articles)
        # The fresh article should get +20 bonus vs -5 penalty for old
        fresh = next(a for a in ranked if 'Fresh' in a['title'])
        old = next(a for a in ranked if 'Old' in a['title'])
        assert fresh['score'] > old['score']

    def test_six_hour_old_gets_20_bonus(self):
        from scraper.news_scraper import NewsScraper
        scraper = NewsScraper()
        articles = [{
            'title': 'Test Article',
            'description': '',
            'source': 'WSJ',
            'category': 'Finance',
            'discovered_at': datetime.utcnow() - timedelta(hours=3),
        }]
        ranked = scraper._rank_articles(articles)
        # Base score for 'test' + 'article' = 2 (1 each) + wall street=0 + recency=20
        assert ranked[0]['score'] >= 20


# ==================== Step 2.1: Context-Aware Glossary ====================

class TestContextAwareGlossary:

    def test_relevant_terms_returned(self):
        from processor.prompt_builder import build_relevant_glossary_section
        glossary = {
            'Bitcoin': 'ביטקוין',
            'ETF': 'קרן סל',
            'Docker': 'דוקר',
            'VPN': 'רשת פרטית',
        }
        result = build_relevant_glossary_section(glossary, 'Bitcoin ETF approval')
        assert 'Bitcoin' in result
        assert 'ETF' in result
        # Docker and VPN are irrelevant
        assert 'Docker' not in result
        assert 'VPN' not in result

    def test_fallback_to_defaults_when_no_match(self):
        from processor.prompt_builder import build_relevant_glossary_section
        glossary = {
            'Bitcoin': 'ביטקוין',
            'fintech': 'פינטק',
            'obscure_term': 'מונח_מעורפל',
        }
        result = build_relevant_glossary_section(glossary, 'unrelated text about cooking')
        # Should fall back to common defaults
        assert result  # Non-empty

    def test_empty_glossary(self):
        from processor.prompt_builder import build_relevant_glossary_section
        result = build_relevant_glossary_section({}, 'Bitcoin')
        assert result == ""

    def test_empty_source_text(self):
        from processor.prompt_builder import build_relevant_glossary_section, build_glossary_section
        glossary = {'Bitcoin': 'ביטקוין'}
        result = build_relevant_glossary_section(glossary, '')
        expected = build_glossary_section(glossary)
        assert result == expected

    def test_max_terms_respected(self):
        from processor.prompt_builder import build_relevant_glossary_section
        glossary = {f'term{i}': f'val{i}' for i in range(50)}
        # All terms match because 'term' is in the text
        result = build_relevant_glossary_section(glossary, 'term0 term1 term2 term3 term4', max_terms=5)
        lines = [l for l in result.split('\n') if l.strip()]
        assert len(lines) <= 5

    def test_partial_match_scoring(self):
        from processor.prompt_builder import build_relevant_glossary_section
        glossary = {
            'blockchain': 'בלוקצ\'יין',
            'block': 'בלוק',
        }
        result = build_relevant_glossary_section(glossary, 'blockchain technology is changing')
        assert 'blockchain' in result


# ==================== Step 2.2: Source Preprocessing ====================

class TestSourcePreprocessing:

    def test_short_text_unchanged(self):
        from processor.content_generator import ContentGenerator
        text = "Short text about Bitcoin."
        assert ContentGenerator._preprocess_source(text) == text

    def test_long_text_truncated(self):
        from processor.content_generator import ContentGenerator
        # Create text with many sentences
        sentences = [f"Sentence number {i}." for i in range(100)]
        text = ' '.join(sentences)
        result = ContentGenerator._preprocess_source(text, max_chars=500)
        assert '[OPENING]' in result
        assert '[CLOSING]' in result
        assert len(result) < len(text)

    def test_exactly_at_limit(self):
        from processor.content_generator import ContentGenerator
        text = "A" * 2000
        result = ContentGenerator._preprocess_source(text, max_chars=2000)
        assert result == text

    def test_empty_text(self):
        from processor.content_generator import ContentGenerator
        assert ContentGenerator._preprocess_source("") == ""
        assert ContentGenerator._preprocess_source(None) is None

    def test_few_sentences_kept(self):
        from processor.content_generator import ContentGenerator
        text = "Sentence one. Sentence two. Sentence three. Sentence four."
        result = ContentGenerator._preprocess_source(text, max_chars=10)
        # Only 4 sentences, <= 5, so should truncate to max_chars
        assert len(result) <= len(text)


# ==================== Step 2.3: Source-Type Detection ====================

class TestSourceTypeDetection:

    def test_tweet_detection(self):
        from processor.content_generator import _detect_source_type
        assert _detect_source_type("Bitcoin hits $100K! 🚀") == 'tweet'

    def test_article_detection(self):
        from processor.content_generator import _detect_source_type
        long_text = ' '.join(['word'] * 200)
        assert _detect_source_type(long_text) == 'article'

    def test_earnings_detection(self):
        from processor.content_generator import _detect_source_type
        text = ("Apple reported Q3 revenue of $83 billion, beating analysts' EPS estimates. "
                "Quarterly earnings per share came in above guidance. "
                "The company raised its full-year profit outlook. " * 5)
        assert _detect_source_type(text) == 'earnings'

    def test_funding_detection(self):
        from processor.content_generator import _detect_source_type
        text = ("Stripe has raised $6.5 billion in a Series I funding round, "
                "led by Sequoia Capital. The investment values the company at "
                "$50 billion, making it the most valuable fintech startup. " * 3)
        assert _detect_source_type(text) == 'funding'

    def test_empty_text(self):
        from processor.content_generator import _detect_source_type
        assert _detect_source_type("") == 'article'

    def test_source_type_instructions_dict(self):
        from processor.content_generator import SOURCE_TYPE_INSTRUCTIONS
        assert 'tweet' in SOURCE_TYPE_INSTRUCTIONS
        assert 'article' in SOURCE_TYPE_INSTRUCTIONS
        assert 'earnings' in SOURCE_TYPE_INSTRUCTIONS
        assert 'funding' in SOURCE_TYPE_INSTRUCTIONS
        assert 'headline' in SOURCE_TYPE_INSTRUCTIONS


# ==================== Step 2.4: Quality Scoring ====================

class TestQualityScoring:

    def test_high_quality_hebrew(self):
        from processor.prompt_builder import score_hebrew_quality
        # Mostly Hebrew, good length, proper ending
        text = "ביטקוין הגיע לשיא חדש של מאה אלף דולר. המשקיעים המוסדיים ממשיכים להצטרף לשוק הקריפטו."
        score = score_hebrew_quality(text)
        assert score['total'] >= 70
        assert score['hebrew_ratio'] >= 35
        assert score['length'] >= 15

    def test_english_text_scores_low(self):
        from processor.prompt_builder import score_hebrew_quality
        text = "This is entirely in English and should score poorly."
        score = score_hebrew_quality(text)
        assert score['hebrew_ratio'] == 0
        # Hebrew ratio is 0, so total is just length + structure
        assert score['total'] < 50

    def test_empty_text(self):
        from processor.prompt_builder import score_hebrew_quality
        score = score_hebrew_quality("")
        assert score['total'] == 0

    def test_score_breakdown_present(self):
        from processor.prompt_builder import score_hebrew_quality
        score = score_hebrew_quality("טקסט בעברית.")
        assert 'total' in score
        assert 'hebrew_ratio' in score
        assert 'length' in score
        assert 'structure' in score

    def test_markdown_artifacts_penalized(self):
        from processor.prompt_builder import score_hebrew_quality
        clean = "טקסט נקי בעברית ללא סימנים מיוחדים."
        dirty = "**טקסט** עם _סימני_ [markdown] בעברית."
        clean_score = score_hebrew_quality(clean)
        dirty_score = score_hebrew_quality(dirty)
        assert clean_score['structure'] >= dirty_score['structure']

    def test_proper_ending_bonus(self):
        from processor.prompt_builder import score_hebrew_quality
        with_period = "טקסט בעברית."
        without_period = "טקסט בעברית"
        assert score_hebrew_quality(with_period)['structure'] >= score_hebrew_quality(without_period)['structure']

    def test_optimal_length_scores_highest(self):
        from processor.prompt_builder import score_hebrew_quality
        optimal = "א" * 150  # 150 chars
        too_short = "א" * 30
        score_opt = score_hebrew_quality(optimal)
        score_short = score_hebrew_quality(too_short)
        assert score_opt['length'] > score_short['length']


# ==================== Step 3.1: Recency-Weighted Examples ====================

class TestRecencyWeightedExamples:

    def test_recency_bonus_recent(self):
        from processor.prompt_builder import _recency_bonus
        recent = datetime.now(timezone.utc) - timedelta(days=3)
        assert _recency_bonus(recent) == 3

    def test_recency_bonus_30_days(self):
        from processor.prompt_builder import _recency_bonus
        month_old = datetime.now(timezone.utc) - timedelta(days=15)
        assert _recency_bonus(month_old) == 2

    def test_recency_bonus_90_days(self):
        from processor.prompt_builder import _recency_bonus
        old = datetime.now(timezone.utc) - timedelta(days=60)
        assert _recency_bonus(old) == 1

    def test_recency_bonus_ancient(self):
        from processor.prompt_builder import _recency_bonus
        ancient = datetime.now(timezone.utc) - timedelta(days=365)
        assert _recency_bonus(ancient) == 0

    def test_recency_bonus_naive_datetime(self):
        from processor.prompt_builder import _recency_bonus
        naive = datetime.utcnow() - timedelta(days=3)
        assert _recency_bonus(naive) == 3

    def test_recency_bonus_none(self):
        from processor.prompt_builder import _recency_bonus
        assert _recency_bonus(None) == 0


# ==================== Step 3.2: Engagement Tracking ====================

class TestEngagementTracking:

    def test_style_example_has_approval_count(self, test_db):
        ex = StyleExample(
            content="טקסט בעברית כדוגמה לסגנון כתיבה פיננסי",
            source_type='manual',
            word_count=10,
            is_active=True,
            approval_count=5,
            rejection_count=1,
        )
        test_db.add(ex)
        test_db.commit()
        loaded = test_db.query(StyleExample).filter_by(id=ex.id).first()
        assert loaded.approval_count == 5
        assert loaded.rejection_count == 1

    def test_to_dict_includes_counts(self, test_db):
        ex = StyleExample(
            content="טקסט בעברית כדוגמה לסגנון כתיבה פיננסי",
            source_type='manual',
            word_count=10,
            is_active=True,
        )
        test_db.add(ex)
        test_db.commit()
        d = ex.to_dict()
        assert 'approval_count' in d
        assert 'rejection_count' in d

    def test_record_feedback_approval(self, test_db):
        from processor.style_manager import record_feedback
        ex = StyleExample(
            content="דוגמה בעברית לסגנון כתיבה עם תוכן פיננסי",
            source_type='manual',
            word_count=12,
            is_active=True,
        )
        test_db.add(ex)
        test_db.commit()
        result = record_feedback(test_db, ex.id, approved=True)
        assert result is True
        test_db.refresh(ex)
        assert ex.approval_count == 1

    def test_record_feedback_rejection(self, test_db):
        from processor.style_manager import record_feedback
        ex = StyleExample(
            content="דוגמה בעברית לסגנון כתיבה עם תוכן פיננסי",
            source_type='manual',
            word_count=12,
            is_active=True,
        )
        test_db.add(ex)
        test_db.commit()
        record_feedback(test_db, ex.id, approved=False)
        test_db.refresh(ex)
        assert ex.rejection_count == 1

    def test_record_feedback_not_found(self, test_db):
        from processor.style_manager import record_feedback
        result = record_feedback(test_db, 99999, approved=True)
        assert result is False

    def test_find_examples_by_tag_overlap(self, test_db):
        from processor.style_manager import find_examples_by_tag_overlap
        ex1 = StyleExample(
            content="דוגמה ראשונה על ביטקוין וקריפטו לבדיקה",
            source_type='manual',
            word_count=15,
            is_active=True,
            topic_tags=['crypto', 'bitcoin'],
        )
        ex2 = StyleExample(
            content="דוגמה שנייה על בנקאות ופיננסים לבדיקה",
            source_type='manual',
            word_count=15,
            is_active=True,
            topic_tags=['banking', 'fintech'],
        )
        test_db.add_all([ex1, ex2])
        test_db.commit()
        result = find_examples_by_tag_overlap(test_db, ['crypto'], limit=5)
        assert len(result) == 1
        assert result[0].id == ex1.id

    def test_find_examples_empty_tags(self, test_db):
        from processor.style_manager import find_examples_by_tag_overlap
        result = find_examples_by_tag_overlap(test_db, [], limit=5)
        assert result == []


# ==================== Step 3.3: Smart Truncation ====================

class TestSmartTruncation:

    def test_short_text_unchanged(self):
        from processor.prompt_builder import _smart_truncate
        text = "Short text."
        assert _smart_truncate(text) == text

    def test_truncates_at_sentence_boundary(self):
        from processor.prompt_builder import _smart_truncate
        text = "First sentence. Second sentence. " + "A" * 800
        result = _smart_truncate(text, max_chars=50)
        assert result.endswith('.')
        assert len(result) <= 50

    def test_falls_back_to_space(self):
        from processor.prompt_builder import _smart_truncate
        # No sentence boundaries, just spaces
        text = "word " * 200
        result = _smart_truncate(text, max_chars=50)
        assert len(result) <= 53  # 50 + "..."
        assert result.endswith('...')

    def test_preserves_minimum_content(self):
        from processor.prompt_builder import _smart_truncate
        # Sentence boundary very early (less than 50% of max)
        text = "A. " + "B" * 900
        result = _smart_truncate(text, max_chars=800)
        # Should NOT truncate at the early "A." because it's < 50% of 800
        assert len(result) > 400

    def test_exact_limit(self):
        from processor.prompt_builder import _smart_truncate
        text = "A" * 800
        assert _smart_truncate(text, max_chars=800) == text

    def test_exclamation_mark_boundary(self):
        from processor.prompt_builder import _smart_truncate
        text = "Wow! " + "A" * 900
        result = _smart_truncate(text, max_chars=800)
        # Should find "Wow!" but it's only at position 4, which is < 50% of 800
        # So it should fall back
        assert len(result) <= 803  # max_chars + "..."


# ==================== Integration: Pipeline with Diversity ====================

class TestPipelineDiversity:

    def test_pipeline_uses_diversity(self, test_db):
        from processor.auto_pipeline import AutoPipeline
        mock_scraper = MagicMock()
        # Use very similar titles to trigger diversity filter
        mock_scraper.get_latest_news.return_value = [
            {
                'title': 'Bitcoin surges past new record high',
                'description': 'Crypto rally.',
                'source': 'Yahoo Finance',
                'url': 'https://example.com/1',
                'score': 90,
                'category': 'Finance',
                'discovered_at': datetime.utcnow(),
            },
            {
                'title': 'Bitcoin surges past record high again',
                'description': 'Bitcoin milestone.',
                'source': 'WSJ',
                'url': 'https://example.com/2',
                'score': 85,
                'category': 'Finance',
                'discovered_at': datetime.utcnow(),
            },
            {
                'title': 'Stripe Launches Fintech API',
                'description': 'Payment expansion.',
                'source': 'TechCrunch',
                'url': 'https://example.com/3',
                'score': 70,
                'category': 'Tech',
                'discovered_at': datetime.utcnow(),
            },
        ]

        pipeline = AutoPipeline(
            news_scraper=mock_scraper,
            summary_generator=MagicMock(),
            content_generator=MagicMock(),
        )
        # Disable auto_summarize for simplicity
        candidates = pipeline.fetch_and_rank(test_db, top_n=2, auto_summarize=False)
        titles = [c['title'] for c in candidates]
        # Should pick 1 Bitcoin + 1 Stripe (diversity enforcement)
        bitcoin_count = sum(1 for t in titles if 'bitcoin' in t.lower())
        assert bitcoin_count <= 1


# ==================== Integration: Quality Score in generate_post ====================

class TestQualityScoreIntegration:

    def test_generate_post_includes_quality(self):
        from processor.content_generator import ContentGenerator
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "ביטקוין הגיע לשיא חדש של מאה אלף דולר."
        mock_client.chat.completions.create.return_value = mock_response

        gen = ContentGenerator(openai_client=mock_client, glossary={})
        with patch('processor.content_generator.build_style_section', return_value='Style section'):
            variants = gen.generate_post("Bitcoin hits $100K", num_variants=1, angles=['news'])

        assert len(variants) == 1
        assert 'quality_score' in variants[0]
        assert 'quality_breakdown' in variants[0]
        assert variants[0]['quality_score'] > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
