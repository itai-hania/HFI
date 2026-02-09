"""
HFI Dashboard - Hebrew FinTech Informant
Dark Mode UI with Simplified Navigation
"""

import streamlit as st
import logging
import asyncio
import os
import html
from pathlib import Path
from datetime import datetime, timezone
import time

# Load environment variables from .env file
from dotenv import load_dotenv
env_path = Path(__file__).parent.parent.parent / ".env"
load_dotenv(env_path)

from common.models import get_db_session, create_tables, Tweet, Trend, Thread, TrendSource, TweetStatus, StyleExample
import json
from sqlalchemy import func
from dashboard.helpers import get_source_badge_class, parse_media_info, format_status_str

logger = logging.getLogger(__name__)

# Lazy load style manager
def get_style_manager():
    """Lazy load style manager functions."""
    try:
        from processor import style_manager
        return style_manager
    except Exception as e:
        logger.warning(f"Could not load style_manager: {e}")
        return None

# Import summary generator (lazy load to avoid import errors if OpenAI key not set)
def get_summary_generator():
    """Lazy load summary generator to avoid import errors."""
    try:
        from processor.summary_generator import SummaryGenerator
        return SummaryGenerator()
    except Exception as e:
        logger.warning(f"Could not initialize SummaryGenerator: {e}")
        return None

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

    /* ===========================================
       RTL SUPPORT FOR HEBREW CONTENT
       =========================================== */
    .rtl-container {
        direction: rtl;
        text-align: right;
        font-family: 'Heebo', 'Segoe UI', 'Arial', sans-serif;
    }

    .ltr-container {
        direction: ltr;
        text-align: left;
    }

    /* Side-by-side translation panel */
    .translation-panel {
        background: var(--bg-secondary);
        border-radius: var(--radius-lg);
        border: 1px solid var(--border-default);
        padding: 1.25rem;
        margin-bottom: 1rem;
    }

    .translation-panel-header {
        display: flex;
        align-items: center;
        gap: 0.5rem;
        padding: 0.5rem 0.75rem;
        border-radius: var(--radius-sm);
        margin-bottom: 0.75rem;
        font-size: 0.75rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }

    .translation-panel-english {
        background: var(--bg-tertiary);
        color: var(--text-muted);
    }

    .translation-panel-hebrew {
        background: rgba(34, 197, 94, 0.1);
        color: var(--accent-success);
    }

    .translation-content {
        font-size: 0.9rem;
        line-height: 1.7;
        color: var(--text-secondary);
        padding: 0.75rem;
        background: var(--bg-tertiary);
        border-radius: var(--radius-sm);
        min-height: 60px;
        white-space: pre-wrap;
    }

    .translation-content.hebrew {
        direction: rtl;
        text-align: right;
        color: var(--text-primary);
        font-family: 'Heebo', 'David', 'Segoe UI', sans-serif;
    }

    .thread-tweet-item {
        background: var(--bg-secondary);
        border-radius: var(--radius-md);
        padding: 1rem;
        margin-bottom: 0.75rem;
        border: 1px solid var(--border-default);
        transition: all 0.2s ease;
    }

    .thread-tweet-item:hover {
        border-color: rgba(25, 154, 245, 0.3);
    }

    .thread-tweet-number {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        width: 1.5rem;
        height: 1.5rem;
        background: var(--accent-primary);
        color: white;
        font-size: 0.7rem;
        font-weight: 700;
        border-radius: 50%;
        margin-right: 0.5rem;
    }

    .thread-tweet-number.rtl {
        margin-right: 0;
        margin-left: 0.5rem;
    }

    /* Hebrew font loading */
    @import url('https://fonts.googleapis.com/css2?family=Heebo:wght@400;500;600;700&display=swap');
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


def delete_trend(db, trend_id):
    """Delete a trend from the database."""
    trend = db.query(Trend).filter(Trend.id == trend_id).first()
    if trend:
        db.delete(trend)
        db.commit()
        return True
    return False


# =============================================================================
# TREND RANKING
# =============================================================================

