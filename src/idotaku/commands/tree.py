"""Tree command - visualize IDs as tree showing origin → usage flow."""

import click
from rich.console import Console
from rich.tree import Tree
from rich.text import Text

from ..report import load_report

console = Console()


def _format_occurrence(occ: dict, label: str, color: str) -> Text:
    """Format an ID occurrence for tree display."""
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


@click.command()
@click.argument("report_file", default="id_tracker_report.json", type=click.Path(exists=True))
@click.option("--idor-only", is_flag=True, help="Show only potential IDOR targets")
@click.option("--type", "id_type", type=click.Choice(["all", "numeric", "uuid", "token"]), default="all", help="Filter by ID type")
def tree(report_file, idor_only, id_type):
    """Visualize IDs as a tree showing origin → usage flow."""
    data = load_report(report_file)

    tracked_ids = data.tracked_ids
    potential_idor_values = data.idor_values

    if not tracked_ids:
        console.print("[yellow]No IDs found in report.[/yellow]")
        return

    console.print()
    console.print("[bold blue]ID Flow Visualization[/bold blue]")
    console.print()

    # Filter IDs
    filtered_ids = {}
    for id_value, info in tracked_ids.items():
        if idor_only and id_value not in potential_idor_values:
            continue
        if id_type != "all" and info.get("type") != id_type:
            continue
        filtered_ids[id_value] = info

    if not filtered_ids:
        console.print("[yellow]No IDs match the filter criteria.[/yellow]")
        return

    # Sort by first_seen timestamp
    sorted_ids = sorted(filtered_ids.items(), key=lambda x: x[1].get("first_seen", ""))

    for id_value, info in sorted_ids:
        is_idor = id_value in potential_idor_values

        # Create tree root with ID info
        id_type_str = info.get("type", "unknown")
        style = "bold red" if is_idor else "bold cyan"
        idor_marker = " [red]⚠ IDOR[/red]" if is_idor else ""

        tree_root = Tree(
            f"[{style}]{id_value}[/{style}] [dim]({id_type_str})[/dim]{idor_marker}"
        )

        origin = info.get("origin")
        usages = info.get("usages", [])

        # Add origin (response where ID first appeared)
        if origin:
            origin_text = _format_occurrence(origin, "ORIGIN", "green")
            tree_root.add(origin_text)
        else:
            tree_root.add("[dim italic]No origin (not seen in response)[/dim italic]")

        # Add usages (requests where ID was used)
        if usages:
            for i, usage in enumerate(usages):
                usage_text = _format_occurrence(usage, "USAGE", "yellow")
                tree_root.add(usage_text)
        else:
            tree_root.add("[dim italic]No usage (not seen in request)[/dim italic]")

        console.print(tree_root)
        console.print()

    # Summary
    console.print(f"[dim]Total: {len(filtered_ids)} IDs shown[/dim]")
    if potential_idor_values:
        console.print(f"[red]⚠ {len(potential_idor_values)} potential IDOR targets[/red]")
