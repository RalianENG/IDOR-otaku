"""Text formatting utility functions."""


def truncate_text(text: str, max_length: int = 60, suffix: str = "...") -> str:
    """Truncate text to specified length with suffix.

    Args:
        text: Text to truncate
        max_length: Maximum length including suffix
        suffix: Suffix to append if truncated

    Returns:
        Truncated text with suffix, or original if short enough
    """
    if len(text) <= max_length:
        return text
    return text[: max_length - len(suffix)] + suffix


def truncate_id(id_value: str, max_length: int = 16) -> str:
    """Truncate ID value for display.

    Args:
        id_value: ID value to truncate
        max_length: Maximum length before truncation

    Returns:
        Truncated ID with '...' or original if short enough
    """
    if len(id_value) <= max_length:
        return id_value
    return id_value[:max_length] + "..."
