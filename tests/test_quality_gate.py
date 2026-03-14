"""
Tests for the GPT-based quality gate module.

Tests cover:
1. evaluate_quality — scoring, thresholds, error handling
2. gate_content — batch evaluation, key preservation
3. Prompt construction

Run with: pytest tests/test_quality_gate.py -v
"""

import json
import pytest
from unittest.mock import MagicMock, patch, PropertyMock

from processor.quality_gate import (
    evaluate_quality,
    gate_content,
    _build_evaluation_prompt,
    _parse_scores,
)


# ==================== Helpers ====================

def _mock_gpt_response(scores: dict) -> MagicMock:
    """Create a mock OpenAI response returning the given scores as JSON."""
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = json.dumps(scores)
    mock_client.chat.completions.create.return_value = mock_response
    return mock_client


HIGH_SCORE = {
    "authenticity": 28,
    "voice_match": 22,
    "engagement_potential": 20,
    "technical_accuracy": 18,
    "suggestions": ["Minor: could add a specific number"],
    "verdict": "Strong, authentic Hebrew content with good engagement hooks.",
}

LOW_SCORE = {
    "authenticity": 10,
    "voice_match": 5,
    "engagement_potential": 8,
    "technical_accuracy": 7,
    "suggestions": ["Sounds robotic", "Add specific data points", "Match voice patterns"],
    "verdict": "Content feels generic and lacks the author's voice.",
}


# ==================== evaluate_quality ====================

@patch('processor.quality_gate.get_rate_limiter')
@patch('processor.quality_gate.get_openai_client')
def test_evaluate_quality_high_score_passes(mock_get_client, mock_get_rl):
    mock_get_client.return_value = _mock_gpt_response(HIGH_SCORE)
    mock_get_rl.return_value = MagicMock()

    result = evaluate_quality("ביטקוין הגיע לשיא חדש של 100 אלף דולר.", pass_threshold=60)
    assert result['passed'] is True
    assert result['total_score'] == 88


@patch('processor.quality_gate.get_rate_limiter')
@patch('processor.quality_gate.get_openai_client')
def test_evaluate_quality_low_score_fails(mock_get_client, mock_get_rl):
    mock_get_client.return_value = _mock_gpt_response(LOW_SCORE)
    mock_get_rl.return_value = MagicMock()

    result = evaluate_quality("Generic content here.", pass_threshold=60)
    assert result['passed'] is False
    assert result['total_score'] == 30


@patch('processor.quality_gate.get_rate_limiter')
@patch('processor.quality_gate.get_openai_client')
def test_evaluate_quality_returns_all_dimensions(mock_get_client, mock_get_rl):
    mock_get_client.return_value = _mock_gpt_response(HIGH_SCORE)
    mock_get_rl.return_value = MagicMock()

    result = evaluate_quality("ביטקוין הגיע לשיא חדש.")
    scores = result['scores']
    assert 'authenticity' in scores
    assert 'voice_match' in scores
    assert 'engagement_potential' in scores
    assert 'technical_accuracy' in scores


@patch('processor.quality_gate.get_rate_limiter')
@patch('processor.quality_gate.get_openai_client')
def test_evaluate_quality_suggestions_present(mock_get_client, mock_get_rl):
    mock_get_client.return_value = _mock_gpt_response(LOW_SCORE)
    mock_get_rl.return_value = MagicMock()

    result = evaluate_quality("Generic content.")
    assert isinstance(result['suggestions'], list)
    assert len(result['suggestions']) > 0
    assert isinstance(result['verdict'], str)
    assert len(result['verdict']) > 0


@patch('processor.quality_gate.get_rate_limiter')
@patch('processor.quality_gate.get_openai_client')
def test_evaluate_quality_custom_threshold(mock_get_client, mock_get_rl):
    mock_get_client.return_value = _mock_gpt_response(LOW_SCORE)
    mock_get_rl.return_value = MagicMock()

    # Total score is 30, which passes threshold=20 but fails threshold=60
    result_low = evaluate_quality("Content.", pass_threshold=20)
    assert result_low['passed'] is True

    result_high = evaluate_quality("Content.", pass_threshold=60)
    assert result_high['passed'] is False


@patch('processor.quality_gate.get_rate_limiter')
@patch('processor.quality_gate.get_openai_client')
def test_evaluate_quality_with_source_text(mock_get_client, mock_get_rl):
    mock_get_client.return_value = _mock_gpt_response(HIGH_SCORE)
    mock_get_rl.return_value = MagicMock()

    result = evaluate_quality(
        "ביטקוין הגיע לשיא חדש.",
        source_text="Bitcoin reaches new all-time high of $100K",
    )
    assert result['passed'] is True
    # Verify the client was called (prompt included source text)
    call_args = mock_get_client.return_value.chat.completions.create.call_args
    assert call_args is not None


