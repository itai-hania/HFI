"""
HFI Dashboard - Hebrew FinTech Informant
Dark Mode UI with Simplified Navigation
"""

import streamlit as st
from pathlib import Path

# Load environment variables from .env file
from dotenv import load_dotenv
env_path = Path(__file__).parent.parent.parent / ".env"
load_dotenv(env_path)

from common.models import create_tables
from dashboard.styles import DARK_MODE_CSS

# Page config — must be first Streamlit call
st.set_page_config(
    page_title="HFI Dashboard",
    page_icon="",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Inject dark mode CSS
st.markdown(DARK_MODE_CSS, unsafe_allow_html=True)

from dashboard.db_helpers import get_db
from dashboard.auth import check_auth
from dashboard.navigation import init_navigation, render_sidebar
from dashboard.views.home import render_home
from dashboard.views.content import render_content
from dashboard.views.settings import render_settings


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
