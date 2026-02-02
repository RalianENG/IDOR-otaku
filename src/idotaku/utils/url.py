"""URL utility functions."""

import re
from urllib.parse import urlparse


def normalize_api_path(url: str) -> str:
    """Normalize URL path by replacing ID-like segments with placeholders.

    Examples:
        /users/123/orders/456 -> /users/{id}/orders/{id}
        /items/550e8400-e29b-41d4-a716-446655440000 -> /items/{uuid}
        /tokens/abc123def456xyz789012 -> /tokens/{token}

    Args:
        url: Full URL or path to normalize

    Returns:
        Normalized path with ID placeholders
    """
    path = urlparse(url).path or "/"
    segments = path.split("/")
    normalized = []

    for seg in segments:
        if not seg:
            normalized.append(seg)
        elif re.match(r"^\d+$", seg):  # numeric ID
            normalized.append("{id}")
        elif re.match(
            r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
            seg,
            re.IGNORECASE,
        ):  # UUID
            normalized.append("{uuid}")
        elif re.match(r"^[a-zA-Z0-9_-]{20,}$", seg):  # long token-like string
            normalized.append("{token}")
        else:
            normalized.append(seg)

    return "/".join(normalized)


def extract_domain(url: str) -> str:
    """Extract domain from URL.

    Args:
        url: Full URL

    Returns:
        Domain (netloc) or empty string if extraction fails
    """
    try:
        parsed = urlparse(url)
        return parsed.netloc or ""
    except Exception:
        return ""


def get_base_domain(domain: str) -> str:
    """Get base domain from full domain.

    Examples:
        api.example.com -> example.com
        sub.api.example.com -> example.com
        example.com -> example.com

    Args:
        domain: Full domain name

    Returns:
        Base domain (last two parts)
    """
    parts = domain.split(".")
    if len(parts) >= 2:
        return ".".join(parts[-2:])
    return domain
