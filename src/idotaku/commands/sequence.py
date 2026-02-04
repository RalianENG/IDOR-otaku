"""Sequence command - show API call sequence with parameter flow (horizontal timeline)."""

from urllib.parse import urlparse

import click
from rich.console import Console
from rich.panel import Panel

from ..report import load_report
from ..export import export_sequence_html

console = Console()


@click.command()
@click.argument("report_file", default="id_tracker_report.json", type=click.Path(exists=True))
@click.option("--limit", "-n", default=30, help="Max number of API calls to show")
@click.option("--html", "-o", "html_output", default=None, help="Export to interactive HTML file")
def sequence(report_file, limit, html_output):
    """Show API call sequence with parameter flow (horizontal timeline).

    Visualizes the time-ordered sequence of API calls and shows which
    parameters are passed between them.
    """
    data = load_report(report_file)

    if not data.flows:
        console.print("[yellow]No flows found in report.[/yellow]")
        return

    sorted_flows = data.sorted_flows[:limit]

    console.print()
    console.print("[bold blue]API Sequence Timeline[/bold blue]")
    console.print("[dim]Shows API calls in order with parameters flowing between them[/dim]")
    console.print()

    # Build param tracking: which params are active at each point
    # param_value -> {first_seen_idx, last_seen_idx, locations: [(idx, direction, location)]}
    param_tracker = {}

    for i, flow in enumerate(sorted_flows):
        # Response params (created here)
        for res_id in flow.get("response_ids", []):
            val = res_id.get("value", "")
            if not val:
                continue
            if val not in param_tracker:
                param_tracker[val] = {
                    "first_seen": i,
                    "last_seen": i,
                    "type": res_id.get("type", "?"),
                    "events": [],
                }
            param_tracker[val]["events"].append((i, "RES", res_id.get("field") or res_id.get("location", "?")))
            param_tracker[val]["last_seen"] = i

        # Request params (used here)
        for req_id in flow.get("request_ids", []):
            val = req_id.get("value", "")
            if not val:
                continue
            if val not in param_tracker:
                param_tracker[val] = {
                    "first_seen": i,
                    "last_seen": i,
                    "type": req_id.get("type", "?"),
                    "events": [],
                }
            param_tracker[val]["events"].append((i, "REQ", req_id.get("field") or req_id.get("location", "?")))
            param_tracker[val]["last_seen"] = i

    # Display each API call as a column
    for i, flow in enumerate(sorted_flows):
        method = flow.get("method", "?")
        url = flow.get("url", "?")
        timestamp = flow.get("timestamp", "")
        time_part = timestamp.split("T")[1][:8] if "T" in timestamp else ""

        # Shorten URL to path only
        parsed = urlparse(url)
        path = parsed.path or "/"
        if len(path) > 40:
            path = path[:37] + "..."

        # Build content
        lines = []
        lines.append(f"[bold magenta]{method}[/bold magenta] [dim]{time_part}[/dim]")
        lines.append(f"[white]{path}[/white]")
        lines.append("")

        # Request params (inputs)
        req_ids = flow.get("request_ids", [])
        if req_ids:
            lines.append("[yellow]▼ IN[/yellow]")
            for rid in req_ids[:5]:
                val = rid.get("value", "?")
                short_val = val[:12] + ".." if len(val) > 12 else val
                field = rid.get("field") or rid.get("location", "?")
                lines.append(f"  [cyan]{short_val}[/cyan]")
                lines.append(f"  [dim]@ {field}[/dim]")
            if len(req_ids) > 5:
                lines.append(f"  [dim]+{len(req_ids)-5} more[/dim]")

        # Response params (outputs)
        res_ids = flow.get("response_ids", [])
        if res_ids:
            if req_ids:
                lines.append("")
            lines.append("[green]▲ OUT[/green]")
            for rid in res_ids[:5]:
                val = rid.get("value", "?")
                short_val = val[:12] + ".." if len(val) > 12 else val
                field = rid.get("field") or rid.get("location", "?")
                # Check if this param is used later
                tracker = param_tracker.get(val, {})
                used_later = tracker.get("last_seen", i) > i
                arrow = " [yellow]→[/yellow]" if used_later else ""
                lines.append(f"  [cyan]{short_val}[/cyan]{arrow}")
                lines.append(f"  [dim]@ {field}[/dim]")
            if len(res_ids) > 5:
                lines.append(f"  [dim]+{len(res_ids)-5} more[/dim]")

        content = "\n".join(lines)
        panel = Panel(content, title=f"[bold]#{i+1}[/bold]", width=35, border_style="blue")
        console.print(panel)

        # Show arrow to next if there are shared params
        if i < len(sorted_flows) - 1:
            next_flow = sorted_flows[i + 1]
            next_req_ids = {r.get("value", "") for r in next_flow.get("request_ids", [])}
            current_res_ids = {r.get("value", "") for r in res_ids}
            shared = current_res_ids & next_req_ids
            if shared:
                shared_display = ", ".join(list(shared)[:3])
                if len(shared_display) > 30:
                    shared_display = shared_display[:27] + "..."
                console.print("        [yellow]│[/yellow]")
                console.print(f"        [yellow]▼[/yellow] [dim]{shared_display}[/dim]")
                console.print("        [yellow]│[/yellow]")
            else:
                console.print()

    console.print()
    console.print(f"[dim]Showing {len(sorted_flows)} of {len(data.flows)} API calls[/dim]")

    # HTML export
    if html_output:
        export_sequence_html(
            html_output,
            sorted_flows,
            data.tracked_ids,
            data.potential_idor,
        )
        console.print(f"\n[green]HTML exported to:[/green] {html_output}")
