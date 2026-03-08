import streamlit as st
from dashboard.db_helpers import get_stats
from dashboard.state import (
    get_current_view,
    init_session_state,
    set_current_view,
)


def init_navigation():
    """Initialize navigation state."""
    init_session_state()


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
        is_active = get_current_view() == key
        if st.button(
            label,
            key=f"nav_{key}",
            use_container_width=True,
            type="primary" if is_active else "secondary"
        ):
            set_current_view(key)

    st.markdown("---")

    # Quick stats
    stats = get_stats(db)
    col1, col2 = st.columns(2)
    with col1:
        st.metric("Inbox", stats['pending'])
    with col2:
        st.metric("Ready", stats['approved'])
