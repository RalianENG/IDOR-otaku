"""Rich console formatting utilities for idotaku."""

from urllib.parse import urlparse
from rich.text import Text


def format_occurrence(occ: dict, label: str, color: str) -> Text:
    """Format an ID occurrence for Rich tree display.

    Args:
        occ: Occurrence dict with method, url, location, field_name/field, timestamp
        label: Label to show (e.g., "ORIGIN", "USAGE")
        color: Rich color for the label

    Returns:
        Rich Text object with formatted occurrence
    """
    method = occ.get("method", "?")
    url = occ.get("url", "?")
    location = occ.get("location", "?")
    field = occ.get("field_name") or occ.get("field")
    timestamp = occ.get("timestamp", "")

    # Shorten URL for display
    if len(url) > 60:
        url = url[:57] + "..."

    # Format location info
    if field:
        loc_info = f"{location}.{field}"
    else:
        loc_info = location

    # Extract time part from ISO timestamp
    time_part = ""
    if timestamp and "T" in timestamp:
        time_part = timestamp.split("T")[1][:8]

    text = Text()
    text.append(f"[{label}] ", style=color)
    text.append(f"{method} ", style="bold")
    text.append(f"{url} ", style="dim")
    text.append(f"→ {loc_info}", style="italic")
    if time_part:
        text.append(f" ({time_part})", style="dim")

    return text


def format_api(flow: dict, max_path_length: int = 45) -> str:
    """Format API endpoint for Rich display.

    Args:
        flow: Flow dict with method and url
        max_path_length: Maximum path length before truncation

    Returns:
        Rich markup string for the API
    """
    method = flow.get("method", "?")
    url = flow.get("url", "?")
    path = urlparse(url).path or "/"

    if len(path) > max_path_length:
        path = path[: max_path_length - 3] + "..."

    # Escape [ in path to prevent Rich markup parsing
    path = path.replace("[", "\\[")

    return f"[bold magenta]{method}[/bold magenta] [white]{path}[/white]"


def escape_rich(text: str) -> str:
    """Escape Rich markup characters in text.

    Args:
        text: Text to escape

    Returns:
        Escaped text safe for Rich display
    """
    return str(text).replace("[", "\\[")


def format_param(params, max_length: int = 20) -> str:
    """Format parameter(s) for Rich display.

    Args:
        params: Single param string or list of params
        max_length: Maximum length for single param display

    Returns:
        Rich markup string for the parameter(s)
    """
    if isinstance(params, list):
        if len(params) == 0:
            return "[dim]none[/dim]"
        if len(params) == 1:
            param = params[0]
        else:
            # Multiple params - show count and first few
            short_list = [
                escape_rich(p[:12] + ".." if len(p) > 12 else p) for p in params[:3]
            ]
            suffix = f"+{len(params) - 3}" if len(params) > 3 else ""
            return f"[cyan]{', '.join(short_list)}{suffix}[/cyan]"
    else:
        param = params

    short = param[:max_length] + ".." if len(param) > max_length else param
    return f"[cyan]{escape_rich(short)}[/cyan]"


def format_id_value(id_value: str, max_length: int = 16) -> str:
    """Format ID value for display with truncation.

    Args:
        id_value: The ID value to format
        max_length: Maximum length before truncation

    Returns:
        Truncated ID value with '...' if needed
    """
    if len(id_value) <= max_length:
        return id_value
    return id_value[:max_length] + "..."


def format_id_with_type(
    id_value: str,
    id_type: str,
    is_idor: bool = False,
    max_length: int = 16,
) -> str:
    """Format ID with type annotation and IDOR marking.

    Args:
        id_value: The ID value
        id_type: Type of ID (numeric, uuid, token)
        is_idor: Whether this is a potential IDOR target
        max_length: Maximum length for ID value

    Returns:
        Rich markup string for the ID
    """
    display_val = format_id_value(id_value, max_length)
    style = "bold red" if is_idor else "bold cyan"
    idor_marker = " [red]⚠ IDOR[/red]" if is_idor else ""

    return f"[{style}]{display_val}[/{style}] [dim]({id_type})[/dim]{idor_marker}"
