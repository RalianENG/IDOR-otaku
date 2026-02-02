"""Base HTML utilities for export."""

import html as html_module


def html_escape(text) -> str:
    """Escape text for safe HTML output.

    Args:
        text: Text to escape (will be converted to string)

    Returns:
        HTML-escaped string
    """
    return html_module.escape(str(text))
