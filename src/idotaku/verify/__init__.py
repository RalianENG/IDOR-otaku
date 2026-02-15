"""IDOR verification module."""

from .models import (
    ComparisonResult,
    Modification,
    RequestData,
    ResponseData,
    SuggestedValue,
    VerifyResult,
)
from .suggestions import suggest_modifications
from .http_client import VerifyHttpClient
from .comparison import compare_responses

__all__ = [
    "ComparisonResult",
    "Modification",
    "RequestData",
    "ResponseData",
    "SuggestedValue",
    "VerifyResult",
    "suggest_modifications",
    "VerifyHttpClient",
    "compare_responses",
]
