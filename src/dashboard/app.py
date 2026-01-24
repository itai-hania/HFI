"""
HFI Dashboard - Hebrew FinTech Informant
Modern content management interface inspired by Monday.com
"""

import streamlit as st
import sys
import logging
import asyncio
from pathlib import Path
from datetime import datetime, timezone
import time

sys.path.append(str(Path(__file__).parent.parent))

from common.models import get_db_session, Tweet, Trend, TrendSource, TweetStatus
from sqlalchemy import func

logger = logging.getLogger(__name__)

# Page config
st.set_page_config(
    page_title="HFI Dashboard",
    page_icon="",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Monday.com inspired CSS - Modern, clean, colorful
st.markdown("""
<style>
    /* ============================================
       MONDAY.COM INSPIRED THEME - LIGHT & COLORFUL
       ============================================ */

    /* Import Google Fonts */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

    /* Base styles */
    .stApp, [data-testid="stAppViewContainer"], [data-testid="stHeader"] {
        background: linear-gradient(135deg, #f8fafc 0%, #f1f5f9 100%) !important;
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif !important;
    }

    .main, .main .block-container, [data-testid="stMainBlockContainer"] {
        background: transparent !important;
        padding: 1.5rem 2.5rem !important;
        max-width: 1600px !important;
    }

    /* Hide Streamlit elements */
    #MainMenu, footer, header {visibility: hidden;}
    .stDeployButton {display: none;}

    /* ============================================
       TYPOGRAPHY
       ============================================ */

    h1, h2, h3, .stMarkdown h1, .stMarkdown h2, .stMarkdown h3 {
        font-family: 'Inter', sans-serif !important;
        font-weight: 700 !important;
        color: #1e293b !important;
        letter-spacing: -0.02em !important;
    }

    h1, .stMarkdown h1 {
        font-size: 1.75rem !important;
        margin-bottom: 0.5rem !important;
    }

    h2, .stMarkdown h2 {
        font-size: 1.25rem !important;
    }

    h3, .stMarkdown h3 {
        font-size: 1.1rem !important;
        color: #334155 !important;
    }

    p, span, label, .stMarkdown, .stMarkdown p {
        font-family: 'Inter', sans-serif !important;
        color: #475569 !important;
        font-size: 0.9rem !important;
        line-height: 1.6 !important;
    }

    /* ============================================
       SIDEBAR - Clean & Professional
       ============================================ */

    [data-testid="stSidebar"],
    [data-testid="stSidebar"] > div,
    [data-testid="stSidebarContent"],
    section[data-testid="stSidebar"] {
        background: linear-gradient(180deg, #ffffff 0%, #f8fafc 100%) !important;
        border-right: 1px solid #e2e8f0 !important;
        box-shadow: 4px 0 24px rgba(0, 0, 0, 0.03) !important;
    }

    [data-testid="stSidebar"] .block-container {
        padding: 1.5rem 1rem !important;
        background: transparent !important;
    }

    [data-testid="stSidebar"] h1,
    [data-testid="stSidebar"] h2,
    [data-testid="stSidebar"] h3 {
        color: #1e293b !important;
    }

    [data-testid="stSidebar"] p,
    [data-testid="stSidebar"] span,
    [data-testid="stSidebar"] label {
        color: #64748b !important;
    }

    /* Sidebar brand header */
    .sidebar-brand {
        background: linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%);
        padding: 1.25rem 1rem;
        border-radius: 12px;
        margin-bottom: 1.5rem;
        text-align: center;
    }

    .sidebar-brand h2 {
        color: white !important;
        margin: 0 !important;
        font-size: 1.5rem !important;
        font-weight: 700 !important;
    }

    .sidebar-brand p {
        color: rgba(255,255,255,0.85) !important;
        margin: 0.25rem 0 0 0 !important;
        font-size: 0.8rem !important;
    }

    /* Sidebar section headers */
    .sidebar-section {
        font-size: 0.7rem !important;
        font-weight: 600 !important;
        text-transform: uppercase !important;
        letter-spacing: 0.1em !important;
        color: #94a3b8 !important;
        margin: 1.25rem 0 0.75rem 0 !important;
        padding-left: 0.25rem !important;
    }

    /* ============================================
       STAT CARDS - Colorful & Modern
       ============================================ */

    .stat-card {
        background: white;
        border-radius: 12px;
        padding: 1rem;
        box-shadow: 0 1px 3px rgba(0, 0, 0, 0.04), 0 4px 12px rgba(0, 0, 0, 0.03);
        border: 1px solid #e2e8f0;
        transition: all 0.2s ease;
        margin-bottom: 0.75rem;
    }

    .stat-card:hover {
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08);
        transform: translateY(-1px);
    }

    .stat-card-value {
        font-size: 1.75rem !important;
        font-weight: 700 !important;
        color: #1e293b !important;
        line-height: 1.2 !important;
    }

    .stat-card-label {
        font-size: 0.75rem !important;
        font-weight: 500 !important;
        color: #64748b !important;
        text-transform: uppercase !important;
        letter-spacing: 0.05em !important;
        margin-top: 0.25rem !important;
    }

    .stat-card-icon {
        width: 36px;
        height: 36px;
        border-radius: 10px;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 1rem;
        margin-bottom: 0.5rem;
    }

    .stat-pending { background: linear-gradient(135deg, #fef3c7 0%, #fde68a 100%); }
    .stat-processed { background: linear-gradient(135deg, #dbeafe 0%, #bfdbfe 100%); }
    .stat-approved { background: linear-gradient(135deg, #d1fae5 0%, #a7f3d0 100%); }
    .stat-published { background: linear-gradient(135deg, #ede9fe 0%, #ddd6fe 100%); }

    /* Streamlit metric overrides */
    [data-testid="stMetricValue"] {
        font-size: 1.5rem !important;
        font-weight: 700 !important;
        color: #1e293b !important;
    }

    [data-testid="stMetricLabel"] {
        font-size: 0.7rem !important;
        text-transform: uppercase !important;
        letter-spacing: 0.05em !important;
        color: #64748b !important;
        font-weight: 500 !important;
    }

    [data-testid="stMetric"], [data-testid="metric-container"] {
        background: white !important;
        padding: 0.75rem !important;
        border-radius: 10px !important;
        border: 1px solid #e2e8f0 !important;
        box-shadow: 0 1px 3px rgba(0,0,0,0.02) !important;
    }

    /* ============================================
       BUTTONS - Colorful & Interactive
       ============================================ */

    .stButton > button {
        font-family: 'Inter', sans-serif !important;
        font-size: 0.85rem !important;
        font-weight: 500 !important;
        padding: 0.5rem 1rem !important;
        border-radius: 8px !important;
        border: 1px solid #e2e8f0 !important;
        background: white !important;
        color: #475569 !important;
        transition: all 0.15s ease !important;
        box-shadow: 0 1px 2px rgba(0, 0, 0, 0.04) !important;
    }

    .stButton > button:hover {
        background: #f8fafc !important;
        border-color: #cbd5e1 !important;
        color: #1e293b !important;
        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08) !important;
        transform: translateY(-1px) !important;
    }

    .stButton > button:active {
        transform: translateY(0) !important;
        box-shadow: 0 1px 2px rgba(0, 0, 0, 0.04) !important;
    }

    .stButton > button:focus {
        box-shadow: 0 0 0 3px rgba(99, 102, 241, 0.15) !important;
        border-color: #6366f1 !important;
    }

    /* Primary button - Purple gradient */
    .stButton > button[kind="primary"],
    .stButton > button[data-testid="baseButton-primary"] {
        background: linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%) !important;
        color: white !important;
        border: none !important;
        box-shadow: 0 2px 8px rgba(99, 102, 241, 0.3) !important;
    }

    .stButton > button[kind="primary"]:hover,
    .stButton > button[data-testid="baseButton-primary"]:hover {
        background: linear-gradient(135deg, #4f46e5 0%, #7c3aed 100%) !important;
        box-shadow: 0 4px 16px rgba(99, 102, 241, 0.4) !important;
        color: white !important;
    }

    /* Action button styles */
    .btn-approve {
        background: linear-gradient(135deg, #10b981 0%, #059669 100%) !important;
        color: white !important;
        border: none !important;
    }

    .btn-danger {
        background: linear-gradient(135deg, #f43f5e 0%, #e11d48 100%) !important;
        color: white !important;
        border: none !important;
    }

    /* ============================================
       STATUS BADGES - Colorful Pills
       ============================================ */

    .status-badge {
        display: inline-flex;
        align-items: center;
        padding: 0.35rem 0.85rem;
        border-radius: 50px;
        font-size: 0.75rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.03em;
        box-shadow: 0 1px 3px rgba(0, 0, 0, 0.08);
    }

    .status-pending {
        background: linear-gradient(135deg, #fef3c7 0%, #fde68a 100%);
        color: #92400e;
        border: 1px solid #f59e0b;
    }

    .status-processed {
        background: linear-gradient(135deg, #dbeafe 0%, #bfdbfe 100%);
        color: #1e40af;
        border: 1px solid #3b82f6;
    }

    .status-approved {
        background: linear-gradient(135deg, #d1fae5 0%, #a7f3d0 100%);
        color: #065f46;
        border: 1px solid #10b981;
    }

    .status-published {
        background: linear-gradient(135deg, #ede9fe 0%, #ddd6fe 100%);
        color: #5b21b6;
        border: 1px solid #8b5cf6;
    }

    .status-failed {
        background: linear-gradient(135deg, #fee2e2 0%, #fecaca 100%);
        color: #991b1b;
        border: 1px solid #ef4444;
    }

    /* ============================================
       CONTENT CARDS - Clean & Modern
       ============================================ */

    .content-card {
        background: white;
        border-radius: 16px;
        padding: 1.25rem;
        margin-bottom: 1rem;
        border: 1px solid #e2e8f0;
        box-shadow: 0 1px 3px rgba(0, 0, 0, 0.04), 0 6px 24px rgba(0, 0, 0, 0.03);
        transition: all 0.2s ease;
    }

    .content-card:hover {
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.06), 0 12px 32px rgba(0, 0, 0, 0.06);
        border-color: #cbd5e1;
    }

    .card-header {
        display: flex;
        align-items: center;
        justify-content: space-between;
        margin-bottom: 1rem;
        padding-bottom: 0.75rem;
        border-bottom: 1px solid #f1f5f9;
    }

    .card-author {
        font-weight: 600;
        color: #1e293b;
        font-size: 0.95rem;
    }

    .card-meta {
        display: flex;
        align-items: center;
        gap: 1rem;
        color: #94a3b8;
        font-size: 0.8rem;
    }

    .card-link {
        color: #6366f1 !important;
        text-decoration: none !important;
        font-weight: 500;
        font-size: 0.8rem;
        transition: color 0.15s ease;
    }

    .card-link:hover {
        color: #4f46e5 !important;
        text-decoration: underline !important;
    }

    /* ============================================
       TEXT AREAS - Refined
       ============================================ */

    .stTextArea, .stTextArea > div {
        background-color: transparent !important;
    }

    .stTextArea textarea {
        font-family: 'Inter', sans-serif !important;
        font-size: 0.9rem !important;
        line-height: 1.6 !important;
        border-radius: 10px !important;
        background: #f8fafc !important;
        border: 1px solid #e2e8f0 !important;
        color: #334155 !important;
        padding: 0.75rem !important;
        transition: all 0.15s ease !important;
    }

    .stTextArea textarea:focus {
        border-color: #6366f1 !important;
        box-shadow: 0 0 0 3px rgba(99, 102, 241, 0.1) !important;
        background: white !important;
    }

    .stTextArea textarea::placeholder {
        color: #94a3b8 !important;
    }

    .stTextArea textarea:disabled {
        background: #f1f5f9 !important;
        color: #64748b !important;
        border-color: #e2e8f0 !important;
    }

    /* Text area labels */
    .text-label {
        font-size: 0.7rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        color: #94a3b8;
        margin-bottom: 0.35rem;
        display: flex;
        align-items: center;
        gap: 0.35rem;
    }

    .text-label-en { color: #6366f1; }
    .text-label-he { color: #10b981; }

    /* ============================================
       TABS - Modern Style
       ============================================ */

    .stTabs [data-baseweb="tab-list"] {
        gap: 0.5rem !important;
        background: transparent !important;
        border-bottom: 2px solid #e2e8f0 !important;
        padding: 0 !important;
    }

    .stTabs [data-baseweb="tab"] {
        padding: 0.75rem 1.25rem !important;
        font-family: 'Inter', sans-serif !important;
        font-weight: 500 !important;
        font-size: 0.9rem !important;
        color: #64748b !important;
        border-radius: 8px 8px 0 0 !important;
        border-bottom: 3px solid transparent !important;
        background: transparent !important;
        transition: all 0.15s ease !important;
    }

    .stTabs [data-baseweb="tab"]:hover {
        color: #475569 !important;
        background: #f8fafc !important;
    }

    .stTabs [aria-selected="true"] {
        color: #6366f1 !important;
        border-bottom-color: #6366f1 !important;
        background: white !important;
        font-weight: 600 !important;
    }

    .stTabs [data-baseweb="tab-highlight"] {
        background-color: #6366f1 !important;
    }

    .stTabs [data-baseweb="tab-border"] {
        display: none !important;
    }

    /* ============================================
       SELECT BOXES - Clean Design
       ============================================ */

    .stSelectbox > div,
    .stSelectbox > div > div,
    [data-baseweb="select"] > div {
        background: white !important;
        border: 1px solid #e2e8f0 !important;
        border-radius: 8px !important;
        transition: all 0.15s ease !important;
    }

    .stSelectbox [data-baseweb="select"]:hover > div {
        border-color: #cbd5e1 !important;
    }

    .stSelectbox [data-baseweb="select"] span {
        color: #475569 !important;
        font-family: 'Inter', sans-serif !important;
    }

    .stSelectbox svg {
        fill: #94a3b8 !important;
    }

    [data-baseweb="popover"], [data-baseweb="popover"] > div {
        background: white !important;
        border: 1px solid #e2e8f0 !important;
        border-radius: 10px !important;
        box-shadow: 0 10px 40px rgba(0, 0, 0, 0.1) !important;
    }

    [data-baseweb="menu"] {
        background: white !important;
    }

    [role="option"], [data-baseweb="menu"] li {
        background: white !important;
        color: #475569 !important;
        font-family: 'Inter', sans-serif !important;
        padding: 0.6rem 1rem !important;
    }

    [role="option"]:hover, [data-baseweb="menu"] li:hover {
        background: #f8fafc !important;
    }

    [aria-selected="true"][role="option"] {
        background: #f1f5f9 !important;
        color: #6366f1 !important;
        font-weight: 500 !important;
    }

    /* ============================================
       INPUT FIELDS - Modern
       ============================================ */

    .stTextInput > div {
        background: transparent !important;
    }

    .stTextInput input {
        font-family: 'Inter', sans-serif !important;
        border-radius: 8px !important;
        background: white !important;
        border: 1px solid #e2e8f0 !important;
        color: #334155 !important;
        font-size: 0.9rem !important;
        padding: 0.6rem 0.75rem !important;
        transition: all 0.15s ease !important;
    }

    .stTextInput input:focus {
        border-color: #6366f1 !important;
        box-shadow: 0 0 0 3px rgba(99, 102, 241, 0.1) !important;
    }

    .stTextInput input::placeholder {
        color: #94a3b8 !important;
    }

    /* ============================================
       CHECKBOX - Clean
       ============================================ */

    .stCheckbox > label {
        color: #475569 !important;
        font-family: 'Inter', sans-serif !important;
        font-size: 0.85rem !important;
    }

    .stCheckbox [data-testid="stCheckbox"] > div:first-child {
        background: white !important;
        border: 2px solid #e2e8f0 !important;
        border-radius: 4px !important;
    }

    .stCheckbox [data-testid="stCheckbox"][aria-checked="true"] > div:first-child {
        background: #6366f1 !important;
        border-color: #6366f1 !important;
    }

    /* ============================================
       ALERTS & MESSAGES
       ============================================ */

    .stAlert, [data-testid="stAlert"] {
        border-radius: 10px !important;
        border: none !important;
        font-family: 'Inter', sans-serif !important;
    }

    [data-testid="stAlert"][data-baseweb="notification"] {
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08) !important;
    }

    /* Success message */
    .element-container:has([data-testid="stAlert"]) [kind="success"] {
        background: linear-gradient(135deg, #d1fae5 0%, #a7f3d0 100%) !important;
        color: #065f46 !important;
    }

    /* Info message */
    .element-container:has([data-testid="stAlert"]) [kind="info"] {
        background: linear-gradient(135deg, #dbeafe 0%, #bfdbfe 100%) !important;
        color: #1e40af !important;
    }

    /* Warning message */
    .element-container:has([data-testid="stAlert"]) [kind="warning"] {
        background: linear-gradient(135deg, #fef3c7 0%, #fde68a 100%) !important;
        color: #92400e !important;
    }

    /* Error message */
    .element-container:has([data-testid="stAlert"]) [kind="error"] {
        background: linear-gradient(135deg, #fee2e2 0%, #fecaca 100%) !important;
        color: #991b1b !important;
    }

    /* ============================================
       DIVIDERS & SPACING
       ============================================ */

    hr {
        border: none !important;
        border-top: 1px solid #e2e8f0 !important;
        margin: 1.25rem 0 !important;
    }

    .divider-subtle {
        border-top: 1px solid #f1f5f9 !important;
        margin: 0.75rem 0 !important;
    }

    /* ============================================
       LINKS
       ============================================ */

    a {
        color: #6366f1 !important;
        text-decoration: none !important;
        transition: color 0.15s ease !important;
    }

    a:hover {
        color: #4f46e5 !important;
        text-decoration: underline !important;
    }

    /* ============================================
       CAPTIONS & SMALL TEXT
       ============================================ */

    .stCaption, small, [data-testid="stCaptionContainer"] {
        color: #94a3b8 !important;
        font-family: 'Inter', sans-serif !important;
        font-size: 0.75rem !important;
    }

    /* ============================================
       SPINNER
       ============================================ */

    .stSpinner > div {
        border-color: #6366f1 !important;
        border-top-color: transparent !important;
    }

    /* ============================================
       SCROLLBAR - Subtle
       ============================================ */

    ::-webkit-scrollbar {
        width: 8px;
        height: 8px;
    }

    ::-webkit-scrollbar-track {
        background: #f1f5f9;
        border-radius: 4px;
    }

    ::-webkit-scrollbar-thumb {
        background: #cbd5e1;
        border-radius: 4px;
    }

    ::-webkit-scrollbar-thumb:hover {
        background: #94a3b8;
    }

    /* ============================================
       EMPTY STATE
       ============================================ */

    .empty-state {
        text-align: center;
        padding: 3rem 2rem;
        background: white;
        border-radius: 16px;
        border: 2px dashed #e2e8f0;
    }

    .empty-state-icon {
        font-size: 3rem;
        margin-bottom: 1rem;
        opacity: 0.5;
    }

    .empty-state-title {
        font-size: 1.1rem;
        font-weight: 600;
        color: #475569;
        margin-bottom: 0.5rem;
    }

    .empty-state-text {
        color: #94a3b8;
        font-size: 0.9rem;
    }

    /* ============================================
       ACTION BUTTONS ROW
       ============================================ */

    .action-btn {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        width: 36px;
        height: 36px;
        border-radius: 8px;
        border: 1px solid #e2e8f0;
        background: white;
        color: #64748b;
        cursor: pointer;
        transition: all 0.15s ease;
        font-size: 1rem;
    }

    .action-btn:hover {
        background: #f8fafc;
        border-color: #cbd5e1;
        color: #475569;
    }

    .action-btn-save:hover { background: #dbeafe; border-color: #3b82f6; color: #1e40af; }
    .action-btn-approve:hover { background: #d1fae5; border-color: #10b981; color: #065f46; }
    .action-btn-reset:hover { background: #fef3c7; border-color: #f59e0b; color: #92400e; }
    .action-btn-delete:hover { background: #fee2e2; border-color: #ef4444; color: #991b1b; }

    /* ============================================
       PAGE HEADER
       ============================================ */

    .page-header {
        display: flex;
        align-items: center;
        justify-content: space-between;
        margin-bottom: 1.5rem;
        padding-bottom: 1rem;
        border-bottom: 2px solid #e2e8f0;
    }

    .page-title {
        font-size: 1.5rem;
        font-weight: 700;
        color: #1e293b;
        margin: 0;
    }

    .page-subtitle {
        color: #64748b;
        font-size: 0.9rem;
        margin-top: 0.25rem;
    }

    /* ============================================
       FILTER BAR
       ============================================ */

    .filter-bar {
        background: white;
        border-radius: 12px;
        padding: 1rem 1.25rem;
        margin-bottom: 1.25rem;
        border: 1px solid #e2e8f0;
        box-shadow: 0 1px 3px rgba(0, 0, 0, 0.02);
        display: flex;
        align-items: center;
        gap: 1rem;
    }

    /* ============================================
       TRENDS LIST
       ============================================ */

    .trend-item {
        background: white;
        border-radius: 10px;
        padding: 1rem 1.25rem;
        margin-bottom: 0.5rem;
        border: 1px solid #e2e8f0;
        transition: all 0.15s ease;
        display: flex;
        align-items: center;
        gap: 1rem;
    }

    .trend-item:hover {
        border-color: #cbd5e1;
        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.04);
    }

    .trend-source {
        display: inline-flex;
        align-items: center;
        padding: 0.25rem 0.6rem;
        border-radius: 6px;
        font-size: 0.7rem;
        font-weight: 600;
        text-transform: uppercase;
        background: #f1f5f9;
        color: #64748b;
    }

    /* Source colors */
    .source-x { background: #1e293b; color: white; }
    .source-reuters { background: #ff6600; color: white; }
    .source-wsj { background: #0080c6; color: white; }
    .source-techcrunch { background: #0a9e01; color: white; }
    .source-bloomberg { background: #472f92; color: white; }

    /* ============================================
       WIDGET LABELS
       ============================================ */

    .stWidgetLabel, [data-testid="stWidgetLabel"] {
        color: #64748b !important;
        font-family: 'Inter', sans-serif !important;
        font-weight: 500 !important;
        font-size: 0.8rem !important;
    }

    /* ============================================
       EXPANDER - Clean
       ============================================ */

    .streamlit-expanderHeader {
        background: white !important;
        border: 1px solid #e2e8f0 !important;
        border-radius: 10px !important;
        font-family: 'Inter', sans-serif !important;
        font-weight: 500 !important;
        color: #475569 !important;
    }

    .streamlit-expanderHeader:hover {
        background: #f8fafc !important;
        border-color: #cbd5e1 !important;
    }

    .streamlit-expanderContent {
        border: 1px solid #e2e8f0 !important;
        border-top: none !important;
        border-radius: 0 0 10px 10px !important;
        background: white !important;
    }

    /* ============================================
       COLUMN GAPS
       ============================================ */

    [data-testid="column"] {
        background: transparent !important;
    }

    /* Fix focus rings */
    *:focus {
        outline: none !important;
    }

    *:focus-visible {
        box-shadow: 0 0 0 3px rgba(99, 102, 241, 0.15) !important;
        border-color: #6366f1 !important;
    }
</style>
""", unsafe_allow_html=True)


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


def render_status_badge(status_str):
    """Render a colorful status badge"""
    status_lower = status_str.lower()
    return f'<span class="status-badge status-{status_lower}">{status_str}</span>'


def render_sidebar(db):
    """Modern sidebar with stats and quick actions"""
    with st.sidebar:
        # Brand header
        st.markdown("""
            <div class="sidebar-brand">
                <h2>HFI</h2>
                <p>Hebrew FinTech Informant</p>
            </div>
        """, unsafe_allow_html=True)

        # Stats section
        st.markdown('<p class="sidebar-section">Dashboard Stats</p>', unsafe_allow_html=True)

        stats = get_stats(db)

        # Stats in a grid
        col1, col2 = st.columns(2)
        with col1:
            st.markdown(f"""
                <div class="stat-card">
                    <div class="stat-card-icon stat-pending">&#9203;</div>
                    <div class="stat-card-value">{stats['pending']}</div>
                    <div class="stat-card-label">Pending</div>
                </div>
            """, unsafe_allow_html=True)
            st.markdown(f"""
                <div class="stat-card">
                    <div class="stat-card-icon stat-approved">&#10003;</div>
                    <div class="stat-card-value">{stats['approved']}</div>
                    <div class="stat-card-label">Approved</div>
                </div>
            """, unsafe_allow_html=True)
        with col2:
            st.markdown(f"""
                <div class="stat-card">
                    <div class="stat-card-icon stat-processed">&#9881;</div>
                    <div class="stat-card-value">{stats['processed']}</div>
                    <div class="stat-card-label">Processed</div>
                </div>
            """, unsafe_allow_html=True)
            st.markdown(f"""
                <div class="stat-card">
                    <div class="stat-card-icon stat-published">&#10004;</div>
                    <div class="stat-card-value">{stats['published']}</div>
                    <div class="stat-card-label">Published</div>
                </div>
            """, unsafe_allow_html=True)

        # Total items
        st.markdown(f"""
            <div style="text-align: center; padding: 0.5rem; background: #f1f5f9; border-radius: 8px; margin-top: 0.5rem;">
                <span style="color: #64748b; font-size: 0.8rem;">Total Items:</span>
                <span style="color: #1e293b; font-weight: 700; font-size: 1.1rem; margin-left: 0.5rem;">{stats['total']}</span>
            </div>
        """, unsafe_allow_html=True)

        st.markdown("---")

        # Quick Actions
        st.markdown('<p class="sidebar-section">Quick Actions</p>', unsafe_allow_html=True)

        # Thread Scraper
        st.markdown("**Scrape Thread**")
        thread_url = st.text_input(
            "Thread URL",
            placeholder="https://x.com/user/status/...",
            key="thread_url",
            label_visibility="collapsed"
        )

        col1, col2 = st.columns([1, 1])
        with col1:
            auto_translate = st.checkbox("Auto-translate", value=True, key="auto_trans")
        with col2:
            scrape_btn = st.button("Scrape", key="scrape_btn", use_container_width=True, type="primary")

        if scrape_btn and thread_url:
            with st.spinner("Scraping thread..."):
                try:
                    from scraper.scraper import TwitterScraper

                    async def run():
                        scraper = TwitterScraper()
                        try:
                            await scraper.ensure_logged_in()
                            tweets_data = await scraper.fetch_thread(thread_url)
                            return tweets_data
                        finally:
                            await scraper.close()

                    tweets_data = asyncio.run(run())

                    # Translate entire thread as one text if requested
                    translated_texts = {}
                    if auto_translate and tweets_data:
                        try:
                            from processor.processor import ProcessorConfig, TranslationService
                            config = ProcessorConfig()
                            translator = TranslationService(config)

                            # Concatenate all tweets for context-aware translation
                            all_texts = [t['text'] for t in tweets_data]
                            combined_translation = translator.translate_long_text(all_texts)

                            # Split back by separator
                            if combined_translation:
                                parts = combined_translation.split("\n\n---\n\n")
                                for i, t in enumerate(tweets_data):
                                    if i < len(parts):
                                        translated_texts[t['tweet_id']] = parts[i].strip()

                            st.info(f"Translated {len(translated_texts)} tweets")
                        except Exception as te:
                            logger.warning(f"Translation failed: {te}")
                            st.warning(f"Translation failed: {str(te)[:50]}")

                    # Save to database
                    saved = 0
                    for t in tweets_data:
                        if not db.query(Tweet).filter_by(source_url=t['permalink']).first():
                            media_url = t['media'][0]['src'] if t.get('media') else None
                            hebrew_draft = translated_texts.get(t['tweet_id'])
                            status = TweetStatus.PROCESSED if hebrew_draft else TweetStatus.PENDING

                            db.add(Tweet(
                                source_url=t['permalink'],
                                original_text=t['text'],
                                hebrew_draft=hebrew_draft,
                                status=status,
                                media_url=media_url,
                                trend_topic=t.get('author_handle', '')
                            ))
                            saved += 1
                    db.commit()

                    st.success(f"Saved {saved}/{len(tweets_data)} items")
                    time.sleep(1)
                    st.rerun()
                except Exception as e:
                    st.error(f"Error: {str(e)[:100]}")

        st.markdown("---")

        # Fetch buttons
        st.markdown('<p class="sidebar-section">Fetch Content</p>', unsafe_allow_html=True)
        col1, col2 = st.columns(2)
        with col1:
            if st.button("Trends", use_container_width=True):
                with st.spinner("Fetching trends..."):
                    try:
                        from scraper.scraper import TwitterScraper
                        async def run():
                            scraper = TwitterScraper()
                            try:
                                await scraper.ensure_logged_in()
                                trends = await scraper.get_trending_topics(limit=5)
                                for trend in trends:
                                    db.add(Trend(title=trend['title'], description=trend.get('description', ''), source=TrendSource.X_TWITTER))
                                db.commit()
                                return len(trends)
                            finally:
                                await scraper.close()
                        count = asyncio.run(run())
                        st.success(f"Added {count} trends")
                        st.rerun()
                    except Exception as e:
                        st.error(str(e)[:50])

        with col2:
            if st.button("News", use_container_width=True):
                with st.spinner("Fetching news..."):
                    try:
                        from scraper.news_scraper import NewsScraper
                        source_map = {"Reuters": TrendSource.REUTERS, "WSJ": TrendSource.WSJ, "TechCrunch": TrendSource.TECHCRUNCH, "Bloomberg": TrendSource.BLOOMBERG}
                        scraper = NewsScraper()
                        articles = scraper.get_latest_news(limit_per_source=5)
                        count = 0
                        for article in articles:
                            source_enum = source_map.get(article['source'])
                            if source_enum and not db.query(Trend).filter_by(title=article['title']).first():
                                db.add(Trend(title=article['title'], description=article['description'], source=source_enum, discovered_at=article['discovered_at']))
                                count += 1
                        db.commit()
                        st.success(f"Added {count} articles")
                        st.rerun()
                    except Exception as e:
                        st.error(str(e)[:50])

        st.markdown("---")

        # Bulk Actions
        st.markdown('<p class="sidebar-section">Bulk Actions</p>', unsafe_allow_html=True)
        col1, col2 = st.columns(2)
        with col1:
            if st.button("Approve All", use_container_width=True, help="Approve all processed items"):
                tweets = db.query(Tweet).filter(Tweet.status == TweetStatus.PROCESSED).all()
                count = 0
                for t in tweets:
                    if t.hebrew_draft:
                        t.status = TweetStatus.APPROVED
                        count += 1
                db.commit()
                if count > 0:
                    st.success(f"Approved {count} items")
                st.rerun()
        with col2:
            if st.button("Clear Pending", use_container_width=True, help="Delete all pending items"):
                count = db.query(Tweet).filter(Tweet.status == TweetStatus.PENDING).delete()
                db.commit()
                if count > 0:
                    st.info(f"Cleared {count} items")
                st.rerun()

        st.markdown("---")

        # Footer
        st.markdown(f"""
            <div style="text-align: center; padding: 0.5rem;">
                <span style="color: #94a3b8; font-size: 0.75rem;">
                    Last refresh: {datetime.now().strftime('%H:%M:%S')}
                </span>
            </div>
        """, unsafe_allow_html=True)

        if st.button("Refresh Dashboard", use_container_width=True):
            st.rerun()


def render_content_card(tweet, db, idx):
    """Render a modern content card"""
    status_str = tweet.status.value if hasattr(tweet.status, 'value') else str(tweet.status)
    status_lower = status_str.lower()

    # Card container with custom HTML
    st.markdown(f"""
        <div class="content-card">
            <div class="card-header">
                <div>
                    <span class="card-author">{tweet.trend_topic or 'Unknown Source'}</span>
                    <span style="margin-left: 12px;">{render_status_badge(status_str)}</span>
                </div>
                <div class="card-meta">
                    <span>{tweet.created_at.strftime('%b %d, %Y at %H:%M')}</span>
                    <a href="{tweet.source_url}" target="_blank" class="card-link">View Original</a>
                </div>
            </div>
        </div>
    """, unsafe_allow_html=True)

    # Content columns for English and Hebrew
    col1, col2 = st.columns(2)

    with col1:
        st.markdown('<p class="text-label text-label-en">English (Original)</p>', unsafe_allow_html=True)
        st.text_area(
            "English",
            value=tweet.original_text,
            height=100,
            disabled=True,
            key=f"en_{tweet.id}",
            label_visibility="collapsed"
        )

    with col2:
        st.markdown('<p class="text-label text-label-he">Hebrew (Translation)</p>', unsafe_allow_html=True)
        hebrew_text = st.text_area(
            "Hebrew",
            value=tweet.hebrew_draft or "",
            height=100,
            key=f"he_{tweet.id}",
            label_visibility="collapsed",
            placeholder="Enter Hebrew translation..."
        )

    # Action buttons
    cols = st.columns([1, 1, 1, 1, 1, 4])

    with cols[0]:
        if st.button("Save", key=f"s_{tweet.id}", help="Save changes", use_container_width=True):
            update_tweet(db, tweet.id, hebrew_draft=hebrew_text)
            st.success("Saved!")
            time.sleep(0.5)
            st.rerun()

    with cols[1]:
        if st.button("Approve", key=f"a_{tweet.id}", help="Approve for publishing", type="primary", use_container_width=True):
            update_tweet(db, tweet.id, status=TweetStatus.APPROVED, hebrew_draft=hebrew_text)
            st.success("Approved!")
            time.sleep(0.5)
            st.rerun()

    with cols[2]:
        if st.button("Reset", key=f"r_{tweet.id}", help="Reset to pending", use_container_width=True):
            update_tweet(db, tweet.id, status=TweetStatus.PENDING)
            st.rerun()

    with cols[3]:
        if st.button("Reprocess", key=f"rp_{tweet.id}", help="Clear translation and reprocess", use_container_width=True):
            update_tweet(db, tweet.id, status=TweetStatus.PENDING, hebrew_draft=None)
            st.rerun()

    with cols[4]:
        if st.button("Delete", key=f"d_{tweet.id}", help="Delete this item", use_container_width=True):
            delete_tweet(db, tweet.id)
            st.rerun()

    st.markdown("<hr class='divider-subtle'>", unsafe_allow_html=True)


def render_content_view(db):
    """Main content view with filter bar and cards"""

    # Page header
    st.markdown("""
        <div class="page-header">
            <div>
                <h1 class="page-title">Content Queue</h1>
                <p class="page-subtitle">Review, edit, and approve translations</p>
            </div>
        </div>
    """, unsafe_allow_html=True)

    # Filter bar
    col1, col2, col3, col4 = st.columns([2, 1, 1, 1])

    with col1:
        status_filter = st.selectbox(
            "Filter by Status",
            ['all', 'pending', 'processed', 'approved', 'published'],
            format_func=lambda x: x.capitalize() if x != 'all' else 'All Statuses',
            label_visibility="collapsed"
        )

    with col2:
        limit = st.selectbox(
            "Items per page",
            [25, 50, 100],
            index=0,
            format_func=lambda x: f"Show {x}",
            label_visibility="collapsed"
        )

    with col3:
        sort_order = st.selectbox(
            "Sort",
            ['newest', 'oldest'],
            format_func=lambda x: "Newest First" if x == 'newest' else "Oldest First",
            label_visibility="collapsed"
        )

    with col4:
        if st.button("Refresh", use_container_width=True):
            st.rerun()

    st.markdown("<hr>", unsafe_allow_html=True)

    # Get tweets
    tweets = get_tweets(db, status_filter=status_filter, limit=limit)

    if not tweets:
        st.markdown("""
            <div class="empty-state">
                <div class="empty-state-icon">📭</div>
                <div class="empty-state-title">No content found</div>
                <div class="empty-state-text">Use the sidebar to scrape threads or fetch news articles</div>
            </div>
        """, unsafe_allow_html=True)
    else:
        # Stats bar
        st.markdown(f"""
            <div style="display: flex; align-items: center; gap: 1rem; margin-bottom: 1rem; padding: 0.75rem 1rem; background: #f8fafc; border-radius: 8px;">
                <span style="color: #64748b; font-size: 0.85rem;">Showing <strong style="color: #1e293b;">{len(tweets)}</strong> items</span>
                <span style="color: #e2e8f0;">|</span>
                <span style="color: #64748b; font-size: 0.85rem;">Filter: <strong style="color: #1e293b;">{status_filter.capitalize()}</strong></span>
            </div>
        """, unsafe_allow_html=True)

        # Render content cards
        for idx, tweet in enumerate(tweets):
            render_content_card(tweet, db, idx)


def render_trends_view(db):
    """Trends and news view"""

    # Page header
    col1, col2 = st.columns([4, 1])
    with col1:
        st.markdown("""
            <div class="page-header">
                <div>
                    <h1 class="page-title">Trends & News</h1>
                    <p class="page-subtitle">Discovered topics from various sources</p>
                </div>
            </div>
        """, unsafe_allow_html=True)
    with col2:
        if st.button("Clear All", use_container_width=True):
            db.query(Trend).delete()
            db.commit()
            st.rerun()

    trends = db.query(Trend).order_by(Trend.discovered_at.desc()).limit(50).all()

    if not trends:
        st.markdown("""
            <div class="empty-state">
                <div class="empty-state-icon">📰</div>
                <div class="empty-state-title">No trends discovered yet</div>
                <div class="empty-state-text">Click "Trends" or "News" in the sidebar to fetch content</div>
            </div>
        """, unsafe_allow_html=True)
    else:
        st.markdown(f"""
            <div style="display: flex; align-items: center; gap: 1rem; margin-bottom: 1rem; padding: 0.75rem 1rem; background: #f8fafc; border-radius: 8px;">
                <span style="color: #64748b; font-size: 0.85rem;">Found <strong style="color: #1e293b;">{len(trends)}</strong> trends</span>
            </div>
        """, unsafe_allow_html=True)

        for trend in trends:
            source_str = trend.source.value if hasattr(trend.source, 'value') else str(trend.source)
            source_lower = source_str.lower().replace(' ', '-').replace('_', '-')

            # Map sources to colors
            source_class = 'source-x'
            if 'reuters' in source_lower:
                source_class = 'source-reuters'
            elif 'wsj' in source_lower:
                source_class = 'source-wsj'
            elif 'techcrunch' in source_lower:
                source_class = 'source-techcrunch'
            elif 'bloomberg' in source_lower:
                source_class = 'source-bloomberg'

            col1, col2, col3 = st.columns([5, 1, 1])
            with col1:
                st.markdown(f"""
                    <div style="padding: 0.75rem 0;">
                        <div style="font-weight: 600; color: #1e293b; font-size: 0.95rem; margin-bottom: 0.35rem;">
                            {trend.title[:100]}{'...' if len(trend.title) > 100 else ''}
                        </div>
                        <div style="color: #94a3b8; font-size: 0.8rem;">
                            {trend.description[:150] if trend.description else 'No description'}{'...' if trend.description and len(trend.description) > 150 else ''}
                        </div>
                    </div>
                """, unsafe_allow_html=True)
            with col2:
                st.markdown(f'<span class="trend-source {source_class}">{source_str}</span>', unsafe_allow_html=True)
            with col3:
                st.markdown(f"""
                    <span style="color: #94a3b8; font-size: 0.75rem;">
                        {trend.discovered_at.strftime('%b %d') if trend.discovered_at else '-'}
                    </span>
                """, unsafe_allow_html=True)

            st.markdown("<hr class='divider-subtle'>", unsafe_allow_html=True)


def render_settings_view(db):
    """Settings and configuration view"""

    st.markdown("""
        <div class="page-header">
            <div>
                <h1 class="page-title">Settings</h1>
                <p class="page-subtitle">Database management and configuration</p>
            </div>
        </div>
    """, unsafe_allow_html=True)

    col1, col2 = st.columns(2)

    with col1:
        # Database stats card
        st.markdown("""
            <div class="content-card">
                <h3 style="margin-top: 0; margin-bottom: 1rem;">Database Overview</h3>
            </div>
        """, unsafe_allow_html=True)

        tweet_count = db.query(Tweet).count()
        trend_count = db.query(Trend).count()

        st.markdown(f"""
            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 1rem; margin-bottom: 1rem;">
                <div class="stat-card">
                    <div class="stat-card-value">{tweet_count}</div>
                    <div class="stat-card-label">Total Tweets</div>
                </div>
                <div class="stat-card">
                    <div class="stat-card-value">{trend_count}</div>
                    <div class="stat-card-label">Total Trends</div>
                </div>
            </div>
        """, unsafe_allow_html=True)

        # Danger zone
        st.markdown("""
            <div class="content-card" style="border-color: #fecaca;">
                <h3 style="margin-top: 0; margin-bottom: 1rem; color: #dc2626;">Danger Zone</h3>
                <p style="color: #64748b; font-size: 0.85rem; margin-bottom: 1rem;">These actions cannot be undone. Please proceed with caution.</p>
            </div>
        """, unsafe_allow_html=True)

        col_a, col_b = st.columns(2)
        with col_a:
            if st.button("Delete All Tweets", use_container_width=True):
                db.query(Tweet).delete()
                db.commit()
                st.success("All tweets deleted successfully")
                time.sleep(1)
                st.rerun()

        with col_b:
            if st.button("Delete All Trends", use_container_width=True):
                db.query(Trend).delete()
                db.commit()
                st.success("All trends deleted successfully")
                time.sleep(1)
                st.rerun()

    with col2:
        # Status guide
        st.markdown("""
            <div class="content-card">
                <h3 style="margin-top: 0; margin-bottom: 1rem;">Status Guide</h3>
            </div>
        """, unsafe_allow_html=True)

        st.markdown(f"""
            <div style="display: flex; flex-direction: column; gap: 0.75rem;">
                <div style="display: flex; align-items: center; gap: 0.75rem;">
                    {render_status_badge('PENDING')}
                    <span style="color: #64748b;">Awaiting translation processing</span>
                </div>
                <div style="display: flex; align-items: center; gap: 0.75rem;">
                    {render_status_badge('PROCESSED')}
                    <span style="color: #64748b;">Translated, needs human review</span>
                </div>
                <div style="display: flex; align-items: center; gap: 0.75rem;">
                    {render_status_badge('APPROVED')}
                    <span style="color: #64748b;">Reviewed and ready to publish</span>
                </div>
                <div style="display: flex; align-items: center; gap: 0.75rem;">
                    {render_status_badge('PUBLISHED')}
                    <span style="color: #64748b;">Successfully posted to X</span>
                </div>
            </div>
        """, unsafe_allow_html=True)

        st.markdown("<hr>", unsafe_allow_html=True)

        # Workflow info
        st.markdown("""
            <div class="content-card">
                <h3 style="margin-top: 0; margin-bottom: 1rem;">Workflow</h3>
                <div style="color: #64748b; font-size: 0.9rem; line-height: 1.8;">
                    <p><strong>1. Scrape</strong> - Fetch threads from X or news articles</p>
                    <p><strong>2. Process</strong> - Auto-translate to Hebrew</p>
                    <p><strong>3. Review</strong> - Edit and approve translations</p>
                    <p><strong>4. Publish</strong> - Post approved content to X</p>
                </div>
            </div>
        """, unsafe_allow_html=True)


def main():
    db = get_db()

    # Render sidebar
    render_sidebar(db)

    # Main content with tabs
    tab1, tab2, tab3 = st.tabs(["Content", "Trends", "Settings"])

    with tab1:
        render_content_view(db)

    with tab2:
        render_trends_view(db)

    with tab3:
        render_settings_view(db)


if __name__ == "__main__":
    main()
