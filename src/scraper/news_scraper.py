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
from datetime import datetime
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


class NewsScraper:
    """
    Scraper for RSS news feeds from major financial/tech sources.
    Fetches articles, then ranks them by cross-source keyword overlap.
    """

    FEEDS = {
        "Yahoo Finance": "https://finance.yahoo.com/news/rssindex",
        "WSJ": "https://feeds.a.dj.com/rss/RSSMarketsMain.xml",
        "TechCrunch": "https://techcrunch.com/category/fintech/feed/",
        "Bloomberg": "https://feeds.bloomberg.com/markets/news.rss"
    }

    def __init__(self):
        """Initialize the news scraper."""
        pass

    def get_latest_news(self, limit_per_source: int = 5, total_limit: int = 10) -> List[Dict]:
        """
        Fetch latest news from all configured sources and return
        the top articles ranked by cross-source keyword overlap.

        Args:
            limit_per_source: Max articles to fetch per source
            total_limit: Max total articles to return after ranking

        Returns:
            List of ranked article dicts (top total_limit), each containing:
            - title
            - description (snippet)
            - source
            - url
            - discovered_at
            - score (ranking score)
        """
        all_news = []

        for source_name, feed_url in self.FEEDS.items():
            try:
                logger.info(f"Fetching news from {source_name}...")
                feed = feedparser.parse(feed_url)

                if feed.bozo:
                    logger.warning(f"Potential issue parsing {source_name}: {feed.bozo_exception}")

                count = 0
                for entry in feed.entries:
                    if count >= limit_per_source:
                        break

                    published_at = datetime.utcnow()
                    if hasattr(entry, 'published_parsed') and entry.published_parsed:
                        published_at = datetime.fromtimestamp(time.mktime(entry.published_parsed))

                    article = {
                        "title": entry.title,
                        "description": self._clean_html(entry.get('summary', '') or entry.get('description', '')),
                        "source": source_name,
                        "url": entry.link,
                        "discovered_at": datetime.utcnow()
                    }

                    all_news.append(article)
                    count += 1

                logger.info(f"Retrieved {count} articles from {source_name}")

            except Exception as e:
                logger.error(f"Error fetching {source_name}: {str(e)}")

        ranked = self._rank_articles(all_news)
        return ranked[:total_limit]

    def _rank_articles(self, articles: List[Dict]) -> List[Dict]:
        """
        Rank articles by cross-source keyword overlap.

        Algorithm:
        1. Extract keywords from each article title (strip stopwords, keep words >2 chars)
        2. Build map: keyword -> set of sources mentioning it
        3. Score each article: sum over its keywords —
           if keyword appears in 2+ sources: +10 * source_count, else +1
        4. Sort by score descending
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

        # Score each article
        for article in articles:
            keywords = self._extract_keywords(article.get('title', ''))
            score = 0
            for kw in set(keywords):
                sources = keyword_sources.get(kw, set())
                if len(sources) >= 2:
                    score += 10 * len(sources)
                else:
                    score += 1
            article['score'] = score

        articles.sort(key=lambda a: a['score'], reverse=True)
        return articles

    @staticmethod
    def _extract_keywords(title: str) -> List[str]:
        """Extract significant words from an article title."""
        words = re.findall(r"[A-Za-z0-9']+", title.lower())
        return [w for w in words if w not in STOPWORDS and len(w) > 2]

    def _clean_html(self, text: str) -> str:
        """Remove basic HTML tags from descriptions."""
        clean = re.compile('<.*?>')
        return re.sub(clean, '', text).strip()


if __name__ == "__main__":
    scraper = NewsScraper()
    news = scraper.get_latest_news(limit_per_source=5, total_limit=10)
    for i, article in enumerate(news, 1):
        print(f"#{i} [{article['source']}] (score={article.get('score', 0)}) {article['title']}")
