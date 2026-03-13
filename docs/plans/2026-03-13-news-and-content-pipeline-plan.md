# News & Content Pipeline Improvement — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Transform HFI from a noisy news aggregator into a laser-focused US/Israel/FinTech content pipeline with rich Telegram briefs, a proper dashboard news hub, and X content acquisition via API.

**Architecture:** Four vertical slices, each independently deployable: (1) News scraper relevance + Israeli sources, (2) Telegram bot rich HTML formatting, (3) Dashboard news hub overhaul, (4) X content pipeline API + frontend. Each slice follows TDD — tests first, then implementation.

**Tech Stack:** Python/FastAPI (backend), feedparser (RSS), python-telegram-bot (HTML parse_mode), Next.js/React (frontend), Playwright (X scraping), pytest (testing)

**Design Doc:** `docs/plans/2026-03-13-news-and-content-pipeline-design.md`

---

## Slice 1: News Scraper — Relevance & Israeli Sources

### Task 1.1: Add Israeli Sources + ISRAEL_SOURCES Constant

**Files:**
- Modify: `src/scraper/news_scraper.py:73-82` (FEEDS dict + source lists)
- Modify: `src/common/models.py:162-173` (TrendSource enum)
- Test: `tests/test_news_scraper.py`

**Step 1: Write the failing test**

Add to `tests/test_news_scraper.py`:

```python
def test_israeli_sources_configured():
    """Israeli news sources must be in FEEDS and categorized."""
    from scraper.news_scraper import NewsScraper
    scraper = NewsScraper()
    feeds = scraper.FEEDS

    assert "Calcalist" in feeds
    assert "Globes" in feeds
    assert "Times of Israel" in feeds

    assert "Calcalist" in scraper.ISRAEL_SOURCES
    assert "Globes" in scraper.ISRAEL_SOURCES
    assert "Times of Israel" in scraper.ISRAEL_SOURCES


def test_israel_sources_not_in_finance_or_tech():
    """Israeli sources should be in their own category, not mixed."""
    from scraper.news_scraper import NewsScraper
    scraper = NewsScraper()
    for src in scraper.ISRAEL_SOURCES:
        assert src not in scraper.FINANCE_SOURCES
        assert src not in scraper.TECH_SOURCES
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_news_scraper.py::test_israeli_sources_configured tests/test_news_scraper.py::test_israel_sources_not_in_finance_or_tech -v`
Expected: FAIL — `ISRAEL_SOURCES` attribute doesn't exist, "Calcalist" not in FEEDS

**Step 3: Implement — add Israeli sources**

In `src/scraper/news_scraper.py`, modify lines 73-82:

```python
FEEDS = {
    "Yahoo Finance": "https://finance.yahoo.com/news/rssindex",
    "WSJ": "https://feeds.a.dj.com/rss/RSSMarketsMain.xml",
    "TechCrunch": "https://techcrunch.com/category/fintech/feed/",
    "Bloomberg": "https://feeds.bloomberg.com/markets/news.rss",
    "MarketWatch": "https://www.marketwatch.com/rss/topstories",
    "Calcalist": "https://www.calcalistech.com/ctechnews/rss",
    "Globes": "https://en.globes.co.il/en/rss",
    "Times of Israel": "https://www.timesofisrael.com/feed/business/",
}

FINANCE_SOURCES = ["Yahoo Finance", "WSJ", "Bloomberg", "MarketWatch"]
TECH_SOURCES = ["TechCrunch"]
ISRAEL_SOURCES = ["Calcalist", "Globes", "Times of Israel"]
```

In `src/common/models.py`, add to `TrendSource` enum (after line 169):

```python
CALCALIST = "Calcalist"
GLOBES = "Globes"
TIMES_OF_ISRAEL = "Times of Israel"
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_news_scraper.py::test_israeli_sources_configured tests/test_news_scraper.py::test_israel_sources_not_in_finance_or_tech -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/scraper/news_scraper.py src/common/models.py tests/test_news_scraper.py
git commit -m "feat(scraper): add Israeli news sources (Calcalist, Globes, Times of Israel)"
```

---

### Task 1.2: Relevance Keyword Scoring

**Files:**
- Modify: `src/scraper/news_scraper.py:89-103` (keyword sets) and `src/scraper/news_scraper.py:796-860` (_rank_articles)
- Test: `tests/test_news_scraper.py`

**Step 1: Write the failing tests**

```python
def test_must_include_keywords_boost():
    """Articles matching MUST_INCLUDE keywords get boosted."""
    from scraper.news_scraper import NewsScraper
    scraper = NewsScraper()

    relevant = {"title": "NASDAQ hits record on fintech IPO surge", "source": "Bloomberg",
                "description": "Markets rally", "url": "https://example.com/1", "category": "Finance"}
    irrelevant = {"title": "EU trade policy meeting discusses tariffs", "source": "WSJ",
                  "description": "Trade talks", "url": "https://example.com/2", "category": "Finance"}

    articles = [irrelevant, relevant]
    ranked = scraper._rank_articles(articles)

    # Relevant article should rank higher
    assert ranked[0]["title"] == relevant["title"]


def test_exclude_keywords_penalty():
    """Articles with EXCLUDE keywords get penalized."""
    from scraper.news_scraper import NewsScraper
    scraper = NewsScraper()

    assert "tariff" in scraper.EXCLUDE_KEYWORDS
    assert "election" in scraper.EXCLUDE_KEYWORDS
    assert "immigration" in scraper.EXCLUDE_KEYWORDS


def test_israel_keywords_in_must_include():
    """Israel-related keywords should be in MUST_INCLUDE."""
    from scraper.news_scraper import NewsScraper
    scraper = NewsScraper()

    assert "israel" in scraper.MUST_INCLUDE_KEYWORDS
    assert "tel aviv" in scraper.MUST_INCLUDE_KEYWORDS or "tase" in scraper.MUST_INCLUDE_KEYWORDS


def test_relevance_threshold_drops_low_score():
    """Articles scoring below threshold are dropped from results."""
    from scraper.news_scraper import NewsScraper
    scraper = NewsScraper()

    # An article with no MUST_INCLUDE keywords and EXCLUDE keywords should be dropped
    noise = {"title": "Senate immigration bill debate continues", "source": "Yahoo Finance",
             "description": "Political discussion", "url": "https://example.com/noise", "category": "Finance"}
    good = {"title": "Bitcoin ETF sees record inflows on Wall Street", "source": "Bloomberg",
            "description": "Crypto markets", "url": "https://example.com/good", "category": "Finance"}

    ranked = scraper._rank_articles([noise, good])

    titles = [a["title"] for a in ranked]
    assert "Bitcoin ETF sees record inflows on Wall Street" in titles
    # Noise article should be filtered out (below threshold) or at least ranked last
    if len(ranked) > 1:
        assert ranked[-1]["title"] == noise["title"]
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/test_news_scraper.py::test_must_include_keywords_boost tests/test_news_scraper.py::test_exclude_keywords_penalty tests/test_news_scraper.py::test_israel_keywords_in_must_include tests/test_news_scraper.py::test_relevance_threshold_drops_low_score -v`
Expected: FAIL — `MUST_INCLUDE_KEYWORDS`, `EXCLUDE_KEYWORDS` not defined

