"""Shared dashboard session-state contract and helpers."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, List, Optional

import streamlit as st

KEY_CURRENT_VIEW = "current_view"
KEY_CONTENT_TAB = "content_tab"
KEY_CONTENT_SECTION_SELECTOR = "content_section_selector"
KEY_SELECTED_ITEM = "selected_item"
KEY_HOME_PUBLISH_EXPANDED = "home_publish_expanded"
KEY_HOME_TRENDS_EXPANDED = "home_trends_expanded"
KEY_HOME_THREADS_EXPANDED = "home_threads_expanded"
KEY_FLASH_MESSAGES = "flash_messages"

DEFAULT_STATE: Dict[str, Any] = {
    KEY_CURRENT_VIEW: "home",
    KEY_CONTENT_TAB: "Acquire",
    KEY_CONTENT_SECTION_SELECTOR: "Acquire",
    KEY_SELECTED_ITEM: None,
    KEY_HOME_PUBLISH_EXPANDED: True,
    KEY_HOME_TRENDS_EXPANDED: True,
    KEY_HOME_THREADS_EXPANDED: True,
    KEY_FLASH_MESSAGES: [],
}


def init_session_state() -> None:
    """Initialize dashboard session state with canonical defaults."""
    for key, value in DEFAULT_STATE.items():
        if key not in st.session_state:
            st.session_state[key] = deepcopy(value)


def get_current_view() -> str:
    return str(st.session_state.get(KEY_CURRENT_VIEW, "home"))


def set_current_view(view: str) -> None:
    st.session_state[KEY_CURRENT_VIEW] = view


def get_content_tab() -> str:
    return str(st.session_state.get(KEY_CONTENT_TAB, "Acquire"))


def set_content_tab(tab: str) -> None:
    st.session_state[KEY_CONTENT_TAB] = tab


def get_selected_item() -> Optional[int]:
    value = st.session_state.get(KEY_SELECTED_ITEM)
    return int(value) if isinstance(value, int) else None


def set_selected_item(tweet_id: Optional[int]) -> None:
    st.session_state[KEY_SELECTED_ITEM] = tweet_id


def push_flash(level: str, message: str, view: Optional[str] = None) -> None:
    """Add a flash message that survives reruns."""
    messages: List[Dict[str, Optional[str]]] = st.session_state.setdefault(KEY_FLASH_MESSAGES, [])
    messages.append({
        "level": level,
        "message": message,
        "view": view,
    })


def consume_flash(view: Optional[str] = None) -> List[Dict[str, Optional[str]]]:
    """Consume flash messages scoped to a view (or global)."""
    messages: List[Dict[str, Optional[str]]] = st.session_state.get(KEY_FLASH_MESSAGES, [])
    keep: List[Dict[str, Optional[str]]] = []
    take: List[Dict[str, Optional[str]]] = []

    for item in messages:
        item_view = item.get("view")
        if item_view is None or view is None or item_view == view:
            take.append(item)
        else:
            keep.append(item)

    st.session_state[KEY_FLASH_MESSAGES] = keep
    return take


def rerun_view() -> None:
    """Single rerun entrypoint for dashboard view transitions."""
    st.rerun()
