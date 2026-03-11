"""Shared URL validation helpers for bot/API/dashboard flows."""

from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlparse, urlunparse

X_HOSTS = {
    "x.com",
    "www.x.com",
    "mobile.x.com",
    "twitter.com",
    "www.twitter.com",
    "mobile.twitter.com",
}
SAFE_ARTICLE_CONTENT_TYPES = {"text/html", "application/xhtml+xml"}


class URLValidationError(ValueError):
    """Raised when a URL is unsafe or unsupported."""


def _normalize_url(raw_url: str) -> str:
    value = (raw_url or "").strip()
    if not value:
        raise URLValidationError("URL is required")
    parsed = urlparse(value)
    if parsed.scheme.lower() != "https":
        raise URLValidationError("Only https URLs are allowed")
    if not parsed.netloc:
        raise URLValidationError("URL must include a host")
    if parsed.username or parsed.password:
        raise URLValidationError("URL must not include credentials")

    normalized = parsed._replace(
        scheme="https",
        fragment="",
    )
    return urlunparse(normalized)


def _is_disallowed_ip(ip_text: str) -> bool:
    ip = ipaddress.ip_address(ip_text)
    return any(
        [
            ip.is_private,
            ip.is_loopback,
            ip.is_link_local,
            ip.is_multicast,
            ip.is_unspecified,
            ip.is_reserved,
        ]
    )


def _assert_public_target(hostname: str) -> None:
    host = (hostname or "").strip().lower()
    if not host:
        raise URLValidationError("URL host is missing")
    if host in {"localhost"} or host.endswith(".local"):
        raise URLValidationError("Local hosts are not allowed")

    try:
        if _is_disallowed_ip(host):
            raise URLValidationError("Private or local IP targets are not allowed")
        return
    except ValueError:
        pass

    try:
        addr_info = socket.getaddrinfo(host, None, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise URLValidationError("Cannot resolve URL host") from exc

    if not addr_info:
        raise URLValidationError("Cannot resolve URL host")

    for item in addr_info:
        address = item[4][0]
        if _is_disallowed_ip(address):
            raise URLValidationError("Private or local IP targets are not allowed")


def validate_https_url(raw_url: str) -> str:
    """Validate baseline HTTPS URL constraints."""
    return _normalize_url(raw_url)


def is_x_status_url(raw_url: str) -> bool:
    """Return True when URL points to an X/Twitter status."""
    try:
        normalized = _normalize_url(raw_url)
    except URLValidationError:
        return False

    parsed = urlparse(normalized)
    host = parsed.hostname.lower() if parsed.hostname else ""
    if host not in X_HOSTS:
        return False

    parts = [segment for segment in parsed.path.split("/") if segment]
    for idx, segment in enumerate(parts[:-1]):
        if segment == "status" and parts[idx + 1].isdigit():
            return True
    return False


def is_x_or_twitter_host(raw_url: str) -> bool:
    """Return True when URL host belongs to X/Twitter domains."""
    try:
        normalized = _normalize_url(raw_url)
    except URLValidationError:
        return False
    parsed = urlparse(normalized)
    host = parsed.hostname.lower() if parsed.hostname else ""
    return host in X_HOSTS


def validate_x_status_url(raw_url: str) -> str:
    """Validate X/Twitter status URL."""
    normalized = _normalize_url(raw_url)
    if not is_x_status_url(normalized):
        raise URLValidationError("Invalid X/Twitter status URL")
    return normalized


def validate_article_url(raw_url: str) -> str:
    """Validate safe public article URL targets."""
    normalized = _normalize_url(raw_url)
    parsed = urlparse(normalized)
    _assert_public_target(parsed.hostname or "")
    return normalized


def is_safe_article_content_type(content_type: str) -> bool:
    """Allow only HTML content types for article extraction."""
    lowered = (content_type or "").split(";", maxsplit=1)[0].strip().lower()
    return lowered in SAFE_ARTICLE_CONTENT_TYPES
