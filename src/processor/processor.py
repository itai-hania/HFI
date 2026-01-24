"""
Processor Service for HFI Application

This module handles:
1. Translation from English to Hebrew using OpenAI GPT-4o
2. Media downloading (HLS videos via yt-dlp, images via requests)
3. Processing pending tweets from the database

Architecture Decisions:
-----------------------
1. OpenAI GPT-4o for Translation:
   - Provides "transcreation" not literal translation
   - Understands financial context and terminology
   - Can adapt to specific writing styles
   - Better than traditional translation APIs for creative content

2. Glossary-based Translation:
   - Pre-loads financial term mappings to ensure consistency
   - Prevents mistranslation of technical jargon
   - User can customize terminology over time

3. Style-guided Translation:
   - Injects user's writing style examples into prompt
   - Maintains consistent voice across all content
   - GPT-4o learns tone, structure, and language patterns

4. Media Download Strategy:
   - yt-dlp for videos: Handles HLS streams, m3u8 playlists, complex formats
   - requests for images: Simple, lightweight, no external dependencies
   - Unique filenames using timestamp + hash to avoid collisions

5. Error Handling Philosophy:
   - Translation failures mark tweet as 'failed' (critical path)
   - Media download failures log warning but continue (non-critical)
   - All errors stored in database for debugging
   - Graceful degradation: partial success is acceptable

6. Database Transaction Pattern:
   - Explicit commit/rollback for each tweet
   - Prevents data loss if processing crashes mid-batch
   - Updated timestamp tracking for audit trail
"""

import os
import json
import hashlib
import subprocess
import requests
import re
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Tuple, List
import logging
import sys

# Language detection for skipping already-Hebrew content
try:
    from langdetect import detect, LangDetectException
    HAS_LANGDETECT = True
except ImportError:
    HAS_LANGDETECT = False

# Add parent directory to path for common modules
sys.path.append(str(Path(__file__).parent.parent))

from openai import OpenAI
from sqlalchemy.orm import Session
from common.models import SessionLocal, Tweet, TweetStatus, create_tables

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Configuration paths
PROJECT_ROOT = Path(__file__).parent.parent.parent
CONFIG_DIR = PROJECT_ROOT / "config"
DATA_DIR = PROJECT_ROOT / "data"
MEDIA_DIR = DATA_DIR / "media"

# Ensure directories exist
MEDIA_DIR.mkdir(parents=True, exist_ok=True)


class ProcessorConfig:
    """Configuration holder for the processor service."""

    def __init__(self):
        self.openai_api_key = os.getenv('OPENAI_API_KEY')
        if not self.openai_api_key:
            raise ValueError("OPENAI_API_KEY environment variable is required")

        self.glossary_path = CONFIG_DIR / "glossary.json"
        self.style_path = CONFIG_DIR / "style.txt"

        # Load configuration files
        self.glossary = self._load_glossary()
        self.style_examples = self._load_style()

        # OpenAI client
        self.openai_client = OpenAI(api_key=self.openai_api_key)

        logger.info(f"Processor configured with {len(self.glossary)} glossary terms")

    def _load_glossary(self) -> Dict[str, str]:
        """Load financial terminology glossary from JSON file."""
        if not self.glossary_path.exists():
            logger.warning(f"Glossary not found at {self.glossary_path}, using empty dict")
            return {}

        try:
            with open(self.glossary_path, 'r', encoding='utf-8') as f:
                glossary = json.load(f)
            logger.info(f"Loaded {len(glossary)} terms from glossary")
            return glossary
        except Exception as e:
            logger.error(f"Failed to load glossary: {e}")
            return {}

    def _load_style(self) -> str:
        """Load writing style examples from text file."""
        if not self.style_path.exists():
            logger.warning(f"Style guide not found at {self.style_path}")
            return "Write in a professional, engaging style suitable for financial news."

        try:
            with open(self.style_path, 'r', encoding='utf-8') as f:
                style_content = f.read()
            logger.info(f"Loaded style guide ({len(style_content)} chars)")
            return style_content
        except Exception as e:
            logger.error(f"Failed to load style guide: {e}")
            return "Write in a professional, engaging style suitable for financial news."


