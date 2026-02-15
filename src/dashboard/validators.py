"""Input validation utilities for the HFI dashboard."""

from urllib.parse import urlparse

# Allowed domains for X/Twitter URLs
_X_DOMAINS = {'x.com', 'twitter.com', 'www.x.com', 'www.twitter.com', 'mobile.x.com', 'mobile.twitter.com'}

# Dangerous URL schemes
_DANGEROUS_SCHEMES = {'javascript', 'data', 'vbscript', 'file'}

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
        parsed = urlparse(url)
    except Exception:
        return False, "Invalid URL format"

    if parsed.scheme.lower() != 'https':
        return False, "URL must use HTTPS"

    if not parsed.hostname:
        return False, "Invalid URL: no hostname"

    if parsed.hostname.lower() not in _X_DOMAINS:
        return False, f"URL must be from x.com or twitter.com (got {parsed.hostname})"

    path = (parsed.path or "").lower()
    if "/status/" not in path:
        return False, "URL must point to a tweet/thread status URL"

    return True, ""


def validate_safe_url(url: str) -> tuple[bool, str]:
    """Validate that a URL is safe for rendering in markdown links.

    Rejects javascript:, data:, vbscript: schemes.
    Returns (is_valid, error_message).
    """
    if not url or not url.strip():
        return False, "URL is required"

    url = url.strip()

    try:
        parsed = urlparse(url)
    except Exception:
        return False, "Invalid URL format"

    if parsed.scheme.lower() in _DANGEROUS_SCHEMES:
        return False, f"Dangerous URL scheme: {parsed.scheme}"

    if parsed.scheme.lower() != 'https':
        return False, "URL must use HTTPS"

    if not parsed.hostname:
        return False, "Invalid URL: no hostname"

    return True, ""


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
