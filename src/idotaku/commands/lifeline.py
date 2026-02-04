"""Lifeline command - show parameter lifeline (lifespan and usage across API calls)."""

from urllib.parse import urlparse

import click
from rich.console import Console

from ..report import load_report

console = Console()


@click.command()
@click.argument("report_file", default="id_tracker_report.json", type=click.Path(exists=True))
@click.option("--min-uses", "-m", default=1, help="Minimum usage count to show")
@click.option("--sort", "-s", type=click.Choice(["lifespan", "uses", "first"]), default="lifespan",
              help="Sort by: lifespan (longest first), uses (most used), first (first seen)")
def lifeline(report_file, min_uses, sort):
    """Show parameter lifeline (lifespan and usage across API calls).

    Visualizes how long each parameter lives and how it's used over time.
    Long-lived params = important business entities (user_id, session).
    Short-lived params = temporary/transient (csrf_token, temp_id).
    """
    data = load_report(report_file)

    if not data.flows:
        console.print("[yellow]No flows found in report.[/yellow]")
        return

    sorted_flows = data.sorted_flows
    total_flows = len(sorted_flows)

    # Build param lifecycle: param_value -> {first_idx, last_idx, events}
    param_lifecycle = {}

    for i, flow in enumerate(sorted_flows):
        method = flow.get("method", "?")
        url = flow.get("url", "?")
        path = urlparse(url).path or "/"

        for res_id in flow.get("response_ids", []):
            val = res_id.get("value", "")
            if not val:
                continue
            if val not in param_lifecycle:
                param_lifecycle[val] = {
                    "first_idx": i,
                    "last_idx": i,
                    "type": res_id.get("type", "?"),
                    "events": [],
                    "use_count": 0,
                }
            param_lifecycle[val]["events"].append({
                "idx": i,
                "dir": "RES",
                "method": method,
                "path": path,
                "field": res_id.get("field") or res_id.get("location"),
            })
            param_lifecycle[val]["last_idx"] = i

        for req_id in flow.get("request_ids", []):
            val = req_id.get("value", "")
            if not val:
                continue
            if val not in param_lifecycle:
                param_lifecycle[val] = {
                    "first_idx": i,
                    "last_idx": i,
                    "type": req_id.get("type", "?"),
                    "events": [],
                    "use_count": 0,
                }
            param_lifecycle[val]["events"].append({
                "idx": i,
                "dir": "REQ",
                "method": method,
                "path": path,
                "field": req_id.get("field") or req_id.get("location"),
            })
            param_lifecycle[val]["last_idx"] = i
            param_lifecycle[val]["use_count"] += 1

    # Filter by min_uses
    filtered = {k: v for k, v in param_lifecycle.items() if v["use_count"] >= min_uses}

    # Sort
    if sort == "lifespan":
        sorted_params = sorted(filtered.items(), key=lambda x: x[1]["last_idx"] - x[1]["first_idx"], reverse=True)
    elif sort == "uses":
        sorted_params = sorted(filtered.items(), key=lambda x: x[1]["use_count"], reverse=True)
    else:  # first
        sorted_params = sorted(filtered.items(), key=lambda x: x[1]["first_idx"])

    console.print()
    console.print("[bold blue]Parameter Lifeline[/bold blue]")
    console.print("[dim]Shows parameter lifespan across API calls. Long-lived = important entities.[/dim]")
    console.print()

    for param_val, info in sorted_params[:50]:
        first = info["first_idx"]
        last = info["last_idx"]
        lifespan = last - first + 1
        use_count = info["use_count"]
        param_type = info["type"]

        # Display param header
        short_val = param_val[:20] + "..." if len(param_val) > 20 else param_val
        lifespan_pct = (lifespan / total_flows) * 100 if total_flows > 0 else 0

        # Color based on lifespan
        if lifespan_pct > 50:
            color = "green"  # Long-lived = important
        elif lifespan_pct > 20:
            color = "yellow"
        else:
            color = "dim"  # Short-lived

        console.print(f"[{color}]{short_val}[/{color}] [dim]({param_type})[/dim]")

        # Build timeline bar
        bar_width = min(60, total_flows)
        scale = bar_width / total_flows if total_flows > 0 else 1

        bar = []
        for i in range(bar_width):
            orig_idx = int(i / scale) if scale > 0 else i
            if orig_idx < first:
                bar.append(" ")
            elif orig_idx > last:
                bar.append(" ")
            else:
                # Check if there's an event at this index
                events_at = [e for e in info["events"] if int(e["idx"] * scale) == i]
                if events_at:
                    has_res = any(e["dir"] == "RES" for e in events_at)
                    has_req = any(e["dir"] == "REQ" for e in events_at)
                    if has_res and has_req:
                        bar.append("[magenta]●[/magenta]")
                    elif has_res:
                        bar.append("[green]○[/green]")
                    else:
                        bar.append("[yellow]●[/yellow]")
                else:
                    bar.append("[dim]─[/dim]")

        timeline = "".join(bar)
        console.print(f"  {timeline}")
        console.print(f"  [dim]Lifespan: {lifespan} APIs ({lifespan_pct:.0f}%) | Used in REQ: {use_count}x[/dim]")

        # Show first and last API
        first_event = info["events"][0]
        last_event = info["events"][-1]
        console.print(f"  [dim]First: {first_event['method']} {first_event['path'][:30]}[/dim]")
        if first != last:
            console.print(f"  [dim]Last:  {last_event['method']} {last_event['path'][:30]}[/dim]")
        console.print()

    console.print(f"[dim]Showing {min(50, len(sorted_params))} of {len(filtered)} params (min {min_uses} uses)[/dim]")
    console.print("[dim]Legend: [green]○[/green]=created(RES) [yellow]●[/yellow]=used(REQ) [magenta]●[/magenta]=both[/dim]")