class TranslationService:
    """Handles Hebrew translation using OpenAI GPT-4o with transcreation approach."""

    # Tech terms to keep in English (not translate)
    KEEP_ENGLISH = {
        'API', 'ML', 'AI', 'GPT', 'LLM', 'NFT', 'DeFi', 'ETF', 'IPO', 'VC',
        'CEO', 'CTO', 'CFO', 'COO', 'SaaS', 'B2B', 'B2C', 'ROI', 'KPI',
        'FOMO', 'HODL', 'DCA', 'ATH', 'FUD', 'DAO', 'DEX', 'CEX',
        'startup', 'fintech', 'blockchain', 'crypto', 'bitcoin', 'ethereum',
        'tweet', 'thread', 'retweet', 'like', 'follower'
    }

    def __init__(self, config: ProcessorConfig):
        self.config = config
        self.client = config.openai_client

    def is_hebrew(self, text: str) -> bool:
        """Check if text is already primarily Hebrew."""
        if not text:
            return False

        # Method 1: Use langdetect if available
        if HAS_LANGDETECT:
            try:
                detected = detect(text)
                if detected == 'he':
                    return True
            except LangDetectException:
                pass

        # Method 2: Check Hebrew character ratio
        hebrew_chars = sum(1 for c in text if '\u0590' <= c <= '\u05FF')
        alpha_chars = sum(1 for c in text if c.isalpha())
        if alpha_chars > 0:
            ratio = hebrew_chars / alpha_chars
            return ratio > 0.5

        return False

    def validate_hebrew_output(self, text: str) -> Tuple[bool, str]:
        """
        Validate that output is primarily Hebrew.

        Args:
            text: Output text to validate

        Returns:
            Tuple of (is_valid, reason)
        """
        if not text:
            return False, "Empty output"

        hebrew_chars = sum(1 for c in text if '\u0590' <= c <= '\u05FF')
        alpha_chars = sum(1 for c in text if c.isalpha())

        if alpha_chars == 0:
            return False, "No alphabetic characters"

        ratio = hebrew_chars / alpha_chars

        if ratio < 0.5:
            return False, f"Hebrew ratio too low: {ratio:.1%}"

        return True, ""

    def extract_preservables(self, text: str) -> Dict[str, List[str]]:
        """Extract URLs, @mentions, and hashtags that should be preserved exactly."""
        return {
            'urls': re.findall(r'https?://\S+', text),
            'mentions': re.findall(r'@\w+', text),
            'hashtags': re.findall(r'#\w+', text)
        }

    def translate_and_rewrite(self, text: str, max_retries: int = 2) -> str:
        """
        Translate and rewrite English content to Hebrew with transcreation.

        Key improvements:
        - Skips already-Hebrew content
        - Validates output is ≥50% Hebrew
        - Retries on validation failure
        - Preserves URLs, @mentions, hashtags exactly
        - Keeps tech terms in English

        Args:
            text: English tweet content to translate
            max_retries: Number of retry attempts if validation fails

        Returns:
            Hebrew transcreated content

        Raises:
            Exception: If OpenAI API call fails after retries
        """
        # Skip if already Hebrew
        if self.is_hebrew(text):
            logger.info("Text already Hebrew, skipping translation")
            return text

        # Extract items to preserve
        preservables = self.extract_preservables(text)

        # Build glossary string
        glossary_str = "\n".join([
            f"- {eng}: {heb}"
            for eng, heb in self.config.glossary.items()
        ])

        # Terms to keep in English
        keep_english_str = ", ".join(sorted(self.KEEP_ENGLISH))

        # System prompt with strict rules
        system_prompt = f"""You are an expert Hebrew financial content creator specializing in fintech and tech news.

Your task is to TRANSCREATE (not just translate) English content into Hebrew.

CRITICAL RULES - FOLLOW EXACTLY:

1. KEEP THESE TERMS IN ENGLISH (do NOT translate):
   {keep_english_str}

2. PRESERVE EXACTLY (copy as-is):
   - All URLs: {', '.join(preservables['urls']) or 'none'}
   - All @mentions: {', '.join(preservables['mentions']) or 'none'}
   - All #hashtags: {', '.join(preservables['hashtags']) or 'none'}
   - All numbers and company names

3. TWITTER-SPECIFIC TERMS:
   - tweet = ציוץ
   - thread = שרשור
   - retweet = ריטוויט

4. PUNCTUATION:
   - NO dashes for punctuation
   - Use commas, periods, parentheses instead

5. GLOSSARY (use these term translations):
{glossary_str}

6. STYLE GUIDE:
{self.config.style_examples}

7. OUTPUT REQUIREMENTS:
   - Output ONLY Hebrew content
   - Keep structure (bullets, line breaks)
   - 1-2 emojis maximum
   - No explanations or metadata
   - At least 50% of letters must be Hebrew"""

        for attempt in range(max_retries + 1):
            try:
                logger.info(f"Translating text (attempt {attempt + 1}): {text[:100]}...")

                response = self.client.chat.completions.create(
                    model="gpt-4o",
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": f"Transcreate this to Hebrew:\n\n{text}"}
                    ],
                    temperature=0.1 if attempt > 0 else 0.7,  # Lower temp on retry
                    max_tokens=1000,
                    top_p=0.9
                )

                hebrew_text = response.choices[0].message.content.strip()

                # Validate output
                is_valid, reason = self.validate_hebrew_output(hebrew_text)

                if is_valid:
                    logger.info(f"Translation successful: {hebrew_text[:100]}...")
                    return hebrew_text
                else:
                    logger.warning(f"Validation failed: {reason}")
                    if attempt < max_retries:
                        # Retry with explicit instruction
                        system_prompt += f"\n\nPREVIOUS ATTEMPT FAILED: {reason}. Please ensure output is primarily in Hebrew."
                    else:
                        # Return anyway on last attempt
                        logger.warning(f"Returning unvalidated result after {max_retries + 1} attempts")
                        return hebrew_text

            except Exception as e:
                logger.error(f"Translation failed (attempt {attempt + 1}): {e}")
                if attempt == max_retries:
                    raise Exception(f"OpenAI translation error after {max_retries + 1} attempts: {str(e)}")

        return text  # Fallback to original

    def translate_long_text(self, texts: List[str]) -> str:
        """
        Translate multiple tweets as one coherent text (for context).

        This concatenates all tweets into one text for translation,
        preserving context across the thread.

        Args:
            texts: List of tweet texts

        Returns:
            Single translated text (can be split later if needed)
        """
        if not texts:
            return ""

        # Concatenate with separators
        combined = "\n\n---\n\n".join(texts)

        return self.translate_and_rewrite(combined)


