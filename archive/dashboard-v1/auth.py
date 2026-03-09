import os
import secrets
import time
import logging
import streamlit as st
from dashboard.state import rerun_view

logger = logging.getLogger(__name__)

# Max failed attempts before lockout
MAX_ATTEMPTS = 5
# Lockout window in seconds
LOCKOUT_WINDOW = 120
# Session expiry in seconds (4 hours)
SESSION_EXPIRY = 4 * 60 * 60
# Minimum password length
MIN_PASSWORD_LENGTH = 12


def _is_production() -> bool:
    """Check if app is running in production mode."""
    return os.getenv('ENVIRONMENT', '').strip().lower() in {'production', 'prod'}


def _get_password() -> str:
    """Get dashboard password from environment. Required for security."""
    password = os.getenv('DASHBOARD_PASSWORD')
    if not password:
        return ""
    if len(password) < MIN_PASSWORD_LENGTH:
        logger.warning(
            f"DASHBOARD_PASSWORD is shorter than {MIN_PASSWORD_LENGTH} characters. "
            "Consider using a stronger password."
        )
    return password


def _is_locked_out() -> bool:
    """Check if user is locked out due to too many failed attempts."""
    attempts = st.session_state.get('failed_attempts', [])
    if not attempts:
        return False
    now = time.time()
    recent = [t for t in attempts if now - t < LOCKOUT_WINDOW]
    st.session_state.failed_attempts = recent
    return len(recent) >= MAX_ATTEMPTS


def _lockout_remaining() -> int:
    """Return seconds remaining in lockout period."""
    attempts = st.session_state.get('failed_attempts', [])
    if not attempts:
        return 0
    oldest_relevant = min(t for t in attempts if time.time() - t < LOCKOUT_WINDOW)
    return max(0, int(LOCKOUT_WINDOW - (time.time() - oldest_relevant)))


def _record_failed_attempt():
    """Record a failed login attempt."""
    if 'failed_attempts' not in st.session_state:
        st.session_state.failed_attempts = []
    st.session_state.failed_attempts.append(time.time())
    logger.warning(f"Failed login attempt ({len(st.session_state.failed_attempts)} recent)")


def _is_session_expired() -> bool:
    """Check if the authenticated session has expired."""
    auth_time = st.session_state.get('authenticated_at')
    if not auth_time:
        return True
    return (time.time() - auth_time) > SESSION_EXPIRY


def check_auth() -> bool:
    """Password gate with brute force protection and session expiry.

    Requires DASHBOARD_PASSWORD env var to be set.
    Uses secrets.compare_digest for timing-safe comparison.
    Locks out after MAX_ATTEMPTS failed attempts within LOCKOUT_WINDOW.
    Sessions expire after SESSION_EXPIRY seconds.
    """
    password = _get_password()
    if not password:
        if _is_production():
            # Fail closed in production: never run public dashboard without auth.
            logger.error("DASHBOARD_PASSWORD missing in production; refusing dashboard access")
            st.error("Dashboard authentication is not configured. Set DASHBOARD_PASSWORD.")
            return False

        # Dev-mode fallback only.
        logger.warning("DASHBOARD_PASSWORD not set — auth disabled in non-production mode.")
        return True

    if 'authenticated' not in st.session_state:
        st.session_state.authenticated = False

    # Check session expiry for authenticated users
    if st.session_state.authenticated:
        if _is_session_expired():
            st.session_state.authenticated = False
            logger.info("Session expired, requiring re-authentication")
            st.info("Session expired. Please log in again.")
        else:
            return True

    # Login form
    st.markdown("### HFI Dashboard Login")

    # Check lockout
    if _is_locked_out():
        remaining = _lockout_remaining()
        st.error(f"Too many failed attempts. Try again in {remaining} seconds.")
        return False

    entered = st.text_input("Password", type="password", key="auth_password")
    if st.button("Login"):
        if secrets.compare_digest(entered.encode('utf-8'), password.encode('utf-8')):
            st.session_state.authenticated = True
            st.session_state.authenticated_at = time.time()
            logger.info("Successful login")
            rerun_view()
        else:
            _record_failed_attempt()
            st.error("Incorrect password")
    return False
