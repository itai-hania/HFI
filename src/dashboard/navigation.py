import streamlit as st
from dashboard.db_helpers import get_stats


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
