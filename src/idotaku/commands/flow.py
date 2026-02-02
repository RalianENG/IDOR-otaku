"""Flow command - show ID flow as a timeline (horizontal view)."""

import click
from rich.console import Console

from ..report import load_report

console = Console()


@click.command()
@click.argument("report_file", default="id_tracker_report.json", type=click.Path(exists=True))
def flow(report_file):
    """Show ID flow as a timeline (horizontal view)."""
    data = load_report(report_file)

    tracked_ids = data.tracked_ids
    potential_idor_values = data.idor_values

    if not tracked_ids:
        console.print("[yellow]No IDs found in report.[/yellow]")
        return

    console.print()
    console.print("[bold blue]ID Flow Timeline[/bold blue]")
    console.print()

    # Sort by first_seen
    sorted_ids = sorted(tracked_ids.items(), key=lambda x: x[1].get("first_seen", ""))

    for id_value, info in sorted_ids:
        is_idor = id_value in potential_idor_values

        # Build flow chain
        chain = []

        origin = info.get("origin")
        if origin:
            method = origin.get("method", "?")
            loc = origin.get("location", "?")
            chain.append(f"[green]◉ {method} (res.{loc})[/green]")

        usages = info.get("usages", [])
        for usage in usages:
            method = usage.get("method", "?")
            loc = usage.get("location", "?")
            chain.append(f"[yellow]→ {method} (req.{loc})[/yellow]")

        # ID info
        id_type_str = info.get("type", "?")
        style = "red" if is_idor else "cyan"
        idor_marker = " ⚠" if is_idor else ""

        # Print flow line
        id_display = f"[{style}]{id_value[:20]}{'...' if len(id_value) > 20 else ''}[/{style}]"
        flow_display = " ".join(chain) if chain else "[dim]No activity[/dim]"

        console.print(f"{id_display} [{id_type_str}]{idor_marker}")
        console.print(f"  {flow_display}")
        console.print()