class MediaDownloader:
    """Handles downloading media files from URLs (videos and images)."""

    def __init__(self):
        self.media_dir = MEDIA_DIR

    def download_media(self, media_url: str) -> Optional[str]:
        """
        Download media from URL and save to local storage.

        Architecture Decision: Two different strategies based on media type:
        - Videos (HLS/m3u8): Use yt-dlp for complex streaming formats
        - Images: Use requests library for simple HTTP downloads

        Args:
            media_url: URL of media to download

        Returns:
            Local file path if successful, None if failed

        Note: Failures are logged but don't raise exceptions (non-critical path)
        """
        if not media_url:
            return None

        try:
            # Determine media type from URL
            url_lower = media_url.lower()

            if '.m3u8' in url_lower or 'video' in url_lower:
                return self._download_video(media_url)
            else:
                # Assume image for other URLs
                return self._download_image(media_url)

        except Exception as e:
            logger.warning(f"Media download failed for {media_url}: {e}")
            return None

    def _download_video(self, video_url: str) -> Optional[str]:
        """
        Download video using yt-dlp (handles HLS, m3u8, and other formats).

        Why yt-dlp?
        - Handles complex streaming formats (HLS, DASH, m3u8)
        - Automatic format selection (best quality)
        - Robust error handling and retries
        - Used by millions, well-maintained

        Args:
            video_url: URL of video to download

        Returns:
            Local file path if successful, None if failed
        """
        # Generate unique filename
        url_hash = hashlib.md5(video_url.encode()).hexdigest()[:10]
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_filename = f"video_{timestamp}_{url_hash}.mp4"
        output_path = self.media_dir / output_filename

        logger.info(f"Downloading video from {video_url}")

        try:
            # Use yt-dlp command-line tool
            # -f best: Download best quality
            # --no-playlist: Don't download playlists
            # --no-warnings: Cleaner output
            # -o: Output path
            subprocess.run([
                'yt-dlp',
                '-f', 'best',
                '--no-playlist',
                '--no-warnings',
                video_url,
                '-o', str(output_path)
            ], check=True, capture_output=True, timeout=300)  # 5 minute timeout

            if output_path.exists():
                logger.info(f"Video downloaded successfully: {output_path}")
                return str(output_path)
            else:
                logger.warning(f"Video download completed but file not found: {output_path}")
                return None

        except subprocess.TimeoutExpired:
            logger.error(f"Video download timed out after 5 minutes: {video_url}")
            return None
        except subprocess.CalledProcessError as e:
            logger.error(f"yt-dlp failed: {e.stderr.decode() if e.stderr else str(e)}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error downloading video: {e}")
            return None

    def _download_image(self, image_url: str) -> Optional[str]:
        """
        Download image using requests library.

        Simple HTTP download for images. Fast and lightweight.

        Args:
            image_url: URL of image to download

        Returns:
            Local file path if successful, None if failed
        """
        # Detect file extension from URL
        extension = 'jpg'
        if '.png' in image_url.lower():
            extension = 'png'
        elif '.jpeg' in image_url.lower():
            extension = 'jpeg'
        elif '.gif' in image_url.lower():
            extension = 'gif'
        elif '.webp' in image_url.lower():
            extension = 'webp'

        # Generate unique filename
        url_hash = hashlib.md5(image_url.encode()).hexdigest()[:10]
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_filename = f"image_{timestamp}_{url_hash}.{extension}"
        output_path = self.media_dir / output_filename

        logger.info(f"Downloading image from {image_url}")

        try:
            # Download with timeout and user agent
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            response = requests.get(image_url, headers=headers, timeout=30, stream=True)
            response.raise_for_status()

            # Save to file
            with open(output_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)

            logger.info(f"Image downloaded successfully: {output_path}")
            return str(output_path)

        except requests.RequestException as e:
            logger.error(f"Image download failed: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error downloading image: {e}")
            return None