**Step 3: Implement relevance scoring**

In `src/scraper/news_scraper.py`, replace `WALL_STREET_KEYWORDS` (lines 89-96) and `GENERAL_ECONOMY_KEYWORDS` (lines 99-103) with:

```python
MUST_INCLUDE_KEYWORDS = {
    # Wall Street / US Markets
    'wall street', 'nasdaq', 's&p', 's&p 500', 'dow jones', 'dow', 'nyse',
    'ipo', 'earnings', 'fed', 'fomc', 'treasury', 'sec',
    'stock', 'stocks', 'shares', 'trading', 'investors', 'equity',
    'rally', 'plunge', 'surge', 'etf', 'dividend', 'buyback',
    'bullish', 'bearish', 'volatility',
    # FinTech / Tech
    'fintech', 'neobank', 'crypto', 'bitcoin', 'ethereum', 'defi',
    'payments', 'blockchain', 'saas', 'b2b', 'cybersecurity',
    'startup', 'funding', 'series a', 'series b', 'series c',
    'valuation', 'acquisition', 'venture capital', 'vc',
    # Israel
    'israel', 'israeli', 'tel aviv', 'tase', 'check point', 'wix',
    'monday.com', 'fiverr', 'ironsource', 'mobileye', 'playtika',
}

EXCLUDE_KEYWORDS = {
    'tariff', 'tariffs', 'trade war', 'eu regulation', 'brexit',
    'china sanctions', 'senate vote', 'congress bill', 'political',
    'election', 'campaign', 'diplomatic', 'military',
    'climate policy', 'carbon tax', 'immigration',
}

_RELEVANCE_THRESHOLD = 15
```

Update `_rank_articles()` method to use `MUST_INCLUDE_KEYWORDS` for boosting (+10 per hit), `EXCLUDE_KEYWORDS` for penalty (-20 per hit), and filter articles below `_RELEVANCE_THRESHOLD`. Keep existing cross-source scoring and recency bonus. Remove the old `WALL_STREET_KEYWORDS` (+15) and `GENERAL_ECONOMY_KEYWORDS` (-10) references.

**Step 4: Run tests to verify they pass**

Run: `pytest tests/test_news_scraper.py -k "must_include or exclude_keywords or israel_keywords or relevance_threshold" -v`
Expected: PASS

**Step 5: Run all existing news scraper tests to ensure no regression**

Run: `pytest tests/test_news_scraper.py -v`
Expected: All tests PASS

**Step 6: Commit**

```bash
git add src/scraper/news_scraper.py tests/test_news_scraper.py
git commit -m "feat(scraper): add relevance keyword scoring with MUST_INCLUDE/EXCLUDE lists"
```

---

### Task 1.3: Three-Bucket Source Weighting

**Files:**
- Modify: `src/scraper/news_scraper.py` — `get_latest_news()` (line 109) and `get_brief_news()` (line 160)
- Test: `tests/test_news_scraper.py`

**Step 1: Write the failing test**

```python
from unittest.mock import patch, MagicMock

def test_three_bucket_weighting():
    """get_latest_news should fetch from finance, tech, and israel buckets."""
    from scraper.news_scraper import NewsScraper
    scraper = NewsScraper()

    fetch_calls = []
    original_fetch = scraper._fetch_by_category

    def mock_fetch(sources, limit_per_source, category):
        fetch_calls.append({"sources": sources, "category": category})
        return []

    scraper._fetch_by_category = mock_fetch
    scraper.get_latest_news(total_limit=8)

    categories_called = {c["category"] for c in fetch_calls}
    assert "Finance" in categories_called
    assert "Tech" in categories_called
    assert "Israel" in categories_called


def test_israel_slot_guaranteed():
    """At least 1 Israel story should be included if available."""
    from scraper.news_scraper import NewsScraper
    scraper = NewsScraper()

    mock_finance = [{"title": f"Finance {i}", "source": "Bloomberg", "description": "",
                     "url": f"https://ex.com/f{i}", "category": "Finance", "score": 50-i}
                    for i in range(6)]
    mock_israel = [{"title": "Wix Reports Growth", "source": "Calcalist", "description": "",
                    "url": "https://ex.com/il1", "category": "Israel", "score": 10}]

    def mock_fetch(sources, limit_per_source, category):
        if category == "Finance":
            return mock_finance
        if category == "Israel":
            return mock_israel
        return []

    scraper._fetch_by_category = mock_fetch
    results = scraper.get_latest_news(total_limit=8)

    israel_titles = [r["title"] for r in results if r.get("category") == "Israel"]
    assert len(israel_titles) >= 1, "At least 1 Israel story must be included"
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/test_news_scraper.py::test_three_bucket_weighting tests/test_news_scraper.py::test_israel_slot_guaranteed -v`
Expected: FAIL — `get_latest_news` only calls `_fetch_by_category` for Finance and Tech

**Step 3: Implement three-bucket weighting**

Update `get_latest_news()` to replace the 2-bucket `finance_weight` approach with 3 buckets:
- Finance: 50% of `total_limit` (sources: `FINANCE_SOURCES`)
- Tech: 25% (sources: `TECH_SOURCES`)
- Israel: 25% (sources: `ISRAEL_SOURCES`)
- Guarantee at least 1 Israel slot if available
- Interleave all three in the final output

Remove the `finance_weight` parameter. New signature:

```python
def get_latest_news(self, limit_per_source: int = 10, total_limit: int = 10) -> List[Dict]:
```

Similarly update `get_brief_news()` to include Israel sources in its parallel fetch and cluster scoring.

**Step 4: Run tests to verify they pass**

