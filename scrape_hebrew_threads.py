#!/usr/bin/env python3
"""
Script to scrape Hebrew threads from @FinancialEduX for style matching
"""

import asyncio
import sys
from pathlib import Path

try:
    from scraper.scraper import TwitterScraper
except ImportError:
    sys.path.insert(0, str(Path(__file__).parent / "src"))
    from scraper.scraper import TwitterScraper


THREAD_URLS = [
    "https://x.com/FinancialEduX/status/2002421843874230289",
    "https://x.com/FinancialEduX/status/1984692478901997964",
    "https://x.com/FinancialEduX/status/1952404774407569824",
    "https://x.com/FinancialEduX/status/1926645315374858669",
    "https://x.com/FinancialEduX/status/1913667990072991799",
    "https://x.com/FinancialEduX/status/1908909299948040374",
    "https://x.com/FinancialEduX/status/1903879564386034143",
    "https://x.com/FinancialEduX/status/1881623487175164160",
]


async def scrape_all_threads():
    """Scrape all Hebrew threads and format results"""

    scraper = TwitterScraper(headless=True)
    results = []

    try:
        # Ensure logged in
        await scraper.ensure_logged_in()

        # Scrape each thread
        for idx, url in enumerate(THREAD_URLS, 1):
            print(f"\n{'='*80}")
            print(f"Scraping Thread {idx}/{len(THREAD_URLS)}: {url}")
            print('='*80)

            try:
                # Fetch thread (author_only=True by default)
                thread_data = await scraper.fetch_raw_thread(url, author_only=True)

                # Extract text from tweets
                tweets = thread_data.get('tweets', [])

                if not tweets:
                    print(f"⚠️  No tweets found in thread {idx}")
                    results.append({
                        'thread_num': idx,
                        'url': url,
                        'text': '',
                        'char_count': 0,
                        'tweet_count': 0,
                        'error': 'No tweets found'
                    })
                    continue

                # Combine all tweet texts
                full_text = ""
                for tweet in tweets:
                    tweet_text = tweet.get('text', '').strip()
                    if tweet_text:
                        full_text += tweet_text + "\n\n"

                full_text = full_text.strip()

                # Count characters (excluding whitespace for accurate count)
                char_count = len(full_text)

                result = {
                    'thread_num': idx,
                    'url': url,
                    'text': full_text,
                    'char_count': char_count,
                    'tweet_count': len(tweets),
                    'author_handle': thread_data.get('author_handle', ''),
                    'author_name': thread_data.get('author_name', '')
                }

                results.append(result)

                print(f"✅ Thread {idx} scraped successfully")
                print(f"   Author: {result['author_name']} ({result['author_handle']})")
                print(f"   Tweets: {result['tweet_count']}")
                print(f"   Characters: {result['char_count']}")
                print(f"   Preview: {full_text[:100]}...")

                # Small delay between threads
                await asyncio.sleep(2)

            except Exception as e:
                print(f"❌ Error scraping thread {idx}: {e}")
                results.append({
                    'thread_num': idx,
                    'url': url,
                    'text': '',
                    'char_count': 0,
                    'tweet_count': 0,
                    'error': str(e)
                })
                continue

    finally:
        await scraper.close()

    return results


def format_output(results):
    """Format results for output file"""
    output = []
    output.append("=" * 80)
    output.append("HEBREW THREADS FROM @FinancialEduX")
    output.append("Scraped for style matching in HFI translation pipeline")
    output.append("=" * 80)
    output.append("")

    for result in results:
        output.append("-" * 80)
        output.append(f"Thread {result['thread_num']}: {result['url']}")
        output.append("-" * 80)

        if result.get('error'):
            output.append(f"❌ ERROR: {result['error']}")
            output.append("")
            continue

        output.append(f"Author: {result.get('author_name', '')} ({result.get('author_handle', '')})")
        output.append(f"Tweet Count: {result['tweet_count']}")
        output.append(f"Character Count: {result['char_count']}")
        output.append("")
        output.append("TEXT:")
        output.append(result['text'])
        output.append("")

    output.append("=" * 80)
    output.append("END OF HEBREW THREADS")
    output.append("=" * 80)

    return "\n".join(output)


async def main():
    """Main execution"""
    print("🧵 Starting Hebrew thread scraping...")
    print(f"📋 Will scrape {len(THREAD_URLS)} threads from @FinancialEduX\n")

    # Scrape all threads
    results = await scrape_all_threads()

    # Format output
    output_text = format_output(results)

    # Save to file
    output_dir = Path("/private/tmp/claude/-Users-itayy16-CursorProjects-HFI/7c28a7de-db3d-44a2-9df5-1f7cf4c22c6b/scratchpad")
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / "hebrew_threads.txt"

    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(output_text)

    print("\n" + "=" * 80)
    print("✅ SCRAPING COMPLETE")
    print("=" * 80)
    print(f"📁 Results saved to: {output_file}")
    print(f"\nSummary:")

    successful = [r for r in results if not r.get('error')]
    failed = [r for r in results if r.get('error')]

    print(f"  ✅ Successful: {len(successful)}/{len(results)}")
    print(f"  ❌ Failed: {len(failed)}/{len(results)}")

    if successful:
        total_chars = sum(r['char_count'] for r in successful)
        total_tweets = sum(r['tweet_count'] for r in successful)
        print(f"  📊 Total characters: {total_chars:,}")
        print(f"  🐦 Total tweets: {total_tweets}")

    # Print preview
    print("\n" + "=" * 80)
    print("PREVIEW OF FIRST THREAD:")
    print("=" * 80)
    if successful:
        first = successful[0]
        preview_text = first['text'][:500]
        print(preview_text)
        if len(first['text']) > 500:
            print("\n[... truncated ...]")

    print("\n✅ Done! Check the output file for full content.")


if __name__ == "__main__":
    asyncio.run(main())
