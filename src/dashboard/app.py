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

from common.models import get_db_session, create_tables, Tweet, Trend, Thread, TrendSource, TweetStatus
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

    /* Dark Mode Design Tokens - Typefully Style */
    :root {
        --bg-primary: #0B0E11;
        --bg-secondary: #14181D;
        --bg-tertiary: #1A1F26;
        --bg-elevated: #1E2329;

        --text-primary: #FFFFFF;
        --text-secondary: #9BA3AE;
        --text-muted: #6B7280;

        --accent-primary: #199AF5;
        --accent-primary-hover: #47B1FF;
        --accent-success: #22C55E;
        --accent-warning: #F59E0B;
        --accent-danger: #EF4444;

        --border-default: rgba(255,255,255,0.08);
        --border-muted: rgba(255,255,255,0.04);

        --shadow-sm: 0 2px 8px rgba(0,0,0,0.25);
        --shadow-md: 0 4px 16px rgba(0,0,0,0.35);
        --shadow-lg: 0 12px 48px rgba(0,0,0,0.5);

        --radius-sm: 8px;
        --radius-md: 12px;
        --radius-lg: 20px;
        --radius-pill: 9999px;
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
       GRADIENT SIDEBAR - Typefully Style
       =========================================== */
    [data-testid="stSidebar"],
    [data-testid="stSidebar"] > div,
    [data-testid="stSidebarContent"],
    section[data-testid="stSidebar"] {
        background: linear-gradient(180deg, #0F1318 0%, var(--bg-primary) 100%) !important;
        border-right: 1px solid var(--border-default) !important;
        width: 260px !important;
        min-width: 260px !important;
    }

    [data-testid="stSidebar"] .block-container {
        padding: 1rem 0.75rem !important;
        background: transparent !important;
    }

    /* Nav Brand with Gradient */
    .nav-brand {
        padding: 1.25rem 1.5rem 1.75rem 1.5rem;
        border-bottom: 1px solid var(--border-default);
        margin-bottom: 1rem;
        text-align: center;
    }

    .nav-brand h1 {
        font-size: 1.75rem !important;
        font-weight: 700 !important;
        margin: 0 !important;
        background: linear-gradient(135deg, #FFFFFF 0%, var(--accent-primary) 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
    }

    .nav-brand p {
        color: var(--text-muted) !important;
        font-size: 0.75rem !important;
        margin: 0.35rem 0 0 0 !important;
    }

    /* Sidebar Nav Buttons - Transparent with Active Indicator */
    [data-testid="stSidebar"] .stButton > button {
        background: transparent !important;
        color: var(--text-secondary) !important;
        border: none !important;
        font-weight: 500 !important;
        border-radius: 0 var(--radius-md) var(--radius-md) 0 !important;
        transition: all 0.2s ease !important;
        padding: 0.75rem 1rem !important;
    }

    [data-testid="stSidebar"] .stButton > button:hover {
        background: rgba(255,255,255,0.05) !important;
        color: var(--text-primary) !important;
    }

    [data-testid="stSidebar"] .stButton > button[data-testid="baseButton-primary"] {
        background: rgba(25, 154, 245, 0.15) !important;
        color: var(--accent-primary) !important;
        border-left: 3px solid var(--accent-primary) !important;
        font-weight: 600 !important;
    }

    [data-testid="stSidebar"] .stButton > button[data-testid="baseButton-primary"]:hover {
        background: rgba(25, 154, 245, 0.2) !important;
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
        box-shadow: 0 0 0 4px rgba(25, 154, 245, 0.15) !important;
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
       CONTENT CARDS - Typefully Style
       =========================================== */
    .content-card {
        background: var(--bg-secondary);
        border-radius: var(--radius-lg);
        padding: 1.5rem;
        margin-bottom: 1rem;
        border: 1px solid var(--border-default);
        box-shadow: var(--shadow-sm);
        transition: all 0.2s ease;
    }

    .content-card:hover {
        border-color: rgba(25, 154, 245, 0.3);
        box-shadow: var(--shadow-md);
        transform: translateY(-2px);
    }

    /* Stat Cards */
    .stat-card {
        background: var(--bg-secondary);
        border-radius: var(--radius-lg);
        padding: 1.5rem 1.25rem;
        border: 1px solid var(--border-default);
        text-align: center;
        position: relative;
        overflow: hidden;
        transition: all 0.2s ease;
    }

    .stat-card::before {
        content: '';
        position: absolute;
        top: 0;
        left: 0;
        right: 0;
        height: 3px;
        background: var(--accent-primary);
        opacity: 0;
        transition: opacity 0.2s ease;
    }

    .stat-card:hover::before {
        opacity: 1;
    }

    .stat-card:hover {
        transform: translateY(-2px);
        box-shadow: var(--shadow-md);
    }

    .stat-value {
        font-size: 2.5rem;
        font-weight: 700;
        color: var(--text-primary);
        line-height: 1;
    }

    .stat-label {
        font-size: 0.75rem;
        font-weight: 500;
        color: var(--text-muted);
        text-transform: uppercase;
        letter-spacing: 0.08em;
        margin-top: 0.5rem;
    }

    .stat-inbox .stat-value { color: var(--accent-warning); }
    .stat-inbox::before { background: var(--accent-warning); }
    .stat-drafts .stat-value { color: var(--accent-primary); }
    .stat-drafts::before { background: var(--accent-primary); }
    .stat-ready .stat-value { color: var(--accent-success); }
    .stat-ready::before { background: var(--accent-success); }
    .stat-published .stat-value { color: var(--text-secondary); }
    .stat-published::before { background: var(--text-secondary); }

    /* ===========================================
       PILL BUTTONS - Typefully Style
       =========================================== */
    .stButton > button {
        font-family: 'Inter', sans-serif !important;
        font-size: 0.875rem !important;
        font-weight: 500 !important;
        padding: 0.625rem 1.25rem !important;
        border-radius: var(--radius-pill) !important;
        border: 1px solid var(--border-default) !important;
        background: var(--bg-secondary) !important;
        color: var(--text-primary) !important;
        box-shadow: var(--shadow-sm) !important;
        transition: all 0.2s ease !important;
    }

    .stButton > button:hover {
        background: var(--bg-elevated) !important;
        border-color: rgba(25, 154, 245, 0.3) !important;
        transform: translateY(-1px) !important;
        box-shadow: var(--shadow-md) !important;
    }

    .stButton > button[data-testid="baseButton-primary"] {
        background: rgba(25, 154, 245, 0.15) !important;
        color: #199AF5 !important;
        border: 1px solid rgba(25, 154, 245, 0.3) !important;
        font-weight: 600 !important;
    }

    .stButton > button[data-testid="baseButton-primary"]:hover {
        background: rgba(25, 154, 245, 0.25) !important;
        box-shadow: none !important;
        transform: none !important;
    }

    /* Status Badges - Typefully Style with Borders */
    .status-badge {
        display: inline-flex;
        align-items: center;
        gap: 0.25rem;
        padding: 0.35rem 0.875rem;
        border-radius: var(--radius-pill);
        font-size: 0.65rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }

    .status-pending {
        background: rgba(245, 158, 11, 0.15);
        color: #FBBF24;
        border: 1px solid rgba(245, 158, 11, 0.3);
    }
    .status-processed {
        background: rgba(25, 154, 245, 0.15);
        color: #47B1FF;
        border: 1px solid rgba(25, 154, 245, 0.3);
    }
    .status-approved {
        background: rgba(34, 197, 94, 0.15);
        color: #4ADE80;
        border: 1px solid rgba(34, 197, 94, 0.3);
    }
    .status-published {
        background: rgba(155, 163, 174, 0.15);
        color: #9BA3AE;
        border: 1px solid rgba(155, 163, 174, 0.3);
    }
    .status-failed {
        background: rgba(239, 68, 68, 0.15);
        color: #F87171;
        border: 1px solid rgba(239, 68, 68, 0.3);
    }

    /* Source Badges */
    .source-yahoo-finance { background: rgba(155, 89, 182, 0.15); color: #BB86FC; border: 1px solid rgba(155, 89, 182, 0.3); }
    .source-wsj { background: rgba(25, 154, 245, 0.15); color: #47B1FF; border: 1px solid rgba(25, 154, 245, 0.3); }
    .source-techcrunch { background: rgba(34, 197, 94, 0.15); color: #4ADE80; border: 1px solid rgba(34, 197, 94, 0.3); }
    .source-bloomberg { background: rgba(155, 89, 182, 0.15); color: #BB86FC; border: 1px solid rgba(155, 89, 182, 0.3); }
    .source-marketwatch { background: rgba(255, 193, 7, 0.15); color: #FFC107; border: 1px solid rgba(255, 193, 7, 0.3); }
    .source-manual { background: rgba(155, 163, 174, 0.15); color: #9BA3AE; border: 1px solid rgba(155, 163, 174, 0.3); }
    .source-x { background: rgba(255, 255, 255, 0.1); color: #E4E6EA; border: 1px solid rgba(255, 255, 255, 0.2); }

    /* Category Badges */
    .category-finance { background: rgba(255, 159, 10, 0.15); color: #FFA726; border: 1px solid rgba(255, 159, 10, 0.3); }
    .category-tech { background: rgba(33, 150, 243, 0.15); color: #42A5F5; border: 1px solid rgba(33, 150, 243, 0.3); }

    /* ===========================================
       FORM ELEMENTS - Typefully Style
       =========================================== */
    .stTextInput input, .stTextArea textarea {
        font-family: 'Inter', sans-serif !important;
        border-radius: var(--radius-md) !important;
        border: 1px solid var(--border-default) !important;
        background: var(--bg-tertiary) !important;
        color: var(--text-primary) !important;
        font-size: 0.875rem !important;
        padding: 0.75rem 1rem !important;
        transition: all 0.2s ease !important;
    }

    .stTextInput input:focus, .stTextArea textarea:focus {
        border-color: var(--accent-primary) !important;
        box-shadow: 0 0 0 4px rgba(25, 154, 245, 0.15) !important;
        background: var(--bg-elevated) !important;
    }

    .stTextInput input::placeholder, .stTextArea textarea::placeholder {
        color: var(--text-muted) !important;
    }

    .stSelectbox > div > div {
        border-radius: var(--radius-md) !important;
        border: 1px solid var(--border-default) !important;
        background: var(--bg-tertiary) !important;
        color: var(--text-primary) !important;
        transition: all 0.2s ease !important;
    }

    .stSelectbox > div > div:hover {
        border-color: rgba(25, 154, 245, 0.3) !important;
    }

    .stCheckbox > label {
        font-size: 0.875rem !important;
        color: var(--text-secondary) !important;
    }

    /* Checkbox - Green when checked with white checkmark */
    /* Streamlit uses label[data-baseweb="checkbox"] > span for the visual checkbox */
    /* The span gets a background-image SVG checkmark when checked */
    label[data-baseweb="checkbox"] > span {
        transition: all 0.15s ease !important;
    }

    /* When checkbox input is checked (has aria-checked=true), style the preceding span */
    /* Since CSS can't select previous siblings, we use the label's state */
    label[data-baseweb="checkbox"]:has(input[aria-checked="true"]) > span {
        background-color: #22C55E !important;
        border-color: #22C55E !important;
        background-image: url("data:image/svg+xml,%3Csvg width='17' height='13' viewBox='0 0 17 13' fill='none' xmlns='http://www.w3.org/2000/svg'%3E%3Cpath d='M6.50002 12.6L0.400024 6.60002L2.60002 4.40002L6.50002 8.40002L13.9 0.900024L16.1 3.10002L6.50002 12.6Z' fill='white'/%3E%3C/svg%3E") !important;
    }

    /* Unchecked state - dark background with subtle border */
    label[data-baseweb="checkbox"]:has(input[aria-checked="false"]) > span {
        background-color: var(--bg-tertiary) !important;
        border-color: var(--border-default) !important;
    }

    /* ===========================================
       PAGE HEADER - Typefully Style
       =========================================== */
    .page-header {
        margin-bottom: 2rem;
        padding-bottom: 1.25rem;
        border-bottom: 1px solid var(--border-default);
    }

    .page-title {
        font-size: 1.75rem;
        font-weight: 700;
        color: var(--text-primary);
        letter-spacing: -0.025em;
        margin: 0 0 0.5rem 0;
    }

    .page-subtitle {
        font-size: 0.9rem;
        font-weight: 400;
        color: var(--text-muted);
        margin: 0;
    }

    /* ===========================================
       EMPTY STATE - Typefully Style
       =========================================== */
    .empty-state {
        text-align: center;
        padding: 4rem 2rem;
        background: linear-gradient(180deg, var(--bg-secondary) 0%, var(--bg-primary) 100%);
        border-radius: var(--radius-lg);
        border: 1px solid var(--border-default);
    }

    .empty-state-icon {
        font-size: 4rem;
        margin-bottom: 1.5rem;
        opacity: 0.3;
    }

    .empty-state-title {
        font-size: 1.25rem;
        font-weight: 600;
        color: var(--text-primary);
        margin-bottom: 0.75rem;
    }

    .empty-state-text {
        color: var(--text-muted);
        font-size: 0.9rem;
        max-width: 400px;
        margin: 0 auto;
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

    /* Queue Item - Typefully Style with Slide Animation */
    .queue-item {
        background: var(--bg-secondary);
        border-radius: var(--radius-md);
        padding: 1rem 1.25rem;
        margin-bottom: 0.75rem;
        border: 1px solid var(--border-default);
        transition: all 0.2s ease;
        cursor: pointer;
    }

    .queue-item:hover {
        border-color: rgba(25, 154, 245, 0.4);
        background: var(--bg-tertiary);
        box-shadow: var(--shadow-sm);
        transform: translateX(4px);
    }

    .queue-item-author {
        font-size: 0.8rem;
        font-weight: 600;
        color: var(--text-primary);
        margin-bottom: 0.35rem;
    }

    .queue-item-text {
        font-size: 0.85rem;
        color: var(--text-secondary);
        line-height: 1.5;
        display: -webkit-box;
        -webkit-line-clamp: 2;
        -webkit-box-orient: vertical;
        overflow: hidden;
    }

    .queue-item-meta {
        display: flex;
        align-items: center;
        gap: 0.75rem;
        margin-top: 0.75rem;
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

    /* ===========================================
       MICRO-ANIMATIONS - Typefully Style
       =========================================== */
    * {
        transition-timing-function: cubic-bezier(0.4, 0, 0.2, 1);
    }

    :focus-visible {
        outline: none;
        box-shadow: 0 0 0 3px rgba(25, 154, 245, 0.5) !important;
    }

    @keyframes shimmer {
        0% { background-position: -200% 0; }
        100% { background-position: 200% 0; }
    }

    .loading-shimmer {
        background: linear-gradient(90deg, var(--bg-secondary) 0%, var(--bg-tertiary) 50%, var(--bg-secondary) 100%);
        background-size: 200% 100%;
        animation: shimmer 1.5s infinite;
    }

    @keyframes fadeIn {
        from { opacity: 0; transform: translateY(8px); }
        to { opacity: 1; transform: translateY(0); }
    }

    .fade-in {
        animation: fadeIn 0.3s ease-out;
    }

    @keyframes pulse {
        0%, 100% { opacity: 1; }
        50% { opacity: 0.5; }
    }

    .pulse {
        animation: pulse 2s ease-in-out infinite;
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
# TREND RANKING
# =============================================================================

def get_source_badge_class(source_name: str) -> str:
    """Return CSS class for a source badge."""
    mapping = {
        'Yahoo Finance': 'source-yahoo-finance',
        'WSJ': 'source-wsj',
        'TechCrunch': 'source-techcrunch',
        'Bloomberg': 'source-bloomberg',
        'MarketWatch': 'source-marketwatch',
        'Manual': 'source-manual',
        'X': 'source-x',
    }
    return mapping.get(source_name, 'source-manual')


# =============================================================================
# NAVIGATION - 3 tabs
# =============================================================================

def init_navigation():
    """Initialize navigation state"""
    if 'current_view' not in st.session_state:
        st.session_state.current_view = 'home'


def render_sidebar(db):
    """Sidebar with 3 navigation items"""

    # Brand header
    st.markdown("""
        <div class="nav-brand">
            <h1>HFI</h1>
            <p>Hebrew FinTech Informant</p>
        </div>
    """, unsafe_allow_html=True)

    nav_items = [
        ('home', 'Home'),
        ('content', 'Content'),
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
    """Home - overview of processed content and discovered trends"""

    st.markdown("""
        <div class="page-header">
            <h1 class="page-title">Home</h1>
            <p class="page-subtitle">Your processed content and discovered trends</p>
        </div>
    """, unsafe_allow_html=True)

    stats = get_stats(db)

    # Pipeline stats row
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.markdown(f'<div class="stat-card stat-inbox"><div class="stat-value">{stats["pending"]}</div><div class="stat-label">Inbox</div></div>', unsafe_allow_html=True)
    with col2:
        st.markdown(f'<div class="stat-card stat-drafts"><div class="stat-value">{stats["processed"]}</div><div class="stat-label">Drafts</div></div>', unsafe_allow_html=True)
    with col3:
        st.markdown(f'<div class="stat-card stat-ready"><div class="stat-value">{stats["approved"]}</div><div class="stat-label">Ready</div></div>', unsafe_allow_html=True)
    with col4:
        st.markdown(f'<div class="stat-card stat-published"><div class="stat-value">{stats["published"]}</div><div class="stat-label">Published</div></div>', unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # Two-column layout: processed content + trends
    col_left, col_right = st.columns(2)

    with col_left:
        st.markdown("### Processed Content")
        processed = db.query(Tweet).filter(
            Tweet.status.in_([TweetStatus.PROCESSED, TweetStatus.APPROVED, TweetStatus.PUBLISHED])
        ).order_by(Tweet.updated_at.desc()).limit(10).all()

        if processed:
            for tweet in processed:
                status_str = tweet.status.value if hasattr(tweet.status, 'value') else str(tweet.status)
                hebrew_preview = (tweet.hebrew_draft[:80] + '...') if tweet.hebrew_draft and len(tweet.hebrew_draft) > 80 else (tweet.hebrew_draft or '')
                link_html = f'<a href="{tweet.source_url}" target="_blank" style="color: var(--accent-primary); font-size: 0.7rem; text-decoration: none;">source</a>' if tweet.source_url and tweet.source_url.startswith('http') else ''
                st.markdown(f"""
                    <div class="queue-item">
                        <div style="display: flex; justify-content: space-between; align-items: center;">
                            <span class="queue-item-author">{tweet.trend_topic or 'Unknown'}</span>
                            <span class="status-badge status-{status_str.lower()}">{status_str}</span>
                        </div>
                        <div class="queue-item-text" style="direction: rtl; text-align: right; margin-top: 0.35rem;">{hebrew_preview}</div>
                        <div class="queue-item-meta">{link_html}</div>
                    </div>
                """, unsafe_allow_html=True)
        else:
            st.info("No processed content yet. Go to Content to scrape and translate.")

    with col_right:
        st.markdown("### Discovered Trends")
        trends = db.query(Trend).order_by(Trend.discovered_at.desc()).limit(15).all()

        if trends:
            for trend in trends:
                source_val = trend.source.value if hasattr(trend.source, 'value') else str(trend.source)
                badge_cls = get_source_badge_class(source_val)
                desc_html = f'<div style="font-size: 0.8rem; color: var(--text-muted); margin-top: 0.25rem;">{trend.description[:120]}...</div>' if trend.description and len(trend.description) > 10 else ''
                link_html = f'<a href="{trend.article_url}" target="_blank" style="color: var(--accent-primary); font-size: 0.8rem; text-decoration: none;">{trend.title}</a>' if trend.article_url else f'<span style="color: var(--text-primary); font-size: 0.85rem;">{trend.title}</span>'
                st.markdown(f"""
                    <div class="queue-item">
                        <div style="display: flex; justify-content: space-between; align-items: center;">
                            {link_html}
                            <span class="status-badge {badge_cls}">{source_val}</span>
                        </div>
                        {desc_html}
                    </div>
                """, unsafe_allow_html=True)
        else:
            st.info("No trends discovered yet. Go to Content to fetch trends.")


# =============================================================================
# CONTENT VIEW (Queue + Editor)
# =============================================================================

def render_content(db):
    """Content view - acquire content and manage queue"""

    st.markdown("""
        <div class="page-header">
            <h1 class="page-title">Content</h1>
            <p class="page-subtitle">Acquire and manage content</p>
        </div>
    """, unsafe_allow_html=True)

    # Auto-translate if triggered
    if st.session_state.get('auto_translate'):
        st.session_state.auto_translate = False
        run_batch_translate(db)

    # Initialize selected item state
    if 'selected_item' not in st.session_state:
        st.session_state.selected_item = None

    # If editing a specific item, show editor
    if st.session_state.selected_item:
        render_editor(db, st.session_state.selected_item)
        return

    # Use tabs to organize: Acquire | Queue
    tab_acquire, tab_queue = st.tabs(["Acquire", "Queue"])

    with tab_acquire:
        _render_acquire_section(db)

    with tab_queue:
        _render_queue_section(db)


def _render_acquire_section(db):
    """Acquire section: thread scraper + trend fetching"""

    # ---- Thread Scraper ----
    st.markdown("### Scrape Thread from X")

    url = st.text_input(
        "Thread URL",
        placeholder="https://x.com/user/status/1234567890",
        key="scrape_url",
        label_visibility="collapsed"
    )

    col1, col2, col3 = st.columns([1, 1, 1])
    with col1:
        add_to_queue = st.checkbox("Add to queue", value=True)
    with col2:
        consolidate = st.checkbox("Consolidate thread", value=True)
    with col3:
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
                                return await scraper.fetch_raw_thread(url, author_only=True)
                            finally:
                                await scraper.close()

                        result = asyncio.run(run())
                        tweets_data = result.get('tweets', [])
                        progress.progress(80, "Saving...")

                        if add_to_queue:
                            if consolidate and len(tweets_data) > 1:
                                combined_text = "\n\n---\n\n".join([t.get('text', '') for t in tweets_data])
                                first_url = tweets_data[0].get('permalink', url) if tweets_data else url
                                media_urls = [t['media'][0]['src'] for t in tweets_data if t.get('media')]
                                if not db.query(Tweet).filter_by(source_url=first_url).first():
                                    db.add(Tweet(
                                        source_url=first_url,
                                        original_text=combined_text,
                                        status=TweetStatus.PENDING,
                                        media_url=media_urls[0] if media_urls else None,
                                        trend_topic=result.get('author_handle', '')
                                    ))
                                    db.commit()
                                    progress.progress(100, "Done!")
                                    st.success(f"Added consolidated thread ({len(tweets_data)} tweets combined)")
                                else:
                                    progress.progress(100, "Done!")
                                    st.info("Thread already exists in queue")
                            else:
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
                                st.success(f"Added {saved} tweets to queue")
                        else:
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

    # ---- Fetch All Trends ----
    st.markdown("### Discover Trends")

    fcol1, fcol2 = st.columns([3, 1])
    with fcol1:
        st.markdown('<p style="color: var(--text-secondary); font-size: 0.85rem;">Fetch articles with weighted sampling: 70% finance (Yahoo, WSJ, Bloomberg) + 30% tech (TechCrunch), ranked by keyword overlap.</p>', unsafe_allow_html=True)
    with fcol2:
        fetch_all = st.button("Fetch All Trends", type="primary", use_container_width=True, key="fetch_all_trends")

    if fetch_all:
        with st.spinner("Fetching from all sources..."):
            try:
                from scraper.news_scraper import NewsScraper
                scraper = NewsScraper()
                # Use weighted sampling: 70% finance, 30% tech
                # Fetch 10 per source to account for deduplication and filtering
                ranked_news = scraper.get_latest_news(limit_per_source=10, total_limit=10, finance_weight=0.7)

                # Save to DB with article_url
                source_map = {
                    'Yahoo Finance': TrendSource.YAHOO_FINANCE,
                    'WSJ': TrendSource.WSJ,
                    'TechCrunch': TrendSource.TECHCRUNCH,
                    'Bloomberg': TrendSource.BLOOMBERG,
                    'MarketWatch': TrendSource.MARKETWATCH,
                }
                saved = 0
                for article in ranked_news:
                    if not db.query(Trend).filter_by(title=article['title']).first():
                        db.add(Trend(
                            title=article['title'],
                            description=article.get('description', '')[:500],
                            source=source_map.get(article['source'], TrendSource.MANUAL),
                            article_url=article.get('url', ''),
                        ))
                        saved += 1
                db.commit()

                st.session_state.ranked_articles = ranked_news
                st.success(f"Fetched & ranked top {len(ranked_news)} articles, saved {saved} new trends")
                time.sleep(0.5)
                st.rerun()
            except Exception as e:
                st.error(f"Failed: {str(e)[:150]}")

    # ---- Show Ranked Articles ----
    ranked = st.session_state.get('ranked_articles', None)
    if ranked:
        # Count distribution
        finance_count = sum(1 for a in ranked if a.get('category') == 'Finance')
        tech_count = sum(1 for a in ranked if a.get('category') == 'Tech')

        st.markdown(f"""
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 1rem;">
                <h3 style="margin: 0;">Top Articles (Ranked)</h3>
                <div style="display: flex; gap: 0.5rem;">
                    <span class="status-badge category-finance">💰 Finance: {finance_count}</span>
                    <span class="status-badge category-tech">💻 Tech: {tech_count}</span>
                </div>
            </div>
        """, unsafe_allow_html=True)

        for idx, art in enumerate(ranked, 1):
            art_url = art.get('url', '')
            art_title = art.get('title', '')
            art_desc = (art.get('description', '') or '')[:120]
            art_source = art.get('source', '')
            art_category = art.get('category', 'Unknown')
            badge_cls = get_source_badge_class(art_source)
            category_emoji = "💰" if art_category == "Finance" else "💻"
            title_html = f'<a href="{art_url}" target="_blank" style="color: var(--accent-primary); text-decoration: none; font-size: 0.9rem; font-weight: 500;">{art_title}</a>' if art_url else f'<span style="color: var(--text-primary); font-size: 0.9rem; font-weight: 500;">{art_title}</span>'
            desc_html = f'<div style="font-size: 0.8rem; color: var(--text-muted); margin-top: 0.25rem;">{art_desc}</div>' if art_desc else ''

            st.markdown(f"""
                <div class="queue-item">
                    <div style="display: flex; justify-content: space-between; align-items: center;">
                        <div style="display: flex; align-items: center; gap: 0.5rem;">
                            <span style="font-size: 0.75rem; font-weight: 700; color: var(--text-muted); min-width: 1.5rem;">#{idx}</span>
                            <span style="font-size: 1rem;">{category_emoji}</span>
                            {title_html}
                        </div>
                        <span class="status-badge {badge_cls}">{art_source}</span>
                    </div>
                    {desc_html}
                </div>
            """, unsafe_allow_html=True)
    else:
        # Show recent trends from DB if no ranked results
        trends = db.query(Trend).order_by(Trend.discovered_at.desc()).limit(10).all()
        if trends:
            st.markdown("### Recent Trends")
            for trend in trends:
                source_val = trend.source.value if hasattr(trend.source, 'value') else str(trend.source)
                badge_cls = get_source_badge_class(source_val)
                link_html = f'<a href="{trend.article_url}" target="_blank" style="color: var(--accent-primary); text-decoration: none;">{trend.title}</a>' if trend.article_url else f'<span style="color: var(--text-primary);">{trend.title}</span>'
                st.markdown(f"""
                    <div class="queue-item">
                        <div style="display: flex; justify-content: space-between; align-items: center;">
                            {link_html}
                            <span class="status-badge {badge_cls}">{source_val}</span>
                        </div>
                    </div>
                """, unsafe_allow_html=True)

    st.markdown("---")

    # ---- Manual Trend Entry ----
    st.markdown("### Add Manual Trend")
    mcol1, mcol2 = st.columns([3, 1])
    with mcol1:
        manual = st.text_input("Trend Title", key="manual_trend", label_visibility="collapsed", placeholder="Enter trend topic...")
    with mcol2:
        if st.button("Add Trend", key="add_manual_trend", disabled=not manual, use_container_width=True):
            db.add(Trend(title=manual, source=TrendSource.MANUAL))
            db.commit()
            st.success(f"Added: {manual}")
            time.sleep(0.5)
            st.rerun()


def _render_queue_section(db):
    """Queue section: content list with actions"""
    stats = get_stats(db)

    col1, col2, col3, col4 = st.columns([1, 1, 1, 1])
    with col1:
        if st.button("Translate All", use_container_width=True, disabled=stats['pending'] == 0, key="q_translate"):
            run_batch_translate(db)
    with col2:
        if st.button("Approve All", use_container_width=True, disabled=stats['processed'] == 0, key="q_approve"):
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
            label_visibility="collapsed",
            key="q_filter"
        )
    with col4:
        st.caption(f"Total: {stats['total']} items")

    st.markdown("---")

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

        # ---- Glossary Editor ----
        st.markdown("### Glossary Editor")
        glossary_path = Path(__file__).parent.parent.parent / "config" / "glossary.json"
        try:
            glossary_data = json.loads(glossary_path.read_text(encoding='utf-8')) if glossary_path.exists() else {}
        except Exception:
            glossary_data = {}
        edited_glossary = st.text_area(
            "Glossary (JSON)",
            json.dumps(glossary_data, indent=2, ensure_ascii=False),
            height=200,
            key="glossary_editor"
        )
        if st.button("Save Glossary", key="save_glossary", use_container_width=True):
            try:
                json.loads(edited_glossary)  # validate JSON
                glossary_path.parent.mkdir(parents=True, exist_ok=True)
                glossary_path.write_text(edited_glossary, encoding='utf-8')
                st.success("Glossary saved!")
            except json.JSONDecodeError:
                st.error("Invalid JSON. Please fix and try again.")

        st.markdown("---")

        # ---- Style Guide Editor ----
        st.markdown("### Style Guide Editor")
        style_path = Path(__file__).parent.parent.parent / "config" / "style.txt"
        try:
            style_content = style_path.read_text(encoding='utf-8') if style_path.exists() else ""
        except Exception:
            style_content = ""
        edited_style = st.text_area(
            "Style Examples",
            style_content,
            height=200,
            key="style_editor"
        )
        if st.button("Save Style Guide", key="save_style", use_container_width=True):
            style_path.parent.mkdir(parents=True, exist_ok=True)
            style_path.write_text(edited_style, encoding='utf-8')
            st.success("Style guide saved!")

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

        st.markdown("---")

        # ---- Data Export ----
        st.markdown("### Data Export")
        all_tweets = db.query(Tweet).all()
        tweets_export = json.dumps(
            [{"id": t.id, "text": t.original_text, "hebrew": t.hebrew_draft, "status": t.status.value} for t in all_tweets],
            indent=2, ensure_ascii=False
        )
        st.download_button("Export Tweets (JSON)", tweets_export, "tweets.json", mime="application/json", use_container_width=True)

        all_trends = db.query(Trend).all()
        trends_export = json.dumps(
            [{"title": t.title, "source": t.source.value, "description": t.description} for t in all_trends],
            indent=2, ensure_ascii=False
        )
        st.download_button("Export Trends (JSON)", trends_export, "trends.json", mime="application/json", use_container_width=True)

    st.markdown("---")

    # ---- Danger Zone ----
    st.markdown("### Danger Zone")
    with st.expander("Destructive Actions"):
        st.warning("These actions cannot be undone")
        confirm = st.checkbox("I understand this cannot be undone", key="danger_confirm")

        dcol1, dcol2, dcol3 = st.columns(3)
        with dcol1:
            if st.button("Delete All Tweets", use_container_width=True, disabled=not confirm):
                db.query(Tweet).delete()
                db.commit()
                st.success("Deleted all tweets")
                time.sleep(1)
                st.rerun()
        with dcol2:
            if st.button("Delete All Threads", use_container_width=True, disabled=not confirm):
                db.query(Thread).delete()
                db.commit()
                st.success("Deleted all threads")
                time.sleep(1)
                st.rerun()
        with dcol3:
            if st.button("Delete All Trends", use_container_width=True, disabled=not confirm):
                db.query(Trend).delete()
                db.commit()
                st.success("Deleted all trends")
                time.sleep(1)
                st.rerun()


# =============================================================================
# MAIN
# =============================================================================

def main():
    create_tables()
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
    elif view == 'settings':
        render_settings(db)
    else:
        render_home(db)


if __name__ == "__main__":
    main()
