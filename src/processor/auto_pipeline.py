"""
AutoPipeline — Two-phase trend-to-post autopilot for HFI.

Phase A (Discover & Confirm): Fetch trends, rank, optionally summarize.
Phase B (Generate Hebrew):    Generate Hebrew posts for confirmed trends only.
"""

import logging
import re
import uuid
from datetime import datetime, timezone
from typing import List, Dict, Optional, Set

from sqlalchemy.orm import Session

from common.models import Trend, Tweet, TrendSource, TweetStatus
from scraper.news_scraper import STOPWORDS

logger = logging.getLogger(__name__)


class AutoPipeline:
    """Orchestrates the two-phase trend-to-post workflow."""

    def __init__(self, news_scraper=None, summary_generator=None, content_generator=None):
        self._news_scraper = news_scraper
        self._summary_generator = summary_generator
        self._content_generator = content_generator

    @property
    def news_scraper(self):
        if self._news_scraper is None:
            from scraper.news_scraper import NewsScraper
            self._news_scraper = NewsScraper()
        return self._news_scraper

    @property
    def summary_generator(self):
        if self._summary_generator is None:
            from processor.summary_generator import SummaryGenerator
            self._summary_generator = SummaryGenerator()
        return self._summary_generator

    @property
    def content_generator(self):
        if self._content_generator is None:
            from processor.content_generator import ContentGenerator
            self._content_generator = ContentGenerator()
        return self._content_generator

    @staticmethod
    def _title_keywords(title: str) -> Set[str]:
        """Extract keywords from a title for diversity checking."""
        words = re.findall(r"[A-Za-z0-9']+", title.lower())
        return {w for w in words if w not in STOPWORDS and len(w) > 2}

    @staticmethod
    def _diversify_candidates(candidates: List[Dict], top_n: int) -> List[Dict]:
        """Pick at most one candidate per topic cluster.

        Uses Jaccard similarity (>0.4) on title keywords to cluster
        related articles. Picks highest-score from each cluster first.
        """
        if len(candidates) <= top_n:
            return candidates

        selected = []
        selected_kw_sets: List[Set[str]] = []

        for cand in candidates:
            kws = AutoPipeline._title_keywords(cand.get('title', ''))
            if not kws:
                selected.append(cand)
                selected_kw_sets.append(kws)
                if len(selected) >= top_n:
                    break
                continue

            is_similar = False
            for seen_kws in selected_kw_sets:
                if not seen_kws:
                    continue
                intersection = len(kws & seen_kws)
                union = len(kws | seen_kws)
                if union > 0 and intersection / union > 0.4:
                    is_similar = True
                    break

            if not is_similar:
                selected.append(cand)
                selected_kw_sets.append(kws)
                if len(selected) >= top_n:
                    break

        return selected

    # ------------------------------------------------------------------
    # Phase A
    # ------------------------------------------------------------------

    def fetch_and_rank(
        self,
        db: Session,
        top_n: int = 3,
        auto_summarize: bool = True,
        finance_weight: float = 0.7,
    ) -> List[Dict]:
        """
        Phase A: Fetch trends, save to DB, pick top N, optionally summarize.

        Returns list of enriched trend dicts:
            {trend_id, title, description, summary, source, url, score, keywords}
        """
        SOURCE_MAP = {
            'Yahoo Finance': TrendSource.YAHOO_FINANCE,
            'WSJ': TrendSource.WSJ,
            'TechCrunch': TrendSource.TECHCRUNCH,
            'Bloomberg': TrendSource.BLOOMBERG,
            'MarketWatch': TrendSource.MARKETWATCH,
        }

        # 1. Fetch & rank articles
        ranked_news = self.news_scraper.get_latest_news(
            limit_per_source=10,
            total_limit=10,
            finance_weight=finance_weight,
        )

        # 2. Save new trends to DB
        new_trend_ids = []
        for article in ranked_news:
            existing = db.query(Trend).filter_by(title=article['title']).first()
            if existing:
                continue
            trend = Trend(
                title=article['title'],
                description=article.get('description', '')[:500],
                source=SOURCE_MAP.get(article['source'], TrendSource.MANUAL),
                article_url=article.get('url', ''),
            )
            db.add(trend)
            db.flush()
            new_trend_ids.append(trend.id)
        db.commit()

        logger.info(f"AutoPipeline Phase A: fetched {len(ranked_news)} articles, saved {len(new_trend_ids)} new trends")

        # 3. Pick top N by score, excluding titles already in tweet queue
        queued_titles = {
            t.trend_topic for t in db.query(Tweet.trend_topic).filter(
                Tweet.trend_topic.isnot(None)
            ).all()
        }

        all_candidates = []
        for article in ranked_news:
            if article['title'] in queued_titles:
                continue
            trend_row = db.query(Trend).filter_by(title=article['title']).first()
            if not trend_row:
                continue
            all_candidates.append({
                'trend_id': trend_row.id,
                'title': trend_row.title,
                'description': trend_row.description or '',
                'summary': trend_row.summary or '',
                'source': article.get('source', ''),
                'url': trend_row.article_url or '',
                'score': article.get('score', 0),
                'keywords': article.get('keywords', []),
                'category': article.get('category', 'Unknown'),
            })

        # Enforce topic diversity before cutting to top_n
        candidates = self._diversify_candidates(all_candidates, top_n)

        # 4. Optionally summarize
        if auto_summarize:
            for cand in candidates:
                trend_row = db.query(Trend).filter_by(id=cand['trend_id']).first()
                if trend_row and not trend_row.summary:
                    try:
                        self.summary_generator.process_trend(db, trend_row.id)
                        db.refresh(trend_row)
                        cand['summary'] = trend_row.summary or ''
                        cand['keywords'] = trend_row.keywords or []
                    except Exception as e:
                        logger.warning(f"Summary generation failed for trend {cand['trend_id']}: {e}")
                elif trend_row:
                    cand['summary'] = trend_row.summary or ''
                    cand['keywords'] = trend_row.keywords or []

        logger.info(f"AutoPipeline Phase A complete: {len(candidates)} candidates")
        return candidates

    # ------------------------------------------------------------------
    # Phase B
    # ------------------------------------------------------------------

    def generate_for_confirmed(
        self,
        db: Session,
        trend_ids: List[int],
        angle: str = 'news',
        num_variants: int = 1,
    ) -> List[Dict]:
        """
        Phase B: Generate Hebrew posts for confirmed trends.

        Returns list of result dicts:
            {trend_id, trend_title, variants: [{content, angle, ...}], tweet_id}
        """
        batch_id = f"pipeline_{uuid.uuid4().hex[:8]}"
        results = []

        for trend_id in trend_ids:
            trend = db.query(Trend).filter_by(id=trend_id).first()
            if not trend:
                logger.warning(f"Trend {trend_id} not found, skipping")
                continue

            source_text = f"{trend.title}\n\n{trend.description or trend.summary or ''}"

            try:
                variants = self.content_generator.generate_post(
                    source_text,
                    num_variants=num_variants,
                    angles=[angle],
                )
            except Exception as e:
                logger.error(f"Generation failed for trend {trend_id}: {e}")
                variants = [{
                    'angle': angle,
                    'label': angle,
                    'content': f"Error: {str(e)}",
                    'char_count': 0,
                    'is_valid_hebrew': False,
                }]

            best = variants[0] if variants else None
            tweet_id = None

            if best and best.get('is_valid_hebrew'):
                import hashlib, json
                source_hash = hashlib.md5(source_text.encode()).hexdigest()[:12]
                new_tweet = Tweet(
                    source_url=trend.article_url or f"pipeline_{trend_id}",
                    original_text=source_text,
                    hebrew_draft=best['content'],
                    content_type='generation',
                    generation_metadata=json.dumps({
                        'angle': best.get('angle', angle),
                        'label': best.get('label', ''),
                        'source_hash': source_hash,
                        'pipeline': True,
                    }),
                    trend_topic=trend.title,
                    pipeline_batch_id=batch_id,
                    status=TweetStatus.PROCESSED,
                )
                # Avoid duplicate source_url
                existing = db.query(Tweet).filter_by(source_url=new_tweet.source_url).first()
                if not existing:
                    db.add(new_tweet)
                    db.flush()
                    tweet_id = new_tweet.id
                else:
                    tweet_id = existing.id

            results.append({
                'trend_id': trend_id,
                'trend_title': trend.title,
                'variants': variants,
                'tweet_id': tweet_id,
                'batch_id': batch_id,
            })

        db.commit()
        logger.info(f"AutoPipeline Phase B complete: {len(results)} posts generated (batch={batch_id})")
        return results
