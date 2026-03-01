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
import shutil
import platform
import requests
import re
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Tuple, List
import logging

# Language detection for skipping already-Hebrew content
try:
    from langdetect import detect, LangDetectException
    HAS_LANGDETECT = True
except ImportError:
    HAS_LANGDETECT = False

from urllib.parse import urlparse
from openai import OpenAI
from sqlalchemy.orm import Session
from common.models import SessionLocal, Tweet, TweetStatus, StyleExample, create_tables
from common.openai_client import get_openai_client
from processor.prompt_builder import (
    KEEP_ENGLISH,
    extract_topic_keywords,
    build_glossary_section,
    build_relevant_glossary_section,
    validate_hebrew_output,
    build_style_section,
    load_style_examples_from_db,
    get_completion_params,
    call_with_retry,
)

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

        self.openai_model = os.getenv('OPENAI_MODEL')
        if not self.openai_model:
            raise ValueError("OPENAI_MODEL environment variable is required")

        # Temperature is now optional - some models (like gpt-5-nano) don't support it
        temp_str = os.getenv('OPENAI_TEMPERATURE')
        if temp_str is not None and temp_str.strip():
            self.openai_temperature = float(temp_str)
        else:
            self.openai_temperature = None  # Will use model default

        self.glossary_path = CONFIG_DIR / "glossary.json"
        self.style_path = CONFIG_DIR / "style.txt"

        self.glossary = self._load_glossary()
        self.style_examples = self._load_style()

        self.openai_client = get_openai_client()

        logger.info(f"Processor configured with:")
        logger.info(f"  - Model: {self.openai_model}")
        logger.info(f"  - Temperature: {self.openai_temperature if self.openai_temperature else 'default'}")
        logger.info(f"  - Glossary terms: {len(self.glossary)}")

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

    # Re-export for backward compatibility (tests reference translator.KEEP_ENGLISH)
    KEEP_ENGLISH = KEEP_ENGLISH

    # TTL cache for style examples (5 minutes)
    _STYLE_CACHE_TTL = 300

    def __init__(self, config: ProcessorConfig):
        self.config = config
        self.client = config.openai_client
        self._style_cache = {}  # key: frozenset(tags) -> (examples, timestamp)

    def _cached_style_section(self, source_text: Optional[str] = None) -> str:
        """
        Build style section with TTL-cached DB examples.

        Wraps prompt_builder.build_style_section with a 5-minute cache
        to avoid querying DB on every translation call.
        """
        import time as _time
        source_tags = extract_topic_keywords(source_text) if source_text else None
        cache_key = frozenset(source_tags) if source_tags else frozenset()
        cached = self._style_cache.get(cache_key)
        if cached:
            examples, ts = cached
            if _time.time() - ts < self._STYLE_CACHE_TTL:
                if examples:
                    examples_text = ""
                    for i, example in enumerate(examples, 1):
                        truncated = example[:800] + "..." if len(example) > 800 else example
                        examples_text += f"\n--- Example {i} ---\n{truncated}\n"
                    return f"""STYLE EXAMPLES (match this writing style):
{examples_text}

KEY STYLE REQUIREMENTS:
- Match the tone, vocabulary, and sentence structure from the examples above
- Use similar expressions and phrasing patterns
- Maintain the same level of formality"""
                else:
                    return f"STYLE GUIDE:\n{self.config.style_examples}"

        db_examples = load_style_examples_from_db(limit=5, source_tags=source_tags)
        self._style_cache[cache_key] = (db_examples, _time.time())

        if db_examples:
            examples_text = ""
            for i, example in enumerate(db_examples, 1):
                truncated = example[:800] + "..." if len(example) > 800 else example
                examples_text += f"\n--- Example {i} ---\n{truncated}\n"
            return f"""STYLE EXAMPLES (match this writing style):
{examples_text}

KEY STYLE REQUIREMENTS:
- Match the tone, vocabulary, and sentence structure from the examples above
- Use similar expressions and phrasing patterns
- Maintain the same level of formality"""
        else:
            return f"STYLE GUIDE:\n{self.config.style_examples}"

    def _get_completion_params(self, system_prompt: str, user_content: str) -> dict:
        """Build API call parameters, delegating to prompt_builder."""
        return get_completion_params(
            self.config.openai_model, system_prompt, user_content,
            temperature=self.config.openai_temperature
        )

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
        """Validate that output is primarily Hebrew. Delegates to prompt_builder."""
        return validate_hebrew_output(text)

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

        glossary_str = build_relevant_glossary_section(self.config.glossary, text)
        keep_english_str = ", ".join(sorted(KEEP_ENGLISH))

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

