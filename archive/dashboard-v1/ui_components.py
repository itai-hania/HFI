"""Shared UI primitives for dashboard views."""

from __future__ import annotations

import html
from typing import Optional

import streamlit as st

from dashboard.state import consume_flash


def render_page_header(title: str, subtitle: str) -> None:
    st.markdown(
        f"""
        <div class="page-header">
            <h1 class="page-title">{html.escape(title)}</h1>
            <p class="page-subtitle">{html.escape(subtitle)}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_flash_messages(current_view: str) -> None:
    """Render flash messages queued for this view."""
    messages = consume_flash(view=current_view)
    for item in messages:
        level = (item.get("level") or "info").lower()
        message = item.get("message") or ""
        if level == "success":
            st.success(message)
        elif level == "warning":
            st.warning(message)
        elif level == "error":
            st.error(message)
        else:
            st.info(message)


def render_empty_state(title: str, description: str) -> None:
    st.markdown(
        f"""
        <div class="empty-state">
            <div class="empty-state-title">{html.escape(title)}</div>
            <div class="empty-state-text">{html.escape(description)}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_section_header(title: str, description: Optional[str] = None) -> None:
    st.markdown(f"### {title}")
    if description:
        st.caption(description)
