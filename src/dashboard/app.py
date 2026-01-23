"""
Streamlit Dashboard for HFI Content Approval

This dashboard provides a human-in-the-loop interface for:
- Reviewing scraped tweets
- Editing Hebrew translations
- Approving content for publishing
- Managing the content workflow

Features:
- Real-time status filtering
- Inline content editing
- Media preview (images/videos)
- Bulk actions
- Auto-refresh
"""

import streamlit as st
import sys
import logging
from pathlib import Path
from datetime import datetime, timezone
import time

# Add parent directory to path for imports
sys.path.append(str(Path(__file__).parent.parent))

from common.models import get_db_session, Tweet, Trend, TrendSource
from sqlalchemy import func

# Setup logging
logger = logging.getLogger(__name__)


# Page configuration
st.set_page_config(
    page_title="HFI Dashboard",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for better styling
st.markdown("""
<style>
    .tweet-card {
        background-color: #f0f2f6;
        padding: 20px;
        border-radius: 10px;
        margin-bottom: 20px;
        border-left: 4px solid #1f77b4;
    }
    .status-pending {
        border-left-color: #ff7f0e;
    }
    .status-processed {
        border-left-color: #2ca02c;
    }
    .status-approved {
        border-left-color: #9467bd;
    }
    .status-published {
        border-left-color: #17becf;
    }
    .metric-card {
        background-color: #e1e5eb;
        padding: 15px;
        border-radius: 8px;
        text-align: center;
    }
    .hebrew-text {
        direction: rtl;
        text-align: right;
        font-size: 16px;
        line-height: 1.6;
    }
</style>
""", unsafe_allow_html=True)


def get_db():
    """Get database session with caching"""
    if 'db' not in st.session_state:
        st.session_state.db = get_db_session()
    return st.session_state.db


def get_stats(db):
    """Get dashboard statistics"""
    stats = {
        'total': db.query(func.count(Tweet.id)).scalar(),
        'pending': db.query(func.count(Tweet.id)).filter(Tweet.status == 'pending').scalar(),
        'processed': db.query(func.count(Tweet.id)).filter(Tweet.status == 'processed').scalar(),
        'approved': db.query(func.count(Tweet.id)).filter(Tweet.status == 'approved').scalar(),
        'published': db.query(func.count(Tweet.id)).filter(Tweet.status == 'published').scalar(),
    }
    return stats


def get_tweets(db, status_filter='all', limit=50):
    """Get tweets based on filter"""
    query = db.query(Tweet).order_by(Tweet.created_at.desc())

    if status_filter != 'all':
        query = query.filter(Tweet.status == status_filter)

    return query.limit(limit).all()


def update_tweet(db, tweet_id, **kwargs):
    """Update tweet in database"""
    tweet = db.query(Tweet).filter(Tweet.id == tweet_id).first()
    if tweet:
        for key, value in kwargs.items():
            setattr(tweet, key, value)
        tweet.updated_at = datetime.now(timezone.utc)
        db.commit()
        return True
    return False


def delete_tweet(db, tweet_id):
    """Delete tweet from database"""
    tweet = db.query(Tweet).filter(Tweet.id == tweet_id).first()
    if tweet:
        db.delete(tweet)
        db.commit()
        return True
    return False


def render_tweet_card(tweet, db):
    """Render a single tweet card with actions"""

    # Status badge color
    status_colors = {
        'pending': '🟠',
        'processed': '🟢',
        'approved': '🟣',
        'published': '🔵'
    }

    status_badge = status_colors.get(tweet.status, '⚪')

    with st.expander(
        f"{status_badge} **{tweet.trend_topic or 'No Topic'}** - {tweet.created_at.strftime('%Y-%m-%d %H:%M')}",
        expanded=False
    ):
        # Two column layout
        col1, col2 = st.columns([1, 1])

        with col1:
            st.markdown("### 📝 Original (English)")
            st.text_area(
                "Original Tweet",
                value=tweet.original_text,
                height=150,
                disabled=True,
                key=f"orig_{tweet.id}",
                label_visibility="collapsed"
            )

            st.markdown(f"**Source:** [{tweet.source_url}]({tweet.source_url})")
            st.markdown(f"**Status:** `{tweet.status}`")
            st.markdown(f"**Created:** {tweet.created_at.strftime('%Y-%m-%d %H:%M:%S')}")

        with col2:
            st.markdown("### 🔄 Hebrew Translation")

            # Editable Hebrew text
            hebrew_text = st.text_area(
                "Hebrew Draft",
                value=tweet.hebrew_draft or "",
                height=150,
                key=f"hebrew_{tweet.id}",
                label_visibility="collapsed",
                placeholder="Hebrew translation will appear here after processing..."
            )

            # Media preview
            if tweet.media_path:
                st.markdown("### 🎬 Media")
                media_path = Path(__file__).parent.parent.parent / "data" / "media" / Path(tweet.media_path).name

                if media_path.exists():
                    if media_path.suffix.lower() in ['.jpg', '.jpeg', '.png', '.gif']:
                        st.image(str(media_path), use_column_width=True)
                    elif media_path.suffix.lower() in ['.mp4', '.mov', '.avi']:
                        st.video(str(media_path))
                else:
                    st.warning(f"Media file not found: {tweet.media_path}")
            elif tweet.media_url:
                st.info(f"Media URL: {tweet.media_url} (not downloaded yet)")

        # Action buttons
        st.markdown("---")
        col1, col2, col3, col4, col5 = st.columns(5)

        with col1:
            if st.button("💾 Save Edits", key=f"save_{tweet.id}", use_container_width=True):
                if hebrew_text != tweet.hebrew_draft:
                    if update_tweet(db, tweet.id, hebrew_draft=hebrew_text):
                        st.success("✅ Saved!")
                        st.rerun()
                else:
                    st.info("No changes to save")

        with col2:
            if st.button("✅ Approve", key=f"approve_{tweet.id}", use_container_width=True):
                if update_tweet(db, tweet.id, status='approved', hebrew_draft=hebrew_text):
                    st.success("✅ Approved!")
                    st.rerun()

        with col3:
            if st.button("⏮️ Reset to Pending", key=f"pending_{tweet.id}", use_container_width=True):
                if update_tweet(db, tweet.id, status='pending'):
                    st.success("⏮️ Reset to pending!")
                    st.rerun()

        with col4:
            if st.button("🔄 Reprocess", key=f"reprocess_{tweet.id}", use_container_width=True):
                if update_tweet(db, tweet.id, status='pending', hebrew_draft=None):
                    st.success("🔄 Marked for reprocessing!")
                    st.rerun()

        with col5:
            if st.button("🗑️ Delete", key=f"delete_{tweet.id}", use_container_width=True, type="secondary"):
                if delete_tweet(db, tweet.id):
                    st.success("🗑️ Deleted!")
                    st.rerun()


def render_sidebar(db):
    """Render sidebar with filters and stats"""
    st.sidebar.title("🎛️ Dashboard Controls")

    # Statistics
    st.sidebar.markdown("### 📊 Statistics")
    stats = get_stats(db)

    # Display metrics in a nice format
    st.sidebar.metric("Total Tweets", stats['total'])

    col1, col2 = st.sidebar.columns(2)
    with col1:
        st.metric("Pending", stats['pending'])
        st.metric("Processed", stats['processed'])
    with col2:
        st.metric("Approved", stats['approved'])
        st.metric("Published", stats['published'])

    st.sidebar.markdown("---")

    # Filters
    st.sidebar.markdown("### 🔍 Filters")

    status_filter = st.sidebar.selectbox(
        "Status",
        options=['all', 'pending', 'processed', 'approved', 'published'],
        index=0,
        format_func=lambda x: x.capitalize()
    )

    st.sidebar.markdown("---")

    # Refresh controls
    st.sidebar.markdown("### 🔄 Refresh")

    auto_refresh = st.sidebar.checkbox("Auto-refresh (30s)", value=False)

    if st.sidebar.button("🔄 Refresh Now", use_container_width=True):
        st.rerun()

    # Display last update time
    if 'last_update' not in st.session_state:
        st.session_state.last_update = datetime.now()

    st.sidebar.caption(f"Last update: {st.session_state.last_update.strftime('%H:%M:%S')}")

    st.sidebar.markdown("---")

    # Bulk actions
    st.sidebar.markdown("### ⚡ Bulk Actions")

    if st.sidebar.button("Approve All Processed", use_container_width=True):
        processed_tweets = db.query(Tweet).filter(Tweet.status == 'processed').all()
        count = 0
        for tweet in processed_tweets:
            if tweet.hebrew_draft:  # Only approve if translation exists
                update_tweet(db, tweet.id, status='approved')
                count += 1
        db.commit()
        st.sidebar.success(f"✅ Approved {count} tweets!")
        st.rerun()


    if st.sidebar.button("Delete All Pending", use_container_width=True):
        pending_tweets = db.query(Tweet).filter(Tweet.status == 'pending').all()
        count = len(pending_tweets)
        for tweet in pending_tweets:
            delete_tweet(db, tweet.id)
        st.sidebar.success(f"🗑️ Deleted {count} tweets!")
        st.rerun()

    return status_filter, auto_refresh


def handle_action_sidebar(db):
    """Render and handle the Actions sidebar."""
    st.sidebar.markdown("---")
    st.sidebar.title("🚀 New Task")
    
    # Mode Selection
    mode = st.sidebar.radio(
        "Select Operation:",
        ["Scrape X Trends", "Scrape X Thread", "Scrape News Sources"],
        index=0
    )
    
    # Inputs based on mode
    thread_url = ""
    translate = False
    
    if mode == "Scrape X Thread":
        thread_url = st.sidebar.text_input("Thread URL", placeholder="https://x.com/user/status/...")
        translate = st.sidebar.checkbox("Translate & Rewrite", value=True)
        
    start_btn = st.sidebar.button("▶ Start Scraping", type="primary")
    
    # Helper to run async code
    import asyncio
    
    if start_btn:
        status_container = st.sidebar.empty()
        
        try:
            if mode == "Scrape X Trends":
                status_container.info("🔄 Scraping X trends...")
                # Import here to avoid circular dependencies
                from scraper.scraper import TwitterScraper
                from common.models import Trend
                
                async def run_trends():
                    scraper = TwitterScraper()
                    try:
                        await scraper.ensure_logged_in()
                        trends = await scraper.get_trending_topics(limit=5)

                        count = 0
                        for trend in trends:
                            db_trend = Trend(
                                title=trend['title'],
                                description=trend.get('description', ''),
                                source=TrendSource.X_TWITTER
                            )
                            db.add(db_trend)
                            count += 1
                        db.commit()
                        return count
                    except Exception as e:
                        logger.error(f"Error scraping trends: {e}")
                        raise
                    finally:
                        await scraper.close()
                
                count = asyncio.run(run_trends())
                status_container.success(f"✅ Found {count} trends!")
                time.sleep(2)
                st.rerun()
                
            elif mode == "Scrape X Thread":
                if not thread_url:
                    status_container.error("❌ Please enter a URL")
                    return

                status_container.info(f"🔄 Fetching thread...")
                
                from scraper.scraper import TwitterScraper
                from common.models import Tweet
                
                async def run_thread():
                    scraper = TwitterScraper()
                    try:
                        await scraper.ensure_logged_in()
                        # Use fetch_thread (which handles session etc.)
                        tweets_data = await scraper.fetch_thread(thread_url)
                        
                        saved_count = 0
                        for t_data in tweets_data:
                            # Avoid duplicates (basic check)
                            exists = db.query(Tweet).filter_by(source_url=t_data['url']).first()
                            if not exists:
                                new_tweet = Tweet(
                                    source_url=t_data['url'],
                                    original_text=t_data['text'],
                                    status='pending', # Processor will pick this up if running
                                    media_url=t_data.get('media_url')
                                )
                                db.add(new_tweet)
                                saved_count += 1
                        db.commit()
                        return saved_count
                    except Exception as e:
                        logger.error(f"Error scraping thread: {e}")
                        raise
                    finally:
                        await scraper.close()

                saved = asyncio.run(run_thread())
                status_container.success(f"✅ Saved {saved} tweets!")
                
                if translate:
                    status_container.info("⏳ Waiting for processor...")
                
                time.sleep(2)
                st.rerun()
                
            elif mode == "Scrape News Sources":
                status_container.info("🔄 Scraping news (Reuters, WSJ, etc.)...")
                from scraper.news_scraper import NewsScraper

                # Map string source names to TrendSource enum values
                source_map = {
                    "Reuters": TrendSource.REUTERS,
                    "WSJ": TrendSource.WSJ,
                    "TechCrunch": TrendSource.TECHCRUNCH,
                    "Bloomberg": TrendSource.BLOOMBERG,
                }

                scraper = NewsScraper()
                articles = scraper.get_latest_news(limit_per_source=5)

                count = 0
                for article in articles:
                    source_enum = source_map.get(article['source'])
                    if not source_enum:
                        logger.warning(f"Unknown source: {article['source']}, skipping")
                        continue

                    # Check duplicate
                    exists = db.query(Trend).filter_by(
                        title=article['title'],
                        source=source_enum
                    ).first()

                    if not exists:
                        new_trend = Trend(
                            title=article['title'],
                            description=article['description'],
                            source=source_enum,
                            discovered_at=article['discovered_at']
                        )
                        db.add(new_trend)
                        count += 1
                db.commit()
                status_container.success(f"✅ Added {count} new articles!")
                time.sleep(2)
                st.rerun()
                
        except Exception as e:
            status_container.error(f"❌ Error: {str(e)}")
            # logger might not be defined in this scope if not imported, but Streamlit validation catches most



def main():
    """Main dashboard application"""

    # Header
    st.title("📊 Hebrew FinTech Informant (HFI) Dashboard")
    st.markdown("Human-in-the-loop content approval and editing interface")

    # Get database session
    db = get_db()

    # Render sidebar and get filters
    status_filter, auto_refresh = render_sidebar(db)
    
    # Handle New Task Actions
    handle_action_sidebar(db)

    # Main content area
    st.markdown("---")

    # Get tweets based on filter
    tweets = get_tweets(db, status_filter=status_filter)

    if not tweets:
        st.info(f"📭 No tweets found with status: **{status_filter}**")
        st.markdown("""
        ### Getting Started

        1. **Run the Scraper** to fetch tweets from X/Twitter
        2. **Run the Processor** to translate content to Hebrew
        3. **Review and Edit** translations here
        4. **Approve** content for publishing

        The dashboard will automatically show tweets as they're scraped and processed.
        """)
    else:
        st.markdown(f"### 📝 Showing {len(tweets)} tweet(s)")

        # Render each tweet card
        for tweet in tweets:
            render_tweet_card(tweet, db)

    # Auto-refresh logic
    if auto_refresh:
        time.sleep(30)
        st.session_state.last_update = datetime.now()
        st.rerun()

    # Footer
    st.markdown("---")
    st.caption("HFI Dashboard v1.0 - Built with Streamlit")


if __name__ == "__main__":
    main()