# get_source_badge_class imported from dashboard.helpers


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

    # ==========================================================================
    # PHASE 4: Full-width rows with collapsible sections (using session state)
    # ==========================================================================

    # Initialize section toggle states
    if 'home_trends_expanded' not in st.session_state:
        st.session_state.home_trends_expanded = True
    if 'home_threads_expanded' not in st.session_state:
        st.session_state.home_threads_expanded = True

    # --- Section 1: Discovered Trends (Full Width) ---
    trends = db.query(Trend).order_by(Trend.discovered_at.desc()).limit(15).all()
    trends_count = len(trends)

    # Collapsible section using checkbox styled as header
    trends_expanded = st.checkbox(
        f"📰 Discovered Trends ({trends_count})",
        value=st.session_state.home_trends_expanded,
        key="trends_section_toggle"
    )
    st.session_state.home_trends_expanded = trends_expanded

    if trends_expanded:
        if trends:
            for idx, trend in enumerate(trends):
                source_val = trend.source.value if hasattr(trend.source, 'value') else str(trend.source)
                badge_cls = get_source_badge_class(source_val)
                safe_title = html.escape(trend.title or '')

                # Check if already in queue
                in_queue = db.query(Tweet).filter(Tweet.trend_topic == trend.title).first() is not None

                # Summary (more room now - full width)
                summary_text = ''
                if trend.summary:
                    summary_text = html.escape(trend.summary[:250]) + ('...' if len(trend.summary) > 250 else '')
                elif trend.description and len(trend.description) > 10:
                    summary_text = html.escape(trend.description[:200]) + '...'

                # Full-width trend card using st.container
                with st.container():
                    # Main card row - title, badge, generate, queue, delete buttons
                    card_col1, card_col2, card_col_gen, card_col3, card_col4 = st.columns([4, 1, 1, 1, 0.5])
                    with card_col1:
                        # Title with rank
                        if trend.article_url:
                            st.markdown(f"**#{idx + 1}** [{safe_title}]({html.escape(trend.article_url)})")
                        else:
                            st.markdown(f"**#{idx + 1}** {safe_title}")
                        # Summary
                        if summary_text:
                            st.caption(summary_text)
                        # Keywords
                        if trend.keywords and isinstance(trend.keywords, list) and len(trend.keywords) > 0:
                            st.markdown(f"🏷️ {', '.join(trend.keywords[:5])}")
                    with card_col2:
                        # Source badge
                        st.markdown(f'<span class="status-badge {badge_cls}">{html.escape(source_val)}</span>', unsafe_allow_html=True)
                        if trend.source_count and trend.source_count > 1:
                            st.caption(f"{trend.source_count} sources")
                    with card_col_gen:
                        if st.button("Generate", key=f"home_gen_{trend.id}", use_container_width=True):
                            # Pre-fill source text and navigate to Content > Generate
                            source = f"{trend.title}\n\n{trend.description or trend.summary or ''}"
                            st.session_state['generate_source_text'] = source.strip()
                            st.session_state.current_view = 'content'
                            st.rerun()

                    with card_col3:
                        # Queue button in same row
                        if in_queue:
                            st.success("✓ In Queue")
                        else:
                            if st.button("+ Queue", key=f"home_add_trend_{trend.id}", use_container_width=True):
                                new_tweet = Tweet(
                                    source_url=trend.article_url or f"trend_{trend.id}",
                                    original_text=f"{trend.title}\n\n{trend.description or trend.summary or ''}",
                                    trend_topic=trend.title,
                                    status=TweetStatus.PENDING
                                )
                                db.add(new_tweet)
                                db.commit()
                                st.success(f"Added to queue!")
                                time.sleep(0.5)
                                st.rerun()
                    with card_col4:
                        # Delete button (trash icon)
                        if st.button("🗑️", key=f"delete_trend_{trend.id}", help="Delete this trend"):
                            delete_trend(db, trend.id)
                            st.rerun()

                    # Details expander - FULL WIDTH (not in a column)
                    with st.expander("📋 View Details", expanded=False):
                        # Use columns inside expander for organized layout
                        detail_col1, detail_col2 = st.columns(2)
                        with detail_col1:
                            if trend.article_url:
                                st.markdown(f"**🔗 Source:** [{html.escape(source_val)}]({html.escape(trend.article_url)})")
                            if trend.discovered_at:
                                st.markdown(f"**📅 Discovered:** {trend.discovered_at.strftime('%Y-%m-%d %H:%M')}")
                            if trend.keywords and isinstance(trend.keywords, list):
                                st.markdown(f"**🏷️ Keywords:** {', '.join(trend.keywords)}")
                        with detail_col2:
                            if trend.description:
                                st.markdown(f"**📝 Full Description:**")
                                st.markdown(html.escape(trend.description))
                            elif trend.summary:
                                st.markdown(f"**📝 Summary:**")
                                st.markdown(html.escape(trend.summary))

                    st.divider()
        else:
            st.info("No trends discovered yet. Go to Content to fetch trends.")

    st.markdown("<br>", unsafe_allow_html=True)

    # --- Section 2: Processed Threads (Full Width) ---
    # Only show actual X/Twitter threads (not trend articles added to queue)
    all_tweets = db.query(Tweet).filter(
        Tweet.status.in_([TweetStatus.PROCESSED, TweetStatus.APPROVED, TweetStatus.PUBLISHED, TweetStatus.PENDING])
    ).order_by(Tweet.updated_at.desc()).limit(50).all()

    # Filter to only X/Twitter threads
    x_threads = [t for t in all_tweets if t.source_url and ('x.com/' in t.source_url or 'twitter.com/' in t.source_url)]
    threads_count = len(x_threads)

    # Collapsible section using checkbox styled as header
    threads_expanded = st.checkbox(
        f"🧵 Processed Threads ({threads_count})",
        value=st.session_state.home_threads_expanded,
        key="threads_section_toggle"
    )
    st.session_state.home_threads_expanded = threads_expanded

    if threads_expanded:
        if x_threads:
            for idx, tweet in enumerate(x_threads[:10]):  # Limit to 10
                status_str = tweet.status.value if hasattr(tweet.status, 'value') else str(tweet.status)

                # Preview: First 10-15 words of original text
                original_words = (tweet.original_text or '').split()
                preview_text = ' '.join(original_words[:15])
                if len(original_words) > 15:
                    preview_text += '...'
                preview_text = preview_text if preview_text else 'No content'

                # Source info - extract @username from X URL
                source_handle = ''
                if tweet.source_url:
                    try:
                        if 'x.com/' in tweet.source_url:
                            parts = tweet.source_url.split('x.com/')[1].split('/')
                            if parts:
                                source_handle = f"@{parts[0]}"
                        elif 'twitter.com/' in tweet.source_url:
                            parts = tweet.source_url.split('twitter.com/')[1].split('/')
                            if parts:
                                source_handle = f"@{parts[0]}"
                    except (IndexError, AttributeError):
                        pass

                with st.container():
                    # Preview row
                    preview_col1, preview_col2 = st.columns([5, 1])
                    with preview_col1:
                        st.markdown(f'**"{preview_text}"**')
                        status_source = f"Status: **{status_str}**"
                        if source_handle:
                            status_source += f" | Source: {source_handle}"
                        st.caption(status_source)
                    with preview_col2:
                        # SAFETY: status_str is from TweetStatus enum (controlled values)
                        st.markdown(f'<span class="status-badge status-{status_str.lower()}">{html.escape(status_str)}</span>', unsafe_allow_html=True)

                    # View Full Thread expander - FULL WIDTH
                    with st.expander("📖 View Full Thread"):
                        # Two-column layout inside expander for better readability
                        thread_col1, thread_col2 = st.columns(2)
                        with thread_col1:
                            st.markdown("**Original Thread:**")
                            st.text_area("", value=tweet.original_text or "No content", height=200, disabled=True, key=f"orig_{tweet.id}", label_visibility="collapsed")
                        with thread_col2:
                            st.markdown("**Hebrew Translation:**")
                            if tweet.hebrew_draft:
                                st.text_area("", value=tweet.hebrew_draft, height=200, disabled=True, key=f"heb_{tweet.id}", label_visibility="collapsed")
                            else:
                                st.info("No Hebrew translation yet.")

                        # Action buttons
                        btn1, btn2, btn3, btn4 = st.columns(4)
                        with btn1:
                            if tweet.source_url and tweet.source_url.startswith('http'):
                                st.markdown(f'[🔗 View Source]({tweet.source_url})')
                        with btn2:
                            if st.button("✏️ Edit", key=f"home_edit_{tweet.id}"):
                                st.session_state.selected_item = tweet.id
                                st.session_state.current_view = 'content'
                                st.rerun()

                    st.divider()
        else:
            st.info("No X/Twitter threads yet. Go to Content > Thread Translation to fetch and translate threads.")


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

    # Use tabs to organize: Acquire | Queue | Thread Translation | Generate
    tab_acquire, tab_queue, tab_threads, tab_generate = st.tabs(["Acquire", "Queue", "Thread Translation", "Generate"])

    with tab_acquire:
        _render_acquire_section(db)

    with tab_queue:
        _render_queue_section(db)

    with tab_threads:
        _render_thread_translation(db)

    with tab_generate:
        _render_generate_section(db)


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

    col1, col2, col3, col4, col5 = st.columns([1, 1, 1, 1, 1])
    with col1:
        add_to_queue = st.checkbox("Add to queue", value=True)
    with col2:
        consolidate = st.checkbox("Consolidate thread", value=True)
    with col3:
        auto_translate = st.checkbox("Auto-translate", value=True, help="Translate using context-aware AI")
    with col4:
        download_media = st.checkbox("Download media", value=False, help="Download images and videos from thread")
    with col5:
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
                                # Combine original text for reference
                                combined_text = "\n\n---\n\n".join([t.get('text', '') for t in tweets_data])
                                first_url = tweets_data[0].get('permalink', url) if tweets_data else url
                                media_urls = [t['media'][0]['src'] for t in tweets_data if t.get('media')]

                                if not db.query(Tweet).filter_by(source_url=first_url).first():
                                    # Auto-translate if enabled
                                    hebrew_draft = None
                                    tweet_status = TweetStatus.PENDING

                                    if auto_translate:
                                        progress.progress(60, "Translating with context awareness...")
                                        try:
                                            from processor.processor import ProcessorConfig, TranslationService
                                            config = ProcessorConfig()
                                            translator = TranslationService(config)

                                            # Use context-aware consolidated translation
                                            hebrew_draft = translator.translate_thread_consolidated(tweets_data)
                                            tweet_status = TweetStatus.PROCESSED
                                            logger.info(f"✅ Context-aware translation complete: {hebrew_draft[:100]}...")
                                        except Exception as e:
                                            logger.error(f"Translation failed: {e}")
                                            st.warning(f"Translation failed: {str(e)[:80]}. Added without translation.")

                                    # Download all thread media (optional)
                                    media_paths_json = None
                                    first_media_path = None
                                    if download_media:
                                        try:
                                            progress.progress(75, "Downloading media...")
                                            from processor.processor import MediaDownloader
                                            downloader = MediaDownloader()
                                            media_results = downloader.download_thread_media(result)
                                            if media_results:
                                                import json as json_mod
                                                media_paths_json = json_mod.dumps(media_results)
                                                first_media_path = media_results[0].get('local_path')
                                                logger.info(f"✅ Downloaded {len(media_results)} media files")
                                        except Exception as e:
                                            logger.warning(f"Media download failed: {e}")

                                    db.add(Tweet(
                                        source_url=first_url,
                                        original_text=combined_text,
                                        hebrew_draft=hebrew_draft,
                                        status=tweet_status,
                                        media_url=media_urls[0] if media_urls else None,
                                        media_path=first_media_path,
                                        media_paths=media_paths_json,
                                        trend_topic=result.get('author_handle', '')
                                    ))
                                    db.commit()
                                    progress.progress(100, "Done!")

                                    if auto_translate and hebrew_draft:
                                        st.success(f"✅ Added & translated consolidated thread ({len(tweets_data)} tweets → 1 flowing post)")
                                    else:
                                        st.success(f"Added consolidated thread ({len(tweets_data)} tweets combined)")
                                else:
                                    progress.progress(100, "Done!")
                                    st.info("Thread already exists in queue")
                            else:
                                # Separate tweets mode
                                saved = 0
                                hebrew_translations = []

                                # Auto-translate if enabled (context-aware)
                                if auto_translate and tweets_data:
                                    progress.progress(60, "Translating with context awareness...")
                                    try:
                                        from processor.processor import ProcessorConfig, TranslationService
                                        config = ProcessorConfig()
                                        translator = TranslationService(config)

                                        # Use context-aware separate translation
                                        hebrew_translations = translator.translate_thread_separate(tweets_data)
                                        logger.info(f"✅ Context-aware translation complete: {len(hebrew_translations)} tweets translated")
                                    except Exception as e:
                                        logger.error(f"Translation failed: {e}")
                                        st.warning(f"Translation failed: {str(e)[:80]}. Added without translation.")
                                        hebrew_translations = []

                                for idx, t in enumerate(tweets_data):
                                    permalink = t.get('permalink', '')
                                    if permalink and not db.query(Tweet).filter_by(source_url=permalink).first():
                                        media_url = t['media'][0]['src'] if t.get('media') else None

                                        # Get Hebrew translation if available
                                        hebrew_draft = None
                                        tweet_status = TweetStatus.PENDING
                                        if hebrew_translations and idx < len(hebrew_translations):
                                            hebrew_draft = hebrew_translations[idx]
                                            tweet_status = TweetStatus.PROCESSED

                                        db.add(Tweet(
                                            source_url=permalink,
                                            original_text=t.get('text', ''),
                                            hebrew_draft=hebrew_draft,
                                            status=tweet_status,
                                            media_url=media_url,
                                            trend_topic=t.get('author_handle', '')
                                        ))
                                        saved += 1
                                db.commit()
                                progress.progress(100, "Done!")

                                if auto_translate and hebrew_translations:
                                    st.success(f"✅ Added & translated {saved} tweets (with thread context)")
                                else:
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

    fcol1, fcol2, fcol3 = st.columns([2, 1, 1])
    with fcol1:
        st.markdown('<p style="color: var(--text-secondary); font-size: 0.85rem;">Fetch articles with weighted sampling: 70% finance + 30% tech, ranked by keyword overlap.</p>', unsafe_allow_html=True)
    with fcol2:
        auto_summarize = st.checkbox("Auto-summarize", value=True, key="auto_gen_summary", help="Generate AI summaries automatically when fetching trends")
        st.session_state.auto_generate_summaries = auto_summarize
    with fcol3:
        fetch_all = st.button("Fetch All Trends", type="primary", use_container_width=True, key="fetch_all_trends")

    # Generate Summaries button for existing trends without summaries
    trends_without_summary = db.query(Trend).filter(Trend.summary == None).count()
    if trends_without_summary > 0:
        gcol1, gcol2 = st.columns([3, 1])
        with gcol1:
            st.markdown(f'<p style="color: var(--text-muted); font-size: 0.8rem;">{trends_without_summary} trends need AI summaries</p>', unsafe_allow_html=True)
        with gcol2:
            if st.button("Generate Summaries", key="gen_summaries_btn", use_container_width=True):
                generator = get_summary_generator()
                if generator:
                    with st.spinner(f"Generating summaries for {trends_without_summary} trends..."):
                        stats = generator.backfill_summaries(db, limit=20)
                        st.success(f"Generated {stats['success']} summaries ({stats['failed']} failed)")
                        time.sleep(0.5)
                        st.rerun()
                else:
                    st.error("Could not initialize summary generator. Check OPENAI_API_KEY.")

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
                new_trend_ids = []
                for article in ranked_news:
                    if not db.query(Trend).filter_by(title=article['title']).first():
                        new_trend = Trend(
                            title=article['title'],
                            description=article.get('description', '')[:500],
                            source=source_map.get(article['source'], TrendSource.MANUAL),
                            article_url=article.get('url', ''),
                        )
                        db.add(new_trend)
                        db.flush()  # Get the ID
                        new_trend_ids.append(new_trend.id)
                        saved += 1
                db.commit()

                st.session_state.ranked_articles = ranked_news
                st.session_state.new_trend_ids = new_trend_ids
                st.success(f"Fetched & ranked top {len(ranked_news)} articles, saved {saved} new trends")

                # Auto-generate summaries for new trends
                if new_trend_ids and st.session_state.get('auto_generate_summaries', True):
                    generator = get_summary_generator()
                    if generator:
                        with st.spinner(f"Generating AI summaries for {len(new_trend_ids)} trends..."):
                            success_count = 0
                            for trend_id in new_trend_ids:
                                if generator.process_trend(db, trend_id):
                                    success_count += 1
                            st.success(f"Generated {success_count} AI summaries")

                # Auto-navigate to Home tab after fetch completes
                st.session_state.current_view = 'home'
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
            art_url = html.escape(art.get('url', '') or '')
            art_title = html.escape(art.get('title', '') or '')
            art_desc = html.escape((art.get('description', '') or '')[:120])
            art_source = html.escape(art.get('source', '') or '')
            art_category = art.get('category', 'Unknown')
            badge_cls = get_source_badge_class(art.get('source', ''))
            category_emoji = "💰" if art_category == "Finance" else "💻"
            title_html = f'<a href="{art_url}" target="_blank" style="color: var(--accent-primary); text-decoration: none; font-size: 0.9rem; font-weight: 500;">{art_title}</a>' if art.get('url') else f'<span style="color: var(--text-primary); font-size: 0.9rem; font-weight: 500;">{art_title}</span>'

            # Check if this trend has a summary in DB
            db_trend = db.query(Trend).filter_by(title=art.get('title', '')).first()
            if db_trend and db_trend.summary:
                safe_summary = html.escape(db_trend.summary[:180])
                summary_html = f'<div style="font-size: 0.8rem; color: var(--text-secondary); margin-top: 0.35rem; line-height: 1.4; background: rgba(25, 154, 245, 0.05); padding: 0.5rem; border-radius: 6px; border-left: 2px solid var(--accent-primary);">{safe_summary}{"..." if len(db_trend.summary) > 180 else ""}</div>'
                # Show keywords
                keywords_html = ''
                if db_trend.keywords and isinstance(db_trend.keywords, list) and len(db_trend.keywords) > 0:
                    keywords_tags = ' '.join([f'<span style="background: var(--bg-tertiary); color: var(--text-muted); padding: 0.15rem 0.4rem; border-radius: 4px; font-size: 0.65rem; margin-right: 0.25rem;">{html.escape(str(kw))}</span>' for kw in db_trend.keywords[:4]])
                    keywords_html = f'<div style="margin-top: 0.35rem;">{keywords_tags}</div>'
            elif art_desc:
                summary_html = f'<div style="font-size: 0.8rem; color: var(--text-muted); margin-top: 0.25rem;">{art_desc}</div>'
                keywords_html = ''
            else:
                summary_html = ''
                keywords_html = ''

            card_html = f'<div class="queue-item"><div style="display: flex; justify-content: space-between; align-items: center;"><div style="display: flex; align-items: center; gap: 0.5rem;"><span style="font-size: 0.75rem; font-weight: 700; color: var(--text-muted); min-width: 1.5rem;">#{idx}</span><span style="font-size: 1rem;">{category_emoji}</span>{title_html}</div><span class="status-badge {badge_cls}">{art_source}</span></div>{summary_html}{keywords_html}</div>'
            st.markdown(card_html, unsafe_allow_html=True)
    else:
        # Show recent trends from DB if no ranked results
        trends = db.query(Trend).order_by(Trend.discovered_at.desc()).limit(10).all()
        if trends:
            st.markdown("### Recent Trends")
            for trend in trends:
                source_val = trend.source.value if hasattr(trend.source, 'value') else str(trend.source)
                badge_cls = get_source_badge_class(source_val)
                # HTML-escape user content
                safe_title = html.escape(trend.title or '')
                link_html = f'<a href="{html.escape(trend.article_url or "")}" target="_blank" style="color: var(--accent-primary); text-decoration: none;">{safe_title}</a>' if trend.article_url else f'<span style="color: var(--text-primary);">{safe_title}</span>'

                # Show AI summary if available (escaped)
                if trend.summary:
                    safe_summary = html.escape(trend.summary[:150])
                    summary_html = f'<div style="font-size: 0.8rem; color: var(--text-secondary); margin-top: 0.35rem; line-height: 1.4;">{safe_summary}{"..." if len(trend.summary) > 150 else ""}</div>'
                elif trend.description and len(trend.description) > 10:
                    safe_desc = html.escape(trend.description[:120])
                    summary_html = f'<div style="font-size: 0.8rem; color: var(--text-muted); margin-top: 0.25rem;">{safe_desc}...</div>'
                else:
                    summary_html = ''

                # Show keywords as small tags (escaped)
                keywords_html = ''
                if trend.keywords and isinstance(trend.keywords, list) and len(trend.keywords) > 0:
                    keywords_tags = ' '.join([f'<span style="background: var(--bg-tertiary); color: var(--text-muted); padding: 0.15rem 0.4rem; border-radius: 4px; font-size: 0.65rem; margin-right: 0.25rem;">{html.escape(str(kw))}</span>' for kw in trend.keywords[:4]])
                    keywords_html = f'<div style="margin-top: 0.35rem;">{keywords_tags}</div>'

                # Source count indicator
                source_count_html = ''
                if trend.source_count and trend.source_count > 1:
                    source_count_html = f'<span style="background: rgba(34, 197, 94, 0.15); color: #4ADE80; padding: 0.15rem 0.5rem; border-radius: 9999px; font-size: 0.65rem; margin-left: 0.5rem;">{trend.source_count} sources</span>'

                card_html = f'<div class="queue-item"><div style="display: flex; justify-content: space-between; align-items: center;">{link_html}<div style="display: flex; align-items: center;">{source_count_html}<span class="status-badge {badge_cls}">{html.escape(source_val)}</span></div></div>{summary_html}{keywords_html}</div>'
                st.markdown(card_html, unsafe_allow_html=True)

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


