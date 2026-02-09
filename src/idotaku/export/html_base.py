"""Base HTML utilities for export."""

from __future__ import annotations

import html as html_module
from typing import Any


def html_escape(text: Any) -> str:
    """Escape text for safe HTML output.

    Args:
        text: Text to escape (will be converted to string)

    Returns:
        HTML-escaped string
    """
    return html_module.escape(str(text))