6. {self._cached_style_section(source_text=text)}

7. OUTPUT REQUIREMENTS:
   - Output ONLY Hebrew content
   - Keep structure (bullets, line breaks)
   - 1-2 emojis maximum
   - No explanations or metadata
   - At least 50% of letters must be Hebrew"""

        logger.info(f"Translating text: {text[:100]}...")
        params = self._get_completion_params(
            system_prompt,
            f"Transcreate this to Hebrew:\n\n{text}"
        )

        try:
            result = call_with_retry(
                self.client, params, max_retries=max_retries,
                validator_fn=validate_hebrew_output
            )
            logger.info(f"Translation successful: {result[:100]}...")
            return result
        except Exception as e:
            raise Exception(f"OpenAI translation error after {max_retries + 1} attempts: {str(e)}")

        return text  # Fallback to original

    def translate_text(self, text: str) -> str:
        """Alias for backward compatibility with dashboard."""
        return self.translate_and_rewrite(text)

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

    def translate_thread_consolidated(self, tweets: List[Dict], max_retries: int = 2) -> str:
        """
        Translate entire thread as one flowing narrative in Hebrew.

        This method treats the thread as a SINGLE story to be rewritten,
        not as separate tweets to be concatenated. The result is a cohesive
        Hebrew post without thread markers (1/5, 2/5) or separators.

        Args:
            tweets: List of tweet dicts with 'text', 'author_handle', etc.
                   Expected structure: [{'text': '...', 'author_handle': '@user', ...}, ...]
            max_retries: Number of retry attempts if validation fails

        Returns:
            Single flowing Hebrew post (no thread markers or separators)

        Example:
            >>> tweets = [
            ...     {'text': 'Breaking: Bitcoin hits new ATH', 'author_handle': '@crypto'},
            ...     {'text': 'This is significant because...', 'author_handle': '@crypto'},
            ...     {'text': 'Market implications are huge', 'author_handle': '@crypto'}
            ... ]
            >>> translation = translator.translate_thread_consolidated(tweets)
            >>> print(translation)
            'ביטקוין הגיע לשיא חדש. זה משמעותי כי...'
        """
        if not tweets:
            return ""

        # Extract text from all tweets
        texts = [t.get('text', '') for t in tweets if t.get('text')]

        if not texts:
            logger.warning("No text found in tweets")
            return ""

        # Combine into single context
        combined_text = "\n\n".join(texts)

        # Skip if already Hebrew
        if self.is_hebrew(combined_text):
            logger.info("Thread already Hebrew, skipping translation")
            return combined_text

        # Extract items to preserve from ALL tweets
        all_preservables = {
            'urls': [],
            'mentions': [],
            'hashtags': []
        }
        for text in texts:
            preservables = self.extract_preservables(text)
            all_preservables['urls'].extend(preservables['urls'])
            all_preservables['mentions'].extend(preservables['mentions'])
            all_preservables['hashtags'].extend(preservables['hashtags'])

        combined_text = " ".join(texts)
        glossary_str = build_relevant_glossary_section(self.config.glossary, combined_text) or "No specific terms"
        keep_english_str = ", ".join(sorted(KEEP_ENGLISH))

        system_prompt = f"""You are an expert Hebrew financial content creator specializing in fintech and tech news.

