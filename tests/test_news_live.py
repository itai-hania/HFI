import sys
from pathlib import Path

try:
    from scraper.news_scraper import NewsScraper
except ImportError:
    sys.path.append(str(Path(__file__).parent / "src"))
    from scraper.news_scraper import NewsScraper

print("📰 Testing News Scraper...")
scraper = NewsScraper()
articles = scraper.get_latest_news(limit_per_source=2)

if not articles:
    print("❌ No articles found! Check internet connection or feed URLs.")
    sys.exit(1)

print(f"✅ Successfully fetched {len(articles)} articles.")
for i, article in enumerate(articles[:3]):
    print(f"   {i+1}. [{article['source']}] {article['title']}")

print("\nVerify complete.")