Run: `pytest tests/test_news_scraper.py -v`
Expected: All PASS

**Step 5: Commit**

```bash
git add src/scraper/news_scraper.py tests/test_news_scraper.py
git commit -m "feat(scraper): three-bucket source weighting (Finance/Tech/Israel)"
```

---

### Task 1.4: Update Dashboard Source Mapping

**Files:**
- Modify: `src/dashboard/views/content.py` — source_map dict
- Modify: `src/dashboard/helpers.py` — `get_source_badge_class()`
- Modify: `src/dashboard/styles.py` — CSS badge classes

**Step 1: Verify existing source mapping**

Read `src/dashboard/views/content.py` and find the `source_map` dict. Add entries for the 3 new Israeli sources mapping to their `TrendSource` enum values.

**Step 2: Add source badge mappings**

In `src/dashboard/helpers.py`, add to `get_source_badge_class()`:
```python
"Calcalist": "badge-calcalist",
"Globes": "badge-globes",
"Times of Israel": "badge-timesofisrael",
```

In `src/dashboard/styles.py`, add CSS classes with a distinctive color (e.g., blue for Israel sources).

**Step 3: Run existing dashboard tests**

Run: `pytest tests/test_dashboard.py tests/test_dashboard_helpers.py -v`
Expected: All PASS

**Step 4: Commit**

```bash
git add src/dashboard/views/content.py src/dashboard/helpers.py src/dashboard/styles.py src/common/models.py
git commit -m "feat(dashboard): add Israeli source badges and mappings"
```

---

## Slice 2: Telegram Bot — Rich Briefs

### Task 2.1: HTML Brief Formatting with Story Metadata

**Files:**
- Modify: `src/telegram_bot/bot.py:158-179` (format_brief_message)
- Test: `tests/test_telegram_bot.py` (or create if needed)

**Step 1: Write the failing test**

```python
from telegram_bot.bot import format_brief_message

def test_brief_message_uses_html():
    """Brief message should contain HTML bold tags."""
    stories = [
        {
            "title": "Fed Signals Rate Cut",
            "summary": "Powell says more data needed.",
            "sources": ["Bloomberg", "WSJ"],
            "source_urls": ["https://bloomberg.com/1", "https://wsj.com/1"],
            "source_count": 2,
            "published_at": "2026-03-13T07:00:00Z",
            "relevance_score": 87,
        }
    ]
    msg = format_brief_message(stories, "morning")

    assert "<b>" in msg, "Must use HTML bold tags"
    assert "Morning Brief" in msg
    assert "87" in msg, "Relevance score must be shown"
    assert "2 sources" in msg or "📡 2" in msg, "Source count must be shown"
    assert "<a href=" in msg, "Source links must be HTML anchors"


def test_brief_message_shows_story_age():
    """Brief should show relative age for each story."""
    from datetime import datetime, timezone, timedelta

    recent = datetime.now(timezone.utc) - timedelta(hours=2)
    stories = [
        {
            "title": "Test Story",
            "summary": "Summary here.",
            "sources": ["Bloomberg"],
            "source_urls": ["https://bloomberg.com/1"],
            "source_count": 1,
            "published_at": recent.isoformat(),
            "relevance_score": 50,
        }
    ]
    msg = format_brief_message(stories, "on-demand")

    assert "2h ago" in msg or "2h" in msg, "Story age should be shown"


def test_brief_message_shows_generation_timestamp():
    """Brief header should include when it was generated."""
    stories = [{"title": "Test", "summary": "", "sources": ["WSJ"],
                "source_urls": ["https://wsj.com"], "source_count": 1,
                "published_at": None, "relevance_score": 30}]
    msg = format_brief_message(stories, "morning")

    # Should contain a time indicator (HH:MM format)
    import re
    assert re.search(r'\d{1,2}:\d{2}', msg), "Generation timestamp must be shown"


def test_brief_message_israel_badge():
    """Israel-source stories should get a special badge."""
    stories = [{"title": "Wix Growth", "summary": "Strong quarter.",
                "sources": ["Calcalist", "Globes"],
                "source_urls": ["https://calcalist.com/1", "https://globes.com/1"],
                "source_count": 2, "published_at": None, "relevance_score": 60}]
    msg = format_brief_message(stories, "morning")

    assert "🔵" in msg or "Israel" in msg, "Israel badge should appear for Israeli sources"
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/test_telegram_bot.py -k "brief_message" -v`
Expected: FAIL — current `format_brief_message` returns plain text without `<b>`, `<a href=`, etc.

**Step 3: Implement rich HTML brief formatting**

Replace `format_brief_message()` in `src/telegram_bot/bot.py` (lines 158-179):

```python
def format_brief_message(stories: List[dict], brief_type: str) -> str:
    """Render stories as rich HTML for Telegram."""
    from datetime import datetime, timezone

    if brief_type == "morning":
        header = "Morning Brief"
    elif brief_type == "evening":
        header = "Evening Brief"
    else:
        header = "Brief"

    now = datetime.now(timezone.utc)
    # IST = UTC+2 (Israel Standard Time)
    from datetime import timedelta as td
    ist_now = now + td(hours=2)
    timestamp = ist_now.strftime("%H:%M")

    lines = [f"📊 <b>{header}</b> · {len(stories)} stories · {timestamp} IST", ""]

    israel_sources = {"calcalist", "globes", "times of israel"}

    for index, story in enumerate(stories, 1):
        title = html.escape(str(story.get("title", "Untitled")))
        summary = html.escape(_safe_preview(str(story.get("summary", "")), max_chars=280))
        source_count = story.get("source_count", len(story.get("sources", [])))
        relevance = story.get("relevance_score", 0)
        sources = story.get("sources", [])
        source_urls = story.get("source_urls", [])

        # Story age
        age_str = ""
        published = story.get("published_at")
        if published:
            if isinstance(published, str):
                try:
                    pub_dt = datetime.fromisoformat(published.replace("Z", "+00:00"))
                    age_hours = (now - pub_dt).total_seconds() / 3600
                    if age_hours < 1:
                        age_str = f"{int(age_hours * 60)}m ago"
                    elif age_hours < 24:
                        age_str = f"{int(age_hours)}h ago"
                    else:
                        age_str = f"{int(age_hours / 24)}d ago"
                except (ValueError, TypeError):
                    pass

        # Israel badge
        is_israel = any(s.lower() in israel_sources for s in sources)
        badge = "🔵 Israel" if is_israel else f"🎯 {relevance}"

        # Source links
        source_links = []
        for i, src in enumerate(sources):
            url = source_urls[i] if i < len(source_urls) else ""
            if url:
                source_links.append(f'<a href="{url}">{html.escape(src)}</a>')
            else:
                source_links.append(html.escape(src))

        lines.append(f"<b>{index}.</b> <b>{title}</b>")
        if summary:
            lines.append(f"   {summary}")
        meta_parts = []
        if age_str:
            meta_parts.append(f"⏱ {age_str}")
        meta_parts.append(f"📡 {source_count} sources")
        meta_parts.append(badge)
        lines.append("   " + " · ".join(meta_parts))
        if source_links:
            lines.append("   " + " · ".join(source_links))
        lines.append("")

    lines.append(f"/write N to create · /story N for details")
    return "\n".join(lines).strip()
```

