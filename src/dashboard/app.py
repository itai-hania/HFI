"""
HFI Dashboard - Hebrew FinTech Informant
Dark Mode UI with Simplified Navigation
"""

import streamlit as st
import sys
import logging
import asyncio
from pathlib import Path
from datetime import datetime, timezone
import time

sys.path.append(str(Path(__file__).parent.parent))

from common.models import get_db_session, Tweet, Trend, Thread, TrendSource, TweetStatus
import json
from sqlalchemy import func

logger = logging.getLogger(__name__)

# Page config
st.set_page_config(
    page_title="HFI Dashboard",
    page_icon="",
    layout="wide",
    initial_sidebar_state="expanded"
)

# =============================================================================
# DARK MODE CSS - Full Dark Theme
# =============================================================================
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

    /* Dark Mode Design Tokens */
    :root {
        --bg-primary: #0d1117;
        --bg-secondary: #161b22;
        --bg-tertiary: #21262d;
        --bg-elevated: #30363d;

        --text-primary: #f0f6fc;
        --text-secondary: #8b949e;
        --text-muted: #6e7681;

        --accent-primary: #58a6ff;
        --accent-primary-hover: #79b8ff;
        --accent-success: #3fb950;
        --accent-warning: #d29922;
        --accent-danger: #f85149;

        --border-default: #30363d;
        --border-muted: #21262d;

        --shadow-sm: 0 1px 0 rgba(0,0,0,0.4);
        --shadow-md: 0 3px 6px rgba(0,0,0,0.4);
        --shadow-lg: 0 8px 24px rgba(0,0,0,0.4);

        --radius-sm: 6px;
        --radius-md: 8px;
        --radius-lg: 12px;
    }

    /* Base Dark Background */
    .stApp,
    [data-testid="stAppViewContainer"],
    [data-testid="stHeader"],
    .main,
    .main .block-container,
    [data-testid="stMainBlockContainer"] {
        background: var(--bg-primary) !important;
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif !important;
        color: var(--text-primary) !important;
    }

    .main .block-container, [data-testid="stMainBlockContainer"] {
        padding: 1.5rem 2rem !important;
        max-width: 1400px !important;
    }

    /* Hide Streamlit elements */
    #MainMenu, footer, header {visibility: hidden;}
    .stDeployButton {display: none;}

    /* Typography - Light text on dark */
    h1, h2, h3, .stMarkdown h1, .stMarkdown h2, .stMarkdown h3 {
        font-family: 'Inter', sans-serif !important;
        font-weight: 600 !important;
        color: var(--text-primary) !important;
        letter-spacing: -0.025em !important;
    }

    h1, .stMarkdown h1 { font-size: 1.75rem !important; margin-bottom: 0.5rem !important; }
    h2, .stMarkdown h2 { font-size: 1.25rem !important; }
    h3, .stMarkdown h3 { font-size: 1rem !important; color: var(--text-secondary) !important; }

    p, span, label, .stMarkdown, .stMarkdown p {
        font-family: 'Inter', sans-serif !important;
        color: var(--text-secondary) !important;
        font-size: 0.875rem !important;
        line-height: 1.6 !important;
    }

    /* ===========================================
       DARK SIDEBAR
       =========================================== */
    [data-testid="stSidebar"],
    [data-testid="stSidebar"] > div,
    [data-testid="stSidebarContent"],
    section[data-testid="stSidebar"] {
        background: var(--bg-secondary) !important;
        border-right: 1px solid var(--border-default) !important;
        width: 240px !important;
        min-width: 240px !important;
    }

    [data-testid="stSidebar"] .block-container {
        padding: 1rem 0.75rem !important;
        background: transparent !important;
    }

    /* Nav Brand */
    .nav-brand {
        padding: 1rem 1rem 1.5rem 1rem;
        border-bottom: 1px solid var(--border-default);
        margin-bottom: 1rem;
    }

    .nav-brand h1 {
        color: var(--text-primary) !important;
        font-size: 1.5rem !important;
        font-weight: 700 !important;
        margin: 0 !important;
    }

    .nav-brand p {
        color: var(--text-muted) !important;
        font-size: 0.75rem !important;
        margin: 0.25rem 0 0 0 !important;
    }

    /* Sidebar buttons */
    [data-testid="stSidebar"] .stButton > button {
        background: var(--bg-tertiary) !important;
        color: var(--text-primary) !important;
        border: 1px solid var(--border-default) !important;
        font-weight: 500 !important;
        border-radius: var(--radius-md) !important;
    }

    [data-testid="stSidebar"] .stButton > button:hover {
        background: var(--bg-elevated) !important;
        border-color: var(--border-default) !important;
    }

    [data-testid="stSidebar"] .stButton > button[data-testid="baseButton-primary"] {
        background: var(--accent-primary) !important;
        border: none !important;
        color: var(--bg-primary) !important;
    }

    [data-testid="stSidebar"] .stButton > button[data-testid="baseButton-primary"]:hover {
        background: var(--accent-primary-hover) !important;
    }

    [data-testid="stSidebar"] .stTextInput input {
        background: var(--bg-tertiary) !important;
        border: 1px solid var(--border-default) !important;
        color: var(--text-primary) !important;
        border-radius: var(--radius-md) !important;
        font-size: 0.875rem !important;
    }

    [data-testid="stSidebar"] .stTextInput input::placeholder {
        color: var(--text-muted) !important;
    }

    [data-testid="stSidebar"] .stTextInput input:focus {
        border-color: var(--accent-primary) !important;
        box-shadow: 0 0 0 3px rgba(88, 166, 255, 0.3) !important;
    }

    [data-testid="stSidebar"] p,
    [data-testid="stSidebar"] span,
    [data-testid="stSidebar"] label {
        color: var(--text-secondary) !important;
    }

    [data-testid="stSidebar"] hr {
        border-color: var(--border-default) !important;
        margin: 1rem 0 !important;
    }

    /* Nav Section Label */
    .nav-section {
        font-size: 0.65rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.1em;
        color: var(--text-muted);
        padding: 1rem 1rem 0.5rem 1rem;
        margin-top: 0.5rem;
    }

    /* ===========================================
       DARK CONTENT CARDS
       =========================================== */
    .content-card {
        background: var(--bg-secondary);
        border-radius: var(--radius-lg);
        padding: 1.25rem;
        margin-bottom: 1rem;
        border: 1px solid var(--border-default);
        box-shadow: var(--shadow-sm);
    }

    .content-card:hover {
        border-color: var(--border-default);
        box-shadow: var(--shadow-md);
    }

    /* Stat Cards */
    .stat-card {
        background: var(--bg-secondary);
        border-radius: var(--radius-lg);
        padding: 1.25rem;
        border: 1px solid var(--border-default);
        text-align: center;
    }

    .stat-value {
        font-size: 2rem;
        font-weight: 700;
        color: var(--text-primary);
        line-height: 1.2;
    }

    .stat-label {
        font-size: 0.75rem;
        font-weight: 500;
        color: var(--text-muted);
        text-transform: uppercase;
        letter-spacing: 0.05em;
        margin-top: 0.25rem;
    }

    .stat-inbox .stat-value { color: var(--accent-warning); }
    .stat-drafts .stat-value { color: var(--accent-primary); }
    .stat-ready .stat-value { color: var(--accent-success); }
    .stat-published .stat-value { color: var(--text-secondary); }

    /* ===========================================
       DARK BUTTONS
       =========================================== */
    .stButton > button {
        font-family: 'Inter', sans-serif !important;
        font-size: 0.875rem !important;
        font-weight: 500 !important;
        padding: 0.5rem 1rem !important;
        border-radius: var(--radius-md) !important;
        border: 1px solid var(--border-default) !important;
        background: var(--bg-tertiary) !important;
        color: var(--text-primary) !important;
        transition: all 0.15s ease !important;
    }

    .stButton > button:hover {
        background: var(--bg-elevated) !important;
        border-color: var(--accent-primary) !important;
    }

    .stButton > button[data-testid="baseButton-primary"] {
        background: var(--accent-primary) !important;
        color: var(--bg-primary) !important;
        border: none !important;
    }

    .stButton > button[data-testid="baseButton-primary"]:hover {
        background: var(--accent-primary-hover) !important;
    }

    /* Status Badges */
    .status-badge {
        display: inline-flex;
        align-items: center;
        padding: 0.25rem 0.75rem;
        border-radius: 9999px;
        font-size: 0.7rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.03em;
    }

    .status-pending { background: rgba(210, 153, 34, 0.2); color: #d29922; }
    .status-processed { background: rgba(88, 166, 255, 0.2); color: #58a6ff; }
    .status-approved { background: rgba(63, 185, 80, 0.2); color: #3fb950; }
    .status-published { background: rgba(110, 118, 129, 0.2); color: #8b949e; }
    .status-failed { background: rgba(248, 81, 73, 0.2); color: #f85149; }

    /* ===========================================
       DARK FORM ELEMENTS
       =========================================== */
    .stTextInput input, .stTextArea textarea {
        font-family: 'Inter', sans-serif !important;
        border-radius: var(--radius-md) !important;
        border: 1px solid var(--border-default) !important;
        background: var(--bg-tertiary) !important;
        color: var(--text-primary) !important;
        font-size: 0.875rem !important;
    }

    .stTextInput input:focus, .stTextArea textarea:focus {
        border-color: var(--accent-primary) !important;
        box-shadow: 0 0 0 3px rgba(88, 166, 255, 0.2) !important;
    }

    .stTextInput input::placeholder, .stTextArea textarea::placeholder {
        color: var(--text-muted) !important;
    }

    .stSelectbox > div > div {
        border-radius: var(--radius-md) !important;
        border: 1px solid var(--border-default) !important;
        background: var(--bg-tertiary) !important;
        color: var(--text-primary) !important;
    }

    .stCheckbox > label {
        font-size: 0.875rem !important;
        color: var(--text-secondary) !important;
    }

    /* ===========================================
       PAGE HEADER
       =========================================== */
    .page-header {
        margin-bottom: 1.5rem;
        padding-bottom: 1rem;
        border-bottom: 1px solid var(--border-default);
    }

    .page-title {
        font-size: 1.5rem;
        font-weight: 600;
        color: var(--text-primary);
        margin: 0 0 0.25rem 0;
    }

    .page-subtitle {
        font-size: 0.875rem;
        color: var(--text-muted);
        margin: 0;
    }

    /* ===========================================
       EMPTY STATE
       =========================================== */
    .empty-state {
        text-align: center;
        padding: 3rem 2rem;
        background: var(--bg-secondary);
        border-radius: var(--radius-lg);
        border: 2px dashed var(--border-default);
    }

    .empty-state-icon {
        font-size: 3rem;
        margin-bottom: 1rem;
        opacity: 0.5;
    }

    .empty-state-title {
        font-size: 1.1rem;
        font-weight: 600;
        color: var(--text-primary);
        margin-bottom: 0.5rem;
    }

    .empty-state-text {
        color: var(--text-muted);
        font-size: 0.875rem;
    }

    /* ===========================================
       PIPELINE COLUMNS
       =========================================== */
    .pipeline-header {
        display: flex;
        align-items: center;
        gap: 0.5rem;
        padding: 0.75rem 1rem;
        background: var(--bg-tertiary);
        border-radius: var(--radius-md);
        margin-bottom: 0.75rem;
    }

    .pipeline-title {
        font-size: 0.8rem;
        font-weight: 600;
        color: var(--text-primary);
        text-transform: uppercase;
        letter-spacing: 0.03em;
    }

    .pipeline-count {
        background: var(--bg-elevated);
        padding: 0.15rem 0.5rem;
        border-radius: 9999px;
        font-size: 0.7rem;
        font-weight: 600;
        color: var(--text-secondary);
    }

    /* Queue Item */
    .queue-item {
        background: var(--bg-secondary);
        border-radius: var(--radius-md);
        padding: 0.875rem;
        margin-bottom: 0.5rem;
        border: 1px solid var(--border-default);
        transition: all 0.15s ease;
    }

    .queue-item:hover {
        border-color: var(--accent-primary);
        box-shadow: var(--shadow-sm);
    }

    .queue-item-author {
        font-size: 0.75rem;
        font-weight: 600;
        color: var(--text-primary);
    }

    .queue-item-text {
        font-size: 0.8rem;
        color: var(--text-secondary);
        margin-top: 0.35rem;
        line-height: 1.5;
        display: -webkit-box;
        -webkit-line-clamp: 2;
        -webkit-box-orient: vertical;
        overflow: hidden;
    }

    .queue-item-meta {
        display: flex;
        align-items: center;
        gap: 0.5rem;
        margin-top: 0.5rem;
        font-size: 0.7rem;
        color: var(--text-muted);
    }

    /* ===========================================
       EXPANDER (Dark)
       =========================================== */
    .streamlit-expanderHeader {
        background: var(--bg-secondary) !important;
        border: 1px solid var(--border-default) !important;
        border-radius: var(--radius-md) !important;
        font-weight: 500 !important;
        color: var(--text-primary) !important;
    }

    .streamlit-expanderContent {
        border: 1px solid var(--border-default) !important;
        border-top: none !important;
        border-radius: 0 0 var(--radius-md) var(--radius-md) !important;
        background: var(--bg-secondary) !important;
    }

    details summary {
        color: var(--text-primary) !important;
    }

    /* ===========================================
       SCROLLBAR (Dark)
       =========================================== */
    ::-webkit-scrollbar {
        width: 8px;
        height: 8px;
    }

    ::-webkit-scrollbar-track {
        background: var(--bg-primary);
    }

    ::-webkit-scrollbar-thumb {
        background: var(--bg-elevated);
        border-radius: 4px;
    }

    ::-webkit-scrollbar-thumb:hover {
        background: var(--text-muted);
    }

    /* ===========================================
       ALERTS (Dark)
       =========================================== */
    [data-testid="stAlert"] {
        border-radius: var(--radius-md) !important;
        border: none !important;
        background: var(--bg-tertiary) !important;
    }

    /* ===========================================
       METRICS (Dark)
       =========================================== */
    [data-testid="stMetric"] {
        background: var(--bg-secondary) !important;
        padding: 1rem !important;
        border-radius: var(--radius-lg) !important;
        border: 1px solid var(--border-default) !important;
    }

    [data-testid="stMetricValue"] {
        font-size: 1.75rem !important;
        font-weight: 700 !important;
        color: var(--text-primary) !important;
    }

    [data-testid="stMetricLabel"] {
        font-size: 0.75rem !important;
        text-transform: uppercase !important;
        letter-spacing: 0.05em !important;
        color: var(--text-muted) !important;
    }

    /* ===========================================
       TABS (Dark)
       =========================================== */
    .stTabs [data-baseweb="tab-list"] {
        gap: 0;
        background: var(--bg-secondary);
        border-radius: var(--radius-md);
        padding: 4px;
    }

    .stTabs [data-baseweb="tab"] {
        background: transparent;
        color: var(--text-secondary);
        border-radius: var(--radius-sm);
        padding: 0.5rem 1rem;
    }

    .stTabs [data-baseweb="tab"]:hover {
        background: var(--bg-tertiary);
        color: var(--text-primary);
    }

    .stTabs [aria-selected="true"] {
        background: var(--bg-tertiary) !important;
        color: var(--text-primary) !important;
    }

    /* ===========================================
       SLIDER (Dark)
       =========================================== */
    .stSlider > div > div > div {
        background: var(--bg-elevated) !important;
    }

    .stSlider > div > div > div > div {
        background: var(--accent-primary) !important;
    }

    /* ===========================================
       PROGRESS BAR (Dark)
       =========================================== */
    .stProgress > div > div > div {
        background: var(--bg-elevated) !important;
    }

    .stProgress > div > div > div > div {
        background: var(--accent-primary) !important;
    }

    /* ===========================================
       DOWNLOAD BUTTON (Dark)
       =========================================== */
    .stDownloadButton > button {
        background: var(--bg-tertiary) !important;
        color: var(--text-primary) !important;
        border: 1px solid var(--border-default) !important;
    }

    .stDownloadButton > button:hover {
        background: var(--bg-elevated) !important;
        border-color: var(--accent-primary) !important;
    }
</style>
""", unsafe_allow_html=True)


# =============================================================================
# DATABASE HELPERS
# =============================================================================

def get_db():
    if 'db' not in st.session_state:
        st.session_state.db = get_db_session()
    return st.session_state.db


def get_stats(db):
    return {
        'total': db.query(func.count(Tweet.id)).scalar() or 0,
        'pending': db.query(func.count(Tweet.id)).filter(Tweet.status == TweetStatus.PENDING).scalar() or 0,
        'processed': db.query(func.count(Tweet.id)).filter(Tweet.status == TweetStatus.PROCESSED).scalar() or 0,
        'approved': db.query(func.count(Tweet.id)).filter(Tweet.status == TweetStatus.APPROVED).scalar() or 0,
        'published': db.query(func.count(Tweet.id)).filter(Tweet.status == TweetStatus.PUBLISHED).scalar() or 0,
        'failed': db.query(func.count(Tweet.id)).filter(Tweet.status == TweetStatus.FAILED).scalar() or 0,
    }


def get_tweets(db, status_filter='all', limit=50):
    query = db.query(Tweet).order_by(Tweet.created_at.desc())
    if status_filter != 'all':
        status_enum = getattr(TweetStatus, status_filter.upper(), None)
        if status_enum:
            query = query.filter(Tweet.status == status_enum)
    return query.limit(limit).all()


def update_tweet(db, tweet_id, **kwargs):
    tweet = db.query(Tweet).filter(Tweet.id == tweet_id).first()
    if tweet:
        for key, value in kwargs.items():
            if key == 'status' and isinstance(value, str):
                value = getattr(TweetStatus, value.upper(), value)
            setattr(tweet, key, value)
        tweet.updated_at = datetime.now(timezone.utc)
        db.commit()
        return True
    return False


def delete_tweet(db, tweet_id):
    tweet = db.query(Tweet).filter(Tweet.id == tweet_id).first()
    if tweet:
        db.delete(tweet)
        db.commit()
        return True
    return False


# =============================================================================
# SIMPLIFIED NAVIGATION - Only 4 items
# =============================================================================

def init_navigation():
    """Initialize navigation state"""
    if 'current_view' not in st.session_state:
        st.session_state.current_view = 'home'


def render_sidebar(db):
    """Simplified sidebar with only 4 navigation items"""

    # Brand header
    st.markdown("""
        <div class="nav-brand">
            <h1>HFI</h1>
            <p>Hebrew FinTech Informant</p>
        </div>
    """, unsafe_allow_html=True)

    # SIMPLIFIED NAVIGATION - Only 4 items
    nav_items = [
        ('home', 'Home'),
        ('content', 'Content'),
        ('scrape', 'Scrape'),
        ('settings', 'Settings'),
    ]

    for key, label in nav_items:
        is_active = st.session_state.current_view == key
        if st.button(
            label,
            key=f"nav_{key}",
            use_container_width=True,
            type="primary" if is_active else "secondary"
        ):
            st.session_state.current_view = key
            st.rerun()

    st.markdown("---")

    # Quick stats
    stats = get_stats(db)
    col1, col2 = st.columns(2)
    with col1:
        st.metric("Inbox", stats['pending'])
    with col2:
        st.metric("Ready", stats['approved'])


# =============================================================================
# HOME VIEW (Dashboard)
# =============================================================================

def render_home(db):
    """Home dashboard with stats overview"""

    st.markdown("""
        <div class="page-header">
            <h1 class="page-title">Dashboard</h1>
            <p class="page-subtitle">Overview of your content pipeline</p>
        </div>
    """, unsafe_allow_html=True)

    stats = get_stats(db)

    # Pipeline stats
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.markdown(f"""
            <div class="stat-card stat-inbox">
                <div class="stat-value">{stats['pending']}</div>
                <div class="stat-label">Inbox</div>
            </div>
        """, unsafe_allow_html=True)

    with col2:
        st.markdown(f"""
            <div class="stat-card stat-drafts">
                <div class="stat-value">{stats['processed']}</div>
                <div class="stat-label">Drafts</div>
            </div>
        """, unsafe_allow_html=True)

    with col3:
        st.markdown(f"""
            <div class="stat-card stat-ready">
                <div class="stat-value">{stats['approved']}</div>
                <div class="stat-label">Ready</div>
            </div>
        """, unsafe_allow_html=True)

    with col4:
        st.markdown(f"""
            <div class="stat-card stat-published">
                <div class="stat-value">{stats['published']}</div>
                <div class="stat-label">Published</div>
            </div>
        """, unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # Quick actions
    st.markdown("### Quick Actions")

    col1, col2, col3 = st.columns(3)

    with col1:
        if st.button("Translate All Pending", use_container_width=True, disabled=stats['pending'] == 0):
            st.session_state.current_view = 'content'
            st.session_state.auto_translate = True
            st.rerun()

    with col2:
        if st.button("Approve All Reviewed", use_container_width=True, disabled=stats['processed'] == 0):
            count = db.query(Tweet).filter(
                Tweet.status == TweetStatus.PROCESSED,
                Tweet.hebrew_draft.isnot(None)
            ).update({Tweet.status: TweetStatus.APPROVED})
            db.commit()
            st.success(f"Approved {count} items")
            time.sleep(1)
            st.rerun()

    with col3:
        if st.button("Scrape New Content", use_container_width=True):
            st.session_state.current_view = 'scrape'
            st.rerun()

    st.markdown("---")

    # Recent activity
    col1, col2 = st.columns(2)

    with col1:
        st.markdown("### Recent Items")
        recent = db.query(Tweet).order_by(Tweet.created_at.desc()).limit(5).all()

        if recent:
            for tweet in recent:
                status_str = tweet.status.value if hasattr(tweet.status, 'value') else str(tweet.status)
                st.markdown(f"""
                    <div class="queue-item">
                        <div class="queue-item-author">{tweet.trend_topic or 'Unknown'}</div>
                        <div class="queue-item-text">{tweet.original_text[:100]}...</div>
                        <div class="queue-item-meta">
                            <span class="status-badge status-{status_str.lower()}">{status_str}</span>
                        </div>
                    </div>
                """, unsafe_allow_html=True)
        else:
            st.info("No items yet. Scrape some content to get started.")

    with col2:
        st.markdown("### Pipeline Status")

        total = stats['total'] or 1

        stages = [
            ('Inbox', stats['pending'], 'var(--accent-warning)'),
            ('Drafts', stats['processed'], 'var(--accent-primary)'),
            ('Ready', stats['approved'], 'var(--accent-success)'),
            ('Published', stats['published'], 'var(--text-muted)'),
        ]

        for label, count, color in stages:
            pct = (count / total) * 100 if total > 0 else 0
            st.markdown(f"""
                <div style="margin-bottom: 0.75rem;">
                    <div style="display: flex; justify-content: space-between; margin-bottom: 0.25rem;">
                        <span style="font-size: 0.8rem; font-weight: 500; color: var(--text-primary);">{label}</span>
                        <span style="font-size: 0.8rem; color: var(--text-muted);">{count}</span>
                    </div>
                    <div style="background: var(--bg-elevated); border-radius: 4px; height: 8px; overflow: hidden;">
                        <div style="background: {color}; width: {pct}%; height: 100%; border-radius: 4px;"></div>
                    </div>
                </div>
            """, unsafe_allow_html=True)

        if stats['failed'] > 0:
            st.warning(f"{stats['failed']} items failed processing")


# =============================================================================
# CONTENT VIEW (Queue + Editor)
# =============================================================================

def render_content(db):
    """Content view with list and editor"""

    st.markdown("""
        <div class="page-header">
            <h1 class="page-title">Content</h1>
            <p class="page-subtitle">View, edit, and manage your tweets</p>
        </div>
    """, unsafe_allow_html=True)

    # Auto-translate if triggered
    if st.session_state.get('auto_translate'):
        st.session_state.auto_translate = False
        run_batch_translate(db)

    # Initialize selected item state
    if 'selected_item' not in st.session_state:
        st.session_state.selected_item = None

    stats = get_stats(db)

    # Quick actions bar
    col1, col2, col3, col4 = st.columns([1, 1, 1, 1])

    with col1:
        if st.button("Translate All", use_container_width=True, disabled=stats['pending'] == 0):
            run_batch_translate(db)

    with col2:
        if st.button("Approve All", use_container_width=True, disabled=stats['processed'] == 0):
            count = db.query(Tweet).filter(
                Tweet.status == TweetStatus.PROCESSED,
                Tweet.hebrew_draft.isnot(None)
            ).update({Tweet.status: TweetStatus.APPROVED})
            db.commit()
            if count > 0:
                st.success(f"Approved {count}")
                time.sleep(0.5)
                st.rerun()

    with col3:
        status_filter = st.selectbox(
            "Filter",
            ['all', 'pending', 'processed', 'approved', 'published', 'failed'],
            label_visibility="collapsed"
        )

    with col4:
        st.caption(f"Total: {stats['total']} items")

    st.markdown("---")

    # Check if we have a selected item to edit
    if st.session_state.selected_item:
        render_editor(db, st.session_state.selected_item)
        return

    # List view
    tweets = get_tweets(db, status_filter=status_filter, limit=50)

    if not tweets:
        st.markdown("""
            <div class="empty-state">
                <div class="empty-state-icon">📭</div>
                <div class="empty-state-title">No content found</div>
                <div class="empty-state-text">Scrape some threads to get started</div>
            </div>
        """, unsafe_allow_html=True)
        return

    for tweet in tweets:
        render_content_item(tweet, db)


def render_content_item(tweet, db):
    """Render a content list item"""
    status_str = tweet.status.value if hasattr(tweet.status, 'value') else str(tweet.status)

    with st.container():
        col1, col2, col3 = st.columns([4, 1, 1])

        with col1:
            st.markdown(f"""
                <div style="padding: 0.5rem 0;">
                    <div style="display: flex; align-items: center; gap: 0.5rem;">
                        <span style="font-weight: 500; color: var(--text-primary);">{tweet.trend_topic or 'Unknown'}</span>
                        <span class="status-badge status-{status_str.lower()}">{status_str}</span>
                    </div>
                    <div style="font-size: 0.8rem; color: var(--text-secondary); margin-top: 0.25rem;">
                        {tweet.original_text[:120]}...
                    </div>
                </div>
            """, unsafe_allow_html=True)

        with col2:
            if tweet.hebrew_draft:
                st.markdown(f"""
                    <div style="font-size: 0.75rem; color: var(--accent-success); direction: rtl; text-align: right;">
                        Translated
                    </div>
                """, unsafe_allow_html=True)
            else:
                st.caption("Not translated")

        with col3:
            if st.button("Edit", key=f"edit_{tweet.id}", use_container_width=True):
                st.session_state.selected_item = tweet.id
                st.rerun()

        st.markdown("<hr style='margin: 0.5rem 0; border-color: var(--border-default);'>", unsafe_allow_html=True)


def render_editor(db, tweet_id):
    """Full editor for a single tweet"""
    tweet = db.query(Tweet).filter(Tweet.id == tweet_id).first()

    if not tweet:
        st.error("Item not found")
        st.session_state.selected_item = None
        return

    status_str = tweet.status.value if hasattr(tweet.status, 'value') else str(tweet.status)

    # Top navigation
    col1, col2, col3 = st.columns([1, 3, 1])

    with col1:
        if st.button("< Back", use_container_width=True):
            st.session_state.selected_item = None
            st.rerun()

    with col2:
        st.markdown(f"""
            <div style="text-align: center; padding: 0.5rem;">
                <span style="font-weight: 600; font-size: 1rem; color: var(--text-primary);">{tweet.trend_topic or 'Unknown'}</span>
                <span class="status-badge status-{status_str.lower()}" style="margin-left: 0.75rem;">{status_str}</span>
            </div>
        """, unsafe_allow_html=True)

    with col3:
        if tweet.source_url and tweet.source_url.startswith('http'):
            st.markdown(f"[View on X]({tweet.source_url})")

    st.markdown("---")

    # Side-by-side content
    col1, col2 = st.columns(2)

    with col1:
        st.markdown("""
            <div style="background: var(--bg-tertiary); padding: 0.75rem; border-radius: 8px; margin-bottom: 0.5rem;">
                <span style="font-size: 0.75rem; font-weight: 600; color: var(--text-muted); text-transform: uppercase;">Original (English)</span>
            </div>
        """, unsafe_allow_html=True)

        st.text_area(
            "Original",
            value=tweet.original_text,
            height=250,
            disabled=True,
            key="edit_original",
            label_visibility="collapsed"
        )

    with col2:
        st.markdown("""
            <div style="background: rgba(63, 185, 80, 0.1); padding: 0.75rem; border-radius: 8px; margin-bottom: 0.5rem;">
                <span style="font-size: 0.75rem; font-weight: 600; color: var(--accent-success); text-transform: uppercase;">Hebrew Translation</span>
            </div>
        """, unsafe_allow_html=True)

        hebrew = st.text_area(
            "Hebrew",
            value=tweet.hebrew_draft or "",
            height=250,
            key="edit_hebrew",
            label_visibility="collapsed",
            placeholder="Enter Hebrew translation..."
        )

        # Character count
        char_count = len(hebrew) if hebrew else 0
        pct = min((char_count / 280) * 100, 100)
        bar_color = "var(--accent-success)" if char_count <= 280 else "var(--accent-danger)"

        st.markdown(f"""
            <div style="margin-top: 0.5rem;">
                <div style="display: flex; justify-content: space-between; margin-bottom: 0.25rem;">
                    <span style="font-size: 0.7rem; color: var(--text-muted);">Characters</span>
                    <span style="font-size: 0.75rem; font-weight: 600; color: var(--text-primary);">{char_count}/280</span>
                </div>
                <div style="background: var(--bg-elevated); border-radius: 4px; height: 4px; overflow: hidden;">
                    <div style="background: {bar_color}; width: {pct}%; height: 100%;"></div>
                </div>
            </div>
        """, unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # Action buttons
    col1, col2, col3, col4, col5 = st.columns(5)

    with col1:
        if st.button("Save", key="ed_save", use_container_width=True, type="primary"):
            update_tweet(db, tweet.id, hebrew_draft=hebrew)
            st.success("Saved!")
            time.sleep(0.5)
            st.rerun()

    with col2:
        if st.button("Translate", key="ed_trans", use_container_width=True):
            with st.spinner("Translating..."):
                try:
                    from processor.processor import ProcessorConfig, TranslationService
                    config = ProcessorConfig()
                    translator = TranslationService(config)
                    translation = translator.translate_text(tweet.original_text)
                    if translation:
                        update_tweet(db, tweet.id, hebrew_draft=translation, status=TweetStatus.PROCESSED)
                        st.success("Done!")
                    else:
                        st.error("Empty translation")
                except Exception as e:
                    st.error(str(e)[:50])
            time.sleep(0.5)
            st.rerun()

    with col3:
        if tweet.status != TweetStatus.APPROVED:
            if st.button("Approve", key="ed_approve", use_container_width=True):
                update_tweet(db, tweet.id, status=TweetStatus.APPROVED, hebrew_draft=hebrew)
                st.success("Approved!")
                time.sleep(0.5)
                st.session_state.selected_item = None
                st.rerun()

    with col4:
        if st.button("Reset", key="ed_reset", use_container_width=True):
            update_tweet(db, tweet.id, status=TweetStatus.PENDING)
            st.rerun()

    with col5:
        if st.button("Delete", key="ed_delete", use_container_width=True):
            delete_tweet(db, tweet.id)
            st.session_state.selected_item = None
            st.rerun()

    # Error display
    if tweet.status == TweetStatus.FAILED and tweet.error_message:
        st.error(f"Error: {tweet.error_message}")


def run_batch_translate(db):
    """Run batch translation"""
    pending = db.query(Tweet).filter(Tweet.status == TweetStatus.PENDING).all()

    if not pending:
        st.info("No pending items to translate")
        return

    progress = st.progress(0)
    status_text = st.empty()

    try:
        from processor.processor import ProcessorConfig, TranslationService
        config = ProcessorConfig()
        translator = TranslationService(config)

        success = 0
        for idx, tweet in enumerate(pending):
            status_text.text(f"Translating {idx + 1}/{len(pending)}...")
            progress.progress((idx + 1) / len(pending))

            try:
                translation = translator.translate_text(tweet.original_text)
                if translation:
                    tweet.hebrew_draft = translation
                    tweet.status = TweetStatus.PROCESSED
                    success += 1
                else:
                    tweet.status = TweetStatus.FAILED
                    tweet.error_message = "Empty translation"
            except Exception as e:
                tweet.status = TweetStatus.FAILED
                tweet.error_message = str(e)[:500]

            db.commit()

        progress.empty()
        status_text.empty()
        st.success(f"Translated {success}/{len(pending)} items")
        time.sleep(1)
        st.rerun()

    except Exception as e:
        st.error(f"Error: {str(e)[:100]}")


# =============================================================================
# SCRAPE VIEW
# =============================================================================

def render_scrape(db):
    """Scrape content from X"""

    st.markdown("""
        <div class="page-header">
            <h1 class="page-title">Scrape</h1>
            <p class="page-subtitle">Import threads from X/Twitter</p>
        </div>
    """, unsafe_allow_html=True)

    # Main scrape section
    st.markdown("""
        <div style="background: linear-gradient(135deg, var(--accent-primary) 0%, #7c3aed 100%); padding: 1.5rem; border-radius: 12px; margin-bottom: 1.5rem;">
            <h3 style="color: #ffffff; margin: 0 0 0.5rem 0; font-size: 1.1rem;">Thread Scraper</h3>
            <p style="color: rgba(255,255,255,0.8); margin: 0; font-size: 0.85rem;">Paste a thread URL to import. Only the author's tweets will be captured.</p>
        </div>
    """, unsafe_allow_html=True)

    url = st.text_input(
        "Thread URL",
        placeholder="https://x.com/user/status/1234567890",
        key="scrape_url",
        label_visibility="collapsed"
    )

    col1, col2 = st.columns([1, 2])

    with col1:
        add_to_queue = st.checkbox("Add directly to Content queue", value=True)

    with col2:
        if st.button("Scrape Thread", type="primary", use_container_width=True):
            if not url:
                st.warning("Enter a URL first")
            else:
                with st.spinner("Scraping..."):
                    try:
                        from scraper.scraper import TwitterScraper

                        progress = st.progress(0, "Connecting...")

                        async def run():
                            scraper = TwitterScraper()
                            try:
                                progress.progress(20, "Logging in...")
                                await scraper.ensure_logged_in()
                                progress.progress(40, "Fetching thread...")
                                # Use author_only=True to get only the thread author's tweets
                                return await scraper.fetch_raw_thread(url, author_only=True)
                            finally:
                                await scraper.close()

                        result = asyncio.run(run())
                        tweets_data = result.get('tweets', [])
                        progress.progress(80, "Saving...")

                        if add_to_queue:
                            # Add directly to Content queue
                            saved = 0
                            for t in tweets_data:
                                permalink = t.get('permalink', '')
                                if permalink and not db.query(Tweet).filter_by(source_url=permalink).first():
                                    media_url = t['media'][0]['src'] if t.get('media') else None
                                    db.add(Tweet(
                                        source_url=permalink,
                                        original_text=t.get('text', ''),
                                        status=TweetStatus.PENDING,
                                        media_url=media_url,
                                        trend_topic=t.get('author_handle', '')
                                    ))
                                    saved += 1
                            db.commit()
                            progress.progress(100, "Done!")
                            st.success(f"Added {saved} tweets to Content queue")
                        else:
                            # Store as thread
                            existing = db.query(Thread).filter_by(source_url=url).first()
                            if existing:
                                existing.raw_json = json.dumps(tweets_data)
                                existing.tweet_count = len(tweets_data)
                                existing.updated_at = datetime.now(timezone.utc)
                            else:
                                thread = Thread(
                                    source_url=url,
                                    author_handle=result.get('author_handle', ''),
                                    author_name=result.get('author_name', ''),
                                    raw_json=json.dumps(tweets_data),
                                    tweet_count=len(tweets_data),
                                    status=TweetStatus.PENDING
                                )
                                db.add(thread)
                            db.commit()
                            progress.progress(100, "Done!")
                            st.success(f"Saved thread with {len(tweets_data)} tweets")

                        time.sleep(1)
                        st.rerun()

                    except Exception as e:
                        st.error(f"Scrape failed: {str(e)[:100]}")

    st.markdown("---")

    # Recent scrapes
    st.markdown("### Recent Scrapes")

    recent_tweets = db.query(Tweet).order_by(Tweet.created_at.desc()).limit(10).all()

    if recent_tweets:
        for tweet in recent_tweets:
            status_str = tweet.status.value if hasattr(tweet.status, 'value') else str(tweet.status)
            st.markdown(f"""
                <div style="background: var(--bg-secondary); padding: 0.75rem; border-radius: 8px; margin-bottom: 0.5rem; border: 1px solid var(--border-default);">
                    <div style="display: flex; justify-content: space-between; align-items: center;">
                        <span style="font-weight: 500; color: var(--text-primary);">@{tweet.trend_topic or 'Unknown'}</span>
                        <span class="status-badge status-{status_str.lower()}">{status_str}</span>
                    </div>
                    <div style="font-size: 0.8rem; color: var(--text-secondary); margin-top: 0.25rem;">
                        {tweet.original_text[:100]}...
                    </div>
                </div>
            """, unsafe_allow_html=True)
    else:
        st.info("No content scraped yet. Enter a thread URL above to get started.")


# =============================================================================
# SETTINGS VIEW
# =============================================================================

def render_settings(db):
    """Settings and configuration"""

    st.markdown("""
        <div class="page-header">
            <h1 class="page-title">Settings</h1>
            <p class="page-subtitle">Configuration and database management</p>
        </div>
    """, unsafe_allow_html=True)

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("### Database Stats")

        tweet_count = db.query(Tweet).count()
        thread_count = db.query(Thread).count()
        trend_count = db.query(Trend).count()

        st.metric("Total Tweets", tweet_count)
        st.metric("Total Threads", thread_count)
        st.metric("Total Trends", trend_count)

        st.markdown("---")

        st.markdown("### Danger Zone")
        st.warning("These actions cannot be undone")

        if st.button("Delete All Tweets", use_container_width=True):
            db.query(Tweet).delete()
            db.commit()
            st.success("Deleted all tweets")
            time.sleep(1)
            st.rerun()

        if st.button("Delete All Threads", use_container_width=True):
            db.query(Thread).delete()
            db.commit()
            st.success("Deleted all threads")
            time.sleep(1)
            st.rerun()

    with col2:
        st.markdown("### Status Guide")

        statuses = [
            ('PENDING', 'Inbox - awaiting translation'),
            ('PROCESSED', 'Drafted - needs review'),
            ('APPROVED', 'Ready - approved for publishing'),
            ('PUBLISHED', 'Published - posted to X'),
            ('FAILED', 'Failed - error occurred'),
        ]

        for status, desc in statuses:
            st.markdown(f"""
                <div style="display: flex; align-items: center; gap: 0.75rem; padding: 0.5rem 0;">
                    <span class="status-badge status-{status.lower()}">{status}</span>
                    <span style="color: var(--text-secondary); font-size: 0.85rem;">{desc}</span>
                </div>
            """, unsafe_allow_html=True)

        st.markdown("---")

        st.markdown("### Workflow")
        st.markdown("""
        1. **Scrape** - Fetch threads from X
        2. **Translate** - Auto or manual translation
        3. **Review** - Edit and approve drafts
        4. **Publish** - Post to X (coming soon)
        """)


# =============================================================================
# MAIN
# =============================================================================

def main():
    db = get_db()
    init_navigation()

    # Sidebar with simplified navigation
    with st.sidebar:
        render_sidebar(db)

    # Main content based on current view
    view = st.session_state.current_view

    if view == 'home':
        render_home(db)
    elif view == 'content':
        render_content(db)
    elif view == 'scrape':
        render_scrape(db)
    elif view == 'settings':
        render_settings(db)
    else:
        render_home(db)


if __name__ == "__main__":
    main()