@patch('processor.quality_gate.get_rate_limiter')
@patch('processor.quality_gate.get_openai_client')
def test_evaluate_quality_without_source_text(mock_get_client, mock_get_rl):
    mock_get_client.return_value = _mock_gpt_response(HIGH_SCORE)
    mock_get_rl.return_value = MagicMock()

    result = evaluate_quality("ביטקוין הגיע לשיא חדש.")
    assert result['passed'] is True
    assert result['total_score'] == 88


@patch('processor.quality_gate.get_openai_client')
def test_evaluate_quality_api_error_passes(mock_get_client):
    mock_get_client.side_effect = Exception("API connection failed")

    result = evaluate_quality("Some content")
    assert result['passed'] is True
    assert result['total_score'] == 0
    assert 'error' in result['verdict'].lower() or 'auto-passing' in result['verdict'].lower()


@patch('processor.quality_gate.get_rate_limiter')
@patch('processor.quality_gate.get_openai_client')
def test_evaluate_quality_invalid_json_response(mock_get_client, mock_get_rl):
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = "This is not JSON at all"
    mock_client.chat.completions.create.return_value = mock_response
    mock_get_client.return_value = mock_client
    mock_get_rl.return_value = MagicMock()

    result = evaluate_quality("Some content")
    assert result['passed'] is True
    assert result['total_score'] == 0
    assert 'parse error' in result['verdict'].lower() or 'auto-passing' in result['verdict'].lower()


# ==================== gate_content ====================

@patch('processor.quality_gate.evaluate_quality')
def test_gate_content_adds_evaluation_key(mock_eval):
    mock_eval.return_value = {
        'passed': True, 'total_score': 80,
        'scores': {'authenticity': 25, 'voice_match': 20, 'engagement_potential': 20, 'technical_accuracy': 15},
        'suggestions': [], 'verdict': 'Good',
    }

    variants = [{'hebrew_draft': 'ביטקוין הגיע לשיא.', 'angle': 'news'}]
    result = gate_content(variants)
    assert 'quality_evaluation' in result[0]
    assert result[0]['quality_evaluation']['passed'] is True


@patch('processor.quality_gate.evaluate_quality')
def test_gate_content_marks_pass_fail(mock_eval):
    mock_eval.side_effect = [
        {
            'passed': True, 'total_score': 80,
            'scores': {}, 'suggestions': [], 'verdict': 'Good',
        },
        {
            'passed': False, 'total_score': 30,
            'scores': {}, 'suggestions': ['Needs work'], 'verdict': 'Weak',
        },
    ]

    variants = [
        {'hebrew_draft': 'Good content', 'angle': 'news'},
        {'hebrew_draft': 'Bad content', 'angle': 'opinion'},
    ]
    result = gate_content(variants)
    assert result[0]['quality_evaluation']['passed'] is True
    assert result[1]['quality_evaluation']['passed'] is False


def test_gate_content_empty_list():
    result = gate_content([])
    assert result == []


# ==================== Prompt construction ====================

def test_evaluation_prompt_includes_rubric():
    prompt = _build_evaluation_prompt(
        text="ביטקוין הגיע לשיא חדש.",
        source_text="Bitcoin hits ATH",
    )
    assert 'authenticity' in prompt
    assert 'voice_match' in prompt
    assert 'engagement_potential' in prompt
    assert 'technical_accuracy' in prompt
    assert '0-30' in prompt
    assert '0-25' in prompt
    assert '0-20' in prompt
    assert 'Bitcoin hits ATH' in prompt


# ==================== Threshold edge case ====================

@patch('processor.quality_gate.get_rate_limiter')
@patch('processor.quality_gate.get_openai_client')
def test_evaluate_quality_zero_threshold(mock_get_client, mock_get_rl):
    mock_get_client.return_value = _mock_gpt_response(LOW_SCORE)
    mock_get_rl.return_value = MagicMock()

    result = evaluate_quality("Content.", pass_threshold=0)
    assert result['passed'] is True
    assert result['total_score'] == 30


# ==================== Key preservation ====================

@patch('processor.quality_gate.evaluate_quality')
def test_gate_content_preserves_existing_keys(mock_eval):
    mock_eval.return_value = {
        'passed': True, 'total_score': 75,
        'scores': {}, 'suggestions': [], 'verdict': 'OK',
    }

    variants = [
        {
            'hebrew_draft': 'ביטקוין הגיע לשיא.',
            'angle': 'news',
            'variant_index': 0,
            'custom_key': 'should_survive',
        }
    ]
    result = gate_content(variants)
    assert result[0]['angle'] == 'news'
    assert result[0]['variant_index'] == 0
    assert result[0]['custom_key'] == 'should_survive'
    assert 'quality_evaluation' in result[0]
