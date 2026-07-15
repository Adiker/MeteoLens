"""Outbound URL validation for server-side fetches.

Product rendering downloads GRIB files from URLs supplied by cached IMGW
manifests. Those URLs must be validated immediately before every network
request; a previously cached manifest or binary must not bypass the checks.
"""

from __future__ import annotations

import ipaddress
import re
import socket
from urllib.parse import urlsplit, urlunsplit

# IMGW product detail manifests expose short download paths under /pl/d/ and,
# for some products, the longer datastore route documented in PRODUCT_RESEARCH.
_PRODUCT_DOWNLOAD_PATHS = (
    re.compile(r"^/pl/d/[A-Za-z0-9._-]+$"),
    re.compile(r"^/pl/datastore/getfiledown/.+"),
)


class OutboundUrlError(ValueError):
    """Raised when an outbound URL fails SSRF or allowlist validation."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def validate_product_download_url(url: str, *, allowed_base_url: str) -> None:
    """Require HTTPS, an approved IMGW host/path, and a public DNS resolution."""
    parsed_allowed = urlsplit(allowed_base_url.rstrip("/"))
    if parsed_allowed.scheme != "https" or not parsed_allowed.hostname:
        raise OutboundUrlError(
            "url_not_allowed",
            "Configured IMGW base URL must use HTTPS with a hostname.",
        )

    parsed = urlsplit(url)
    if parsed.scheme != "https":
        raise OutboundUrlError(
            "url_not_allowed",
            "Product download URLs must use HTTPS.",
        )
    if parsed.username or parsed.password:
        raise OutboundUrlError(
            "url_not_allowed",
            "Product download URLs must not include credentials.",
        )
    if parsed.fragment:
        raise OutboundUrlError(
            "url_not_allowed",
            "Product download URLs must not include a fragment.",
        )
    if parsed.query:
        raise OutboundUrlError(
            "url_not_allowed",
            "Product download URLs must not include query parameters.",
        )
    if not parsed.hostname:
        raise OutboundUrlError(
            "url_not_allowed",
            "Product download URL is missing a hostname.",
        )
    try:
        port = parsed.port
    except ValueError as exc:
        raise OutboundUrlError(
            "url_not_allowed",
            "Product download URL has an invalid host.",
        ) from exc
    if port not in (None, 443):
        raise OutboundUrlError(
            "url_not_allowed",
            "Product download URLs must use the default HTTPS port.",
        )

    allowed_host = parsed_allowed.hostname.lower()
    hostname = parsed.hostname.lower()
    if hostname != allowed_host:
        raise OutboundUrlError(
            "url_not_allowed",
            f"Product download host {hostname!r} is not the approved IMGW host.",
        )

    path = parsed.path or ""
    if ".." in path.split("/"):
        raise OutboundUrlError(
            "url_not_allowed",
            "Product download paths must not contain parent-directory segments.",
        )
    if not any(pattern.fullmatch(path) for pattern in _PRODUCT_DOWNLOAD_PATHS):
        raise OutboundUrlError(
            "url_not_allowed",
            "Product download path is not an approved IMGW route.",
        )

    _validate_resolved_addresses(hostname)


def _validate_resolved_addresses(hostname: str) -> None:
    literal = _parse_ip(hostname)
    if literal is not None:
        _reject_disallowed_ip(literal, hostname=hostname)
        return

    try:
        results = socket.getaddrinfo(
            hostname,
            443,
            type=socket.SOCK_STREAM,
            proto=socket.IPPROTO_TCP,
        )
    except socket.gaierror as exc:
        raise OutboundUrlError(
            "url_not_allowed",
            f"Product download host {hostname!r} could not be resolved.",
        ) from exc

    if not results:
        raise OutboundUrlError(
            "url_not_allowed",
            f"Product download host {hostname!r} did not resolve to any address.",
        )

    seen: set[str] = set()
    for _, _, _, _, sockaddr in results:
        address = sockaddr[0]
        if address in seen:
            continue
        seen.add(address)
        ip = _parse_ip(address)
        if ip is None:
            raise OutboundUrlError(
                "url_not_allowed",
                f"Product download host {hostname!r} resolved to an unsupported address.",
            )
        _reject_disallowed_ip(ip, hostname=hostname)


def _parse_ip(value: str) -> ipaddress.IPv4Address | ipaddress.IPv6Address | None:
    try:
        return ipaddress.ip_address(value)
    except ValueError:
        return None


def _reject_disallowed_ip(
    address: ipaddress.IPv4Address | ipaddress.IPv6Address,
    *,
    hostname: str,
) -> None:
    if (
        address.is_private
        or address.is_loopback
        or address.is_link_local
        or address.is_multicast
        or address.is_reserved
        or address.is_unspecified
    ):
        raise OutboundUrlError(
            "url_not_allowed",
            f"Product download host {hostname!r} resolves to a disallowed address "
            f"({address}).",
        )


def normalized_product_download_url(url: str, *, allowed_base_url: str) -> str:
    """Validate and return a canonical HTTPS URL without fragments or queries."""
    validate_product_download_url(url, allowed_base_url=allowed_base_url)
    parsed = urlsplit(url)
    return urlunsplit(("https", parsed.hostname.lower(), parsed.path, "", ""))