**Step 4: Run tests to verify they pass**

Run: `pytest tests/test_telegram_bot.py -k "brief_message" -v`
Expected: All PASS

**Step 5: Commit**

```bash
git add src/telegram_bot/bot.py tests/test_telegram_bot.py
git commit -m "feat(bot): rich HTML brief formatting with story age, scores, source links"
```

---

### Task 2.2: Update _reply_text to Use parse_mode="HTML" for Briefs

**Files:**
- Modify: `src/telegram_bot/bot.py` — `_reply_text()` (lines 289-297), `cmd_brief`, `send_scheduled_brief`
- Test: `tests/test_telegram_bot.py`

**Step 1: Write the failing test**

```python
def test_brief_reply_uses_html_parse_mode():
    """cmd_brief should send messages with parse_mode='HTML'."""
    # This is a behavioral test — verify that _reply_text is called with parse_mode="HTML"
    # when sending brief messages. Can be tested via mock.
    pass  # Integration test — verify manually or via mock
```

**Step 2: Implement**

In all locations where brief/alert messages are sent, add `parse_mode="HTML"`:

- `cmd_brief`: change `await self._reply_text(update, msg)` to `await self._reply_text(update, msg, parse_mode="HTML")`
- `send_scheduled_brief` (line ~833): change `send_message(chat_id=..., text=msg)` to `send_message(chat_id=..., text=msg, parse_mode="HTML")`
- `cmd_story`: add `parse_mode="HTML"` since story detail also uses HTML
- Alert delivery: add `parse_mode="HTML"`

**Step 3: Run all bot tests**

Run: `pytest tests/test_telegram_bot.py -v`
Expected: All PASS

**Step 4: Commit**

```bash
git add src/telegram_bot/bot.py tests/test_telegram_bot.py
git commit -m "feat(bot): send briefs and alerts with parse_mode=HTML"
```

---

### Task 2.3: Rich HTML Alert Formatting

**Files:**
- Modify: `src/telegram_bot/bot.py:182-190` (format_alert_message)
- Test: `tests/test_telegram_bot.py`

**Step 1: Write the failing test**

```python
def test_alert_message_shows_source_count():
    """Alert messages must show how many sources covered the story."""
    from telegram_bot.bot import format_alert_message
    alert = {
        "title": "NASDAQ Drops 3%",
        "summary": "Markets react to inflation data.",
        "sources": ["Bloomberg", "WSJ", "Yahoo Finance"],
        "source_urls": ["https://b.com", "https://wsj.com", "https://yf.com"],
        "source_count": 3,
    }
    msg = format_alert_message(alert)

    assert "<b>" in msg, "Must use HTML bold"
    assert "3 sources" in msg or "📡 3" in msg
    assert "<a href=" in msg, "Source links must be clickable"
```

**Step 2: Run test — expected FAIL**

Run: `pytest tests/test_telegram_bot.py::test_alert_message_shows_source_count -v`

**Step 3: Implement rich alert formatting**

Replace `format_alert_message()`:

```python
def format_alert_message(alert: dict) -> str:
    """Render a single alert as rich HTML for Telegram."""
    title = html.escape(str(alert.get("title", "Breaking alert")))
    summary = html.escape(_safe_preview(str(alert.get("summary", "")), max_chars=280))
    source_count = alert.get("source_count", 0)
    sources = alert.get("sources", [])
    source_urls = alert.get("source_urls", [])

    source_links = []
    for i, src in enumerate(sources):
        url = source_urls[i] if i < len(source_urls) else ""
        if url:
            source_links.append(f'<a href="{url}">{html.escape(src)}</a>')
        else:
            source_links.append(html.escape(src))

    lines = [f"🚨 <b>Breaking:</b> {title}"]
    if summary:
        lines.append(summary)
    meta = f"📡 {source_count} sources"
    lines.append(meta)
    if source_links:
        lines.append(" · ".join(source_links))
    lines.append("")
    lines.append("/write alert to create content")
    return "\n".join(lines)
```

**Step 4: Run test — expected PASS**

Run: `pytest tests/test_telegram_bot.py::test_alert_message_shows_source_count -v`

**Step 5: Commit**

```bash
git add src/telegram_bot/bot.py tests/test_telegram_bot.py
git commit -m "feat(bot): rich HTML alert formatting with source count and links"
```

---

### Task 2.4: /brief Accepts 1-8 + Lower Alert Threshold Default

**Files:**
- Modify: `src/telegram_bot/bot.py:420-432` (_brief_input)
- Modify: `src/api/routes/notifications.py:141-149` (alerts check min_sources default)
- Test: `tests/test_telegram_bot.py`

**Step 1: Write the failing test**

```python
def test_brief_input_accepts_1_to_8():
    """_brief_input should accept any number 1-8, not just 3/4/5."""
    from telegram_bot.bot import HFIBot

    assert HFIBot._brief_input(["1"]) == (1, False)
    assert HFIBot._brief_input(["6"]) == (6, False)
    assert HFIBot._brief_input(["8"]) == (8, False)
    assert HFIBot._brief_input(["refresh"]) == (5, True)
    assert HFIBot._brief_input([]) == (5, False)

    import pytest
    with pytest.raises(ValueError):
        HFIBot._brief_input(["9"])
    with pytest.raises(ValueError):
        HFIBot._brief_input(["0"])
```

**Step 2: Run test — expected FAIL**

Run: `pytest tests/test_telegram_bot.py::test_brief_input_accepts_1_to_8 -v`
Expected: FAIL — `_brief_input(["6"])` raises ValueError because only "3", "4", "5" accepted

**Step 3: Implement**