def _render_thread_translation(db):
    """Thread Translation section with side-by-side English/Hebrew display."""

    st.markdown("### Thread Translation")
    st.markdown('<p style="color: var(--text-secondary); font-size: 0.85rem;">Paste a Twitter/X thread URL to fetch and translate with side-by-side RTL Hebrew display.</p>', unsafe_allow_html=True)

    # Initialize session state for thread translation
    if 'thread_data' not in st.session_state:
        st.session_state.thread_data = None
    if 'thread_translations' not in st.session_state:
        st.session_state.thread_translations = None
    if 'thread_url' not in st.session_state:
        st.session_state.thread_url = ""

    # URL input and fetch button
    col1, col2 = st.columns([4, 1])
    with col1:
        thread_url = st.text_input(
            "Thread URL",
            placeholder="https://x.com/user/status/1234567890",
            key="thread_trans_url",
            label_visibility="collapsed",
            value=st.session_state.thread_url
        )
    with col2:
        fetch_btn = st.button("Fetch Thread", type="primary", use_container_width=True, key="fetch_thread_btn")

    # Fetch thread when button clicked
    if fetch_btn and thread_url:
        with st.spinner("Fetching thread..."):
            try:
                from scraper.scraper import TwitterScraper

                async def fetch():
                    scraper = TwitterScraper()
                    try:
                        await scraper.ensure_logged_in()
                        return await scraper.fetch_raw_thread(thread_url, author_only=True)
                    finally:
                        await scraper.close()

                result = asyncio.run(fetch())
                tweets_data = result.get('tweets', [])

                if tweets_data:
                    st.session_state.thread_data = {
                        'tweets': tweets_data,
                        'author_handle': result.get('author_handle', ''),
                        'author_name': result.get('author_name', ''),
                        'url': thread_url
                    }
                    st.session_state.thread_url = thread_url
                    st.session_state.thread_translations = None  # Reset translations
                    st.success(f"Fetched {len(tweets_data)} tweets from thread")
                    time.sleep(0.5)
                    st.rerun()
                else:
                    st.warning("No tweets found in thread")

            except Exception as e:
                st.error(f"Failed to fetch thread: {str(e)[:100]}")

    # Display thread if fetched
    if st.session_state.thread_data:
        thread = st.session_state.thread_data
        tweets = thread.get('tweets', [])
        author = thread.get('author_handle', 'Unknown')

        st.markdown("---")

        # Thread header with author and translate button
        header_col1, header_col2, header_col3 = st.columns([2, 1, 1])
        with header_col1:
            st.markdown(f'<p style="font-weight: 600; color: var(--text-primary);">{html.escape(author)} ({len(tweets)} tweets)</p>', unsafe_allow_html=True)
        with header_col2:
            translation_mode = st.selectbox(
                "Mode",
                ["Consolidated", "Separate"],
                key="trans_mode",
                label_visibility="collapsed",
                help="Consolidated: One flowing post. Separate: Keep thread structure."
            )
        with header_col3:
            translate_btn = st.button("Translate to Hebrew", type="primary", use_container_width=True, key="translate_thread_btn")

        # Translate thread when button clicked
        if translate_btn:
            with st.spinner("Translating thread to Hebrew..."):
                try:
                    from processor.processor import ProcessorConfig, TranslationService
                    config = ProcessorConfig()
                    translator = TranslationService(config)

                    if translation_mode == "Consolidated":
                        # Single flowing post
                        hebrew_text = translator.translate_thread_consolidated(tweets)
                        st.session_state.thread_translations = {
                            'mode': 'consolidated',
                            'hebrew': hebrew_text
                        }
                    else:
                        # Separate tweets with context
                        hebrew_list = translator.translate_thread_separate(tweets)
                        st.session_state.thread_translations = {
                            'mode': 'separate',
                            'hebrew_list': hebrew_list
                        }

                    st.success("Translation complete!")
                    time.sleep(0.5)
                    st.rerun()

                except Exception as e:
                    st.error(f"Translation failed: {str(e)[:100]}")

        # Side-by-side display
        st.markdown("---")

        col_en, col_he = st.columns(2)

        translations = st.session_state.thread_translations

        with col_en:
            st.markdown('<div class="translation-panel-header translation-panel-english">English (LTR)</div>', unsafe_allow_html=True)

            if translations and translations.get('mode') == 'consolidated':
                # Show original combined text
                combined_text = "\n\n".join([t.get('text', '') for t in tweets])
                st.markdown(f'<div class="translation-content ltr-container">{html.escape(combined_text)}</div>', unsafe_allow_html=True)
            else:
                # Show individual tweets with numbers
                for idx, tweet in enumerate(tweets, 1):
                    tweet_text = tweet.get('text', '')
                    st.markdown(f'''
                        <div class="thread-tweet-item">
                            <span class="thread-tweet-number">{idx}</span>
                            <span style="color: var(--text-secondary); font-size: 0.85rem;">{html.escape(tweet_text)}</span>
                        </div>
                    ''', unsafe_allow_html=True)

        with col_he:
            st.markdown('<div class="translation-panel-header translation-panel-hebrew">Hebrew (RTL)</div>', unsafe_allow_html=True)

            if translations:
                if translations.get('mode') == 'consolidated':
                    # Show consolidated Hebrew translation
                    hebrew_text = translations.get('hebrew', '')
                    if hebrew_text:
                        st.markdown(f'<div class="translation-content hebrew rtl-container">{html.escape(hebrew_text)}</div>', unsafe_allow_html=True)
                    else:
                        st.markdown('<div class="translation-content" style="color: var(--text-muted); font-style: italic;">Translation pending...</div>', unsafe_allow_html=True)
                else:
                    # Show individual Hebrew tweets with numbers (RTL)
                    hebrew_list = translations.get('hebrew_list', [])
                    for idx, hebrew_text in enumerate(hebrew_list, 1):
                        if hebrew_text:
                            st.markdown(f'''
                                <div class="thread-tweet-item rtl-container">
                                    <span class="thread-tweet-number rtl">{idx}</span>
                                    <span style="color: var(--text-primary); font-size: 0.85rem;">{html.escape(hebrew_text)}</span>
                                </div>
                            ''', unsafe_allow_html=True)
                        else:
                            st.markdown(f'''
                                <div class="thread-tweet-item rtl-container">
                                    <span class="thread-tweet-number rtl">{idx}</span>
                                    <span style="color: var(--text-muted); font-size: 0.85rem; font-style: italic;">Not translated</span>
                                </div>
                            ''', unsafe_allow_html=True)
            else:
                # Placeholder for Hebrew translations
                for idx in range(1, len(tweets) + 1):
                    st.markdown(f'''
                        <div class="thread-tweet-item rtl-container">
                            <span class="thread-tweet-number rtl">{idx}</span>
                            <span style="color: var(--text-muted); font-size: 0.85rem; font-style: italic;">Click "Translate to Hebrew" to translate</span>
                        </div>
                    ''', unsafe_allow_html=True)

        # Action buttons for translated content
        if translations:
            st.markdown("---")

            action_col1, action_col2, action_col3, action_col4 = st.columns(4)

            with action_col1:
                if st.button("Add to Queue", use_container_width=True, key="add_trans_queue"):
                    try:
                        if translations.get('mode') == 'consolidated':
                            # Add as single consolidated tweet
                            combined_text = "\n\n".join([t.get('text', '') for t in tweets])
                            hebrew_text = translations.get('hebrew', '')

                            if not db.query(Tweet).filter_by(source_url=thread.get('url', '')).first():
                                new_tweet = Tweet(
                                    source_url=thread.get('url', ''),
                                    original_text=combined_text,
                                    hebrew_draft=hebrew_text,
                                    trend_topic=thread.get('author_handle', ''),
                                    status=TweetStatus.PROCESSED if hebrew_text else TweetStatus.PENDING
                                )
                                db.add(new_tweet)
                                db.commit()
                                st.success("Added consolidated thread to queue!")
                            else:
                                st.info("Thread already in queue")
                        else:
                            # Add as separate tweets
                            hebrew_list = translations.get('hebrew_list', [])
                            saved = 0
                            for idx, tweet in enumerate(tweets):
                                permalink = tweet.get('permalink', '')
                                if permalink and not db.query(Tweet).filter_by(source_url=permalink).first():
                                    hebrew_text = hebrew_list[idx] if idx < len(hebrew_list) else None
                                    new_tweet = Tweet(
                                        source_url=permalink,
                                        original_text=tweet.get('text', ''),
                                        hebrew_draft=hebrew_text,
                                        trend_topic=thread.get('author_handle', ''),
                                        status=TweetStatus.PROCESSED if hebrew_text else TweetStatus.PENDING
                                    )
                                    db.add(new_tweet)
                                    saved += 1
                            db.commit()
                            st.success(f"Added {saved} tweets to queue!")

                        time.sleep(0.5)
                        st.rerun()

                    except Exception as e:
                        st.error(f"Failed to add to queue: {str(e)[:80]}")

            with action_col2:
                # Copy Hebrew text button
                if translations.get('mode') == 'consolidated':
                    hebrew_copy = translations.get('hebrew', '')
                else:
                    hebrew_copy = "\n\n".join(translations.get('hebrew_list', []))

                if hebrew_copy:
                    st.download_button(
                        "Download Hebrew",
                        data=hebrew_copy,
                        file_name="hebrew_translation.txt",
                        mime="text/plain",
                        use_container_width=True,
                        key="download_hebrew"
                    )

            with action_col3:
                if st.button("Re-translate", use_container_width=True, key="retranslate_btn"):
                    st.session_state.thread_translations = None
                    st.rerun()

            with action_col4:
                if st.button("Clear Thread", use_container_width=True, key="clear_thread_btn"):
                    st.session_state.thread_data = None
                    st.session_state.thread_translations = None
                    st.session_state.thread_url = ""
                    st.rerun()
    else:
        # Empty state
        st.markdown("""
            <div class="empty-state" style="margin-top: 2rem;">
                <div class="empty-state-icon">🧵</div>
                <div class="empty-state-title">No thread loaded</div>
                <div class="empty-state-text">Paste a Twitter/X thread URL above and click "Fetch Thread" to get started with side-by-side translation.</div>
            </div>
        """, unsafe_allow_html=True)


