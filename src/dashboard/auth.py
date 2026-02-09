import os
import streamlit as st


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
