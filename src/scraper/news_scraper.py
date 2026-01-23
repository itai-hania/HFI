"""
News Scraper Module for HFI

This module handles scraping news from various RSS feeds:
- Reuters (Business News)
- WSJ (Markets)
- TechCrunch (Startups/Tech)
- Bloomberg (Markets)

It normalizes the data into a common format for the database.
"""

import feedparser
import logging
import time
from datetime import datetime
from typing import List, Dict, Optional

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class NewsScraper:
    """
    Scraper for RSS news feeds from major financial/tech sources.
    """
    
    FEEDS = {
        "Reuters": "https://cdn.feedcontrol.net/8/1114-wioSIX3uu8/3c1a93d077d8a/org.xml", # Reuters Business (via FeedControl as direct RSS is deprecated)
        "WSJ": "https://feeds.a.dj.com/rss/RSSMarketsMain.xml",
        "TechCrunch": "https://techcrunch.com/feed/",
        "Bloomberg": "https://feeds.bloomberg.com/markets/news.rss"
    }

    def __init__(self):
        """Initialize the news scraper."""
        pass

    def get_latest_news(self, limit_per_source: int = 5) -> List[Dict]:
        """
        Fetch latest news from all configured sources.
        
        Args:
            limit_per_source: Max articles to fetch per source
            
        Returns:
            List of dictionaries containing:
            - title
            - description (snippet)
            - source (e.g. "Reuters")
            - url
            - published_at
        """
        all_news = []
        
        for source_name, feed_url in self.FEEDS.items():
            try:
                logger.info(f"Fetching news from {source_name}...")
                feed = feedparser.parse(feed_url)
                
                # Check for parsing errors
                if feed.bozo:
                    logger.warning(f"Potential issue parsing {source_name}: {feed.bozo_exception}")

                count = 0
                for entry in feed.entries:
                    if count >= limit_per_source:
                        break
                        
                    # Extract published date
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
                    
                logger.info(f"✅ Retrieved {count} articles from {source_name}")
                
            except Exception as e:
                logger.error(f"❌ Error fetching {source_name}: {str(e)}")
                
        return all_news

    def _clean_html(self, text: str) -> str:
        """Remove basic HTML tags from descriptions."""
        import re
        clean = re.compile('<.*?>')
        return re.sub(clean, '', text).strip()

if __name__ == "__main__":
    # Test run
    scraper = NewsScraper()
    news = scraper.get_latest_news(limit_per_source=2)
    for article in news:
        print(f"[{article['source']}] {article['title']}")