class TweetProcessor:
    """Main processor that orchestrates translation and media download."""

    def __init__(self):
        self.config = ProcessorConfig()
        self.translator = TranslationService(self.config)
        self.downloader = MediaDownloader()

    def process_pending_tweets(self) -> int:
        """
        Process all pending tweets in the database.

        For each pending tweet:
        1. Translate text to Hebrew
        2. Download media if URL exists
        3. Update database with results
        4. Mark as 'processed' or 'failed'

        Returns:
            Number of tweets successfully processed

        Architecture Note: Each tweet is processed in its own transaction
        for atomicity. If one fails, others continue.
        """
        db: Session = SessionLocal()
        processed_count = 0

        try:
            # Query all pending tweets
            pending_tweets = db.query(Tweet).filter(Tweet.status == TweetStatus.PENDING).all()

            if not pending_tweets:
                logger.info("No pending tweets to process")
                return 0

            logger.info(f"Found {len(pending_tweets)} pending tweets to process")

            for tweet in pending_tweets:
                try:
                    success = self._process_single_tweet(db, tweet)
                    if success:
                        processed_count += 1
                        logger.info(f"Successfully processed tweet {tweet.id}")
                    else:
                        logger.warning(f"Failed to process tweet {tweet.id}")

                except Exception as e:
                    logger.error(f"Error processing tweet {tweet.id}: {e}")
                    # Mark as failed
                    tweet.status = TweetStatus.FAILED
                    tweet.error_message = str(e)
                    tweet.updated_at = datetime.utcnow()
                    db.commit()

            logger.info(f"Batch complete: {processed_count}/{len(pending_tweets)} tweets processed")
            return processed_count

        except Exception as e:
            logger.error(f"Error in process_pending_tweets: {e}")
            db.rollback()
            return processed_count

        finally:
            db.close()

    def _process_single_tweet(self, db: Session, tweet: Tweet) -> bool:
        """
        Process a single tweet (translate + download media).

        Args:
            db: Database session
            tweet: Tweet object to process

        Returns:
            True if successful, False otherwise
        """
        logger.info(f"Processing tweet {tweet.id}: {tweet.original_text[:50]}...")

        try:
            # Step 1: Translate text
            hebrew_text = self.translator.translate_and_rewrite(tweet.original_text)
            tweet.hebrew_draft = hebrew_text

            # Step 2: Download media (if exists)
            media_path = None
            if tweet.media_url:
                media_path = self.downloader.download_media(tweet.media_url)
                if media_path:
                    tweet.media_path = media_path
                    logger.info(f"Media downloaded: {media_path}")
                else:
                    logger.warning(f"Media download failed, continuing without media")

            # Step 3: Update tweet status
            tweet.status = TweetStatus.PROCESSED
            tweet.updated_at = datetime.utcnow()
            tweet.error_message = None  # Clear any previous errors

            # Commit transaction
            db.commit()

            logger.info(f"Tweet {tweet.id} processed successfully")
            return True

        except Exception as e:
            logger.error(f"Failed to process tweet {tweet.id}: {e}")
            # Mark as failed but commit the error state
            tweet.status = TweetStatus.FAILED
            tweet.error_message = str(e)
            tweet.updated_at = datetime.utcnow()
            db.commit()
            return False


def main():
    """Entry point for running processor as standalone service."""
    logger.info("Initializing Processor Service")

    # Ensure database exists
    create_tables()

    # Create processor instance
    processor = TweetProcessor()

    # Process pending tweets
    count = processor.process_pending_tweets()
    logger.info(f"Processing complete: {count} tweets processed")


if __name__ == "__main__":
    main()
