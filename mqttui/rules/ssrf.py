"""SSRF URL validation for webhook destinations.

Blocks webhook URLs that resolve to private, loopback, or link-local addresses
to prevent Server-Side Request Forgery attacks.
"""

import ipaddress
import logging
import socket
from urllib.parse import urlparse

logger = logging.getLogger(__name__)


def is_ssrf_safe(url: str) -> tuple:
    """Check if a URL is safe from SSRF by resolving and validating the IP.

    Args:
        url: The webhook destination URL to validate.

    Returns:
        Tuple of (safe: bool, reason: str). If safe is False, reason explains why.
    """
    try:
        parsed = urlparse(url)
    except Exception:
        return False, "Invalid URL"

    hostname = parsed.hostname
    if not hostname:
        return False, "No hostname in URL"

    # Try to parse hostname directly as IP address first
    try:
        addr = ipaddress.ip_address(hostname)
        return _check_ip(addr)
    except ValueError:
        pass

    # Resolve hostname via DNS
    try:
        results = socket.getaddrinfo(hostname, parsed.port or 80, proto=socket.IPPROTO_TCP)
    except socket.gaierror as e:
        return False, f"DNS resolution failed: {e}"

    if not results:
        return False, "DNS resolution returned no results"

    # Check ALL resolved addresses -- block if any are private
    for family, _, _, _, sockaddr in results:
        ip_str = sockaddr[0]
        try:
            addr = ipaddress.ip_address(ip_str)
            safe, reason = _check_ip(addr)
            if not safe:
                return False, reason
        except ValueError:
            continue

    return True, "URL is safe"


def _check_ip(addr) -> tuple:
    """Check a single IP address against blocked ranges.

    Returns:
        Tuple of (safe: bool, reason: str).
    """
    if addr.is_private:
        return False, f"Blocked: {addr} is a private address"
    if addr.is_loopback:
        return False, f"Blocked: {addr} is a loopback address"
    if addr.is_link_local:
        return False, f"Blocked: {addr} is a link-local address"
    if addr.is_reserved:
        return False, f"Blocked: {addr} is a reserved address"
    if addr.is_multicast:
        return False, f"Blocked: {addr} is a multicast address"
    if addr.is_unspecified:
        return False, f"Blocked: {addr} is an unspecified address"

    return True, "Address is safe"
