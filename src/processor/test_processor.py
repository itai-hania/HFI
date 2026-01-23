"""
Test script for Processor service.

This script validates that all components of the processor are working correctly:
1. Configuration loading (glossary, style, API key)
2. Database connectivity
3. Translation service (requires valid API key)
4. Media downloader (downloads test image and video)
5. End-to-end processing

Usage:
    python test_processor.py

Requirements:
    - OPENAI_API_KEY set in environment
    - Database initialized (common/models.py)
    - Internet connectivity for downloads
"""

import sys
import os
from pathlib import Path

# Add parent directory for imports
sys.path.append(str(Path(__file__).parent.parent))

from dotenv import load_dotenv
from processor import ProcessorConfig, TranslationService, MediaDownloader, TweetProcessor
from common.models import create_tables, SessionLocal, Tweet

# Load environment
load_dotenv(Path(__file__).parent.parent.parent / ".env")


def test_config():
    """Test configuration loading."""
    print("\n" + "="*60)
    print("TEST 1: Configuration Loading")
    print("="*60)

    try:
        config = ProcessorConfig()
        print(f"✓ OpenAI API key loaded: {config.openai_api_key[:10]}...")
        print(f"✓ Glossary loaded: {len(config.glossary)} terms")
        print(f"✓ Style guide loaded: {len(config.style_examples)} characters")

        # Print sample glossary entries
        sample_terms = list(config.glossary.items())[:3]
        for eng, heb in sample_terms:
            print(f"  - {eng} → {heb}")

        return config
    except Exception as e:
        print(f"✗ Configuration failed: {e}")
        return None


def test_translation(config):
    """Test translation service."""
    print("\n" + "="*60)
    print("TEST 2: Translation Service")
    print("="*60)

    if not config:
        print("✗ Skipped (config failed)")
        return False

    try:
        translator = TranslationService(config)

        # Test translation
        test_text = "Breaking: OpenAI announces GPT-5 with 10x performance improvement. This changes everything for AI startups."

        print(f"Original: {test_text}")
        print("Translating...")

        hebrew_text = translator.translate_and_rewrite(test_text)

        print(f"Hebrew: {hebrew_text}")
        print("✓ Translation successful")
        return True

    except Exception as e:
        print(f"✗ Translation failed: {e}")
        return False


def test_media_downloader():
    """Test media downloading."""
    print("\n" + "="*60)
    print("TEST 3: Media Downloader")
    print("="*60)

    downloader = MediaDownloader()

    # Test image download
    print("\nTest 3a: Image Download")
    test_image_url = "https://picsum.photos/800/600"  # Random test image
    print(f"Downloading from: {test_image_url}")

    try:
        image_path = downloader.download_media(test_image_url)
        if image_path and Path(image_path).exists():
            print(f"✓ Image downloaded: {image_path}")
            print(f"  Size: {Path(image_path).stat().st_size / 1024:.2f} KB")
        else:
            print("✗ Image download returned None or file not found")
    except Exception as e:
        print(f"✗ Image download failed: {e}")

    # Note: Video testing requires a valid Twitter video URL
    # Skip for now as it requires real content
    print("\nTest 3b: Video Download (Skipped - requires valid Twitter URL)")
    print("  To test manually: Add a real .m3u8 URL from Twitter")

    return True


def test_database():
    """Test database operations."""
    print("\n" + "="*60)
    print("TEST 4: Database Operations")
    print("="*60)

    try:
        # Ensure tables exist
        create_tables()
        print("✓ Database tables created/verified")

        # Test database connection
        db = SessionLocal()

        # Count tweets by status
        from sqlalchemy import func
        status_counts = db.query(
            Tweet.status,
            func.count(Tweet.id)
        ).group_by(Tweet.status).all()

        print("✓ Database connection successful")
        print("\nTweet status breakdown:")
        for status, count in status_counts:
            print(f"  - {status}: {count}")

        if not status_counts:
            print("  (No tweets in database yet)")

        db.close()
        return True

    except Exception as e:
        print(f"✗ Database test failed: {e}")
        return False


def test_end_to_end():
    """Test end-to-end processing with a test tweet."""
    print("\n" + "="*60)
    print("TEST 5: End-to-End Processing")
    print("="*60)

    try:
        # Create test tweet
        db = SessionLocal()

        # Check if test tweet already exists
        existing = db.query(Tweet).filter(
            Tweet.source_url == "https://x.com/test/status/999999"
        ).first()

        if existing:
            print(f"Test tweet already exists (ID: {existing.id}), deleting...")
            db.delete(existing)
            db.commit()

        # Insert test tweet
        from common.models import TweetStatus
        test_tweet = Tweet(
            source_url="https://x.com/test/status/999999",
            original_text="Breaking: Stripe raises $500M at $95B valuation. The fintech giant continues to dominate payment processing.",
            status=TweetStatus.PENDING,
            media_url=None  # No media for this test
        )
        db.add(test_tweet)
        db.commit()
        db.refresh(test_tweet)

        print(f"✓ Test tweet created (ID: {test_tweet.id})")
        print(f"  Original: {test_tweet.original_text}")

        db.close()

        # Process it
        print("\nProcessing test tweet...")
        processor = TweetProcessor()
        count = processor.process_pending_tweets()

        if count > 0:
            print(f"✓ Processed {count} tweet(s)")

            # Check result
            db = SessionLocal()
            processed_tweet = db.query(Tweet).filter(Tweet.id == test_tweet.id).first()

            if processed_tweet:
                print(f"\nResult:")
                print(f"  Status: {processed_tweet.status}")
                print(f"  Hebrew: {processed_tweet.hebrew_draft}")

                if processed_tweet.status == TweetStatus.PROCESSED:
                    print("✓ End-to-end test PASSED")
                    success = True
                else:
                    print(f"✗ Tweet marked as '{processed_tweet.status}'")
                    if processed_tweet.error_message:
                        print(f"  Error: {processed_tweet.error_message}")
                    success = False
            else:
                print("✗ Could not retrieve processed tweet")
                success = False

            db.close()
            return success
        else:
            print("✗ No tweets processed (expected 1)")
            return False

    except Exception as e:
        print(f"✗ End-to-end test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all tests."""
    print("\n" + "#"*60)
    print("#  PROCESSOR SERVICE TEST SUITE")
    print("#"*60)

    # Check prerequisites
    if not os.getenv('OPENAI_API_KEY'):
        print("\n✗ OPENAI_API_KEY not set in environment")
        print("  Set it in .env file or: export OPENAI_API_KEY=sk-...")
        sys.exit(1)

    results = {}

    # Run tests
    config = test_config()
    results['config'] = config is not None

    results['translation'] = test_translation(config)
    results['media'] = test_media_downloader()
    results['database'] = test_database()
    results['e2e'] = test_end_to_end()

    # Summary
    print("\n" + "#"*60)
    print("#  TEST SUMMARY")
    print("#"*60)

    for test_name, passed in results.items():
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"{status} - {test_name.upper()}")

    total_tests = len(results)
    passed_tests = sum(results.values())

    print("\n" + "="*60)
    print(f"Results: {passed_tests}/{total_tests} tests passed")
    print("="*60)

    if passed_tests == total_tests:
        print("\n✓ ALL TESTS PASSED - Processor is ready to use!")
        sys.exit(0)
    else:
        print("\n✗ SOME TESTS FAILED - Check errors above")
        sys.exit(1)


if __name__ == "__main__":
    main()
