"""Input validation utilities for the HFI dashboard."""

from urllib.parse import urlparse

from common.url_validation import URLValidationError, validate_https_url, validate_x_status_url

# Allowed domains for yt-dlp media downloads
_MEDIA_DOMAINS = {'twimg.com', 'video.twimg.com', 'pbs.twimg.com', 'twitter.com', 'x.com', 'abs.twimg.com'}


def validate_x_url(url: str) -> tuple[bool, str]:
    """Validate that a URL is a valid X/Twitter URL.

    Returns (is_valid, error_message).
    """
    if not url or not url.strip():
        return False, "URL is required"

    url = url.strip()

    if len(url) > 500:
        return False, "URL is too long (max 500 characters)"

    try:
        validate_x_status_url(url)
        return True, ""
    except URLValidationError as exc:
        return False, str(exc)


def validate_safe_url(url: str) -> tuple[bool, str]:
    """Validate that a URL is safe for rendering in markdown links.

    Rejects javascript:, data:, vbscript: schemes.
    Returns (is_valid, error_message).
    """
    if not url or not url.strip():
        return False, "URL is required"

    url = url.strip()

    try:
        validate_https_url(url)
        return True, ""
    except URLValidationError as exc:
        return False, str(exc)


def validate_media_domain(url: str) -> tuple[bool, str]:
    """Validate that a URL domain is allowed for media downloads (yt-dlp).

    Returns (is_valid, error_message).
    """
    if not url or not url.strip():
        return False, "URL is required"

    try:
        parsed = urlparse(url)
    except Exception:
        return False, "Invalid URL format"

    if parsed.scheme.lower() != 'https':
        return False, "Media URL must use HTTPS"

    if not parsed.hostname:
        return False, "Invalid URL: no hostname"

    hostname = parsed.hostname.lower()

    # Check if hostname matches or is a subdomain of allowed domains
    for domain in _MEDIA_DOMAINS:
        if hostname == domain or hostname.endswith('.' + domain):
            return True, ""

    return False, f"Domain not allowed for media download: {hostname}"
