"""Response comparison logic for verification results."""

from __future__ import annotations

from typing import Optional

from .models import ComparisonResult, ResponseData


def compare_responses(
    modified: ResponseData,
    original: Optional[ResponseData] = None,
) -> ComparisonResult:
    """Compare the modified response against the original.

    When original is None (no original data available), verdict is based
    on the modified response alone.
    """
    details: list[str] = []

    if original is not None:
        return _compare_with_original(modified, original, details)
    else:
        return _analyze_standalone(modified, details)


def _compare_with_original(
    modified: ResponseData,
    original: ResponseData,
    details: list[str],
) -> ComparisonResult:
    """Compare when we have both original and modified responses."""
    status_match = modified.status_code == original.status_code
    content_length_diff = modified.content_length - original.content_length

    details.append(
        f"Status: {original.status_code} -> {modified.status_code}"
    )
    details.append(
        f"Content-Length: {original.content_length} -> {modified.content_length} "
        f"(diff: {content_length_diff:+d})"
    )

    if modified.status_code == original.status_code:
        if abs(content_length_diff) < 50:
            verdict = "VULNERABLE"
            details.append(
                "Same status AND similar content length "
                "-- likely accessing another user's data"
            )
        else:
            verdict = "LIKELY_VULNERABLE"
            details.append(
                "Same status but different content length "
                "-- may be different user's data"
            )
    elif modified.status_code in (401, 403):
        verdict = "NOT_VULNERABLE"
        details.append("Access denied -- authorization check is in place")
    elif modified.status_code == 404:
        verdict = "INCONCLUSIVE"
        details.append("Resource not found -- ID may not exist")
    else:
        verdict = "INCONCLUSIVE"
        details.append(
            f"Different status code "
            f"({original.status_code} vs {modified.status_code})"
        )

    return ComparisonResult(
        status_match=status_match,
        status_original=original.status_code,
        status_modified=modified.status_code,
        content_length_diff=content_length_diff,
        verdict=verdict,
        details=details,
    )


def _analyze_standalone(
    modified: ResponseData,
    details: list[str],
) -> ComparisonResult:
    """Analyze when we only have the modified response."""
    details.append(f"Status: {modified.status_code}")
    details.append(f"Content-Length: {modified.content_length}")

    if modified.status_code == 200:
        verdict = "LIKELY_VULNERABLE"
        details.append(
            "200 OK with modified ID -- may indicate IDOR (compare manually)"
        )
    elif modified.status_code in (401, 403):
        verdict = "NOT_VULNERABLE"
        details.append(
            "Access denied -- authorization check appears to be in place"
        )
    elif modified.status_code == 404:
        verdict = "INCONCLUSIVE"
        details.append(
            "Resource not found -- ID may not exist, or access is controlled"
        )
    elif modified.status_code >= 500:
        verdict = "INCONCLUSIVE"
        details.append(
            "Server error -- application may have crashed on unexpected input"
        )
    else:
        verdict = "INCONCLUSIVE"
        details.append(
            f"Unexpected status {modified.status_code} -- manual review needed"
        )

    return ComparisonResult(
        status_match=False,
        status_original=None,
        status_modified=modified.status_code,
        content_length_diff=None,
        verdict=verdict,
        details=details,
    )