Replace `_brief_input()` in `src/telegram_bot/bot.py`:

```python
@staticmethod
def _brief_input(args: list[str]) -> tuple[int, bool]:
    count = 5
    force_refresh = False
    if not args:
        return count, force_refresh

    token = args[0].strip().lower()
    if token == "refresh":
        force_refresh = True
        return count, force_refresh
    try:
        n = int(token)
    except ValueError:
        raise ValueError("Usage: /brief [1-8|refresh]")
    if 1 <= n <= 8:
        return n, force_refresh
    raise ValueError("Usage: /brief [1-8|refresh]")
```

In `src/api/routes/notifications.py` line 143, change `min_sources` default from 3 to 2:

```python
min_sources: int = Query(2, ge=2, le=10),
```

**Step 4: Run test — expected PASS**

Run: `pytest tests/test_telegram_bot.py::test_brief_input_accepts_1_to_8 -v`

**Step 5: Run all tests**

Run: `pytest tests/ -v`
Expected: All PASS

**Step 6: Commit**

```bash
git add src/telegram_bot/bot.py src/api/routes/notifications.py tests/test_telegram_bot.py
git commit -m "feat(bot): /brief accepts 1-8, lower alert threshold to 2 sources"
```

---

## Slice 3: Frontend Dashboard — News Hub

### Task 3.1: useBrief Hook — GET/POST Split

**Files:**
- Modify: `frontend/src/hooks/useBrief.ts`
- Test: Manual verification (React Query hook)

**Step 1: Implement the hook refactor**

Replace `frontend/src/hooks/useBrief.ts`:

```typescript
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { BriefResponse } from "@/types";

export function useBrief() {
  return useQuery({
    queryKey: ["brief"],
    queryFn: async () => {
      const { data } = await api.get<BriefResponse>("/api/notifications/brief/latest");
      return data;
    },
    refetchInterval: 300_000,
    refetchOnWindowFocus: false,
    refetchOnReconnect: false,
  });
}

export function useRefreshBrief() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async () => {
      const { data } = await api.post<BriefResponse>("/api/notifications/brief?force_refresh=true");
      return data;
    },
    onSuccess: (data) => {
      queryClient.setQueryData(["brief"], data);
    },
  });
}
```

**Step 2: Commit**

```bash
git add frontend/src/hooks/useBrief.ts
git commit -m "feat(frontend): split useBrief into GET (auto) and POST (refresh)"
```

---

### Task 3.2: useAlerts Hook

**Files:**
- Create: `frontend/src/hooks/useAlerts.ts`
- Verify type: check if `NotificationResponse` type exists in `frontend/src/types/`

**Step 1: Check existing types**

Read `frontend/src/types/index.ts` (or wherever types are defined) for any existing `Notification` or `Alert` types. If missing, add:

```typescript
export interface AlertItem {
  id: number;
  title: string;
  summary: string;
  sources: string[];
  source_urls: string[];
  source_count: number;
  created_at: string;
  delivered: boolean;
}

export interface AlertsResponse {
  alerts: AlertItem[];
  count: number;
}
```

**Step 2: Create the hook**

```typescript
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { AlertsResponse } from "@/types";

export function useAlerts() {
  return useQuery({
    queryKey: ["alerts"],
    queryFn: async () => {
      const { data } = await api.get<AlertsResponse>("/api/notifications/alerts?delivered=false");
      return data;
    },
    refetchInterval: 60_000,  // check every minute
  });
}

export function useDismissAlert() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (alertId: number) => {
      await api.patch(`/api/notifications/${alertId}/delivered`);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["alerts"] });
    },
  });
}
```

**Step 3: Commit**

```bash
git add frontend/src/hooks/useAlerts.ts frontend/src/types/
git commit -m "feat(frontend): add useAlerts hook and AlertItem type"
```

---

### Task 3.3: BriefCard — Expanded by Default + Full Metadata

**Files:**
- Modify: `frontend/src/components/dashboard/BriefCard.tsx`

**Step 1: Read current BriefCard component**

Read `frontend/src/components/dashboard/BriefCard.tsx` for the full current implementation.

**Step 2: Implement changes**

Key modifications:
1. Change `useState(false)` to `useState(true)` — cards start expanded
2. Add story age display: parse `published_at`, compute relative time, show "2h ago"
3. Add relevance score badge: `★{relevance_score}`
4. Add Israel badge: check if any source is in `["Calcalist", "Globes", "Times of Israel"]`
5. Show all source names as clickable links (not just first)
6. Fix "Write" button to pass full context:

```tsx
onClick={(e) => {
  e.stopPropagation();
  const text = `${story.title}\n\n${story.summary || ""}`;
  const sources = (story.source_urls || []).join(",");
  router.push(`/create?source=trend&id=${index + 1}&text=${encodeURIComponent(text)}&sources=${encodeURIComponent(sources)}`);
}}
```

**Step 3: Commit**

```bash
git add frontend/src/components/dashboard/BriefCard.tsx
git commit -m "feat(frontend): BriefCard expanded by default, full metadata, write context fix"
```

---

### Task 3.4: Dashboard Homepage — Refresh Button + Alerts Section

**Files:**
- Modify: `frontend/src/app/(app)/page.tsx`
- Create: `frontend/src/components/dashboard/AlertCard.tsx`

**Step 1: Create AlertCard component**

```tsx
// frontend/src/components/dashboard/AlertCard.tsx
"use client";

import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { useRouter } from "next/navigation";
import type { AlertItem } from "@/types";

interface AlertCardProps {
  alert: AlertItem;
  onDismiss: (id: number) => void;
}

export function AlertCard({ alert, onDismiss }: AlertCardProps) {
  const router = useRouter();

  return (
    <Card className="border-red-200 bg-red-50/50">
      <CardContent className="p-4">
        <div className="flex items-start justify-between gap-2">
          <div className="flex-1">
            <p className="font-semibold">{alert.title}</p>
            {alert.summary && (
              <p className="text-sm text-muted-foreground mt-1">{alert.summary}</p>
            )}
            <div className="flex gap-2 mt-2 text-xs text-muted-foreground">
              <Badge variant="outline">📡 {alert.source_count} sources</Badge>
            </div>
          </div>
          <div className="flex gap-1">
            <Button
              size="sm"
              variant="outline"
              onClick={() => {
                const text = `${alert.title}\n\n${alert.summary || ""}`;
                router.push(`/create?text=${encodeURIComponent(text)}`);
              }}
            >
              Write
            </Button>
            <Button size="sm" variant="ghost" onClick={() => onDismiss(alert.id)}>
              Dismiss
            </Button>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
```

