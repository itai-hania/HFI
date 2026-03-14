"""
Tests for the self-tweet scraper (tools/scrape_self_tweets.py).

Covers:
- Filter functions (retweets, replies, min words, Hebrew)
- Storage functions (creates records, dedup, source_type)
- Dry-run behaviour
- Engagement metrics parsing

Run with: pytest tests/test_self_scraper.py -v
"""

import json
import hashlib
import pytest
from unittest.mock import MagicMock, AsyncMock, patch, PropertyMock
from types import SimpleNamespace

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))
sys.path.insert(0, str(PROJECT_ROOT / "tools"))

from scrape_self_tweets import (
    is_retweet,
    is_reply,
    passes_min_words,
    passes_language_filter,
    content_hash,
    filter_tweets,
    parse_engagement_from_js,
    store_tweets,
    save_engagement_json,
    get_existing_hashes,
    build_parser,
    ENGAGEMENT_JS,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_tweet(
    text="",
    author_handle="@FinancialEduX",
    tweet_id="123",
    permalink="https://x.com/FinancialEduX/status/123",
    timestamp="2026-03-01T12:00:00.000Z",
):
    return {
        "tweet_id": tweet_id,
        "author_handle": author_handle,
        "author_name": "FinEdu",
        "text": text,
        "permalink": permalink,
        "timestamp": timestamp,
        "media": [],
    }


HEBREW_LONG = "זהו טקסט ארוך מספיק בעברית שמכיל יותר מחמש עשרה מילים כדי לעבור את הסינון של המערכת"
ENGLISH_LONG = "This is a sufficiently long English text that contains more than fifteen words to pass the filter"


# ---------------------------------------------------------------------------
# Filter tests
# ---------------------------------------------------------------------------

class TestIsRetweet:
    def test_same_handle_not_retweet(self):
        tweet = _make_tweet(author_handle="@FinancialEduX")
        assert is_retweet(tweet, "FinancialEduX") is False

    def test_different_handle_is_retweet(self):
        tweet = _make_tweet(author_handle="@SomeoneElse")
        assert is_retweet(tweet, "FinancialEduX") is True

    def test_case_insensitive(self):
        tweet = _make_tweet(author_handle="@financialedux")
        assert is_retweet(tweet, "FinancialEduX") is False

    def test_missing_handle_is_retweet(self):
        tweet = _make_tweet(author_handle="")
        assert is_retweet(tweet, "FinancialEduX") is True


class TestIsReply:
    def test_normal_tweet_not_reply(self):
        tweet = _make_tweet(text="Hello world, this is a normal tweet")
        assert is_reply(tweet) is False

    def test_reply_tweet(self):
        tweet = _make_tweet(text="@someone thanks for sharing!")
        assert is_reply(tweet) is True

    def test_empty_text(self):
        tweet = _make_tweet(text="")
        assert is_reply(tweet) is False

    def test_mention_in_middle_not_reply(self):
        tweet = _make_tweet(text="Check out what @someone said about markets")
        assert is_reply(tweet) is False


class TestPassesMinWords:
    def test_above_threshold(self):
        tweet = _make_tweet(text=HEBREW_LONG)
        assert passes_min_words(tweet, 15) is True

    def test_below_threshold(self):
        tweet = _make_tweet(text="מילה אחת שתיים")
        assert passes_min_words(tweet, 15) is False

    def test_exact_threshold(self):
        words = " ".join(["מילה"] * 15)
        tweet = _make_tweet(text=words)
        assert passes_min_words(tweet, 15) is True


class TestPassesLanguageFilter:
    def test_hebrew_passes_default(self):
        tweet = _make_tweet(text=HEBREW_LONG)
        assert passes_language_filter(tweet, include_english=False) is True

    def test_english_blocked_by_default(self):
        tweet = _make_tweet(text=ENGLISH_LONG)
        assert passes_language_filter(tweet, include_english=False) is False

    def test_english_passes_when_included(self):
        tweet = _make_tweet(text=ENGLISH_LONG)
        assert passes_language_filter(tweet, include_english=True) is True


class TestFilterTweets:
    def test_full_pipeline(self):
        tweets = [
            _make_tweet(text=HEBREW_LONG, author_handle="@FinancialEduX"),
            _make_tweet(text=HEBREW_LONG, author_handle="@Other", tweet_id="2"),
            _make_tweet(text="@reply " + HEBREW_LONG, tweet_id="3"),
            _make_tweet(text="קצר", tweet_id="4"),
            _make_tweet(text=ENGLISH_LONG, tweet_id="5"),
        ]
        result = filter_tweets(tweets, "FinancialEduX", min_words=5, include_english=False)
        assert len(result) == 1
        assert result[0]["tweet_id"] == "123"

    def test_include_english_flag(self):
        tweets = [
            _make_tweet(text=ENGLISH_LONG, author_handle="@FinancialEduX"),
        ]
        result = filter_tweets(tweets, "FinancialEduX", min_words=5, include_english=True)
        assert len(result) == 1


# ---------------------------------------------------------------------------
# Engagement tests
# ---------------------------------------------------------------------------

class TestParseEngagement:
    def test_normal_parsing(self):
        raw = {
            "111": {"replies": 5, "retweets": 10, "likes": 42, "views": 1200},
            "222": {"replies": 0, "retweets": 0, "likes": 0, "views": 0},
        }
        result = parse_engagement_from_js(raw)
        assert result["111"]["likes"] == 42
        assert result["222"]["views"] == 0

    def test_empty_input(self):
        assert parse_engagement_from_js({}) == {}
        assert parse_engagement_from_js(None) == {}

    def test_missing_fields_default_zero(self):
        raw = {"999": {"likes": 7}}
        result = parse_engagement_from_js(raw)
        assert result["999"]["likes"] == 7
        assert result["999"]["replies"] == 0
        assert result["999"]["retweets"] == 0
        assert result["999"]["views"] == 0


# ---------------------------------------------------------------------------
# Content hash & dedup
# ---------------------------------------------------------------------------

class TestContentHash:
    def test_deterministic(self):
        assert content_hash("hello world") == content_hash("hello world")

    def test_normalises_whitespace(self):
        assert content_hash("hello   world") == content_hash("hello world")

    def test_case_insensitive(self):
        assert content_hash("Hello") == content_hash("hello")


# ---------------------------------------------------------------------------
# Storage tests
# ---------------------------------------------------------------------------

class TestStoreTweets:
    def test_saves_new_tweets(self):
        db = MagicMock()
        tweet = _make_tweet(text=HEBREW_LONG)
        existing = set()

        with patch("scrape_self_tweets.add_style_example") as mock_add:
            mock_example = MagicMock()
            mock_example.id = 1
            mock_add.return_value = mock_example

            saved, skipped = store_tweets([tweet], {}, existing, db)

        assert saved == 1
        assert skipped == 0
        mock_add.assert_called_once()
        call_kwargs = mock_add.call_args
        assert call_kwargs.kwargs["source_type"] == "self_scraped"

    def test_skips_duplicates(self):
        db = MagicMock()
        tweet = _make_tweet(text=HEBREW_LONG)
        existing = {content_hash(HEBREW_LONG)}

        with patch("scrape_self_tweets.add_style_example") as mock_add:
            saved, skipped = store_tweets([tweet], {}, existing, db)

        assert saved == 0
        assert skipped == 1
        mock_add.assert_not_called()

    def test_source_type_self_scraped(self):
        db = MagicMock()
        tweet = _make_tweet(text=HEBREW_LONG)
        existing = set()

        with patch("scrape_self_tweets.add_style_example") as mock_add:
            mock_add.return_value = MagicMock(id=1)
            store_tweets([tweet], {}, existing, db)

        assert mock_add.call_args.kwargs["source_type"] == "self_scraped"


class TestGetExistingHashes:
    def test_returns_hashes(self):
        db = MagicMock()
        row1 = MagicMock()
        row1.content = "text one"
        row2 = MagicMock()
        row2.content = "text two"
        db.query.return_value.filter.return_value.all.return_value = [row1, row2]

        hashes = get_existing_hashes(db)
        assert len(hashes) == 2
        assert content_hash("text one") in hashes


# ---------------------------------------------------------------------------
# Engagement JSON output
# ---------------------------------------------------------------------------

class TestSaveEngagementJson:
    def test_writes_file(self, tmp_path):
        tweet = _make_tweet(text=HEBREW_LONG)
        engagement = {"123": {"replies": 1, "retweets": 2, "likes": 3, "views": 100}}
        out = tmp_path / "engagement.json"

        save_engagement_json([tweet], engagement, out)

        assert out.exists()
        data = json.loads(out.read_text(encoding="utf-8"))
        assert len(data) == 1
        assert data[0]["engagement"]["likes"] == 3

    def test_missing_engagement_defaults(self, tmp_path):
        tweet = _make_tweet(text=HEBREW_LONG, tweet_id="999")
        out = tmp_path / "eng.json"

        save_engagement_json([tweet], {}, out)

        data = json.loads(out.read_text(encoding="utf-8"))
        assert data[0]["engagement"] == {"replies": 0, "retweets": 0, "likes": 0, "views": 0}


# ---------------------------------------------------------------------------
# CLI / dry-run
# ---------------------------------------------------------------------------

class TestCLI:
    def test_default_args(self):
        parser = build_parser()
        args = parser.parse_args([])
        assert args.dry_run is False
        assert args.min_words == 15
        assert args.include_english is False
        assert args.limit == 50

    def test_custom_args(self):
        parser = build_parser()
        args = parser.parse_args([
            "--username", "TestUser",
            "--limit", "200",
            "--min-words", "10",
            "--include-english",
            "--dry-run",
        ])
        assert args.username == "TestUser"
        assert args.limit == 200
        assert args.min_words == 10
        assert args.include_english is True
        assert args.dry_run is True


class TestEngagementJS:
    def test_js_snippet_is_string(self):
        assert isinstance(ENGAGEMENT_JS, str)
        assert "data-testid" in ENGAGEMENT_JS
        assert "parseCount" in ENGAGEMENT_JS
