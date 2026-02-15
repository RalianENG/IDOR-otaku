"""Data models for IDOR verification."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class RequestData:
    """Full HTTP request data for verification."""

    method: str
    url: str
    headers: dict[str, str] = field(default_factory=dict)
    body: Optional[str] = None


@dataclass
class ResponseData:
    """HTTP response data for comparison."""

    status_code: int
    headers: dict[str, str] = field(default_factory=dict)
    body: str = ""
    content_length: int = 0
    elapsed_ms: float = 0.0


@dataclass
class SuggestedValue:
    """A suggested parameter modification."""

    value: str
    description: str


@dataclass
class Modification:
    """Describes the modification made to the original request."""

    original_value: str
    modified_value: str
    location: str  # url_path, query, body, header
    field_name: Optional[str]
    description: str


@dataclass
class ComparisonResult:
    """Comparison between original and modified responses."""

    status_match: bool
    status_original: Optional[int]
    status_modified: int
    content_length_diff: Optional[int]
    verdict: str  # VULNERABLE, LIKELY_VULNERABLE, INCONCLUSIVE, NOT_VULNERABLE
    details: list[str] = field(default_factory=list)


@dataclass
class VerifyResult:
    """Result of a single verification attempt."""

    finding_id_value: str
    finding_id_type: str
    original_request: RequestData
    modified_request: RequestData
    modification: Modification
    response: ResponseData
    original_response: Optional[ResponseData]
    comparison: ComparisonResult
    timestamp: str