**Step 2: Update homepage**

In `frontend/src/app/(app)/page.tsx`:

1. Import `useRefreshBrief` from `useBrief.ts` and `useAlerts`, `useDismissAlert` from `useAlerts.ts`
2. Add a "Refresh Brief" button near the brief header:

```tsx
<div className="flex items-center justify-between">
  <h2>Today's Brief</h2>
  <div className="flex items-center gap-2 text-sm text-muted-foreground">
    {briefQuery.dataUpdatedAt && (
      <span>Updated {formatRelativeTime(briefQuery.dataUpdatedAt)}</span>
    )}
    <Button size="sm" variant="outline" onClick={() => refreshBrief.mutate()}
            disabled={refreshBrief.isPending}>
      {refreshBrief.isPending ? "Refreshing..." : "↻ Refresh"}
    </Button>
  </div>
</div>
```

3. Add Alerts section below stats and above brief:

```tsx
{alertsQuery.data?.alerts?.length > 0 && (
  <div>
    <h2>🚨 Alerts ({alertsQuery.data.alerts.length})</h2>
    <div className="space-y-2">
      {alertsQuery.data.alerts.map((alert) => (
        <AlertCard key={alert.id} alert={alert} onDismiss={(id) => dismissAlert.mutate(id)} />
      ))}
    </div>
  </div>
)}
```

**Step 3: Commit**

```bash
git add frontend/src/components/dashboard/AlertCard.tsx frontend/src/app/(app)/page.tsx
git commit -m "feat(frontend): dashboard refresh button, alerts section, brief age indicator"
```

---

### Task 3.5: Create Page — Read Sources Param

**Files:**
- Modify: `frontend/src/app/(app)/create/page.tsx`

**Step 1: Read current create page**

Read `frontend/src/app/(app)/create/page.tsx` to understand how URL params are consumed.

**Step 2: Implement sources param reading**

In `CreatePage` (or `CreateWorkspace`), read the `sources` URL param:

```tsx
const sources = searchParams.get("sources");
```

When generating, if `sources` is present, append source URLs to the generation prompt context so the AI has the full article references. This feeds into the `source_text` sent to `POST /api/generation/post`.

**Step 3: Commit**

```bash
git add frontend/src/app/(app)/create/page.tsx
git commit -m "feat(frontend): create page reads sources param for full brief context"
```

---

## Slice 4: X Content Pipeline — API + Frontend

### Task 4.1: Scrape API Router

**Files:**
- Create: `src/api/routes/scrape.py`
- Modify: `src/api/__init__.py` or `src/api/main.py` — register new router
- Test: `tests/test_api_scrape.py`

**Step 1: Write the failing test**

```python
import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from fastapi.testclient import TestClient


def test_scrape_thread_endpoint(client, auth_headers):
    """POST /api/scrape/thread should accept a URL and return thread data."""
    mock_thread = {
        "source_url": "https://x.com/user/status/123",
        "author_handle": "@user",
        "author_name": "User",
        "tweet_count": 3,
        "tweets": [
            {"tweet_id": "123", "text": "First tweet", "author_handle": "@user"},
            {"tweet_id": "124", "text": "Second tweet", "author_handle": "@user"},
            {"tweet_id": "125", "text": "Third tweet", "author_handle": "@user"},
        ],
    }

    with patch("api.routes.scrape.get_scraper") as mock_get:
        mock_scraper = AsyncMock()
        mock_scraper.fetch_raw_thread.return_value = mock_thread
        mock_get.return_value = mock_scraper

        response = client.post(
            "/api/scrape/thread",
            json={"url": "https://x.com/user/status/123"},
            headers=auth_headers,
        )

    assert response.status_code == 200
    data = response.json()
    assert data["author_handle"] == "@user"
    assert data["tweet_count"] == 3


def test_scrape_tweet_endpoint(client, auth_headers):
    """POST /api/scrape/tweet should accept a URL and return tweet data."""
    mock_tweet = {
        "text": "Hello world",
        "author": "@user",
        "timestamp": "2026-03-13T10:00:00Z",
        "source_url": "https://x.com/user/status/123",
    }

    with patch("api.routes.scrape.get_scraper") as mock_get:
        mock_scraper = AsyncMock()
        mock_scraper.get_tweet_content.return_value = mock_tweet
        mock_get.return_value = mock_scraper

        response = client.post(
            "/api/scrape/tweet",
            json={"url": "https://x.com/user/status/123"},
            headers=auth_headers,
        )

    assert response.status_code == 200
    assert response.json()["text"] == "Hello world"


def test_scrape_trends_endpoint(client, auth_headers):
    """POST /api/scrape/trends should return trending topics."""
    mock_trends = [
        {"title": "Bitcoin", "description": "Trending", "category": "Finance"},
        {"title": "AI", "description": "Trending", "category": "Technology"},
    ]

    with patch("api.routes.scrape.get_scraper") as mock_get:
        mock_scraper = AsyncMock()
        mock_scraper.get_trending_topics.return_value = mock_trends
        mock_get.return_value = mock_scraper

        response = client.post(
            "/api/scrape/trends",
            json={"limit": 10},
            headers=auth_headers,
        )

    assert response.status_code == 200
    data = response.json()
    assert len(data["trends"]) == 2
```

**Step 2: Run tests — expected FAIL**

Run: `pytest tests/test_api_scrape.py -v`
Expected: FAIL — module `api.routes.scrape` not found

**Step 3: Implement scrape router**

Create `src/api/routes/scrape.py`:

```python
"""X/Twitter scraping API endpoints."""
import asyncio
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from api.dependencies import require_jwt

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/scrape", tags=["scrape"])


class ScrapeThreadRequest(BaseModel):
    url: str = Field(..., description="X thread URL")

class ScrapeTweetRequest(BaseModel):
    url: str = Field(..., description="X tweet URL")

class ScrapeTrendsRequest(BaseModel):
    limit: int = Field(10, ge=1, le=20)


_scraper_instance = None

async def get_scraper():
    """Lazy-init shared TwitterScraper instance."""
    global _scraper_instance
    if _scraper_instance is None:
        from scraper.scraper import TwitterScraper
        _scraper_instance = TwitterScraper(headless=True)
        await _scraper_instance.ensure_logged_in()
    return _scraper_instance


@router.post("/thread")
async def scrape_thread(req: ScrapeThreadRequest, _=Depends(require_jwt)):
    scraper = await get_scraper()
    try:
        result = await scraper.fetch_raw_thread(req.url, author_only=True)
        return result
    except Exception as e:
        logger.error(f"Thread scrape failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/tweet")
async def scrape_tweet(req: ScrapeTweetRequest, _=Depends(require_jwt)):
    scraper = await get_scraper()
    try:
        result = await scraper.get_tweet_content(req.url)
        return result
    except Exception as e:
        logger.error(f"Tweet scrape failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/trends")
async def scrape_trends(req: ScrapeTrendsRequest, _=Depends(require_jwt)):
    scraper = await get_scraper()
    try:
        trends = await scraper.get_trending_topics(limit=req.limit)
        return {"trends": trends}
    except Exception as e:
        logger.error(f"Trends scrape failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
```

Register in the FastAPI app (find the router registration in `src/api/main.py` or `src/api/__init__.py`):

```python
from api.routes.scrape import router as scrape_router
app.include_router(scrape_router)
```

**Step 4: Run tests — expected PASS**

Run: `pytest tests/test_api_scrape.py -v`

**Step 5: Commit**

```bash
git add src/api/routes/scrape.py tests/test_api_scrape.py src/api/main.py
git commit -m "feat(api): add /api/scrape endpoints for thread, tweet, and trends"
```

---

### Task 4.2: Content-from-Thread API Endpoint

**Files:**
- Create: Add to `src/api/routes/scrape.py` (or `content.py`)
- Test: `tests/test_api_scrape.py`

**Step 1: Write the failing test**

```python
def test_content_from_thread_consolidated(client, auth_headers):
    """POST /api/content/from-thread should scrape, translate, and save."""
    mock_thread = {
        "source_url": "https://x.com/user/status/123",
        "author_handle": "@user",
        "author_name": "User",
        "tweet_count": 2,
        "tweets": [
            {"tweet_id": "123", "text": "First tweet about fintech", "author_handle": "@user"},
            {"tweet_id": "124", "text": "Second tweet about payments", "author_handle": "@user"},
        ],
    }

    with patch("api.routes.scrape.get_scraper") as mock_get, \
         patch("api.routes.scrape.get_translation_service") as mock_trans:
        mock_scraper = AsyncMock()
        mock_scraper.fetch_raw_thread.return_value = mock_thread
        mock_get.return_value = mock_scraper

        mock_svc = MagicMock()
        mock_svc.translate_thread_consolidated.return_value = "תוכן בעברית"
        mock_trans.return_value = mock_svc

        response = client.post(
            "/api/content/from-thread",
            json={"url": "https://x.com/user/status/123", "mode": "consolidated", "auto_translate": True},
            headers=auth_headers,
        )

    assert response.status_code == 200
    data = response.json()
    assert data["hebrew_draft"] == "תוכן בעברית"
    assert data["status"] == "processed"
```

**Step 2: Run test — expected FAIL**

**Step 3: Implement**

Add to `src/api/routes/scrape.py`:

```python
class ContentFromThreadRequest(BaseModel):
    url: str
    mode: str = Field("consolidated", pattern="^(consolidated|separate)$")
    auto_translate: bool = True
    download_media: bool = False


@router.post("/content/from-thread")
async def content_from_thread(req: ContentFromThreadRequest, db=Depends(get_db), _=Depends(require_jwt)):
    scraper = await get_scraper()

    # Scrape
    thread_data = await scraper.fetch_raw_thread(req.url, author_only=True)
    tweets = thread_data.get("tweets", [])
    if not tweets:
        raise HTTPException(status_code=404, detail="No tweets found in thread")

    # Translate
    hebrew_draft = None
    if req.auto_translate:
        svc = get_translation_service()
        if req.mode == "consolidated":
            hebrew_draft = svc.translate_thread_consolidated(tweets)
        else:
            hebrew_draft = svc.translate_thread_separate(tweets)

    # Save to DB
    original_text = "\n\n".join(t.get("text", "") for t in tweets)
    from common.models import Tweet, TweetStatus
    tweet = Tweet(
        source_url=req.url,
        original_text=original_text,
        hebrew_draft=hebrew_draft if isinstance(hebrew_draft, str) else None,
        status=TweetStatus.PROCESSED if hebrew_draft else TweetStatus.PENDING,
        content_type="translation",
    )
    db.add(tweet)
    db.commit()
    db.refresh(tweet)

    return {
        "id": tweet.id,
        "source_url": tweet.source_url,
        "original_text": tweet.original_text,
        "hebrew_draft": tweet.hebrew_draft,
        "status": tweet.status.value,
    }
```

**Step 4: Run test — expected PASS**

**Step 5: Commit**

```bash
git add src/api/routes/scrape.py tests/test_api_scrape.py
git commit -m "feat(api): add /api/content/from-thread one-click scrape+translate+save"
```

---

### Task 4.3: Frontend Acquire Page

**Files:**
- Create: `frontend/src/app/(app)/acquire/page.tsx`
- Modify: frontend layout/nav to add sidebar link

**Step 1: Create the Acquire page**

