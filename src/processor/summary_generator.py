"""
Summary Generator Service for HFI Application

This module generates AI-powered summaries and extracts keywords from article trends.

Key Features:
1. AI-generated summaries using OpenAI GPT-4o
2. Keyword extraction from article titles
3. Related content grouping by keyword overlap
4. Batch processing for existing trends

Author: HFI Development Team
Last Updated: 2026-02-01
"""

import os
import re
import logging
import sys
from typing import Optional, List, Dict, Set

from openai import OpenAI
from sqlalchemy.orm import Session
from common.models import Trend, get_db
from common.openai_client import get_openai_client

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class SummaryGenerator:
    """
    Generates AI summaries and extracts context from article trends.

    Responsibilities:
    - Generate 1-2 sentence summaries using OpenAI GPT-4o
    - Extract keywords from article titles
    - Calculate source_count from existing data
    - Group related trends by keyword overlap
    """

    # Common stopwords to exclude from keywords
    STOPWORDS = {
        'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for',
        'of', 'with', 'by', 'from', 'up', 'about', 'into', 'through', 'during',
        'is', 'are', 'was', 'were', 'be', 'been', 'being', 'have', 'has', 'had',
        'do', 'does', 'did', 'will', 'would', 'could', 'should', 'may', 'might',
        'can', 'as', 'this', 'that', 'these', 'those', 'it', 'its', 'their',
        'his', 'her', 'our', 'your', 'my', 'all', 'some', 'any', 'no', 'not',
        'what', 'which', 'who', 'when', 'where', 'why', 'how'
    }

    def __init__(self, api_key: Optional[str] = None, model: str = "gpt-4o"):
        """
        Initialize the summary generator.

        Args:
            api_key: OpenAI API key (defaults to OPENAI_API_KEY env var)
            model: OpenAI model to use (default: gpt-4o)
        """
        self.api_key = api_key or os.getenv('OPENAI_API_KEY')
        if not self.api_key:
            raise ValueError("OpenAI API key is required (set OPENAI_API_KEY env var)")

        self.model = model
        self.client = get_openai_client() if not api_key else OpenAI(api_key=api_key)
        logger.info(f"Initialized SummaryGenerator with model: {self.model}")

    def generate_summary(self, title: str, description: Optional[str] = None) -> str:
        """
        Generate a 1-2 sentence summary for an article.

        Args:
            title: Article title
            description: Optional article description/content

        Returns:
            AI-generated summary (1-2 sentences)

        Raises:
            Exception: If summary generation fails
        """
        try:
            # Build prompt based on available content
            content = f"Title: {title}"
            if description:
                content += f"\nContent: {description}"

            prompt = f"""Summarize this FinTech article in 1-2 sentences.

{content}

Focus on: What happened, why it matters to FinTech professionals.
Be concise and informative."""

            logger.info(f"Generating summary for: {title[:60]}...")

            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a FinTech industry analyst who writes concise, informative summaries."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=100,
                temperature=0.7
            )

            summary = response.choices[0].message.content.strip()
            logger.info(f"Generated summary: {summary[:60]}...")

            return summary

        except Exception as e:
            logger.error(f"Failed to generate summary for '{title}': {e}")
            # Fallback to first sentence of description or title
            if description:
                first_sentence = description.split('.')[0] + '.'
                return first_sentence if len(first_sentence) < 200 else title
            return title

    def extract_keywords(self, title: str) -> List[str]:
        """
        Extract significant keywords from article title.

        Removes stopwords and keeps words >2 characters.

        Args:
            title: Article title

        Returns:
            List of extracted keywords (lowercase)
        """
        # Clean and tokenize
        words = re.findall(r'\b\w+\b', title.lower())

        # Filter: remove stopwords, keep words >2 chars
        keywords = [
            word for word in words
            if word not in self.STOPWORDS and len(word) > 2
        ]

        # Remove duplicates while preserving order
        seen = set()
        unique_keywords = []
        for keyword in keywords:
            if keyword not in seen:
                seen.add(keyword)
                unique_keywords.append(keyword)

        logger.debug(f"Extracted keywords from '{title}': {unique_keywords}")
        return unique_keywords

    def calculate_source_count(self, db: Session, trend: Trend) -> int:
        """
        Calculate how many different sources mention similar trends.

        Uses keyword overlap to identify related trends.

        Args:
            db: Database session
            trend: Trend to calculate source count for

        Returns:
            Number of unique sources mentioning this trend
        """
        if not trend.keywords:
            return 1

        # Find trends with overlapping keywords
        all_trends = db.query(Trend).all()
        related_sources = {trend.source.value}

        for other in all_trends:
            if other.id == trend.id or not other.keywords:
                continue

            # Calculate keyword overlap
            trend_keywords = set(trend.keywords)
            other_keywords = set(other.keywords)
            overlap = trend_keywords & other_keywords

            # If 2+ keywords match, consider it the same story
            if len(overlap) >= 2:
                related_sources.add(other.source.value)

        return len(related_sources)

    def find_related_trends(self, db: Session, trend: Trend, min_overlap: int = 2) -> List[int]:
        """
        Find related trends by keyword overlap.

        Args:
            db: Database session
            trend: Trend to find related trends for
            min_overlap: Minimum number of overlapping keywords (default: 2)

        Returns:
            List of related trend IDs
        """
        if not trend.keywords:
            return []

        related_ids = []
        trend_keywords = set(trend.keywords)

        # Query trends from similar time period (within 7 days)
        all_trends = db.query(Trend).filter(
            Trend.id != trend.id,
            Trend.discovered_at >= trend.discovered_at - __import__('datetime').timedelta(days=7),
            Trend.discovered_at <= trend.discovered_at + __import__('datetime').timedelta(days=7)
        ).all()

        for other in all_trends:
            if not other.keywords:
                continue

            other_keywords = set(other.keywords)
            overlap = trend_keywords & other_keywords

            if len(overlap) >= min_overlap:
                related_ids.append(other.id)

        logger.debug(f"Found {len(related_ids)} related trends for trend {trend.id}")
        return related_ids

    def process_trend(self, db: Session, trend_id: int) -> bool:
        """
        Process a single trend: generate summary, extract keywords, find related.

        Args:
            db: Database session
            trend_id: ID of trend to process

        Returns:
            True if successful, False otherwise
        """
        try:
            trend = db.query(Trend).filter(Trend.id == trend_id).first()

            if not trend:
                logger.warning(f"Trend {trend_id} not found")
                return False

            logger.info(f"Processing trend {trend_id}: {trend.title}")

            # Generate summary
            if not trend.summary:
                trend.summary = self.generate_summary(trend.title, trend.description)

            # Extract keywords
            if not trend.keywords:
                trend.keywords = self.extract_keywords(trend.title)

            # Calculate source count
            trend.source_count = self.calculate_source_count(db, trend)

            # Find related trends
            trend.related_trend_ids = self.find_related_trends(db, trend)

            db.commit()
            logger.info(f"✓ Processed trend {trend_id} successfully")
            return True

        except Exception as e:
            logger.error(f"Failed to process trend {trend_id}: {e}")
            db.rollback()
            return False

    def backfill_summaries(self, db: Session, limit: Optional[int] = None) -> Dict[str, int]:
        """
        Generate summaries for all trends missing them.

        Args:
            db: Database session
            limit: Maximum number of trends to process (None = all)

        Returns:
            Dictionary with statistics: {success: N, failed: N, skipped: N}
        """
        stats = {'success': 0, 'failed': 0, 'skipped': 0}

        # Find trends without summaries
        query = db.query(Trend).filter(Trend.summary == None)

        if limit:
            query = query.limit(limit)

        trends = query.all()

        logger.info(f"Backfilling summaries for {len(trends)} trends")

        for trend in trends:
            if self.process_trend(db, trend.id):
                stats['success'] += 1
            else:
                stats['failed'] += 1

        logger.info(f"Backfill complete: {stats}")
        return stats


def main():
    """CLI entry point for running summary generation."""
    import argparse

    parser = argparse.ArgumentParser(description="Generate summaries for HFI trends")
    parser.add_argument('--backfill', action='store_true', help="Backfill summaries for all trends")
    parser.add_argument('--trend-id', type=int, help="Process a specific trend by ID")
    parser.add_argument('--limit', type=int, help="Limit number of trends to process")

    args = parser.parse_args()

    # Initialize generator
    generator = SummaryGenerator()

    with get_db() as db:
        if args.trend_id:
            # Process single trend
            success = generator.process_trend(db, args.trend_id)
            sys.exit(0 if success else 1)

        elif args.backfill:
            # Backfill all trends
            stats = generator.backfill_summaries(db, limit=args.limit)
            print(f"\nBackfill Results:")
            print(f"  Success: {stats['success']}")
            print(f"  Failed: {stats['failed']}")
            print(f"  Skipped: {stats['skipped']}")
            sys.exit(0 if stats['failed'] == 0 else 1)

        else:
            parser.print_help()
            sys.exit(1)


if __name__ == "__main__":
    main()