Your task is to TRANSCREATE (not just translate) an English Twitter THREAD into Hebrew.

CRITICAL - THIS IS A THREAD, NOT A SINGLE TWEET:
- This is {len(tweets)} tweets by the same author forming ONE story
- Rewrite as a SINGLE FLOWING HEBREW POST
- NO thread markers (1/5, 2/5, 1/n, etc.)
- NO separators (---, ===, •••)
- NO "part 1", "part 2" references
- Combine into ONE cohesive narrative
- Use natural Hebrew paragraph structure
- Preserve ALL key information and insights
- Keep it concise but complete

OUTPUT REQUIREMENTS:
1. KEEP THESE TERMS IN ENGLISH (do NOT translate):
   {keep_english_str}

2. PRESERVE EXACTLY (copy as-is):
   - URLs: {', '.join(all_preservables['urls'][:5]) or 'none'}
   - @mentions: {', '.join(all_preservables['mentions'][:5]) or 'none'}
   - #hashtags: {', '.join(all_preservables['hashtags'][:5]) or 'none'}
   - Numbers, percentages, company names

3. GLOSSARY (use these translations):
{glossary_str}

4. {self._cached_style_section(source_text=combined_text)}

5. FORMAT:
   - Output ONLY Hebrew content
   - Use paragraph breaks naturally (not per original tweet)
   - 1-2 emojis maximum
   - No explanations or metadata
   - At least 50% of letters must be Hebrew

Remember: Create ONE unified Hebrew post that tells the complete story."""

        logger.info(f"Translating thread ({len(tweets)} tweets) as consolidated narrative")

        user_message = f"""Original thread ({len(tweets)} tweets):

{combined_text}

Transcreate this entire thread into ONE flowing Hebrew post."""

        params = self._get_completion_params(system_prompt, user_message)

        try:
            result = call_with_retry(
                self.client, params, max_retries=max_retries,
                validator_fn=validate_hebrew_output
            )
            logger.info(f"Thread translation successful: {result[:100]}...")
            return result
        except Exception as e:
            raise Exception(f"OpenAI translation error after {max_retries + 1} attempts: {str(e)}")

        return combined_text  # Fallback

    def translate_thread_separate(self, tweets: List[Dict], max_retries: int = 2) -> List[str]:
        """
        Translate each tweet in a thread with context of previous tweets.

        This method maintains thread structure (separate tweets) but provides
        context from earlier tweets to ensure continuity and avoid repetition.

        Args:
            tweets: List of tweet dicts with 'text', 'author_handle', etc.
            max_retries: Number of retry attempts per tweet if validation fails

        Returns:
            List of Hebrew translations (one per tweet, in same order)

        Example:
            >>> tweets = [
            ...     {'text': 'Breaking news about fintech', ...},
            ...     {'text': 'More details here...', ...}
            ... ]
            >>> translations = translator.translate_thread_separate(tweets)
            >>> len(translations) == 2
            True
        """
        if not tweets:
            return []

        results = []
        context_texts = []  # Store original English context

        logger.info(f"Translating thread ({len(tweets)} tweets) as separate tweets with context")

        for idx, tweet in enumerate(tweets):
            tweet_text = tweet.get('text', '')

            if not tweet_text:
                logger.warning(f"Tweet {idx+1} has no text, skipping")
                results.append("")
                continue

            # Skip if already Hebrew
            if self.is_hebrew(tweet_text):
                logger.info(f"Tweet {idx+1} already Hebrew, using as-is")
                results.append(tweet_text)
                context_texts.append(f"{idx+1}. {tweet_text}")
                continue

            context_str = "\n".join(context_texts) if context_texts else "This is the first tweet in the thread."
            preservables = self.extract_preservables(tweet_text)
            glossary_str = build_relevant_glossary_section(self.config.glossary, tweet_text) or "No specific terms"
            keep_english_str = ", ".join(sorted(KEEP_ENGLISH))

            system_prompt = f"""You are an expert Hebrew financial content creator.

