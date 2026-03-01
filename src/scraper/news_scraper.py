"""
News Scraper Module for HFI

This module handles scraping news from various RSS feeds:
- Yahoo Finance (News)
- WSJ (Markets)
- TechCrunch (Fintech)
- Bloomberg (Markets)

It normalizes the data into a common format for the database,
then ranks articles by cross-source keyword overlap.
"""

import feedparser
import logging
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from html.parser import HTMLParser
from io import StringIO
from typing import List, Dict, Optional

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

STOPWORDS = {
    'the', 'a', 'an', 'in', 'on', 'at', 'for', 'of', 'to', 'is', 'are', 'was',
    'were', 'be', 'been', 'has', 'have', 'had', 'do', 'does', 'did', 'will',
    'would', 'could', 'should', 'may', 'might', 'can', 'shall', 'and', 'but',
    'or', 'nor', 'not', 'no', 'so', 'yet', 'both', 'either', 'neither',
    'each', 'every', 'all', 'any', 'few', 'more', 'most', 'other', 'some',
    'such', 'than', 'too', 'very', 'just', 'also', 'now', 'new', 'says',
    'said', 'its', 'it', 'this', 'that', 'these', 'those', 'what', 'which',
    'who', 'whom', 'how', 'why', 'when', 'where', 'with', 'from', 'by',
    'about', 'into', 'through', 'during', 'before', 'after', 'above', 'below',
    'up', 'down', 'out', 'off', 'over', 'under', 'again', 'further', 'then',
    'once', 'here', 'there', 'as', 'if', 'while', 'report', 'reports',
    'according', 'amid', 'among', 'like', 'between', 'against', 'despite',
}


class _HTMLStripper(HTMLParser):
    """Lightweight HTML tag stripper without regex (ReDoS-safe)."""

    def __init__(self):
        super().__init__()
        self.fed = []

    def handle_data(self, d):
        self.fed.append(d)

    def get_data(self):
        return ''.join(self.fed)