def _render_generate_section(db):
    """Generate original Hebrew content from English source material."""

    st.markdown("### Generate Original Hebrew Post")
    st.caption("Paste English source content to generate original Hebrew posts in your voice.")

    # Pre-fill from session state if navigated from trend card
    prefill = st.session_state.get('generate_source_text', '')

    source_text = st.text_area(
        "Source Content (English)",
        value=prefill,
        height=150,
        key="gen_source_text",
        placeholder="Paste English article text, tweet, or news snippet here..."
    )

    # Clear prefill after displaying
    if 'generate_source_text' in st.session_state:
        del st.session_state['generate_source_text']

    col_mode, col_angles, col_btn = st.columns([1, 2, 1])

    with col_mode:
        gen_mode = st.selectbox("Mode", ["Single Post", "Thread"], key="gen_mode")

    with col_angles:
        if gen_mode == "Single Post":
            angle_options = ["All (3 variants)", "News/Breaking", "Educational", "Opinion/Analysis"]
            selected_angle = st.selectbox("Angle", angle_options, key="gen_angle")
        else:
            thread_angle = st.selectbox("Thread Angle", ["Educational", "News/Breaking", "Opinion/Analysis"], key="gen_thread_angle")
            thread_count = st.slider("Tweets in thread", 2, 5, 3, key="gen_thread_count")

    with col_btn:
        st.markdown("<br>", unsafe_allow_html=True)
        generate_clicked = st.button("Generate", key="gen_submit", use_container_width=True, type="primary")

    if generate_clicked and source_text and source_text.strip():
        with st.spinner("Generating Hebrew content..."):
            try:
                from processor.content_generator import ContentGenerator
                generator = ContentGenerator()

                if gen_mode == "Single Post":
                    # Map UI selection to angle names
                    angle_map = {
                        "All (3 variants)": None,
                        "News/Breaking": ['news'],
                        "Educational": ['educational'],
                        "Opinion/Analysis": ['opinion'],
                    }
                    angles = angle_map.get(selected_angle)
                    num = 3 if angles is None else 1
                    variants = generator.generate_post(source_text, num_variants=num, angles=angles)
                    st.session_state['gen_variants'] = variants
                    st.session_state['gen_source_for_save'] = source_text
                    st.session_state['gen_mode_result'] = 'post'
                else:
                    angle_name_map = {"Educational": "educational", "News/Breaking": "news", "Opinion/Analysis": "opinion"}
                    thread_tweets = generator.generate_thread(
                        source_text,
                        num_tweets=thread_count,
                        angle=angle_name_map.get(thread_angle, 'educational')
                    )
                    st.session_state['gen_thread_result'] = thread_tweets
                    st.session_state['gen_source_for_save'] = source_text
                    st.session_state['gen_mode_result'] = 'thread'

                st.rerun()
            except Exception as e:
                st.error(f"Generation failed: {str(e)[:200]}")

    # ---- Display generated post variants ----
    if st.session_state.get('gen_mode_result') == 'post' and 'gen_variants' in st.session_state:
        variants = st.session_state['gen_variants']
        source_for_save = st.session_state.get('gen_source_for_save', '')

        st.markdown("---")
        st.markdown("### Generated Variants")
        st.caption("Select a variant, edit if needed, then approve to save.")

        for i, variant in enumerate(variants):
            with st.container():
                col_header, col_status = st.columns([4, 1])
                with col_header:
                    valid_icon = "" if variant.get('is_valid_hebrew') else ""
                    st.markdown(f"**Variant {i+1}: {variant['label']}** {valid_icon}")
                with col_status:
                    st.caption(f"{variant['char_count']} chars")

                # Editable text area with RTL support
                edited = st.text_area(
                    f"Variant {i+1}",
                    value=variant['content'],
                    height=120,
                    key=f"gen_var_{i}",
                    label_visibility="collapsed"
                )

                # Char counter
                char_count = len(edited) if edited else 0
                over = char_count > 280
                st.markdown(
                    f"<div style='text-align:right; font-size:0.75rem; color: {'var(--accent-danger)' if over else 'var(--text-muted)'};'>"
                    f"{char_count}/280</div>",
                    unsafe_allow_html=True
                )

                col_approve, col_save_draft = st.columns(2)
                with col_approve:
                    if st.button(f"Approve & Save", key=f"gen_approve_{i}", use_container_width=True, type="primary"):
                        import hashlib as _hashlib
                        source_hash = _hashlib.md5(source_for_save.encode()).hexdigest()[:12]
                        new_tweet = Tweet(
                            source_url=f"generated_{source_hash}_{i}",
                            original_text=source_for_save,
                            hebrew_draft=edited,
                            content_type='generation',
                            generation_metadata=json.dumps({
                                'angle': variant['angle'],
                                'label': variant['label'],
                                'source_hash': variant.get('source_hash', ''),
                                'variant_index': i,
                            }),
                            status=TweetStatus.APPROVED
                        )
                        db.add(new_tweet)
                        db.commit()
                        # Auto-style learning
                        if edited and len(edited.strip()) > 30:
                            _auto_learn_style(db, edited.strip())
                        st.success(f"Variant {i+1} approved and saved!")
                        time.sleep(0.5)
                        st.rerun()

                with col_save_draft:
                    if st.button(f"Save as Draft", key=f"gen_draft_{i}", use_container_width=True):
                        import hashlib as _hashlib
                        source_hash = _hashlib.md5(source_for_save.encode()).hexdigest()[:12]
                        new_tweet = Tweet(
                            source_url=f"generated_{source_hash}_{i}",
                            original_text=source_for_save,
                            hebrew_draft=edited,
                            content_type='generation',
                            generation_metadata=json.dumps({
                                'angle': variant['angle'],
                                'label': variant['label'],
                                'source_hash': variant.get('source_hash', ''),
                                'variant_index': i,
                            }),
                            status=TweetStatus.PROCESSED
                        )
                        db.add(new_tweet)
                        db.commit()
                        st.success(f"Variant {i+1} saved as draft!")
                        time.sleep(0.5)
                        st.rerun()

                st.divider()

        if st.button("Clear Results", key="gen_clear"):
            for k in ['gen_variants', 'gen_source_for_save', 'gen_mode_result']:
                st.session_state.pop(k, None)
            st.rerun()

    # ---- Display generated thread ----
    if st.session_state.get('gen_mode_result') == 'thread' and 'gen_thread_result' in st.session_state:
        thread_tweets = st.session_state['gen_thread_result']
        source_for_save = st.session_state.get('gen_source_for_save', '')

        st.markdown("---")
        st.markdown("### Generated Thread")

        all_edited = []
        for i, tweet_data in enumerate(thread_tweets):
            valid_icon = "" if tweet_data.get('is_valid_hebrew') else ""
            st.markdown(f"**Tweet {tweet_data['index']}/{len(thread_tweets)}** {valid_icon} ({tweet_data['char_count']} chars)")

            edited = st.text_area(
                f"Thread tweet {i+1}",
                value=tweet_data['content'],
                height=80,
                key=f"gen_thread_{i}",
                label_visibility="collapsed"
            )
            all_edited.append(edited)

            char_count = len(edited) if edited else 0
            over = char_count > 280
            st.markdown(
                f"<div style='text-align:right; font-size:0.75rem; color: {'var(--accent-danger)' if over else 'var(--text-muted)'};'>"
                f"{char_count}/280</div>",
                unsafe_allow_html=True
            )

        col_approve_thread, col_draft_thread, col_clear_thread = st.columns(3)
        with col_approve_thread:
            if st.button("Approve Thread", key="gen_thread_approve", use_container_width=True, type="primary"):
                import hashlib as _hashlib
                source_hash = _hashlib.md5(source_for_save.encode()).hexdigest()[:12]
                combined = "\n\n---\n\n".join(all_edited)
                new_tweet = Tweet(
                    source_url=f"generated_thread_{source_hash}",
                    original_text=source_for_save,
                    hebrew_draft=combined,
                    content_type='generation',
                    generation_metadata=json.dumps({
                        'type': 'thread',
                        'tweet_count': len(all_edited),
                        'source_hash': source_hash,
                    }),
                    status=TweetStatus.APPROVED
                )
                db.add(new_tweet)
                db.commit()
                if combined and len(combined.strip()) > 30:
                    _auto_learn_style(db, combined.strip())
                st.success("Thread approved and saved!")
                time.sleep(0.5)
                st.rerun()

        with col_draft_thread:
            if st.button("Save as Draft", key="gen_thread_draft", use_container_width=True):
                import hashlib as _hashlib
                source_hash = _hashlib.md5(source_for_save.encode()).hexdigest()[:12]
                combined = "\n\n---\n\n".join(all_edited)
                new_tweet = Tweet(
                    source_url=f"generated_thread_{source_hash}",
                    original_text=source_for_save,
                    hebrew_draft=combined,
                    content_type='generation',
                    generation_metadata=json.dumps({
                        'type': 'thread',
                        'tweet_count': len(all_edited),
                        'source_hash': source_hash,
                    }),
                    status=TweetStatus.PROCESSED
                )
                db.add(new_tweet)
                db.commit()
                st.success("Thread saved as draft!")
                time.sleep(0.5)
                st.rerun()

        with col_clear_thread:
            if st.button("Clear", key="gen_thread_clear", use_container_width=True):
                for k in ['gen_thread_result', 'gen_source_for_save', 'gen_mode_result']:
                    st.session_state.pop(k, None)
                st.rerun()