You are translating tweet {idx+1}/{len(tweets)} from a Twitter thread.

CONTEXT - PREVIOUS TWEETS IN THIS THREAD:
{context_str}

CURRENT TWEET TO TRANSLATE:
{tweet_text}

CRITICAL INSTRUCTIONS:
1. This tweet is part of a larger thread
2. Consider the context from previous tweets
3. Avoid repeating information already mentioned
4. Maintain narrative continuity
5. Use references appropriately ("this", "therefore", etc.)

OUTPUT REQUIREMENTS:
1. KEEP IN ENGLISH: {keep_english_str}
2. PRESERVE: URLs={', '.join(preservables['urls']) or 'none'}, @mentions={', '.join(preservables['mentions']) or 'none'}, #hashtags={', '.join(preservables['hashtags']) or 'none'}
3. GLOSSARY:
{glossary_str}
4. {self._cached_style_section(source_text=tweet_text)}
5. Output ONLY Hebrew content (at least 50% Hebrew characters)

Transcreate this tweet to Hebrew:"""

            params = self._get_completion_params(system_prompt, tweet_text)

            try:
                logger.info(f"Translating tweet {idx+1}/{len(tweets)}")
                hebrew_text = call_with_retry(
                    self.client, params, max_retries=max_retries,
                    validator_fn=validate_hebrew_output
                )
                logger.info(f"Tweet {idx+1} translated: {hebrew_text[:80]}...")
                results.append(hebrew_text)
                context_texts.append(f"{idx+1}. {tweet_text}")
            except Exception as e:
                logger.error(f"Failed to translate tweet {idx+1} after {max_retries + 1} attempts: {e}")
                results.append(tweet_text)  # Fallback to original
                context_texts.append(f"{idx+1}. {tweet_text}")

        logger.info(f"Thread separate translation complete: {len(results)} tweets translated")
        return results


class MediaDownloader:
    """Handles downloading media files from URLs (videos and images)."""

    # Allowed domains for media downloads
    ALLOWED_MEDIA_DOMAINS = {
        'twimg.com', 'video.twimg.com', 'pbs.twimg.com', 'abs.twimg.com',
        'twitter.com', 'x.com',
    }

    # Allowed image extensions
    ALLOWED_IMAGE_EXTENSIONS = {'jpg', 'jpeg', 'png', 'gif', 'webp'}

    # Size limits
    MAX_IMAGE_SIZE = 10 * 1024 * 1024  # 10MB
    MAX_VIDEO_SIZE = 100 * 1024 * 1024  # 100MB

    def __init__(self):
        self.media_dir = MEDIA_DIR
        # Create subdirectories for organized storage
        self.images_dir = self.media_dir / "images"
        self.videos_dir = self.media_dir / "videos"
        self.images_dir.mkdir(parents=True, exist_ok=True)
        self.videos_dir.mkdir(parents=True, exist_ok=True)

    def _is_allowed_domain(self, url: str) -> bool:
        """Check if URL domain is in the allow list."""
        try:
            parsed = urlparse(url)
            if parsed.scheme.lower() != 'https':
                return False
            hostname = (parsed.hostname or '').lower()
            if not hostname:
                return False
            for domain in self.ALLOWED_MEDIA_DOMAINS:
                if hostname == domain or hostname.endswith('.' + domain):
                    return True
            return False
        except Exception:
            return False

    def _find_yt_dlp(self) -> Optional[str]:
        """
        Find yt-dlp executable in a cross-platform way.
        
        Uses shutil.which() for PATH search (works on Windows, macOS, Linux),
        then falls back to common installation locations based on platform.
        
        Returns:
            Path to yt-dlp if found, None otherwise
        """
        yt_dlp = shutil.which('yt-dlp')
        if yt_dlp:
            return yt_dlp
        
        if platform.system() == 'Windows':
            additional_paths = [
                Path.home() / 'AppData' / 'Local' / 'Programs' / 'Python' / 'Python39' / 'Scripts' / 'yt-dlp.exe',
                Path.home() / 'AppData' / 'Local' / 'Programs' / 'Python' / 'Python310' / 'Scripts' / 'yt-dlp.exe',
                Path.home() / 'AppData' / 'Local' / 'Programs' / 'Python' / 'Python311' / 'Scripts' / 'yt-dlp.exe',
                Path.home() / 'AppData' / 'Local' / 'Programs' / 'Python' / 'Python312' / 'Scripts' / 'yt-dlp.exe',
                Path.home() / 'AppData' / 'Roaming' / 'Python' / 'Python39' / 'Scripts' / 'yt-dlp.exe',
                Path.home() / 'AppData' / 'Roaming' / 'Python' / 'Python310' / 'Scripts' / 'yt-dlp.exe',
                Path.home() / 'AppData' / 'Roaming' / 'Python' / 'Python311' / 'Scripts' / 'yt-dlp.exe',
                Path.home() / 'AppData' / 'Roaming' / 'Python' / 'Python312' / 'Scripts' / 'yt-dlp.exe',
                Path('C:/yt-dlp/yt-dlp.exe'),
            ]
        else:
            additional_paths = [
                Path('/usr/local/bin/yt-dlp'),
                Path('/usr/bin/yt-dlp'),
                Path.home() / '.local' / 'bin' / 'yt-dlp',
                Path.home() / 'Library' / 'Python' / '3.9' / 'bin' / 'yt-dlp',
                Path.home() / 'Library' / 'Python' / '3.10' / 'bin' / 'yt-dlp',
                Path.home() / 'Library' / 'Python' / '3.11' / 'bin' / 'yt-dlp',
                Path.home() / 'Library' / 'Python' / '3.12' / 'bin' / 'yt-dlp',
            ]
        
        for path in additional_paths:
            if path.exists():
                return str(path)
        
        return None


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

        if not self._is_allowed_domain(media_url):
            logger.warning(f"Media download blocked — domain not allowed: {media_url[:100]}")
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

    def _extract_video_id_from_thumbnail(self, thumbnail_url: str) -> Optional[str]:
        """
        Extract video ID from X/Twitter video thumbnail URL.

        Thumbnail URL format: https://pbs.twimg.com/amplify_video_thumb/{VIDEO_ID}/img/{HASH}.jpg
        Returns: VIDEO_ID (e.g., "1947778747421147138")
        """
        match = re.search(r'amplify_video_thumb/(\d+)/', thumbnail_url)
        if match:
            return match.group(1)
        return None

    def _construct_video_url_from_id(self, video_id: str) -> str:
        """
        Construct high-quality video URL from video ID.

        Based on X network analysis, videos are at:
        https://video.twimg.com/amplify_video/{VIDEO_ID}/vid/avc1/0/0/{RESOLUTION}/{HASH}.mp4

        Since we don't know the hash, we'll use yt-dlp with a constructed base URL
        that yt-dlp can follow to find the actual video.
        """
        return f"https://video.twimg.com/amplify_video/{video_id}/pl/playlist.m3u8"

    def _download_video(self, video_url: str) -> Optional[str]:
        """
        Download video using yt-dlp (handles HLS, m3u8, and other formats).

        Why yt-dlp?
        - Handles complex streaming formats (HLS, DASH, m3u8)
        - Automatic format selection (best quality)
        - Robust error handling and retries
        - Used by millions, well-maintained

        Special handling for X/Twitter videos:
        - If URL is a thumbnail, extract video ID and construct m3u8 playlist URL
        - yt-dlp will automatically find and download the best quality MP4

        Args:
            video_url: URL of video to download (can be thumbnail or direct video URL)

        Returns:
            Local file path if successful, None if failed
        """
        # Domain whitelist check before passing to yt-dlp subprocess
        if not self._is_allowed_domain(video_url):
            logger.warning(f"Video download blocked — domain not allowed: {video_url[:100]}")
            return None

        # Check if this is an X video thumbnail URL
        if "amplify_video_thumb" in video_url:
            video_id = self._extract_video_id_from_thumbnail(video_url)
            if video_id:
                logger.info(f"Detected X video thumbnail, extracting video ID: {video_id}")
                video_url = self._construct_video_url_from_id(video_id)
                logger.info(f"Constructed m3u8 playlist URL: {video_url}")
            else:
                logger.warning(f"Failed to extract video ID from thumbnail URL: {video_url}")
                return None

        # Generate unique filename
        url_hash = hashlib.md5(video_url.encode()).hexdigest()[:10]
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_filename = f"video_{timestamp}_{url_hash}.mp4"
        output_path = self.videos_dir / output_filename

        logger.info(f"Downloading video from {video_url}")

        if video_url.startswith('-'):
            logger.warning(f"Suspicious video URL starts with dash: {video_url[:100]}")
            return None

        try:
            # Find yt-dlp binary using cross-platform method
            yt_dlp_cmd = self._find_yt_dlp()

            if not yt_dlp_cmd:
                logger.error("yt-dlp not found in PATH or common locations")
                return None

            # Use yt-dlp command-line tool
            # -f best: Download best quality
            # --no-playlist: Don't download playlists
            # --no-warnings: Cleaner output
            # -o: Output path
            subprocess.run([
                yt_dlp_cmd,
                '-f', 'best',
                '--no-playlist',
                '--no-warnings',
                '--max-filesize', f'{self.MAX_VIDEO_SIZE // (1024 * 1024)}M',
                '-o', str(output_path),
                '--', video_url
            ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, timeout=300)  # 5 minute timeout

            if output_path.exists():
                file_size = output_path.stat().st_size
                if file_size > self.MAX_VIDEO_SIZE:
                    logger.warning(
                        f"Video exceeded size limit after download ({file_size} bytes > {self.MAX_VIDEO_SIZE}): {video_url[:100]}"
                    )
                    output_path.unlink(missing_ok=True)
                    return None
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
        # Domain whitelist check
        if not self._is_allowed_domain(image_url):
            logger.warning(f"Image download blocked — domain not allowed: {image_url[:100]}")
            return None

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

        # Extension whitelist check
        if extension not in self.ALLOWED_IMAGE_EXTENSIONS:
            logger.warning(f"Image extension not allowed: {extension}")
            return None

        # Generate unique filename
        url_hash = hashlib.md5(image_url.encode()).hexdigest()[:10]
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_filename = f"image_{timestamp}_{url_hash}.{extension}"
        output_path = self.images_dir / output_filename

        logger.info(f"Downloading image from {image_url}")

        response = None
        try:
            # Download with timeout and user agent
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            response = requests.get(image_url, headers=headers, timeout=30, stream=True)
            response.raise_for_status()

            # Check Content-Length before downloading
            content_length = response.headers.get('Content-Length')
            if content_length:
                try:
                    content_length_int = int(content_length)
                    if content_length_int > self.MAX_IMAGE_SIZE:
                        logger.warning(
                            f"Image too large ({content_length_int} bytes > {self.MAX_IMAGE_SIZE}): {image_url[:100]}"
                        )
                        return None
                except ValueError:
                    logger.debug(f"Ignoring non-integer Content-Length value: {content_length!r}")

            # Save to file with size limit enforcement
            downloaded = 0
            with open(output_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if not chunk:
                        continue
                    downloaded += len(chunk)
                    if downloaded > self.MAX_IMAGE_SIZE:
                        logger.warning(f"Image exceeded size limit during download: {image_url[:100]}")
                        f.close()
                        output_path.unlink(missing_ok=True)
                        return None
                    f.write(chunk)

            logger.info(f"Image downloaded successfully: {output_path}")
            return str(output_path)

        except requests.RequestException as e:
            logger.error(f"Image download failed: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error downloading image: {e}")
            return None
        finally:
            if response is not None:
                response.close()

    def download_thread_media(self, thread_data: Dict) -> List[Dict[str, str]]:
        """
        Download all media from a thread (images and videos).

        Based on X thread structure analysis:
        - Images: Direct URLs from pbs.twimg.com/media/{id}
        - Videos: MP4 URLs from video.twimg.com/amplify_video/{video_id}/vid/avc1/...

        Args:
            thread_data: Thread JSON from scraper with structure:
                {
                    "tweets": [
                        {
                            "tweet_id": "...",
                            "text": "...",
                            "media": [
                                {"type": "photo", "src": "https://..."},
                                {"type": "video", "src": "https://..."}
                            ]
                        }
                    ]
                }

        Returns:
            List of downloaded media info:
            [
                {"tweet_id": "...", "type": "photo", "src": "...", "local_path": "..."},
                {"tweet_id": "...", "type": "video", "src": "...", "local_path": "..."}
            ]
        """
        if not thread_data or "tweets" not in thread_data:
            logger.warning("Invalid thread data, no tweets found")
            return []

        downloaded_media = []
        tweets = thread_data.get("tweets", [])

        logger.info(f"Processing media from {len(tweets)} tweets in thread")

        for tweet in tweets:
            tweet_id = tweet.get("tweet_id", "unknown")
            media_items = tweet.get("media", [])

            if not media_items:
                continue

            logger.info(f"Tweet {tweet_id}: Found {len(media_items)} media items")

            for media_item in media_items:
                media_type = media_item.get("type", "")
                media_src = media_item.get("src", "")

                if not media_src:
                    logger.warning(f"Tweet {tweet_id}: Empty media src, skipping")
                    continue

                # Download based on type
                local_path = None

                if media_type == "photo":
                    logger.info(f"Downloading image from tweet {tweet_id}: {media_src}")
                    local_path = self._download_image(media_src)
                elif media_type == "video":
                    # For X videos, use tweet permalink if available (yt-dlp can extract from tweets)
                    tweet_permalink = tweet.get("permalink", "")
                    if tweet_permalink:
                        logger.info(f"Downloading video from tweet permalink: {tweet_permalink}")
                        local_path = self._download_video(tweet_permalink)
                    else:
                        logger.info(f"Downloading video from tweet {tweet_id}: {media_src}")
                        local_path = self._download_video(media_src)
                else:
                    logger.warning(f"Unknown media type '{media_type}' in tweet {tweet_id}")
                    continue

                # Store result
                if local_path:
                    downloaded_media.append({
                        "tweet_id": tweet_id,
                        "type": media_type,
                        "src": media_src,
                        "local_path": local_path
                    })
                    logger.info(f"✅ Downloaded {media_type}: {local_path}")
                else:
                    logger.warning(f"❌ Failed to download {media_type} from tweet {tweet_id}")

        logger.info(f"Thread media download complete: {len(downloaded_media)} files downloaded")
        return downloaded_media


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
            batch_size_raw = os.getenv("PROCESSOR_BATCH_SIZE", "50")
            try:
                batch_size = max(1, int(batch_size_raw))
            except ValueError:
                logger.warning(f"Invalid PROCESSOR_BATCH_SIZE={batch_size_raw!r}; using 50")
                batch_size = 50

            total_seen = 0

            while True:
                pending_tweets = (
                    db.query(Tweet)
                    .filter(Tweet.status == TweetStatus.PENDING)
                    .order_by(Tweet.id.asc())
                    .limit(batch_size)
                    .all()
                )

                if not pending_tweets:
                    break

                total_seen += len(pending_tweets)
                logger.info(f"Processing batch of {len(pending_tweets)} pending tweets (batch size={batch_size})")

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

                # Prevent session memory growth in long-running batches.
                db.expunge_all()

            if total_seen == 0:
                logger.info("No pending tweets to process")
                return 0

            logger.info(f"Batch complete: {processed_count}/{total_seen} tweets processed")
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
