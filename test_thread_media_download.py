"""
Test script for thread media download functionality.

Tests the new download_thread_media() method using the Finance_Nerd_ thread
that was analyzed via Chrome MCP.
"""

import json
import sys
from pathlib import Path

try:
    from processor.processor import MediaDownloader
except ImportError:
    sys.path.append(str(Path(__file__).parent / "src"))
    from processor.processor import MediaDownloader

def main():
    print("=" * 80)
    print("Thread Media Download Test")
    print("=" * 80)

    # Load the thread JSON from our analysis
    thread_json_path = "/tmp/thread_media_analysis.json"

    try:
        with open(thread_json_path, 'r', encoding='utf-8') as f:
            thread_data = json.load(f)

        print(f"\n✅ Loaded thread data: {thread_data.get('tweet_count', 0)} tweets")
        print(f"   Source: {thread_data.get('source_url', 'N/A')}")
        print(f"   Author: {thread_data.get('author_name', 'N/A')}")

        # Count media items
        total_media = 0
        for tweet in thread_data.get("tweets", []):
            total_media += len(tweet.get("media", []))

        print(f"   Total media items: {total_media}")

        # Initialize downloader
        print("\n" + "=" * 80)
        print("Initializing MediaDownloader...")
        print("=" * 80)

        downloader = MediaDownloader()

        print(f"✅ Images directory: {downloader.images_dir}")
        print(f"✅ Videos directory: {downloader.videos_dir}")

        # Download all media
        print("\n" + "=" * 80)
        print("Starting media download...")
        print("=" * 80)

        downloaded_media = downloader.download_thread_media(thread_data)

        # Report results
        print("\n" + "=" * 80)
        print("Download Results")
        print("=" * 80)

        print(f"\n✅ Successfully downloaded: {len(downloaded_media)} / {total_media} files")

        # Group by type
        photos = [m for m in downloaded_media if m["type"] == "photo"]
        videos = [m for m in downloaded_media if m["type"] == "video"]

        print(f"   📷 Images: {len(photos)}")
        print(f"   🎥 Videos: {len(videos)}")

        # Show details
        if downloaded_media:
            print("\nDownloaded Files:")
            print("-" * 80)
            for i, media in enumerate(downloaded_media, 1):
                emoji = "📷" if media["type"] == "photo" else "🎥"
                print(f"{i}. {emoji} Tweet {media['tweet_id']}")
                print(f"   Type: {media['type']}")
                print(f"   Local: {media['local_path']}")
                print()

        print("=" * 80)
        print("Test Complete!")
        print("=" * 80)

    except FileNotFoundError:
        print(f"\n❌ Error: Thread JSON not found at {thread_json_path}")
        print("   Please ensure the file exists from the Chrome MCP analysis.")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