class NewsScraper:
    """
    Scraper for RSS news feeds from major financial/tech sources.
    Fetches articles, then ranks them by cross-source keyword overlap.
    Supports weighted sampling (default: 70% finance, 30% tech).
    """

    # Feed categories for weighted sampling
    # Focus on Wall Street, specific companies, and stock markets
    FEEDS = {
        "Yahoo Finance": "https://finance.yahoo.com/news/rssindex",
        "WSJ": "https://feeds.a.dj.com/rss/RSSMarketsMain.xml",
        "TechCrunch": "https://techcrunch.com/category/fintech/feed/",
        "Bloomberg": "https://feeds.bloomberg.com/markets/news.rss",
        "MarketWatch": "https://www.marketwatch.com/rss/topstories"
    }

    FINANCE_SOURCES = ["Yahoo Finance", "WSJ", "Bloomberg", "MarketWatch"]
    TECH_SOURCES = ["TechCrunch"]

    _HTML_RE = re.compile('<.*?>')
    _FEED_TIMEOUT = 10  # seconds per feed

    # Keywords that indicate Wall Street / stock market focus (boost these)
    WALL_STREET_KEYWORDS = {
        'stock', 'stocks', 'shares', 'trading', 'trader', 'investors', 'investment',
        'nasdaq', 'nyse', 's&p', 'dow', 'earnings', 'ipo', 'market', 'markets',
        'ticker', 'equity', 'equities', 'portfolio', 'hedge', 'fund', 'valuation',
        'buyback', 'dividend', 'rally', 'plunge', 'surge', 'analyst', 'rating',
        'upgrade', 'downgrade', 'target', 'price', 'wall', 'street', 'bullish',
        'bearish', 'volatility', 'gain', 'loss', 'index', 'etf', 'sec'
    }

    # Keywords that indicate general economy (penalize these for finance)
    GENERAL_ECONOMY_KEYWORDS = {
        'economy', 'gdp', 'unemployment', 'inflation', 'deflation', 'recession',
        'policy', 'tariff', 'tariffs', 'trade', 'deficit', 'budget', 'senate',
        'congress', 'government', 'federal', 'reserve', 'central', 'bank'
    }

    def __init__(self):
        """Initialize the news scraper."""
        pass

    def get_latest_news(self, limit_per_source: int = 10, total_limit: int = 10, finance_weight: float = 0.7) -> List[Dict]:
        """
        Fetch latest news from all configured sources and return
        the top articles ranked by Wall Street focus with weighted sampling.

        Args:
            limit_per_source: Max articles to fetch per source (increased to account for deduplication)
            total_limit: Max total articles to return after ranking
            finance_weight: Percentage of finance articles (0.0-1.0, default: 0.7 for 70% finance)

        Returns:
            List of ranked, deduplicated article dicts (top total_limit), each containing:
            - title
            - description (snippet)
            - source
            - url
            - discovered_at
            - score (ranking score)
            - category (Finance/Tech)
        """
        # Calculate target counts for each category (overfetch to account for deduplication)
        finance_count = int(total_limit * finance_weight) + 3  # +3 buffer for deduplication
        tech_count = total_limit - int(total_limit * finance_weight) + 2  # +2 buffer

        logger.info(f"Weighted sampling: targeting {int(total_limit * finance_weight)} finance + {total_limit - int(total_limit * finance_weight)} tech articles (with buffer)")

        # Fetch articles by category (fetch more per source to account for filtering)
        finance_articles = self._fetch_by_category(self.FINANCE_SOURCES, limit_per_source, "Finance")
        tech_articles = self._fetch_by_category(self.TECH_SOURCES, limit_per_source, "Tech")

        logger.info(f"Fetched {len(finance_articles)} finance, {len(tech_articles)} tech articles (before ranking/dedup)")

        # Rank within each category (includes deduplication)
        finance_ranked = self._rank_articles(finance_articles)[:finance_count]
        tech_ranked = self._rank_articles(tech_articles)[:tech_count]

        # Trim to exact target counts
        finance_final = finance_ranked[:int(total_limit * finance_weight)]
        tech_final = tech_ranked[:total_limit - int(total_limit * finance_weight)]

        # Combine and interleave for variety (finance, tech, finance, tech...)
        combined = []
        for i in range(max(len(finance_final), len(tech_final))):
            if i < len(finance_final):
                combined.append(finance_final[i])
            if i < len(tech_final):
                combined.append(tech_final[i])

        logger.info(f"Final mix: {len(finance_final)} finance + {len(tech_final)} tech = {len(combined)} total")
        return combined[:total_limit]

    def _fetch_single_feed(self, source_name: str, limit_per_source: int, category: str) -> List[Dict]:
        """Fetch articles from a single RSS feed (called in parallel)."""
        feed_url = self.FEEDS.get(source_name)
        if not feed_url:
            return []

        try:
            logger.info(f"Fetching {category} news from {source_name}...")
            import requests
            resp = requests.get(feed_url, timeout=self._FEED_TIMEOUT, headers={'User-Agent': 'HFI/1.0'})
            feed = feedparser.parse(resp.content)

            if feed.bozo:
                logger.warning(f"Potential issue parsing {source_name}: {feed.bozo_exception}")

            articles = []
            for entry in feed.entries[:limit_per_source]:
                articles.append({
                    "title": entry.title,
                    "description": self._clean_html(entry.get('summary', '') or entry.get('description', '')),
                    "source": source_name,
                    "url": entry.link,
                    "discovered_at": datetime.utcnow(),
                    "category": category
                })

            logger.info(f"Retrieved {len(articles)} {category} articles from {source_name}")
            return articles

        except Exception as e:
            logger.error(f"Error fetching {source_name}: {str(e)}")
            return []

    def _fetch_by_category(self, sources: List[str], limit_per_source: int, category: str) -> List[Dict]:
        """Fetch articles from sources in parallel with timeout."""
        valid_sources = [s for s in sources if s in self.FEEDS]
        if not valid_sources:
            return []

        articles = []
        with ThreadPoolExecutor(max_workers=len(valid_sources)) as executor:
            futures = {
                executor.submit(self._fetch_single_feed, src, limit_per_source, category): src
                for src in valid_sources
            }
            for future in as_completed(futures, timeout=self._FEED_TIMEOUT + 5):
                try:
                    articles.extend(future.result())
                except Exception as e:
                    logger.error(f"Feed fetch failed for {futures[future]}: {e}")

        return articles

    def _rank_articles(self, articles: List[Dict]) -> List[Dict]:
        """
        Rank articles by cross-source keyword overlap with Wall Street focus.

        Algorithm:
        1. Extract keywords from each article title
        2. Build map: keyword -> set of sources mentioning it
        3. Score each article:
           - Cross-source keywords: +10 * source_count
           - Wall Street keywords: +15 bonus
           - General economy keywords: -10 penalty (for finance sources)
           - Single-source keywords: +1
        4. Deduplicate similar articles (keep highest scored)
        5. Sort by score descending
        """
        # Build keyword -> set of sources
        keyword_sources: Dict[str, set] = {}
        for article in articles:
            keywords = self._extract_keywords(article.get('title', ''))
            source = article['source']
            for kw in set(keywords):
                if kw not in keyword_sources:
                    keyword_sources[kw] = set()
                keyword_sources[kw].add(source)

        # Score each article (using title + description keywords)
        for article in articles:
            keywords = self._extract_article_keywords(article)
            score = 0

            # Base score from keyword cross-source overlap
            for kw in set(keywords):
                sources = keyword_sources.get(kw, set())
                if len(sources) >= 2:
                    score += 10 * len(sources)
                else:
                    score += 1

            # Boost Wall Street focused articles
            wall_street_count = sum(1 for kw in keywords if kw in self.WALL_STREET_KEYWORDS)
            score += wall_street_count * 15

            # Penalize general economy articles (for finance sources only)
            if article.get('category') == 'Finance':
                economy_count = sum(1 for kw in keywords if kw in self.GENERAL_ECONOMY_KEYWORDS)
                score -= economy_count * 10

            # Recency bonus: fresher articles score higher
            discovered_at = article.get('discovered_at')
            if discovered_at:
                age_hours = (datetime.utcnow() - discovered_at).total_seconds() / 3600
                if age_hours <= 6:
                    score += 20
                elif age_hours <= 24:
                    score += 10
                elif age_hours > 72:
                    score -= 5

            article['score'] = score

        # Remove duplicates (similar articles from different sources)
        articles = self._deduplicate_articles(articles)

        articles.sort(key=lambda a: a['score'], reverse=True)
        return articles

    def _deduplicate_articles(self, articles: List[Dict]) -> List[Dict]:
        """
        Remove duplicate articles based on title similarity.

        Pre-computes keywords once per article to avoid O(n^2) re-extraction.
        """
        # Pre-compute keyword sets for all articles
        article_keywords = [set(self._extract_keywords(a.get('title', ''))) for a in articles]

        unique_articles = []
        unique_kw_sets = []

        for i, article in enumerate(articles):
            keywords = article_keywords[i]

            is_duplicate = False
            for seen_keywords in unique_kw_sets:
                if not keywords or not seen_keywords:
                    continue

                intersection = len(keywords & seen_keywords)
                union = len(keywords | seen_keywords)
                if union > 0 and intersection / union > 0.6:
                    is_duplicate = True
                    break

            if not is_duplicate:
                unique_articles.append(article)
                unique_kw_sets.append(keywords)

        logger.info(f"Deduplication: {len(articles)} → {len(unique_articles)} articles")
        return unique_articles

    @staticmethod
    def _extract_keywords(title: str) -> List[str]:
        """Extract significant words from an article title."""
        words = re.findall(r"[A-Za-z0-9']+", title.lower())
        return [w for w in words if w not in STOPWORDS and len(w) > 2]

    @staticmethod
    def _extract_article_keywords(article: Dict) -> List[str]:
        """Extract keywords from both title (2x weight) and description.

        Title keywords appear twice to give them higher weight in scoring.
        Description keywords add once for additional context.
        """
        title = article.get('title', '')
        desc = article.get('description', '')
        title_kws = NewsScraper._extract_keywords(title)
        desc_kws = NewsScraper._extract_keywords(desc)
        return title_kws + title_kws + desc_kws

    def _clean_html(self, text: str) -> str:
        """Remove HTML tags safely without regex."""
        if not text:
            return ""
        stripper = _HTMLStripper()
        try:
            stripper.feed(text)
            return stripper.get_data().strip()
        except Exception:
            return self._HTML_RE.sub('', text).strip()


if __name__ == "__main__":
    scraper = NewsScraper()
    print("Fetching news with weighted sampling (70% finance, 30% tech)...\n")
    news = scraper.get_latest_news(limit_per_source=5, total_limit=10, finance_weight=0.7)

    finance_count = sum(1 for a in news if a.get('category') == 'Finance')
    tech_count = sum(1 for a in news if a.get('category') == 'Tech')

    print(f"\n📊 Distribution: {finance_count} Finance ({finance_count/len(news)*100:.0f}%) + {tech_count} Tech ({tech_count/len(news)*100:.0f}%)\n")

    for i, article in enumerate(news, 1):
        category_emoji = "💰" if article.get('category') == 'Finance' else "💻"
        print(f"#{i} {category_emoji} [{article['source']}] (score={article.get('score', 0)}) {article['title']}")