def render_content_item(tweet, db):
    """Render a content list item with media indicators"""
    status_str = format_status_str(tweet.status)
    media_count, media_icon = parse_media_info(tweet.media_paths)

    with st.container():
        col1, col2, col3 = st.columns([4, 1, 1])

        with col1:
            # SAFETY: trend_topic and original_text are user-derived, must escape
            st.markdown(f"""
                <div style="padding: 0.5rem 0;">
                    <div style="display: flex; align-items: center; gap: 0.5rem;">
                        <span style="font-weight: 500; color: var(--text-primary);">{html.escape(tweet.trend_topic or 'Unknown')}</span>
                        <span class="status-badge status-{status_str.lower()}">{html.escape(status_str)}</span>
                    </div>
                    <div style="font-size: 0.8rem; color: var(--text-secondary); margin-top: 0.25rem;">
                        {html.escape(tweet.original_text[:120])}...
                    </div>
                </div>
            """, unsafe_allow_html=True)

        with col2:
            if media_count > 0:
                st.markdown(f"""
                    <div style="font-size: 0.75rem; color: var(--accent-primary); text-align: center;">
                        {media_icon} {media_count} media
                    </div>
                """, unsafe_allow_html=True)
            elif tweet.hebrew_draft:
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


def _auto_learn_style(db, hebrew_text: str, source_url: str = None):
    """Auto-add approved Hebrew content to style examples for learning."""
    try:
        sm = get_style_manager()
        if not sm:
            return
        # Check minimum Hebrew content
        if not sm.is_hebrew_content(hebrew_text, min_ratio=0.5):
            return
        word_count = sm.count_words(hebrew_text)
        if word_count < 10:
            return
        # Avoid duplicates: check if content already exists
        existing = db.query(StyleExample).filter(
            StyleExample.content == hebrew_text,
            StyleExample.is_active == True
        ).first()
        if existing:
            return
        # Extract topic tags using fallback (no API call on approval)
        tags = sm._fallback_topic_tags(hebrew_text)
        sm.add_style_example(
            db, hebrew_text,
            source_type='approved',
            source_url=source_url,
            topic_tags=tags
        )
        logger.info(f"Auto-learned style from approved content ({word_count} words)")
    except Exception as e:
        logger.warning(f"Auto-style learning failed: {e}")


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

    # Media Gallery Section (if media exists)
    if tweet.media_paths:
        try:
            import json as json_mod
            from pathlib import Path
            media_list = json_mod.loads(tweet.media_paths)
            
            if media_list:
                st.markdown("---")
                st.markdown(f"""
                    <div style="background: var(--bg-tertiary); padding: 0.75rem; border-radius: 8px; margin-bottom: 0.5rem;">
                        <span style="font-size: 0.75rem; font-weight: 600; color: var(--accent-primary); text-transform: uppercase;">
                            Thread Media ({len(media_list)} files)
                        </span>
                    </div>
                """, unsafe_allow_html=True)
                
                num_cols = min(len(media_list), 4)
                cols = st.columns(num_cols)
                
                for idx, media_item in enumerate(media_list):
                    with cols[idx % num_cols]:
                        media_type = media_item.get('type', 'unknown')
                        local_path = media_item.get('local_path', '')
                        tweet_id = media_item.get('tweet_id', 'N/A')
                        
                        if local_path and Path(local_path).exists():
                            if media_type == 'photo':
                                st.image(local_path, caption=f"Tweet #{idx+1}")
                            elif media_type == 'video':
                                st.video(local_path)
                                st.caption(f"🎥 Video #{idx+1}")
                        else:
                            st.markdown(f"""
                                <div style="background: var(--bg-elevated); padding: 1rem; border-radius: 8px; text-align: center; color: var(--text-muted);">
                                    ❌ {media_type.title()} missing<br>
                                    <small>File not found</small>
                                </div>
                            """, unsafe_allow_html=True)
        except Exception as e:
            logger.warning(f"Failed to parse media_paths: {e}")

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
                # Auto-style learning: add approved Hebrew content to style examples
                if hebrew and len(hebrew.strip()) > 30:
                    _auto_learn_style(db, hebrew.strip(), tweet.source_url)
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
        except (json.JSONDecodeError, OSError) as e:
            logger.warning(f"Failed to load glossary: {e}")
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

    # ==========================================
    # STYLE LEARNING SYSTEM (Full Width)
    # ==========================================
    st.markdown("---")
    st.markdown("### Style Learning System")
    st.markdown('<p style="color: var(--text-secondary); font-size: 0.85rem;">Import your Hebrew writing samples for style-matched translations.</p>', unsafe_allow_html=True)

    sm = get_style_manager()

    # Get statistics
    if sm:
        stats = sm.get_example_stats(db)
        example_count = stats['count']
        total_words = stats['total_words']
        topics = stats['topics']
    else:
        example_count = db.query(StyleExample).filter(StyleExample.is_active == True).count()
        total_words = 0
        topics = []

    # Stats row
    stat_col1, stat_col2, stat_col3, stat_col4 = st.columns(4)
    with stat_col1:
        st.metric("Examples", example_count)
    with stat_col2:
        st.metric("Total Words", f"{total_words:,}")
    with stat_col3:
        st.metric("Topics", len(topics))
    with stat_col4:
        if example_count >= 100:
            st.warning("100+ examples")
        elif example_count >= 50:
            st.info("Good coverage")
        elif example_count > 0:
            st.caption("Add more examples")
        else:
            st.caption("No examples yet")

    # Soft limit warning
    if example_count >= 100:
        st.info("You have 100+ examples. This provides excellent style coverage, but you can still add more if needed.")

    # Import section
    import_col1, import_col2 = st.columns(2)

    with import_col1:
        st.markdown("#### Import from X Thread")
        thread_url_import = st.text_input(
            "Thread URL",
            placeholder="https://x.com/user/status/123...",
            key="style_import_url",
            label_visibility="collapsed"
        )
        if st.button("Fetch Thread", key="import_x_thread", use_container_width=True, disabled=not thread_url_import):
            with st.spinner("Fetching thread..."):
                try:
                    from scraper.scraper import TwitterScraper

                    async def fetch_for_style():
                        scraper = TwitterScraper()
                        try:
                            await scraper.ensure_logged_in()
                            return await scraper.fetch_raw_thread(thread_url_import, author_only=True)
                        finally:
                            await scraper.close()

                    result = asyncio.run(fetch_for_style())
                    tweets_data = result.get('tweets', [])

                    if tweets_data:
                        all_text = "\n\n".join([t.get('text', '') for t in tweets_data if t.get('text')])

                        if sm and sm.is_hebrew_content(all_text, min_ratio=0.5):
                            tags = sm.extract_topic_tags(all_text)
                            st.session_state.style_import_preview = all_text
                            st.session_state.style_import_tags = tags
                            st.session_state.style_import_tweet_count = len(tweets_data)
                            st.rerun()
                        else:
                            st.warning("Thread doesn't contain enough Hebrew content (need >50%)")
                    else:
                        st.warning("No tweets found in thread")
                except Exception as e:
                    st.error(f"Import failed: {str(e)[:100]}")

        # Preview fetched thread before saving
        if st.session_state.get('style_import_preview'):
            preview_text = st.session_state.style_import_preview
            preview_tags = st.session_state.get('style_import_tags', [])
            tweet_count = st.session_state.get('style_import_tweet_count', 0)
            st.text_area("Preview", preview_text[:500] + ("..." if len(preview_text) > 500 else ""), height=100, disabled=True, key="x_thread_preview_area")
            edited_tags = st.text_input("Edit Tags (comma-separated)", value=", ".join(preview_tags), key="x_thread_edit_tags")
            pcol1, pcol2 = st.columns(2)
            with pcol1:
                if st.button("Save Example", key="confirm_x_import", use_container_width=True):
                    final_tags = [t.strip() for t in edited_tags.split(",") if t.strip()]
                    example = sm.add_style_example(
                        db,
                        content=preview_text,
                        source_type='x_thread',
                        source_url=thread_url_import,
                        topic_tags=final_tags
                    )
                    if example:
                        st.success(f"Imported {tweet_count} tweets as style example")
                    else:
                        st.error("Failed to save example")
                    st.session_state.pop('style_import_preview', None)
                    st.session_state.pop('style_import_tags', None)
                    st.session_state.pop('style_import_tweet_count', None)
                    time.sleep(0.5)
                    st.rerun()
            with pcol2:
                if st.button("Cancel", key="cancel_x_import", use_container_width=True):
                    st.session_state.pop('style_import_preview', None)
                    st.session_state.pop('style_import_tags', None)
                    st.session_state.pop('style_import_tweet_count', None)
                    st.rerun()

    with import_col2:
        st.markdown("#### Upload Local File")
        uploaded_file = st.file_uploader(
            "Upload .txt or .md file",
            type=['txt', 'md'],
            key="style_file_upload",
            label_visibility="collapsed"
        )
        if uploaded_file:
            file_content = uploaded_file.read().decode('utf-8')
            if sm and sm.is_hebrew_content(file_content, min_ratio=0.5):
                st.text_area("Preview", file_content[:500] + ("..." if len(file_content) > 500 else ""), height=100, disabled=True)
                file_tags = sm.extract_topic_tags(file_content) if sm else ['fintech']
                edited_file_tags = st.text_input("Edit Tags (comma-separated)", value=", ".join(file_tags), key="file_edit_tags")
                if st.button("Add to Style Examples", key="add_uploaded_file", use_container_width=True):
                    final_tags = [t.strip() for t in edited_file_tags.split(",") if t.strip()]
                    example = sm.add_style_example(
                        db,
                        content=file_content,
                        source_type='local_file',
                        source_url=uploaded_file.name,
                        topic_tags=final_tags
                    ) if sm else None
                    if example:
                        st.success(f"Added file as style example (tags: {', '.join(final_tags[:3])})")
                        time.sleep(0.5)
                        st.rerun()
            else:
                st.warning("File doesn't contain enough Hebrew content (need >50%)")

    # Manual entry
    st.markdown("#### Add Manual Example")
    manual_content = st.text_area(
        "Hebrew Text",
        placeholder="הקלד כאן טקסט עברי לדוגמה...",
        height=100,
        key="manual_style_input",
        label_visibility="collapsed"
    )
    if manual_content and sm and sm.is_hebrew_content(manual_content, min_ratio=0.5):
        manual_auto_tags = sm.extract_topic_tags(manual_content)
        edited_manual_tags = st.text_input("Edit Tags (comma-separated)", value=", ".join(manual_auto_tags), key="manual_edit_tags")
    else:
        edited_manual_tags = ""
    manual_col1, manual_col2 = st.columns([3, 1])
    with manual_col2:
        if st.button("Add Example", key="add_manual_style", use_container_width=True, disabled=not manual_content):
            if sm and sm.is_hebrew_content(manual_content, min_ratio=0.5):
                final_tags = [t.strip() for t in edited_manual_tags.split(",") if t.strip()] if edited_manual_tags else ['fintech']
                example = sm.add_style_example(
                    db,
                    content=manual_content,
                    source_type='manual',
                    topic_tags=final_tags
                )
                if example:
                    st.success(f"Added manual example (tags: {', '.join(final_tags[:3])})")
                    time.sleep(0.5)
                    st.rerun()
            else:
                st.warning("Text doesn't contain enough Hebrew (need >50%)")

    # Export button
    st.markdown("---")
    export_col1, export_col2 = st.columns([3, 1])
    with export_col2:
        if example_count > 0 and sm:
            export_data = sm.export_to_json(db)
            st.download_button(
                "Export Examples (JSON)",
                export_data,
                "style_examples.json",
                mime="application/json",
                use_container_width=True
            )

    # Examples list with search/filter
    if example_count > 0:
        st.markdown("#### Your Style Examples")

        # Topic tag filter
        filter_col1, filter_col2 = st.columns([3, 1])
        with filter_col1:
            if topics:
                selected_tag = st.selectbox("Filter by topic", ["All"] + sorted(topics), key="style_tag_filter")
            else:
                selected_tag = "All"

        # Pagination state
        if 'style_examples_limit' not in st.session_state:
            st.session_state.style_examples_limit = 20

        display_limit = st.session_state.style_examples_limit

        # Query with optional tag filter
        query = db.query(StyleExample).filter(StyleExample.is_active == True).order_by(StyleExample.created_at.desc())

        if selected_tag != "All":
            all_active = query.all()
            filtered = []
            for ex in all_active:
                ex_tags = ex.topic_tags or []
                if isinstance(ex_tags, str):
                    try:
                        ex_tags = json.loads(ex_tags)
                    except (json.JSONDecodeError, ValueError):
                        ex_tags = []
                if selected_tag.lower() in [t.lower() for t in ex_tags]:
                    filtered.append(ex)
            examples = filtered[:display_limit]
            filtered_count = len(filtered)
        else:
            examples = query.limit(display_limit).all()
            filtered_count = example_count

        for ex in examples:
            source_label = html.escape({'x_thread': 'X Thread', 'local_file': 'File', 'manual': 'Manual'}.get(ex.source_type, ex.source_type or 'unknown'))
            tags_str = html.escape(', '.join(ex.topic_tags[:3]) if ex.topic_tags else 'No tags')
            preview = html.escape(ex.content[:100]) + ('...' if len(ex.content) > 100 else '')

            # Check if this example is being edited
            is_editing = st.session_state.get(f'editing_style_{ex.id}', False)

            if is_editing:
                st.markdown(f"**Editing Example #{ex.id}**")
                new_content = st.text_area("Content", value=ex.content, height=150, key=f"edit_content_{ex.id}")
                current_tags = ', '.join(ex.topic_tags) if ex.topic_tags else ''
                new_tags_str = st.text_input("Tags (comma-separated)", value=current_tags, key=f"edit_tags_{ex.id}")
                edit_btn_col1, edit_btn_col2 = st.columns(2)
                with edit_btn_col1:
                    if st.button("Save", key=f"save_edit_{ex.id}", use_container_width=True):
                        new_tags = [t.strip() for t in new_tags_str.split(",") if t.strip()]
                        if sm:
                            sm.update_example(db, ex.id, content=new_content, topic_tags=new_tags)
                        st.session_state[f'editing_style_{ex.id}'] = False
                        st.rerun()
                with edit_btn_col2:
                    if st.button("Cancel", key=f"cancel_edit_{ex.id}", use_container_width=True):
                        st.session_state[f'editing_style_{ex.id}'] = False
                        st.rerun()
            else:
                ex_col1, ex_col2, ex_col3 = st.columns([5, 1, 1])
                with ex_col1:
                    st.markdown(f"""
                        <div class="queue-item" style="padding: 0.75rem;">
                            <div style="display: flex; justify-content: space-between; align-items: center;">
                                <span style="font-size: 0.8rem; font-weight: 500; color: var(--text-primary);">#{ex.id}</span>
                                <div>
                                    <span class="status-badge source-manual" style="font-size: 0.6rem;">{source_label}</span>
                                    <span style="font-size: 0.7rem; color: var(--text-muted); margin-left: 0.5rem;">{ex.word_count} words</span>
                                </div>
                            </div>
                            <div style="font-size: 0.75rem; color: var(--text-secondary); margin-top: 0.25rem; direction: rtl; text-align: right;">{preview}</div>
                            <div style="font-size: 0.65rem; color: var(--text-muted); margin-top: 0.25rem;">Tags: {tags_str}</div>
                        </div>
                    """, unsafe_allow_html=True)
                with ex_col2:
                    if st.button("Edit", key=f"edit_style_{ex.id}", help="Edit this example"):
                        st.session_state[f'editing_style_{ex.id}'] = True
                        st.rerun()
                with ex_col3:
                    if st.button("🗑️", key=f"del_style_{ex.id}", help="Delete this example"):
                        if sm:
                            sm.delete_example(db, ex.id)
                            st.rerun()

        # Load More pagination
        if filtered_count > display_limit:
            st.caption(f"Showing {min(display_limit, len(examples))} of {filtered_count} examples")
            if st.button("Load More", key="load_more_examples", use_container_width=True):
                st.session_state.style_examples_limit = display_limit + 20
                st.rerun()
        elif len(examples) > 0 and filtered_count > len(examples):
            st.caption(f"Showing {len(examples)} of {filtered_count} examples")

    st.markdown("---")

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
        tweet_count = db.query(Tweet).count()
        tweets_data = []
        for t in db.query(Tweet).yield_per(100):
            tweets_data.append({"id": t.id, "text": t.original_text, "hebrew": t.hebrew_draft, "status": t.status.value})
        tweets_export = json.dumps(tweets_data, indent=2, ensure_ascii=False)
        st.download_button(f"Export Tweets (JSON) ({tweet_count})", tweets_export, "tweets.json", mime="application/json", use_container_width=True)

        trend_count = db.query(Trend).count()
        trends_data = []
        for t in db.query(Trend).yield_per(100):
            trends_data.append({"title": t.title, "source": t.source.value, "description": t.description})
        trends_export = json.dumps(trends_data, indent=2, ensure_ascii=False)
        st.download_button(f"Export Trends (JSON) ({trend_count})", trends_export, "trends.json", mime="application/json", use_container_width=True)

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

def check_auth() -> bool:
    """Simple password gate. Set DASHBOARD_PASSWORD env var to enable."""
    password = os.getenv('DASHBOARD_PASSWORD')
    if not password:
        return True  # No password set = auth disabled

    if 'authenticated' not in st.session_state:
        st.session_state.authenticated = False

    if st.session_state.authenticated:
        return True

    st.markdown("### HFI Dashboard Login")
    entered = st.text_input("Password", type="password", key="auth_password")
    if st.button("Login"):
        if entered == password:
            st.session_state.authenticated = True
            st.rerun()
        else:
            st.error("Incorrect password")
    return False


def main():
    create_tables()

    if not check_auth():
        return

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