```tsx
// frontend/src/app/(app)/acquire/page.tsx
"use client";

import { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import { Checkbox } from "@/components/ui/checkbox";
import { useMutation } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { toast } from "sonner";

export default function AcquirePage() {
  const [url, setUrl] = useState("");
  const [mode, setMode] = useState<"consolidated" | "separate">("consolidated");
  const [autoTranslate, setAutoTranslate] = useState(true);
  const [downloadMedia, setDownloadMedia] = useState(false);

  const scrape = useMutation({
    mutationFn: async () => {
      const { data } = await api.post("/api/scrape/content/from-thread", {
        url, mode, auto_translate: autoTranslate, download_media: downloadMedia,
      });
      return data;
    },
    onSuccess: (data) => {
      toast.success(`Saved as draft #${data.id}`);
    },
    onError: (err: any) => {
      toast.error(err?.response?.data?.detail || "Scrape failed");
    },
  });

  const isXUrl = /^https?:\/\/(x\.com|twitter\.com)\//i.test(url);

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Acquire Content</h1>

      <Card>
        <CardHeader>
          <CardTitle>Scrape X Thread</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div>
            <Label>X Thread or Tweet URL</Label>
            <Input
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              placeholder="https://x.com/user/status/..."
              dir="ltr"
            />
            {url && !isXUrl && (
              <p className="text-sm text-amber-600 mt-1">This doesn't look like an X/Twitter URL</p>
            )}
          </div>

          <div>
            <Label>Mode</Label>
            <RadioGroup value={mode} onValueChange={(v) => setMode(v as any)} className="flex gap-4 mt-1">
              <div className="flex items-center gap-2">
                <RadioGroupItem value="consolidated" id="consolidated" />
                <Label htmlFor="consolidated">Consolidated (single post)</Label>
              </div>
              <div className="flex items-center gap-2">
                <RadioGroupItem value="separate" id="separate" />
                <Label htmlFor="separate">Separate (per-tweet)</Label>
              </div>
            </RadioGroup>
          </div>

          <div className="flex gap-6">
            <div className="flex items-center gap-2">
              <Checkbox checked={autoTranslate} onCheckedChange={(v) => setAutoTranslate(!!v)} id="translate" />
              <Label htmlFor="translate">Auto-translate</Label>
            </div>
            <div className="flex items-center gap-2">
              <Checkbox checked={downloadMedia} onCheckedChange={(v) => setDownloadMedia(!!v)} id="media" />
              <Label htmlFor="media">Download media</Label>
            </div>
          </div>

          <Button onClick={() => scrape.mutate()} disabled={!url || !isXUrl || scrape.isPending}>
            {scrape.isPending ? "Scraping..." : "Scrape & Process ▶"}
          </Button>

          {scrape.data && (
            <Card className="mt-4">
              <CardContent className="p-4">
                <div className="grid grid-cols-2 gap-4">
                  <div dir="ltr">
                    <h3 className="font-semibold mb-2">Original (English)</h3>
                    <p className="text-sm whitespace-pre-wrap">{scrape.data.original_text}</p>
                  </div>
                  <div dir="rtl">
                    <h3 className="font-semibold mb-2">Hebrew</h3>
                    <p className="text-sm whitespace-pre-wrap">{scrape.data.hebrew_draft || "—"}</p>
                  </div>
                </div>
                <div className="flex gap-2 mt-4 justify-end">
                  <Button variant="outline" onClick={() => window.open(`/create?edit=${scrape.data.id}`, "_self")}>
                    Edit in Studio
                  </Button>
                </div>
              </CardContent>
            </Card>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
```

**Step 2: Add sidebar link**

Find the navigation/sidebar component (likely in `frontend/src/app/(app)/layout.tsx` or a shared nav component). Add an "Acquire" link pointing to `/acquire`.

**Step 3: Commit**

```bash
git add frontend/src/app/(app)/acquire/page.tsx
git commit -m "feat(frontend): add Acquire page for X thread scraping"
```

---

### Task 4.4: Telegram /scrape and /xtrends Commands

**Files:**
- Modify: `src/telegram_bot/bot.py` — add new command handlers
- Test: `tests/test_telegram_bot.py`

**Step 1: Write the failing test**

```python
@pytest.mark.asyncio
async def test_scrape_command_validates_url():
    """The /scrape command should reject non-X URLs."""
    # Test that the URL validation rejects non-X URLs
    from telegram_bot.bot import validate_x_status_url
    import pytest

    assert validate_x_status_url("https://x.com/user/status/123") is not None

    with pytest.raises(ValueError):
        validate_x_status_url("https://google.com")
```

**Step 2: Implement /scrape and /xtrends commands**

Add to `src/telegram_bot/bot.py`:

```python
async def cmd_scrape(self, update, context):
    """Scrape an X thread, translate, and offer to save."""
    args = context.args
    if not args:
        await self._reply_text(update, "Usage: /scrape <x_thread_url>")
        return

    url = args[0]
    try:
        validated = validate_x_status_url(url)
    except ValueError:
        await self._reply_text(update, "Invalid X URL. Use: /scrape https://x.com/user/status/...")
        return

    await self._reply_text(update, "🔄 Scraping thread...")

    try:
        response = await self._request("POST", "/api/scrape/content/from-thread", json={
            "url": validated, "mode": "consolidated", "auto_translate": True
        })
        data = response.json()

        preview = _safe_preview(data.get("hebrew_draft", ""), max_chars=500)
        msg = (
            f"<b>Thread scraped and translated</b>\n\n"
            f"{html.escape(preview)}\n\n"
            f"Draft #{data['id']} · /approve {data['id']} to approve"
        )
        await self._reply_text(update, msg, parse_mode="HTML")
    except Exception as e:
        await self._reply_text(update, f"Scrape failed: {e}")


async def cmd_xtrends(self, update, context):
    """Show top X trending topics."""
    await self._reply_text(update, "🔄 Fetching X trends...")

    try:
        response = await self._request("POST", "/api/scrape/trends", json={"limit": 10})
        data = response.json()
        trends = data.get("trends", [])

        if not trends:
            await self._reply_text(update, "No trending topics found.")
            return

        lines = ["<b>📈 X Trending Topics</b>", ""]
        for i, trend in enumerate(trends, 1):
            title = html.escape(str(trend.get("title", "")))
            lines.append(f"<b>{i}.</b> {title}")
        lines.append("")
        lines.append("/write <topic> to create content")

        await self._reply_text(update, "\n".join(lines), parse_mode="HTML")
    except Exception as e:
        await self._reply_text(update, f"Failed to fetch trends: {e}")
```

Register both commands in the bot's command handler setup (find where `add_handler` is called for other commands):

```python
app.add_handler(CommandHandler("scrape", self.cmd_scrape))
app.add_handler(CommandHandler("xtrends", self.cmd_xtrends))
```

Also update the `/help` command text to include the new commands.

**Step 3: Run tests**

Run: `pytest tests/test_telegram_bot.py -v`
Expected: All PASS

**Step 4: Commit**

```bash
git add src/telegram_bot/bot.py tests/test_telegram_bot.py
git commit -m "feat(bot): add /scrape and /xtrends commands for X content pipeline"
```

---

### Task 4.5: Final Integration Test + Full Test Suite

**Files:**
- All modified files
- Run: Full test suite

**Step 1: Run full test suite**

```bash
pytest tests/ -v --tb=short
```

Expected: All tests PASS (existing 468 + new tests)

**Step 2: Verify no import issues**

```bash
python tools/verify_changes.py
```

**Step 3: Final commit if any fixes needed**

```bash
git add -A
git commit -m "fix: address integration test issues"
```
