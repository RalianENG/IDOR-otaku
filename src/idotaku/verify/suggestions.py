"""Parameter modification suggestions for IDOR verification."""

from __future__ import annotations

import uuid as uuid_mod

from .models import SuggestedValue

# Sentinel value for custom user input
CUSTOM_INPUT = "__CUSTOM__"


def suggest_modifications(
    id_value: str,
    id_type: str,
) -> list[SuggestedValue]:
    """Generate suggested parameter modifications based on ID type.

    Args:
        id_value: The original ID value
        id_type: Type of ID (numeric, uuid, token)

    Returns:
        List of suggested modifications
    """
    if id_type == "numeric":
        suggestions = _suggest_numeric(id_value)
    elif id_type == "uuid":
        suggestions = _suggest_uuid()
    elif id_type == "token":
        suggestions = _suggest_token(id_value)
    else:
        suggestions = []

    # Universal suggestions for all types
    suggestions.append(SuggestedValue("", "Empty string"))
    suggestions.append(SuggestedValue(CUSTOM_INPUT, "Enter custom value"))

    return suggestions


def _suggest_numeric(id_value: str) -> list[SuggestedValue]:
    """Suggest modifications for numeric IDs."""
    try:
        num = int(id_value)
    except ValueError:
        return []

    return [
        SuggestedValue(str(num + 1), f"Original + 1 ({num + 1})"),
        SuggestedValue(str(num - 1), f"Original - 1 ({num - 1})"),
        SuggestedValue(str(num + 10), f"Original + 10 ({num + 10})"),
        SuggestedValue("0", "Zero"),
        SuggestedValue("1", "ID = 1 (often admin)"),
        SuggestedValue("-1", "Negative value"),
    ]


def _suggest_uuid() -> list[SuggestedValue]:
    """Suggest modifications for UUID IDs."""
    random_uuid = str(uuid_mod.uuid4())
    return [
        SuggestedValue(random_uuid, f"Random UUID ({random_uuid[:8]}...)"),
        SuggestedValue(
            "00000000-0000-0000-0000-000000000000", "Null UUID"
        ),
    ]


def _suggest_token(id_value: str) -> list[SuggestedValue]:
    """Suggest modifications for token-like IDs."""
    return [
        SuggestedValue("invalid_token", "Invalid token string"),
        SuggestedValue(
            "a" * len(id_value),
            f"Repeated 'a' (same length: {len(id_value)})",
        ),
    ]
