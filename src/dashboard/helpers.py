"""
Pure helper functions for the HFI Dashboard.

These functions contain no Streamlit dependencies and can be
imported and tested independently.
"""

import json


# Source name -> CSS class mapping
_SOURCE_BADGE_MAP = {
    'Yahoo Finance': 'source-yahoo-finance',
    'WSJ': 'source-wsj',
    'TechCrunch': 'source-techcrunch',
    'Bloomberg': 'source-bloomberg',
    'MarketWatch': 'source-marketwatch',
    'Manual': 'source-manual',
    'X': 'source-x',
}


def get_source_badge_class(source_name: str) -> str:
    """Return CSS class for a source badge."""
    return _SOURCE_BADGE_MAP.get(source_name, 'source-manual')


def parse_media_info(media_paths_json: str) -> tuple:
    """Parse media_paths JSON and return (count, media_label).

    Args:
        media_paths_json: JSON string of media list, e.g.
            '[{"type": "video", "path": "..."}, {"type": "photo", "path": "..."}]'

    Returns:
        (media_count, media_label) tuple. Label is "Video", "Image", or empty.
    """
    if not media_paths_json:
        return 0, ""
    try:
        media_list = json.loads(media_paths_json)
        count = len(media_list)
        has_video = any(m.get('type') == 'video' for m in media_list)
        has_photo = any(m.get('type') == 'photo' for m in media_list)
        if has_video:
            return count, "Video"
        elif has_photo:
            return count, "Image"
        return count, ""
    except (json.JSONDecodeError, TypeError, AttributeError):
        return 0, ""


def format_status_str(status) -> str:
    """Extract string value from a status enum or string.

    Args:
        status: TweetStatus enum value or plain string.

    Returns:
        Lowercase status string.
    """
    if hasattr(status, 'value'):
        return status.value
    return str(status)
