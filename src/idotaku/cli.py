"""idotaku CLI entry point."""

import os
import sys
import shutil
import signal
import subprocess
import tempfile
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table
from rich.tree import Tree
from rich.panel import Panel
from rich.text import Text

console = Console()


def get_tracker_script_path() -> Path:
    """Get path to tracker.py for mitmproxy addon."""
    return Path(__file__).parent / "tracker.py"


def find_browser() -> tuple[str, str] | None:
    """Find available browser."""
    browsers = [
        ("chrome", [
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
            "google-chrome",
            "chromium",
        ]),
        ("edge", [
            r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
            r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        ]),
        ("firefox", [
            r"C:\Program Files\Mozilla Firefox\firefox.exe",
            r"C:\Program Files (x86)\Mozilla Firefox\firefox.exe",
            "/Applications/Firefox.app/Contents/MacOS/firefox",
            "firefox",
        ]),
    ]

    for browser_name, paths in browsers:
        for path in paths:
            if os.path.isfile(path):
                return browser_name, path
            if shutil.which(path):
                return browser_name, shutil.which(path)

    return None


def find_mitmweb() -> str | None:
    """Find mitmweb executable."""
    # Check if mitmweb is in PATH
    mitmweb = shutil.which("mitmweb")
    if mitmweb:
        return mitmweb

    # Check common locations
    locations = [
        Path(sys.prefix) / "Scripts" / "mitmweb.exe",
        Path(sys.prefix) / "bin" / "mitmweb",
        Path.home() / "AppData" / "Roaming" / "Python" / f"Python{sys.version_info.major}{sys.version_info.minor}" / "Scripts" / "mitmweb.exe",
    ]

    for loc in locations:
        if loc.exists():
            return str(loc)

    return None


@click.group(invoke_without_command=True)
@click.option("--port", "-p", default=8080, help="Proxy port")
@click.option("--web-port", "-w", default=8081, help="Web UI port")
@click.option("--output", "-o", default="id_tracker_report.json", help="Output report file")
@click.option("--min-numeric", default=100, help="Minimum numeric ID value to track")
@click.option("--config", "-c", default=None, help="Config file path (idotaku.yaml)")
@click.option("--no-browser", is_flag=True, help="Don't launch browser automatically")
@click.option("--browser", type=click.Choice(["chrome", "edge", "firefox", "auto"]), default="auto", help="Browser to use")
@click.pass_context
def main(ctx, port, web_port, output, min_numeric, config, no_browser, browser):
    """idotaku - API ID tracking tool for security testing.

    Tracks ID generation and usage patterns to detect potential IDOR vulnerabilities.
    """
    if ctx.invoked_subcommand is not None:
        return

    # Find mitmweb
    mitmweb_path = find_mitmweb()
    if not mitmweb_path:
        console.print("[red]Error:[/red] mitmweb not found. Install with: pip install mitmproxy")
        sys.exit(1)

    tracker_script = get_tracker_script_path()

    console.print(f"[bold blue]idotaku[/bold blue] - API ID Tracker")
    console.print(f"  Proxy: [green]127.0.0.1:{port}[/green]")
    console.print(f"  Web UI: [green]http://127.0.0.1:{web_port}[/green]")
    console.print(f"  Report: [green]{output}[/green]")
    if config:
        config_path = Path(config).resolve()
        console.print(f"  Config: [green]{config_path}[/green]")
    console.print()

    # Build mitmweb command
    cmd = [
        mitmweb_path,
        "-s", str(tracker_script),
        "--listen-port", str(port),
        "--web-port", str(web_port),
        "--set", f"idotaku_output={output}",
        "--set", f"idotaku_min_numeric={min_numeric}",
    ]

    if config:
        # 絶対パスに変換（mitmwebの実行ディレクトリに依存しないように）
        config_abs = str(Path(config).resolve())
        cmd.extend(["--set", f"idotaku_config={config_abs}"])

    # Start mitmweb
    console.print("[yellow]Starting mitmweb...[/yellow]")
    mitmweb_proc = subprocess.Popen(cmd)

    browser_proc = None
    temp_profile = None

    try:
        if not no_browser:
            # Find and launch browser
            if browser == "auto":
                browser_info = find_browser()
            else:
                browser_info = find_browser()
                if browser_info and browser_info[0] != browser:
                    # Try to find the specific browser
                    for name, path in [find_browser()]:
                        if name == browser:
                            browser_info = (name, path)
                            break

            if browser_info:
                browser_name, browser_path = browser_info
                temp_profile = tempfile.mkdtemp(prefix="idotaku_")

                console.print(f"[yellow]Launching {browser_name}...[/yellow]")

                if browser_name in ("chrome", "edge"):
                    browser_cmd = [
                        browser_path,
                        f"--proxy-server=127.0.0.1:{port}",
                        f"--user-data-dir={temp_profile}",
                        "--ignore-certificate-errors",
                        "--no-first-run",
                        "--no-default-browser-check",
                    ]
                else:  # firefox
                    browser_cmd = [
                        browser_path,
                        "-no-remote",
                        "-profile", temp_profile,
                    ]
                    # Firefox needs proxy set differently (manual config)
                    console.print(f"[yellow]Note: Set Firefox proxy manually to 127.0.0.1:{port}[/yellow]")

                browser_proc = subprocess.Popen(browser_cmd)
            else:
                console.print("[yellow]No browser found. Configure proxy manually.[/yellow]")

        console.print()
        console.print("[bold green]Ready![/bold green] Press Ctrl+C to stop and generate report.")
        console.print()

        # Wait for mitmweb
        mitmweb_proc.wait()

    except KeyboardInterrupt:
        console.print()
        console.print("[yellow]Stopping...[/yellow]")

    finally:
        # Cleanup
        if mitmweb_proc and mitmweb_proc.poll() is None:
            mitmweb_proc.terminate()
            try:
                mitmweb_proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                mitmweb_proc.kill()

        if browser_proc and browser_proc.poll() is None:
            browser_proc.terminate()

        if temp_profile and os.path.exists(temp_profile):
            try:
                shutil.rmtree(temp_profile)
            except Exception:
                pass

    console.print(f"[bold green]Done![/bold green] Report saved to: {output}")


@main.command()
@click.argument("report_file", default="id_tracker_report.json", type=click.Path(exists=True))
def report(report_file):
    """View ID tracking report."""
    import json

    with open(report_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    summary = data.get("summary", {})
    console.print()
    console.print("[bold blue]ID Tracker Report[/bold blue]")
    console.print(f"  Total unique IDs: [green]{summary.get('total_unique_ids', 0)}[/green]")
    console.print(f"  IDs with origin: [green]{summary.get('ids_with_origin', 0)}[/green]")
    console.print(f"  IDs with usage: [green]{summary.get('ids_with_usage', 0)}[/green]")
    console.print()

    # Potential IDOR table
    potential_idor = data.get("potential_idor", [])
    if potential_idor:
        console.print("[bold red]Potential IDOR Targets[/bold red]")
        table = Table()
        table.add_column("ID Value", style="cyan")
        table.add_column("Type", style="yellow")
        table.add_column("Usages", style="green")
        table.add_column("Reason", style="red")

        for item in potential_idor[:20]:
            table.add_row(
                item["id_value"],
                item["id_type"],
                str(len(item["usages"])),
                item["reason"][:50] + "..." if len(item["reason"]) > 50 else item["reason"],
            )

        console.print(table)
    else:
        console.print("[green]No potential IDOR targets found.[/green]")


@main.command()
@click.argument("report_file", default="id_tracker_report.json", type=click.Path(exists=True))
@click.option("--idor-only", is_flag=True, help="Show only potential IDOR targets")
@click.option("--type", "id_type", type=click.Choice(["all", "numeric", "uuid", "token"]), default="all", help="Filter by ID type")
def tree(report_file, idor_only, id_type):
    """Visualize IDs as a tree showing origin → usage flow."""
    import json

    with open(report_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    tracked_ids = data.get("tracked_ids", {})
    potential_idor_values = {item["id_value"] for item in data.get("potential_idor", [])}

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
                is_last = i == len(usages) - 1
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


@main.command()
@click.argument("report_file", default="id_tracker_report.json", type=click.Path(exists=True))
def flow(report_file):
    """Show ID flow as a timeline (horizontal view)."""
    import json

    with open(report_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    tracked_ids = data.get("tracked_ids", {})
    potential_idor_values = {item["id_value"] for item in data.get("potential_idor", [])}

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


@main.command()
@click.argument("report_file", default="id_tracker_report.json", type=click.Path(exists=True))
@click.option("--compact", is_flag=True, help="Compact view (hide IDs not used in subsequent requests)")
def trace(report_file, compact):
    """Visualize API call transitions showing how IDs flow between requests.

    Shows a tree where each API response's IDs connect to subsequent requests that use them.
    """
    import json

    with open(report_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    flows = data.get("flows", [])
    potential_idor_values = {item["id_value"] for item in data.get("potential_idor", [])}

    if not flows:
        console.print("[yellow]No flows found in report.[/yellow]")
        return

    # Sort flows by timestamp
    sorted_flows = sorted(flows, key=lambda x: x.get("timestamp", ""))

    console.print()
    console.print("[bold blue]API Call Trace - ID Transition Tree[/bold blue]")
    console.print()

    # Build transition map: which IDs from response are used in which subsequent requests
    # response_id -> [(flow_index, location, field)]
    id_to_subsequent_usage = {}

    for i, flow in enumerate(sorted_flows):
        for req_id in flow.get("request_ids", []):
            id_val = req_id["value"]
            if id_val not in id_to_subsequent_usage:
                id_to_subsequent_usage[id_val] = []
            id_to_subsequent_usage[id_val].append({
                "flow_idx": i,
                "location": req_id.get("location", "?"),
                "field": req_id.get("field"),
            })

    # Build origin map: which response first produced each ID (backward tracking)
    # id_value -> {flow_idx, location, field}
    id_to_origin = {}
    for i, flow in enumerate(sorted_flows):
        for res_id in flow.get("response_ids", []):
            id_val = res_id["value"]
            if id_val not in id_to_origin:  # First occurrence only
                id_to_origin[id_val] = {
                    "flow_idx": i,
                    "location": res_id.get("location", "?"),
                    "field": res_id.get("field"),
                }

    # Track which flows have been shown as children
    shown_as_child = set()

    def format_id(id_info, show_arrow=False):
        """Format an ID for display."""
        id_val = id_info["value"]
        id_type = id_info.get("type", "?")
        location = id_info.get("location", "?")
        field = id_info.get("field")
        is_idor = id_val in potential_idor_values

        # Shorten long IDs
        display_val = id_val[:16] + "..." if len(id_val) > 16 else id_val

        style = "red" if is_idor else "cyan"
        idor_mark = " [red]⚠[/red]" if is_idor else ""

        loc_str = f"{location}"
        if field:
            loc_str += f".{field}"

        arrow = "→ " if show_arrow else ""
        return f"{arrow}[{style}]{display_val}[/{style}] [dim]({id_type})[/dim] @ {loc_str}{idor_mark}"

    def get_id_transitions(response_ids):
        """Get subsequent API calls that use these response IDs."""
        transitions = {}  # id_value -> list of (flow_idx, usage_info)
        for res_id in response_ids:
            id_val = res_id["value"]
            if id_val in id_to_subsequent_usage:
                transitions[id_val] = id_to_subsequent_usage[id_val]
        return transitions

    # Display the trace tree
    for i, flow in enumerate(sorted_flows):
        # Skip if this flow was already shown as a child transition
        if compact and i in shown_as_child:
            continue

        method = flow.get("method", "?")
        url = flow.get("url", "?")
        timestamp = flow.get("timestamp", "")
        time_part = timestamp.split("T")[1][:8] if "T" in timestamp else ""
        request_ids = flow.get("request_ids", [])
        response_ids = flow.get("response_ids", [])

        # Shorten URL
        if len(url) > 50:
            url = url[:47] + "..."

        # Create tree for this API call
        tree = Tree(
            f"[bold magenta]({method})[/bold magenta] [white]{url}[/white] [dim]{time_part}[/dim]"
        )

        # Add request IDs (inputs to this API) with origin tracking
        if request_ids:
            req_branch = tree.add("[yellow]REQ[/yellow]")
            for req_id in request_ids:
                id_val = req_id["value"]
                req_node = req_branch.add(format_id(req_id))

                # Show where this ID came from (origin)
                if id_val in id_to_origin:
                    origin_info = id_to_origin[id_val]
                    origin_flow_idx = origin_info["flow_idx"]
                    if origin_flow_idx < i:  # Only show if from a previous flow
                        origin_flow = sorted_flows[origin_flow_idx]
                        origin_method = origin_flow.get("method", "?")
                        origin_url = origin_flow.get("url", "?")
                        origin_time = origin_flow.get("timestamp", "").split("T")[1][:8] if "T" in origin_flow.get("timestamp", "") else ""

                        if len(origin_url) > 35:
                            origin_url = origin_url[:32] + "..."

                        origin_loc = origin_info["location"]
                        if origin_info["field"]:
                            origin_loc += f".{origin_info['field']}"

                        req_node.add(
                            f"[green]← from[/green] [bold magenta]({origin_method})[/bold magenta] [dim]{origin_url}[/dim] [dim]{origin_time}[/dim] @ {origin_loc}"
                        )

        # Add response IDs and their transitions
        if response_ids:
            res_branch = tree.add("[green]RES[/green]")

            # Get transitions for response IDs
            transitions = get_id_transitions(response_ids)

            for res_id in response_ids:
                id_val = res_id["value"]
                id_node = res_branch.add(format_id(res_id))

                # Show subsequent usages of this ID
                if id_val in transitions:
                    for usage in transitions[id_val]:
                        next_flow_idx = usage["flow_idx"]
                        if next_flow_idx <= i:
                            continue  # Only show forward transitions

                        shown_as_child.add(next_flow_idx)
                        next_flow = sorted_flows[next_flow_idx]
                        next_method = next_flow.get("method", "?")
                        next_url = next_flow.get("url", "?")
                        next_time = next_flow.get("timestamp", "").split("T")[1][:8] if "T" in next_flow.get("timestamp", "") else ""

                        if len(next_url) > 40:
                            next_url = next_url[:37] + "..."

                        loc_str = usage["location"]
                        if usage["field"]:
                            loc_str += f".{usage['field']}"

                        # Add the transition arrow and subsequent API call
                        transition_node = id_node.add(
                            f"[yellow]→[/yellow] [bold magenta]({next_method})[/bold magenta] [white]{next_url}[/white] [dim]{next_time}[/dim] @ {loc_str}"
                        )

                        # Show what IDs this subsequent call produced
                        next_response_ids = next_flow.get("response_ids", [])
                        if next_response_ids:
                            for next_res_id in next_response_ids[:5]:  # Limit to 5
                                transition_node.add(format_id(next_res_id, show_arrow=True))
                            if len(next_response_ids) > 5:
                                transition_node.add(f"[dim]... +{len(next_response_ids) - 5} more[/dim]")
                elif compact:
                    # In compact mode, mark IDs that aren't used later
                    pass  # Already shown, just no children

        console.print(tree)
        console.print()

    # Summary
    console.print(f"[dim]Total: {len(sorted_flows)} API calls[/dim]")
    if potential_idor_values:
        console.print(f"[red]⚠ {len(potential_idor_values)} potential IDOR IDs marked[/red]")


@main.command()
@click.argument("report_file", default="id_tracker_report.json", type=click.Path(exists=True))
@click.option("--limit", "-n", default=30, help="Max number of API calls to show")
def sequence(report_file, limit):
    """Show API call sequence with parameter flow (horizontal timeline).

    Visualizes the time-ordered sequence of API calls and shows which
    parameters are passed between them.
    """
    import json
    from rich.panel import Panel
    from rich.columns import Columns

    with open(report_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    flows = data.get("flows", [])
    if not flows:
        console.print("[yellow]No flows found in report.[/yellow]")
        return

    sorted_flows = sorted(flows, key=lambda x: x.get("timestamp", ""))[:limit]

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
            val = res_id["value"]
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
            val = req_id["value"]
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
        from urllib.parse import urlparse
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
                val = rid["value"]
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
                val = rid["value"]
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
            next_req_ids = {r["value"] for r in next_flow.get("request_ids", [])}
            current_res_ids = {r["value"] for r in res_ids}
            shared = current_res_ids & next_req_ids
            if shared:
                shared_display = ", ".join(list(shared)[:3])
                if len(shared_display) > 30:
                    shared_display = shared_display[:27] + "..."
                console.print(f"        [yellow]│[/yellow]")
                console.print(f"        [yellow]▼[/yellow] [dim]{shared_display}[/dim]")
                console.print(f"        [yellow]│[/yellow]")
            else:
                console.print()

    console.print()
    console.print(f"[dim]Showing {len(sorted_flows)} of {len(flows)} API calls[/dim]")


@main.command()
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
    import json
    from rich.table import Table

    with open(report_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    flows = data.get("flows", [])
    if not flows:
        console.print("[yellow]No flows found in report.[/yellow]")
        return

    sorted_flows = sorted(flows, key=lambda x: x.get("timestamp", ""))
    total_flows = len(sorted_flows)

    # Build param lifecycle: param_value -> {first_idx, last_idx, events}
    param_lifecycle = {}

    for i, flow in enumerate(sorted_flows):
        method = flow.get("method", "?")
        url = flow.get("url", "?")
        from urllib.parse import urlparse
        path = urlparse(url).path or "/"

        for res_id in flow.get("response_ids", []):
            val = res_id["value"]
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
            val = req_id["value"]
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


@main.command()
@click.argument("report_file", default="id_tracker_report.json", type=click.Path(exists=True))
@click.option("--min-connections", "-m", default=1, help="Minimum connections to show an API")
def graph(report_file, min_connections):
    """Show API dependency graph (which API produces params used by which).

    Visualizes the dependency structure: API-A produces param X,
    which is consumed by API-B, API-C, etc.
    """
    import json
    from collections import defaultdict

    with open(report_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    flows = data.get("flows", [])
    if not flows:
        console.print("[yellow]No flows found in report.[/yellow]")
        return

    sorted_flows = sorted(flows, key=lambda x: x.get("timestamp", ""))

    # Build: param -> producer API (first response that had it)
    # Build: param -> consumer APIs (requests that used it)
    param_producer = {}  # param_val -> (flow_idx, method, path, field)
    param_consumers = defaultdict(list)  # param_val -> [(flow_idx, method, path, field)]

    from urllib.parse import urlparse

    for i, flow in enumerate(sorted_flows):
        method = flow.get("method", "?")
        url = flow.get("url", "?")
        path = urlparse(url).path or "/"

        # Track producers (first response)
        for res_id in flow.get("response_ids", []):
            val = res_id["value"]
            if val not in param_producer:
                param_producer[val] = {
                    "idx": i,
                    "method": method,
                    "path": path,
                    "field": res_id.get("field") or res_id.get("location"),
                }

        # Track consumers
        for req_id in flow.get("request_ids", []):
            val = req_id["value"]
            param_consumers[val].append({
                "idx": i,
                "method": method,
                "path": path,
                "field": req_id.get("field") or req_id.get("location"),
            })

    # Build API -> API dependency: producer_api -> [(param, consumer_api)]
    # Group by producer API (method + path)
    api_deps = defaultdict(lambda: defaultdict(list))  # producer_key -> param -> [consumer_keys]

    for param_val, producer in param_producer.items():
        if param_val not in param_consumers:
            continue
        producer_key = f"{producer['method']} {producer['path']}"
        for consumer in param_consumers[param_val]:
            if consumer["idx"] <= producer["idx"]:
                continue  # Only forward dependencies
            consumer_key = f"{consumer['method']} {consumer['path']}"
            if consumer_key != producer_key:  # Don't self-reference
                api_deps[producer_key][param_val].append({
                    "api": consumer_key,
                    "field": consumer["field"],
                })

    console.print()
    console.print("[bold blue]API Dependency Graph[/bold blue]")
    console.print("[dim]Shows which APIs produce parameters consumed by other APIs[/dim]")
    console.print()

    # Filter and sort by connection count
    api_with_deps = []
    for producer_key, params in api_deps.items():
        total_connections = sum(len(consumers) for consumers in params.values())
        if total_connections >= min_connections:
            api_with_deps.append((producer_key, params, total_connections))

    api_with_deps.sort(key=lambda x: x[2], reverse=True)

    for producer_key, params, total_conn in api_with_deps[:30]:
        tree = Tree(f"[bold green]{producer_key}[/bold green] [dim]({total_conn} connections)[/dim]")

        for param_val, consumers in list(params.items())[:10]:
            short_param = param_val[:16] + "..." if len(param_val) > 16 else param_val
            param_node = tree.add(f"[cyan]{short_param}[/cyan]")

            # Group consumers by API
            consumer_apis = defaultdict(list)
            for c in consumers:
                consumer_apis[c["api"]].append(c["field"])

            for consumer_api, fields in list(consumer_apis.items())[:5]:
                field_str = ", ".join(set(fields))[:20]
                param_node.add(f"[yellow]→[/yellow] [white]{consumer_api}[/white] [dim]@ {field_str}[/dim]")

            if len(consumer_apis) > 5:
                param_node.add(f"[dim]+{len(consumer_apis) - 5} more APIs[/dim]")

        if len(params) > 10:
            tree.add(f"[dim]+{len(params) - 10} more params[/dim]")

        console.print(tree)
        console.print()

    # Also show "orphan" APIs (consume but don't produce dependencies)
    all_consumers = set()
    for params in api_deps.values():
        for consumers in params.values():
            for c in consumers:
                all_consumers.add(c["api"])

    all_producers = set(api_deps.keys())
    leaf_apis = all_consumers - all_producers

    if leaf_apis:
        console.print("[dim]Leaf APIs (consume but don't produce tracked params):[/dim]")
        for api in list(leaf_apis)[:10]:
            console.print(f"  [dim]└─ {api}[/dim]")
        if len(leaf_apis) > 10:
            console.print(f"  [dim]   +{len(leaf_apis) - 10} more[/dim]")

    console.print()
    console.print(f"[dim]Showing {len(api_with_deps)} producer APIs with {min_connections}+ connections[/dim]")


def _export_chain_html(output_path, sorted_flows, flow_graph, flow_produces, selected_roots):
    """Export chain trees to interactive HTML."""
    import html as html_module
    import re
    from datetime import datetime
    from urllib.parse import urlparse

    def esc(s):
        return html_module.escape(str(s))

    def normalize_api_path(url):
        """Normalize URL path by replacing ID-like segments with placeholders.

        e.g., /users/123/orders/456 -> /users/{id}/orders/{id}
        """
        path = urlparse(url).path or "/"
        # Replace common ID patterns in path segments
        segments = path.split("/")
        normalized = []
        for seg in segments:
            if not seg:
                normalized.append(seg)
            elif re.match(r'^\d+$', seg):  # numeric ID
                normalized.append("{id}")
            elif re.match(r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$', seg, re.I):  # UUID
                normalized.append("{uuid}")
            elif re.match(r'^[a-zA-Z0-9_-]{20,}$', seg):  # long token-like string
                normalized.append("{token}")
            else:
                normalized.append(seg)
        return "/".join(normalized)

    def get_flow_details(flow_idx):
        """Get detailed info for a flow."""
        flow = sorted_flows[flow_idx]
        return {
            "idx": flow_idx,
            "method": flow.get("method", "?"),
            "url": flow.get("url", "?"),
            "path": urlparse(flow.get("url", "")).path or "/",
            "timestamp": flow.get("timestamp", ""),
            "request_ids": flow.get("request_ids", []),
            "response_ids": flow.get("response_ids", []),
        }

    def get_api_key(flow_idx):
        """Get API key (method + normalized path) for cycle detection."""
        flow = sorted_flows[flow_idx]
        method = flow.get("method", "?")
        url = flow.get("url", "")
        return f"{method} {normalize_api_path(url)}"

    def build_tree_json(flow_idx, via_params, visited_apis, node_index_map, index_counter,
                        deferred_children, first_occurrence):
        """Build JSON tree structure for HTML with cycle continuation.

        Cycle detection is based on API pattern (method + normalized path), not flow_idx.
        This allows the same parameter to flow through different APIs without being
        treated as a cycle.

        Args:
            via_params: list of params connecting to this node (or None for root)
            visited_apis: set of API patterns already visited on current path
            deferred_children: dict to collect children that should be added to cycle targets
            first_occurrence: dict mapping API pattern to first flow_idx that used it
        """
        api_key = get_api_key(flow_idx)
        is_cycle = api_key in visited_apis

        # Already visited this API pattern? Return ref
        if is_cycle:
            # Find the first occurrence of this API pattern
            first_idx = first_occurrence.get(api_key, flow_idx)
            target_index = node_index_map.get(first_idx, "?")
            return {"type": "cycle_ref", "flow_idx": flow_idx, "target_index": target_index,
                    "via_params": via_params, "api_key": api_key}

        # Mark this API pattern as visited
        new_visited = visited_apis | {api_key}
        first_occurrence[api_key] = flow_idx

        # Assign index to this node
        current_index = index_counter[0]
        index_counter[0] += 1
        node_index_map[flow_idx] = current_index

        details = get_flow_details(flow_idx)
        children = []

        for next_idx, next_params in flow_graph.get(flow_idx, []):
            child = build_tree_json(next_idx, next_params, new_visited, node_index_map,
                                   index_counter, deferred_children, first_occurrence)
            if child:
                # If child is a cycle_ref, defer its grandchildren to the cycle target
                if child.get("type") == "cycle_ref":
                    target_index = child.get("target_index")
                    target_idx = child["flow_idx"]  # The skipped node's flow_idx
                    for gc_idx, gc_params in flow_graph.get(target_idx, []):
                        gc_api = get_api_key(gc_idx)
                        if gc_idx != target_idx and gc_api not in new_visited:
                            if target_index not in deferred_children:
                                deferred_children[target_index] = []
                            gc = build_tree_json(gc_idx, gc_params, new_visited, node_index_map,
                                               index_counter, deferred_children, first_occurrence)
                            if gc:
                                gc["from_cycle"] = True
                                deferred_children[target_index].append(gc)
                children.append(child)

        return {
            "flow_idx": flow_idx,
            "index": current_index,
            "via_params": via_params,
            "is_cycle": False,  # Not a cycle since we expanded it
            "api_key": api_key,
            "method": details["method"],
            "url": details["url"],
            "path": details["path"],
            "timestamp": details["timestamp"],
            "request_ids": details["request_ids"],
            "response_ids": details["response_ids"],
            "children": children,
        }

    def inject_deferred_children(tree, deferred_children):
        """Inject deferred children into their target nodes."""
        if not tree or tree.get("type") == "cycle_ref":
            return

        # Inject deferred children for this node
        node_index = tree.get("index")
        if node_index in deferred_children:
            tree["children"].extend(deferred_children[node_index])
            # Mark these as coming from cycle
            for child in deferred_children[node_index]:
                child["from_cycle"] = True
            del deferred_children[node_index]

        # Recurse into children
        for child in tree.get("children", []):
            inject_deferred_children(child, deferred_children)

    # Build tree data for all selected roots
    trees_data = []
    for rank, (score, depth, nodes, root_idx) in enumerate(selected_roots, 1):
        # Initialize tracking for this tree
        node_index_map = {}
        index_counter = [1]
        deferred_children = {}  # target_index -> [children]
        visited_apis = set()  # API patterns visited on current path
        first_occurrence = {}  # API pattern -> first flow_idx

        tree = build_tree_json(root_idx, None, visited_apis, node_index_map, index_counter,
                              deferred_children, first_occurrence)

        # Inject deferred children into their targets
        inject_deferred_children(tree, deferred_children)

        tree["rank"] = rank
        tree["depth"] = depth
        tree["nodes"] = nodes
        trees_data.append(tree)

    import json
    trees_json = json.dumps(trees_data, ensure_ascii=False)

    html_content = f'''<!DOCTYPE html>
<html lang="ja">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>idotaku - Parameter Chain Trees</title>
    <style>
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: #0d1117;
            color: #c9d1d9;
            min-height: 100vh;
        }}

        /* Main Tree Panel - Full Width */
        .tree-panel {{
            padding: 20px;
            padding-right: 40px;
            max-width: 1200px;
            margin: 0 auto;
        }}
        .tree-panel h1 {{
            color: #58a6ff;
            font-size: 1.4em;
            margin-bottom: 20px;
            border-bottom: 1px solid #30363d;
            padding-bottom: 10px;
        }}

        /* Tree Styles */
        .tree-root {{
            margin-bottom: 30px;
        }}
        .tree-header {{
            background: #161b22;
            padding: 12px 16px;
            border-radius: 8px;
            margin-bottom: 8px;
            border-left: 4px solid #58a6ff;
        }}
        .tree-header .rank {{
            color: #f0883e;
            font-weight: bold;
            margin-right: 10px;
        }}
        .tree-header .stats {{
            color: #8b949e;
            font-size: 0.85em;
            margin-left: 10px;
        }}

        .tree-node {{
            margin-left: 24px;
            border-left: 2px solid #30363d;
            padding-left: 16px;
        }}
        .node-item {{
            padding: 8px 12px;
            margin: 4px 0;
            background: #161b22;
            border-radius: 6px;
            cursor: pointer;
            transition: all 0.15s;
            position: relative;
        }}
        .node-item:hover {{
            background: #1f2937;
            border-color: #58a6ff;
        }}
        .node-item.selected {{
            background: #1f3a5f;
            border-left: 3px solid #58a6ff;
        }}
        .node-item.highlight-target {{
            animation: highlight-pulse 0.5s ease-in-out 3;
        }}
        @keyframes highlight-pulse {{
            0%, 100% {{ background: #1f3a5f; box-shadow: 0 0 0 0 rgba(88, 166, 255, 0.7); }}
            50% {{ background: #2d4a7c; box-shadow: 0 0 0 4px rgba(88, 166, 255, 0); }}
        }}
        .cycle-link:hover {{
            background: #2d1f1f !important;
        }}
        .cycle-badge:hover {{
            background: rgba(248, 81, 73, 0.2);
            border-radius: 4px;
        }}
        .node-item.from-cycle {{
            border-left: 2px solid #f0883e;
            padding-left: 10px;
            margin-left: -2px;
        }}
        .node-item::before {{
            content: "";
            position: absolute;
            left: -18px;
            top: 50%;
            width: 16px;
            height: 2px;
            background: #30363d;
        }}

        .method {{
            display: inline-block;
            padding: 2px 6px;
            border-radius: 4px;
            font-size: 0.75em;
            font-weight: bold;
            margin-right: 8px;
        }}
        .method.GET {{ background: #238636; color: #fff; }}
        .method.POST {{ background: #a371f7; color: #fff; }}
        .method.PUT {{ background: #f0883e; color: #fff; }}
        .method.DELETE {{ background: #f85149; color: #fff; }}
        .method.PATCH {{ background: #3fb950; color: #fff; }}

        .path {{ color: #c9d1d9; font-size: 0.9em; }}
        .param-arrow {{
            color: #f0883e;
            margin: 0 6px;
        }}
        .param-value {{
            color: #79c0ff;
            font-family: monospace;
            font-size: 0.85em;
            background: #1f2937;
            padding: 2px 6px;
            border-radius: 4px;
        }}

        .toggle-btn {{
            display: inline-block;
            width: 18px;
            height: 18px;
            text-align: center;
            line-height: 18px;
            background: #30363d;
            border-radius: 4px;
            margin-right: 8px;
            font-size: 0.8em;
            cursor: pointer;
        }}
        .toggle-btn:hover {{ background: #484f58; }}

        /* Slide-in Detail Panel */
        .detail-overlay {{
            position: fixed;
            top: 0;
            right: 0;
            width: 450px;
            height: 100vh;
            background: #161b22;
            box-shadow: -4px 0 20px rgba(0,0,0,0.5);
            transform: translateX(100%);
            transition: transform 0.25s ease-out;
            z-index: 1000;
            display: flex;
            flex-direction: column;
        }}
        .detail-overlay.open {{
            transform: translateX(0);
        }}
        .detail-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 16px 20px;
            border-bottom: 1px solid #30363d;
            background: #0d1117;
        }}
        .detail-header h2 {{
            color: #58a6ff;
            font-size: 1.1em;
            margin: 0;
        }}
        .close-btn {{
            background: #30363d;
            border: none;
            color: #c9d1d9;
            width: 32px;
            height: 32px;
            border-radius: 6px;
            cursor: pointer;
            font-size: 1.2em;
            display: flex;
            align-items: center;
            justify-content: center;
            transition: background 0.15s;
        }}
        .close-btn:hover {{
            background: #484f58;
        }}
        .detail-body {{
            flex: 1;
            overflow-y: auto;
            padding: 20px;
        }}
        .detail-section {{
            margin-bottom: 20px;
        }}
        .detail-section h3 {{
            color: #8b949e;
            font-size: 0.85em;
            text-transform: uppercase;
            margin-bottom: 8px;
        }}
        .detail-url {{
            background: #0d1117;
            padding: 12px;
            border-radius: 6px;
            font-family: monospace;
            font-size: 0.9em;
            word-break: break-all;
            color: #79c0ff;
        }}
        .detail-time {{
            color: #8b949e;
            font-size: 0.9em;
        }}

        .param-table {{
            width: 100%;
            border-collapse: collapse;
            font-size: 0.85em;
        }}
        .param-table th {{
            text-align: left;
            padding: 8px;
            background: #0d1117;
            color: #8b949e;
            font-weight: normal;
        }}
        .param-table td {{
            padding: 8px;
            border-bottom: 1px solid #30363d;
        }}
        .param-table .value {{
            font-family: monospace;
            color: #79c0ff;
            max-width: 200px;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
        }}
        .param-table .type {{ color: #a371f7; }}
        .param-table .location {{ color: #3fb950; }}
        .param-table .field {{ color: #f0883e; }}

        .badge {{
            display: inline-block;
            padding: 2px 8px;
            border-radius: 12px;
            font-size: 0.75em;
            margin-right: 4px;
        }}
        .badge.req {{ background: #f0883e33; color: #f0883e; }}
        .badge.res {{ background: #3fb95033; color: #3fb950; }}

        /* Collapse animation */
        .tree-children {{
            overflow: hidden;
            transition: max-height 0.2s ease-out;
        }}
        .tree-children.collapsed {{
            max-height: 0 !important;
        }}

        /* Keyboard hint */
        .hint {{
            position: fixed;
            bottom: 20px;
            right: 20px;
            background: #30363d;
            padding: 8px 14px;
            border-radius: 6px;
            font-size: 0.8em;
            color: #8b949e;
        }}
        .hint kbd {{
            background: #0d1117;
            padding: 2px 6px;
            border-radius: 4px;
            margin: 0 2px;
        }}
    </style>
</head>
<body>
    <div class="tree-panel">
        <h1>Parameter Chain Trees</h1>
        <div id="trees"></div>
    </div>

    <div class="detail-overlay" id="detailPanel">
        <div class="detail-header">
            <h2>API Details</h2>
            <button class="close-btn" onclick="closePanel()" title="Close (Esc)">×</button>
        </div>
        <div class="detail-body" id="details"></div>
    </div>

    <div class="hint">Click node to view details | <kbd>Esc</kbd> to close</div>

    <script>
        const treesData = {trees_json};
        let selectedNode = null;

        function truncatePath(path, max) {{
            return path.length > max ? path.substring(0, max - 3) + '...' : path;
        }}

        function truncateValue(val, max) {{
            return val.length > max ? val.substring(0, max - 2) + '..' : val;
        }}

        function formatParams(params, maxLen) {{
            // Format array of params for display
            if (!params || params.length === 0) return '';
            if (params.length === 1) {{
                return truncateValue(params[0], maxLen);
            }}
            // Multiple params: show count
            const first = truncateValue(params[0], maxLen - 6);
            return first + ' +' + (params.length - 1);
        }}

        function renderNode(node, isRoot = false) {{
            // Handle cycle reference nodes (max path visits, children deferred to target)
            if (node.type === 'cycle_ref') {{
                let html = '<div class="node-item" style="color: #8b949e; font-style: italic;">';
                html += '<span style="width: 26px; display: inline-block;"></span>';
                html += '↩ <span style="color: #3fb950;">[#' + node.target_index + ']</span>';
                if (node.via_params && node.via_params.length > 0) {{
                    html += ' <span style="color: #6e7681;">via </span><span class="param-value" style="color: #6e7681;">' + formatParams(node.via_params, 16) + '</span>';
                }}
                html += ' <span style="color: #6e7681; font-size: 0.85em;">(continues below)</span>';
                html += '</div>';
                return html;
            }}

            const hasChildren = node.children && node.children.length > 0;
            const nodeId = 'node-' + node.flow_idx + '-' + Math.random().toString(36).substr(2, 9);

            let html = '<div class="node-item' + (node.from_cycle ? ' from-cycle' : '') + '" data-flow=\\'' + JSON.stringify(node).replace(/'/g, "\\\\'") + '\\' data-node-index="' + node.index + '" id="' + nodeId + '">';

            if (hasChildren) {{
                html += '<span class="toggle-btn" onclick="toggleChildren(event, \\'' + nodeId + '\\')">−</span>';
            }} else {{
                html += '<span style="width: 26px; display: inline-block;"></span>';
            }}

            // Show cycle continuation indicator
            if (node.from_cycle) {{
                html += '<span style="color: #f0883e; margin-right: 4px;" title="Continued from cycle">↳</span>';
            }}

            // Display index
            html += '<span style="color: #3fb950; font-weight: bold; margin-right: 6px;">[#' + node.index + ']</span>';

            html += '<span class="method ' + node.method + '">' + node.method + '</span>';

            if (node.via_params && node.via_params.length > 0 && !isRoot) {{
                html += '<span class="param-value">' + formatParams(node.via_params, 16) + '</span>';
                html += '<span class="param-arrow">→</span>';
            }}

            html += '<span class="path">' + truncatePath(node.path, 40) + '</span>';
            html += '</div>';

            if (hasChildren) {{
                html += '<div class="tree-children" id="children-' + nodeId + '">';
                html += '<div class="tree-node">';
                for (const child of node.children) {{
                    html += renderNode(child);
                }}
                html += '</div></div>';
            }}

            return html;
        }}

        function renderTrees() {{
            const container = document.getElementById('trees');
            let html = '';

            for (const tree of treesData) {{
                html += '<div class="tree-root">';
                html += '<div class="tree-header">';
                html += '<span class="rank">#' + tree.rank + '</span>';
                html += '<span style="color: #3fb950; font-weight: bold; margin-right: 6px;">[#' + tree.index + ']</span>';
                html += '<span class="method ' + tree.method + '">' + tree.method + '</span> ';
                html += '<span class="path">' + truncatePath(tree.path, 50) + '</span>';
                html += '<span class="stats">depth:' + tree.depth + ' nodes:' + tree.nodes + '</span>';
                html += '</div>';
                html += '<div class="tree-node">';
                for (const child of tree.children) {{
                    html += renderNode(child);
                }}
                html += '</div></div>';
            }}

            container.innerHTML = html;

            // Add click handlers
            document.querySelectorAll('.node-item').forEach(item => {{
                item.addEventListener('click', (e) => {{
                    if (e.target.classList.contains('toggle-btn')) return;
                    selectNode(item);
                }});
            }});

            // Also make tree headers clickable
            document.querySelectorAll('.tree-header').forEach((header, idx) => {{
                header.style.cursor = 'pointer';
                header.addEventListener('click', () => {{
                    showDetails(treesData[idx]);
                }});
            }});
        }}

        function toggleChildren(event, nodeId) {{
            event.stopPropagation();
            const childrenEl = document.getElementById('children-' + nodeId);
            const toggleBtn = event.target;

            if (childrenEl.classList.contains('collapsed')) {{
                childrenEl.classList.remove('collapsed');
                childrenEl.style.maxHeight = childrenEl.scrollHeight + 'px';
                toggleBtn.textContent = '−';
            }} else {{
                childrenEl.style.maxHeight = childrenEl.scrollHeight + 'px';
                childrenEl.offsetHeight; // Force reflow
                childrenEl.classList.add('collapsed');
                toggleBtn.textContent = '+';
            }}
        }}

        function selectNode(item) {{
            document.querySelectorAll('.node-item').forEach(n => n.classList.remove('selected'));
            item.classList.add('selected');
            const data = JSON.parse(item.dataset.flow);
            showDetails(data);
        }}

        function openPanel() {{
            document.getElementById('detailPanel').classList.add('open');
        }}

        function closePanel() {{
            document.getElementById('detailPanel').classList.remove('open');
            document.querySelectorAll('.node-item').forEach(n => n.classList.remove('selected'));
        }}

        function scrollToNode(targetIndex) {{
            // Find the node with the target index
            const targetNode = document.querySelector('[data-node-index="' + targetIndex + '"]');
            if (!targetNode) return;

            // Expand all parent tree-children to make target visible
            let parent = targetNode.parentElement;
            while (parent) {{
                if (parent.classList && parent.classList.contains('tree-children') && parent.classList.contains('collapsed')) {{
                    parent.classList.remove('collapsed');
                    parent.style.maxHeight = parent.scrollHeight + 'px';
                    // Update toggle button
                    const prevSibling = parent.previousElementSibling;
                    if (prevSibling) {{
                        const toggleBtn = prevSibling.querySelector('.toggle-btn');
                        if (toggleBtn) toggleBtn.textContent = '−';
                    }}
                }}
                parent = parent.parentElement;
            }}

            // Scroll to the node
            targetNode.scrollIntoView({{ behavior: 'smooth', block: 'center' }});

            // Highlight the node temporarily
            targetNode.classList.add('highlight-target');
            setTimeout(() => {{
                targetNode.classList.remove('highlight-target');
            }}, 2000);

            // Select the node and show details
            selectNode(targetNode);
        }}

        // Esc key to close
        document.addEventListener('keydown', (e) => {{
            if (e.key === 'Escape') closePanel();
        }});

        function showDetails(node) {{
            const container = document.getElementById('details');
            openPanel();

            let html = '';

            // URL
            html += '<div class="detail-section">';
            html += '<h3>URL</h3>';
            html += '<div class="detail-url">' + node.url + '</div>';
            html += '</div>';

            // Timestamp
            if (node.timestamp) {{
                html += '<div class="detail-section">';
                html += '<h3>Timestamp</h3>';
                html += '<div class="detail-time">' + node.timestamp + '</div>';
                html += '</div>';
            }}

            // Via Parameters (connection params)
            if (node.via_params && node.via_params.length > 0) {{
                html += '<div class="detail-section">';
                html += '<h3>Connected via Parameter' + (node.via_params.length > 1 ? 's (' + node.via_params.length + ')' : '') + '</h3>';
                html += '<div class="detail-url">';
                for (const p of node.via_params) {{
                    html += '<div style="font-family: monospace; margin: 4px 0;">' + p + '</div>';
                }}
                html += '</div>';
                html += '</div>';
            }}

            // From Cycle indicator
            if (node.from_cycle) {{
                html += '<div class="detail-section">';
                html += '<h3 style="color: #f0883e;">↳ Continued from Cycle</h3>';
                html += '<div class="detail-url" style="background: #f0883e22; border: 1px solid #f0883e;">';
                html += '<div>This node was added as a continuation from a cycle.</div>';
                html += '</div>';
                html += '</div>';
            }}

            // Cycle Information
            if (node.is_cycle && node.cycle_to_index !== undefined) {{
                html += '<div class="detail-section">';
                html += '<h3 style="color: #f85149;">⟳ Cycle Detected</h3>';
                html += '<div class="detail-url" style="background: #f8514922; border: 1px solid #f85149;">';
                html += '<div>Same API as <span style="color: #3fb950; font-weight: bold;">[#' + node.cycle_to_index + ']</span></div>';
                if (node.via_params && node.via_params.length > 0) {{
                    html += '<div style="color: #8b949e; margin-top: 8px;">via parameter' + (node.via_params.length > 1 ? 's' : '') + ':</div>';
                    for (const p of node.via_params) {{
                        html += '<div style="color: #79c0ff; font-family: monospace; margin-left: 8px;">' + p + '</div>';
                    }}
                }}
                html += '</div>';
                html += '</div>';
            }}

            // Request IDs
            if (node.request_ids && node.request_ids.length > 0) {{
                html += '<div class="detail-section">';
                html += '<h3><span class="badge req">REQ</span> Request Parameters (' + node.request_ids.length + ')</h3>';
                html += '<table class="param-table"><thead><tr>';
                html += '<th>Value</th><th>Type</th><th>Location</th><th>Field</th>';
                html += '</tr></thead><tbody>';
                for (const id of node.request_ids) {{
                    html += '<tr>';
                    html += '<td class="value" title="' + id.value + '">' + truncateValue(id.value, 24) + '</td>';
                    html += '<td class="type">' + (id.type || '-') + '</td>';
                    html += '<td class="location">' + (id.location || '-') + '</td>';
                    html += '<td class="field">' + (id.field || '-') + '</td>';
                    html += '</tr>';
                }}
                html += '</tbody></table></div>';
            }}

            // Response IDs
            if (node.response_ids && node.response_ids.length > 0) {{
                html += '<div class="detail-section">';
                html += '<h3><span class="badge res">RES</span> Response Parameters (' + node.response_ids.length + ')</h3>';
                html += '<table class="param-table"><thead><tr>';
                html += '<th>Value</th><th>Type</th><th>Location</th><th>Field</th>';
                html += '</tr></thead><tbody>';
                for (const id of node.response_ids) {{
                    html += '<tr>';
                    html += '<td class="value" title="' + id.value + '">' + truncateValue(id.value, 24) + '</td>';
                    html += '<td class="type">' + (id.type || '-') + '</td>';
                    html += '<td class="location">' + (id.location || '-') + '</td>';
                    html += '<td class="field">' + (id.field || '-') + '</td>';
                    html += '</tr>';
                }}
                html += '</tbody></table></div>';
            }}

            container.innerHTML = html;
        }}

        // Initialize
        renderTrees();
    </script>
</body>
</html>
'''

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html_content)


@main.command()
@click.argument("report_file", default="id_tracker_report.json", type=click.Path(exists=True))
@click.option("--top", "-n", default=10, help="Number of top root chains to show")
@click.option("--min-depth", "-m", default=2, help="Minimum tree depth")
@click.option("--html", "-o", "html_output", default=None, help="Export to interactive HTML file")
def chain(report_file, top, min_depth, html_output):
    """Detect and rank parameter chains as trees (main business flows).

    Finds parameter flow trees where:
    API-A produces params → multiple APIs use them → they produce more params → ...

    Shows branching structure when one API's params feed multiple downstream APIs.
    """
    import json
    from collections import defaultdict
    from urllib.parse import urlparse

    with open(report_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    flows = data.get("flows", [])
    if not flows:
        console.print("[yellow]No flows found in report.[/yellow]")
        return

    sorted_flows = sorted(flows, key=lambda x: x.get("timestamp", ""))

    # Build mappings
    param_origins = defaultdict(list)  # param -> list of origin flow idx (all producers)
    param_usages = defaultdict(list)  # param -> list of flow idx that use it
    flow_produces = defaultdict(list)  # flow_idx -> list of params produced

    for i, flow in enumerate(sorted_flows):
        for res_id in flow.get("response_ids", []):
            val = res_id["value"]
            param_origins[val].append(i)  # Track ALL origins
            flow_produces[i].append(val)

        for req_id in flow.get("request_ids", []):
            val = req_id["value"]
            param_usages[val].append(i)

    # Build flow graph: flow_idx -> [(next_flow_idx, [params]), ...]
    # Allow backward edges to detect cycles (e.g., API A → B → C → A)
    # Group multiple params for same edge
    flow_graph_raw = defaultdict(lambda: defaultdict(list))  # origin -> usage -> [params]
    for param, origin_idxs in param_origins.items():
        for origin_idx in origin_idxs:
            for usage_idx in param_usages[param]:
                if usage_idx != origin_idx:  # Prevent self-loops only
                    flow_graph_raw[origin_idx][usage_idx].append(param)

    # Convert to list format with sorted edges
    flow_graph = defaultdict(list)  # origin -> [(usage_idx, [params])]
    for origin_idx, usages in flow_graph_raw.items():
        for usage_idx, params in sorted(usages.items()):
            flow_graph[origin_idx].append((usage_idx, params))

    def format_api(flow_idx):
        """Format API for display."""
        flow = sorted_flows[flow_idx]
        method = flow.get("method", "?")
        url = flow.get("url", "?")
        path = urlparse(url).path or "/"
        if len(path) > 45:
            path = path[:42] + "..."
        # Escape [ in path to prevent Rich markup parsing
        path = path.replace("[", "\\[")
        return f"[bold magenta]{method}[/bold magenta] [white]{path}[/white]"

    def escape_rich(text):
        """Escape Rich markup characters in text."""
        # Only need to escape [ since that starts markup tags
        return str(text).replace("[", "\\[")

    def format_param(params):
        """Format param(s) for display. Accepts single param or list."""
        if isinstance(params, list):
            if len(params) == 0:
                return "[dim]none[/dim]"
            if len(params) == 1:
                param = params[0]
            else:
                # Multiple params - show count and first few
                short_list = [escape_rich(p[:12] + ".." if len(p) > 12 else p) for p in params[:3]]
                suffix = f"+{len(params)-3}" if len(params) > 3 else ""
                return f"[cyan]{', '.join(short_list)}{suffix}[/cyan]"
        else:
            param = params
        short = param[:20] + ".." if len(param) > 20 else param
        return f"[cyan]{escape_rich(short)}[/cyan]"

    def calc_tree_depth(flow_idx, visited):
        """Calculate max depth from this flow."""
        if flow_idx in visited:
            return 0
        visited.add(flow_idx)
        edges = flow_graph.get(flow_idx, [])
        if not edges:
            return 1
        max_child_depth = 0
        for next_idx, _ in edges:
            child_depth = calc_tree_depth(next_idx, visited.copy())
            max_child_depth = max(max_child_depth, child_depth)
        return 1 + max_child_depth

    def count_tree_nodes(flow_idx, visited):
        """Count total nodes in tree."""
        if flow_idx in visited:
            return 0
        visited.add(flow_idx)
        count = 1
        for next_idx, _ in flow_graph.get(flow_idx, []):
            count += count_tree_nodes(next_idx, visited.copy())
        return count

    def normalize_api_path(url):
        """Normalize URL path by replacing ID-like segments with placeholders."""
        import re
        path = urlparse(url).path or "/"
        segments = path.split("/")
        normalized = []
        for seg in segments:
            if not seg:
                normalized.append(seg)
            elif re.match(r'^\d+$', seg):
                normalized.append("{id}")
            elif re.match(r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$', seg, re.I):
                normalized.append("{uuid}")
            elif re.match(r'^[a-zA-Z0-9_-]{20,}$', seg):
                normalized.append("{token}")
            else:
                normalized.append(seg)
        return "/".join(normalized)

    def get_api_key(flow_idx):
        """Get API key (method + normalized path) for cycle detection."""
        flow = sorted_flows[flow_idx]
        method = flow.get("method", "?")
        url = flow.get("url", "")
        return f"{method} {normalize_api_path(url)}"

    def build_tree_data(flow_idx, via_params, visited_apis, node_index_map, index_counter,
                        deferred_children, first_occurrence):
        """Build tree data structure with cycle continuation.

        Cycle detection is based on API pattern (method + normalized path), not flow_idx.
        """
        api_key = get_api_key(flow_idx)
        is_cycle = api_key in visited_apis

        # Already visited this API pattern? Return ref
        if is_cycle:
            first_idx = first_occurrence.get(api_key, flow_idx)
            target_index = node_index_map.get(first_idx, "?")
            return {"type": "ref", "target_index": target_index, "via_params": via_params, "api_key": api_key}

        # Mark this API pattern as visited
        new_visited = visited_apis | {api_key}
        first_occurrence[api_key] = flow_idx

        # Assign index
        current_index = index_counter[0]
        index_counter[0] += 1
        node_index_map[flow_idx] = current_index

        children = []
        for next_idx, next_params in flow_graph.get(flow_idx, []):
            child = build_tree_data(
                next_idx, next_params, new_visited,
                node_index_map, index_counter, deferred_children, first_occurrence
            )
            if child:
                # If child is a ref, defer its grandchildren to the cycle target
                if child.get("type") == "ref":
                    target_index = child.get("target_index")
                    target_idx = next_idx  # The skipped node's flow_idx
                    for gc_idx, gc_params in flow_graph.get(target_idx, []):
                        gc_api = get_api_key(gc_idx)
                        if gc_idx != target_idx and gc_api not in new_visited:
                            if target_index not in deferred_children:
                                deferred_children[target_index] = []
                            gc = build_tree_data(gc_idx, gc_params, new_visited, node_index_map,
                                               index_counter, deferred_children, first_occurrence)
                            if gc:
                                gc["from_cycle"] = True
                                deferred_children[target_index].append(gc)
                children.append(child)

        return {
            "flow_idx": flow_idx,
            "index": current_index,
            "via_params": via_params,
            "is_cycle": False,
            "api_key": api_key,
            "children": children,
        }

    def inject_deferred(node, deferred_children):
        """Inject deferred children into target nodes."""
        if not node or node.get("type") == "ref":
            return
        idx = node.get("index")
        if idx in deferred_children:
            node["children"].extend(deferred_children[idx])
            del deferred_children[idx]
        for child in node.get("children", []):
            inject_deferred(child, deferred_children)

    def render_tree_node(node, parent_tree, is_root=False):
        """Render tree data to Rich Tree."""
        if node.get("type") == "ref":
            target = node.get("target_index", "?")
            via = format_param(node.get("via_params")) if node.get("via_params") else ""
            parent_tree.add(f"[dim]↩ \\[#{target}] via {via} [italic](continues below)[/italic][/dim]")
            return

        flow_idx = node["flow_idx"]
        current_index = node["index"]
        via_params = node.get("via_params")
        from_cycle = node.get("from_cycle", False)
        children = node.get("children", [])

        # Build label
        from_cycle_mark = "[bold yellow]↳[/bold yellow] " if from_cycle else ""
        index_label = f"[bold green]\\[#{current_index}][/bold green]"

        if via_params and not is_root:
            label = f"{from_cycle_mark}{index_label} [yellow]→[/yellow] {format_param(via_params)} [yellow]→[/yellow] {format_api(flow_idx)}"
        else:
            label = f"{from_cycle_mark}{index_label} {format_api(flow_idx)}"

        if children:
            child_node = parent_tree.add(label)
            for child in children:
                render_tree_node(child, child_node)
        else:
            parent_tree.add(label)

    # Find root candidates (flows that produce params used by others)
    # and rank by tree size/depth
    root_candidates = []
    for flow_idx in flow_produces.keys():
        if flow_graph.get(flow_idx):  # Has outgoing edges
            depth = calc_tree_depth(flow_idx, set())
            nodes = count_tree_nodes(flow_idx, set())
            if depth >= min_depth:
                # Score: prioritize depth, then breadth
                score = depth * 100 + nodes
                root_candidates.append((score, depth, nodes, flow_idx))

    root_candidates.sort(key=lambda x: x[0], reverse=True)

    # Deduplicate: remove roots that are subtrees of higher-ranked roots
    covered_flows = set()
    selected_roots = []

    for score, depth, nodes, flow_idx in root_candidates:
        if flow_idx not in covered_flows:
            selected_roots.append((score, depth, nodes, flow_idx))
            # Mark all flows in this tree as covered
            def mark_covered(idx, visited):
                if idx in visited:
                    return
                visited.add(idx)
                covered_flows.add(idx)
                for next_idx, _ in flow_graph.get(idx, []):
                    mark_covered(next_idx, visited)
            mark_covered(flow_idx, set())

            if len(selected_roots) >= top:
                break

    if not selected_roots:
        console.print("[yellow]No parameter chains found.[/yellow]")
        console.print(f"[dim]Try lowering --min-depth (current: {min_depth})[/dim]")
        return

    console.print()
    console.print("[bold blue]Parameter Chain Trees[/bold blue]")
    console.print("[dim]Showing parameter flow from API responses to subsequent requests[/dim]")
    console.print()

    for rank, (score, depth, nodes, root_idx) in enumerate(selected_roots, 1):
        # Initialize tracking for this tree
        node_index_map = {}
        index_counter = [1]
        deferred_children = {}
        visited_apis = set()
        first_occurrence = {}

        # Build tree data with cycle continuation
        tree_data = build_tree_data(root_idx, None, visited_apis, node_index_map, index_counter,
                                   deferred_children, first_occurrence)

        # Inject deferred children into their targets
        inject_deferred(tree_data, deferred_children)

        # Create Rich Tree for display
        # Note: \[ escapes the bracket in Rich markup to display literal [#N]
        tree = Tree(
            f"[bold yellow]#{rank}[/bold yellow] [bold green]\\[#1][/bold green] {format_api(root_idx)} "
            f"[dim](depth:{depth}, nodes:{nodes})[/dim]"
        )

        # Render children to Rich Tree
        for child in tree_data.get("children", []):
            render_tree_node(child, tree)

        console.print(tree)
        console.print()

    # Summary
    total_roots = len([r for r in root_candidates if r[1] >= min_depth])
    console.print(f"[dim]Showing {len(selected_roots)} of {total_roots} root chains (min depth: {min_depth})[/dim]")
    if selected_roots:
        max_depth = max(d for _, d, _, _ in selected_roots)
        max_nodes = max(n for _, _, n, _ in selected_roots)
        console.print(f"[dim]Max depth: {max_depth}, Max nodes: {max_nodes}[/dim]")

    # HTML export
    if html_output:
        _export_chain_html(html_output, sorted_flows, flow_graph, flow_produces, selected_roots)
        console.print(f"\n[green]HTML exported to:[/green] {html_output}")


@main.command()
@click.argument("report_file", default="id_tracker_report.json", type=click.Path(exists=True))
@click.option("--output", "-o", default=None, help="Output HTML file (default: based on section)")
@click.option("--section", "-s", type=click.Choice(["all", "tree", "trace", "timeline"]), default="all",
              help="Section to export: tree (ID flow), trace (API transitions), timeline (flow table), or all")
def export(report_file, output, section):
    """Export report as HTML with interactive tree visualization.

    Sections:
      tree     - ID Flow Tree (origin → usage by ID)
      trace    - API Trace (ID transitions between API calls)
      timeline - Flow Timeline (request/response table)
      all      - All sections in one file
    """
    import json
    from datetime import datetime
    import html as html_module

    # Default output filename based on section
    if output is None:
        if section == "all":
            output = "id_report.html"
        else:
            output = f"id_report_{section}.html"
    from urllib.parse import urlparse

    with open(report_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    tracked_ids = data.get("tracked_ids", {})
    potential_idor = data.get("potential_idor", [])
    potential_idor_values = {item["id_value"] for item in potential_idor}
    flows = data.get("flows", [])
    summary = data.get("summary", {})

    def esc(s):
        return html_module.escape(str(s))

    def extract_domain(url):
        """Extract domain from URL."""
        try:
            parsed = urlparse(url)
            return parsed.netloc or ""
        except:
            return ""

    def get_base_domain(domain):
        """Get base domain (e.g., api.example.com -> example.com)."""
        parts = domain.split(".")
        if len(parts) >= 2:
            return ".".join(parts[-2:])
        return domain

    # Collect all unique domains from tracked IDs
    all_domains = set()
    for id_value, info in tracked_ids.items():
        origin = info.get("origin")
        if origin and origin.get("url"):
            domain = extract_domain(origin["url"])
            if domain:
                all_domains.add(domain)
        for usage in info.get("usages", []):
            if usage.get("url"):
                domain = extract_domain(usage["url"])
                if domain:
                    all_domains.add(domain)

    # Also collect from flows
    for flow in flows:
        if flow.get("url"):
            domain = extract_domain(flow["url"])
            if domain:
                all_domains.add(domain)

    sorted_domains = sorted(all_domains)

    # Build ID tree HTML
    id_trees = []
    sorted_ids = sorted(tracked_ids.items(), key=lambda x: x[1].get("first_seen", ""))

    for id_value, info in sorted_ids:
        is_idor = id_value in potential_idor_values
        id_type_str = info.get("type", "unknown")
        origin = info.get("origin")
        usages = info.get("usages", [])

        idor_class = "idor" if is_idor else ""
        idor_badge = '<span class="badge idor-badge">IDOR</span>' if is_idor else ""

        children = []

        # Origin
        if origin:
            method = origin.get("method", "?")
            url = origin.get("url", "?")
            location = origin.get("location", "?")
            field = origin.get("field_name") or origin.get("field") or ""
            timestamp = origin.get("timestamp", "")
            time_part = timestamp.split("T")[1][:8] if "T" in timestamp else ""
            domain = extract_domain(url)

            # Field name as prominent badge if exists
            field_html = f'<span class="field-name">{esc(field)}</span>' if field else ''
            loc_html = f'<span class="location-type">{esc(location)}</span>'

            children.append(f'''
                <li class="origin" data-domain="{esc(domain)}" data-base-domain="{esc(get_base_domain(domain))}">
                    <span class="label origin-label">ORIGIN</span>
                    <span class="method">{esc(method)}</span>
                    <span class="url" title="{esc(url)}">{esc(url[:60] + '...' if len(url) > 60 else url)}</span>
                    <span class="location-info">→ {loc_html}{field_html}</span>
                    {f'<span class="time">({time_part})</span>' if time_part else ''}
                </li>
            ''')
        else:
            children.append('<li class="no-origin">No origin (not seen in response)</li>')

        # Usages
        for i, usage in enumerate(usages, 1):
            method = usage.get("method", "?")
            url = usage.get("url", "?")
            location = usage.get("location", "?")
            field = usage.get("field_name") or usage.get("field") or ""
            timestamp = usage.get("timestamp", "")
            time_part = timestamp.split("T")[1][:8] if "T" in timestamp else ""
            domain = extract_domain(url)

            # Field name as prominent badge if exists
            field_html = f'<span class="field-name">{esc(field)}</span>' if field else ''
            loc_html = f'<span class="location-type">{esc(location)}</span>'

            children.append(f'''
                <li class="usage" data-domain="{esc(domain)}" data-base-domain="{esc(get_base_domain(domain))}">
                    <span class="label usage-label">USAGE {i}</span>
                    <span class="method">{esc(method)}</span>
                    <span class="url" title="{esc(url)}">{esc(url[:60] + '...' if len(url) > 60 else url)}</span>
                    <span class="location-info">→ {loc_html}{field_html}</span>
                    {f'<span class="time">({time_part})</span>' if time_part else ''}
                </li>
            ''')

        if not usages:
            children.append('<li class="no-usage">No usage (not seen in request)</li>')

        # Collect domains for this ID tree
        tree_domains = set()
        tree_base_domains = set()
        if origin and origin.get("url"):
            d = extract_domain(origin["url"])
            if d:
                tree_domains.add(d)
                tree_base_domains.add(get_base_domain(d))
        for usage in usages:
            if usage.get("url"):
                d = extract_domain(usage["url"])
                if d:
                    tree_domains.add(d)
                    tree_base_domains.add(get_base_domain(d))

        id_trees.append(f'''
            <details class="id-tree {idor_class}" open data-domains="{esc(','.join(tree_domains))}" data-base-domains="{esc(','.join(tree_base_domains))}">
                <summary>
                    <code class="id-value">{esc(id_value)}</code>
                    <span class="id-type">({id_type_str})</span>
                    {idor_badge}
                </summary>
                <ul class="tree-children">
                    {''.join(children)}
                </ul>
            </details>
        ''')

    # Build flow table
    flow_rows = []
    for i, flow in enumerate(flows[:100], 1):
        method = flow.get("method", "?")
        url = flow.get("url", "?")
        req_ids = flow.get("request_ids", [])
        res_ids = flow.get("response_ids", [])

        req_badges = ''.join(f'<span class="id-badge req">{esc(r["value"][:12])}</span>' for r in req_ids[:3])
        if len(req_ids) > 3:
            req_badges += f'<span class="more">+{len(req_ids)-3}</span>'

        res_badges = ''.join(f'<span class="id-badge res">{esc(r["value"][:12])}</span>' for r in res_ids[:3])
        if len(res_ids) > 3:
            res_badges += f'<span class="more">+{len(res_ids)-3}</span>'

        flow_rows.append(f'''
            <tr>
                <td>{i}</td>
                <td><span class="method-badge">{esc(method)}</span></td>
                <td class="url-cell" title="{esc(url)}">{esc(url[:50] + '...' if len(url) > 50 else url)}</td>
                <td>{req_badges or '-'}</td>
                <td>{res_badges or '-'}</td>
            </tr>
        ''')

    # Build API Trace (ID transition tree)
    sorted_flows = sorted(flows, key=lambda x: x.get("timestamp", ""))

    # Build transition map: response ID -> subsequent request usages
    id_to_subsequent_usage = {}
    for i, flow in enumerate(sorted_flows):
        for req_id in flow.get("request_ids", []):
            id_val = req_id["value"]
            if id_val not in id_to_subsequent_usage:
                id_to_subsequent_usage[id_val] = []
            id_to_subsequent_usage[id_val].append({
                "flow_idx": i,
                "location": req_id.get("location", "?"),
                "field": req_id.get("field"),
            })

    # Build origin map: which response first produced each ID (backward tracking)
    id_to_origin_html = {}
    for i, flow in enumerate(sorted_flows):
        for res_id in flow.get("response_ids", []):
            id_val = res_id["value"]
            if id_val not in id_to_origin_html:  # First occurrence only
                id_to_origin_html[id_val] = {
                    "flow_idx": i,
                    "location": res_id.get("location", "?"),
                    "field": res_id.get("field"),
                    "method": flow.get("method", "?"),
                    "url": flow.get("url", "?"),
                    "timestamp": flow.get("timestamp", ""),
                }

    def format_trace_id(id_info, is_idor=False):
        """Format ID for trace display."""
        id_val = id_info["value"]
        id_type = id_info.get("type", "?")
        location = id_info.get("location", "?")
        field = id_info.get("field")
        display_val = id_val[:16] + "..." if len(id_val) > 16 else id_val

        idor_class = "idor" if is_idor else ""
        field_html = f'<span class="trace-field">{esc(field)}</span>' if field else ''

        return f'''<span class="trace-id {idor_class}">
            <code>{esc(display_val)}</code>
            <span class="trace-id-type">({id_type})</span>
            <span class="trace-loc">{esc(location)}</span>{field_html}
        </span>'''

    api_trace_items = []
    shown_as_child = set()

    for i, flow in enumerate(sorted_flows[:50]):  # Limit to 50 for performance
        if i in shown_as_child:
            continue

        method = flow.get("method", "?")
        url = flow.get("url", "?")
        timestamp = flow.get("timestamp", "")
        time_part = timestamp.split("T")[1][:8] if "T" in timestamp else ""
        request_ids = flow.get("request_ids", [])
        response_ids = flow.get("response_ids", [])

        short_url = url[:50] + "..." if len(url) > 50 else url

        # Build request IDs HTML with origin tracking
        req_html = ""
        if request_ids:
            req_items = []
            for req_id in request_ids[:10]:
                id_val = req_id["value"]
                is_idor = id_val in potential_idor_values
                id_html = format_trace_id(req_id, is_idor)

                # Check for origin (where this ID came from)
                origin_html = ""
                if id_val in id_to_origin_html:
                    origin = id_to_origin_html[id_val]
                    origin_idx = origin["flow_idx"]
                    if origin_idx < i:  # Only show if from a previous flow
                        origin_method = origin["method"]
                        origin_url = origin["url"]
                        origin_short_url = origin_url[:35] + "..." if len(origin_url) > 35 else origin_url
                        origin_loc = origin["location"]
                        if origin["field"]:
                            origin_loc += f".{origin['field']}"
                        origin_html = f'''
                            <div class="trace-origin">
                                <span class="trace-arrow-back">←</span>
                                <span class="trace-origin-label">from</span>
                                <span class="method-badge">{esc(origin_method)}</span>
                                <span class="trace-origin-url" title="{esc(origin_url)}">{esc(origin_short_url)}</span>
                                <span class="trace-at">@ {esc(origin_loc)}</span>
                            </div>
                        '''

                req_items.append(f'<li>{id_html}{origin_html}</li>')

            if len(request_ids) > 10:
                req_items.append(f'<li class="more">+{len(request_ids) - 10} more</li>')
            req_html = f'<div class="trace-section req"><span class="trace-label">REQ</span><ul>{"".join(req_items)}</ul></div>'

        # Build response IDs HTML with transitions
        res_html = ""
        if response_ids:
            res_items = []
            for res_id in response_ids[:15]:
                id_val = res_id["value"]
                is_idor = id_val in potential_idor_values
                id_html = format_trace_id(res_id, is_idor)

                # Check for transitions
                transitions_html = ""
                if id_val in id_to_subsequent_usage:
                    trans_items = []
                    for usage in id_to_subsequent_usage[id_val]:
                        next_idx = usage["flow_idx"]
                        if next_idx <= i:
                            continue
                        shown_as_child.add(next_idx)
                        next_flow = sorted_flows[next_idx]
                        next_method = next_flow.get("method", "?")
                        next_url = next_flow.get("url", "?")
                        next_short_url = next_url[:35] + "..." if len(next_url) > 35 else next_url
                        next_time = next_flow.get("timestamp", "").split("T")[1][:8] if "T" in next_flow.get("timestamp", "") else ""

                        loc_str = usage["location"]
                        if usage["field"]:
                            loc_str += f".{usage['field']}"

                        # Get response IDs from the transitioned flow
                        next_res_ids = next_flow.get("response_ids", [])
                        next_res_html = ""
                        if next_res_ids:
                            next_res_items = ''.join(
                                f'<span class="trace-next-id">{format_trace_id(nr, nr["value"] in potential_idor_values)}</span>'
                                for nr in next_res_ids[:3]
                            )
                            if len(next_res_ids) > 3:
                                next_res_items += f'<span class="more">+{len(next_res_ids) - 3}</span>'
                            next_res_html = f'<div class="trace-next-res">→ {next_res_items}</div>'

                        trans_items.append(f'''
                            <div class="trace-transition">
                                <span class="trace-arrow">→</span>
                                <span class="trace-next-api">
                                    <span class="method-badge">{esc(next_method)}</span>
                                    <span class="trace-next-url" title="{esc(next_url)}">{esc(next_short_url)}</span>
                                    <span class="trace-time">{next_time}</span>
                                    <span class="trace-at">@ {esc(loc_str)}</span>
                                </span>
                                {next_res_html}
                            </div>
                        ''')

                    if trans_items:
                        transitions_html = f'<div class="trace-transitions">{"".join(trans_items[:5])}</div>'
                        if len(trans_items) > 5:
                            transitions_html += f'<div class="more">+{len(trans_items) - 5} more transitions</div>'

                res_items.append(f'<li>{id_html}{transitions_html}</li>')

            if len(response_ids) > 15:
                res_items.append(f'<li class="more">+{len(response_ids) - 15} more</li>')
            res_html = f'<div class="trace-section res"><span class="trace-label">RES</span><ul>{"".join(res_items)}</ul></div>'

        api_trace_items.append(f'''
            <details class="api-trace-item" open>
                <summary>
                    <span class="method-badge">{esc(method)}</span>
                    <span class="trace-url" title="{esc(url)}">{esc(short_url)}</span>
                    <span class="trace-time">{time_part}</span>
                </summary>
                <div class="trace-body">
                    {req_html}
                    {res_html}
                </div>
            </details>
        ''')

    # Build section HTML blocks
    section_titles = {
        "tree": "ID Flow Tree",
        "trace": "API Trace",
        "timeline": "Flow Timeline",
        "all": "ID Tracking Report",
    }

    tree_section_html = f'''
        <h2>ID Flow Tree</h2>
        <div class="filter-bar">
            <label>Filter:</label>
            <input type="text" id="search" placeholder="Search ID..." oninput="filterIDs()">
            <select id="typeFilter" onchange="filterIDs()">
                <option value="all">All Types</option>
                <option value="numeric">Numeric</option>
                <option value="uuid">UUID</option>
                <option value="token">Token</option>
            </select>
            <select id="domainFilter" onchange="filterIDs()">
                <option value="all">All Domains</option>
                {''.join(f'<option value="{esc(d)}">{esc(d)}</option>' for d in sorted_domains)}
            </select>
            <label><input type="checkbox" id="includeSubdomains" onchange="filterIDs()" checked> Include Subdomains</label>
            <label><input type="checkbox" id="idorOnly" onchange="filterIDs()"> IDOR Only</label>
            <button onclick="toggleAll(true)">Expand All</button>
            <button onclick="toggleAll(false)">Collapse All</button>
        </div>
        <div id="id-trees">
            {''.join(id_trees)}
        </div>
    '''

    trace_section_html = f'''
        <h2>API Trace (ID Transitions)</h2>
        <p style="color: #888; margin-bottom: 15px;">Shows how IDs flow from API responses to subsequent requests. Click to expand/collapse.</p>
        <div id="api-trace">
            {''.join(api_trace_items)}
        </div>
        {f'<p style="color: #666; text-align: center;">Showing first 50 of {len(sorted_flows)} API calls</p>' if len(sorted_flows) > 50 else ''}
    '''

    timeline_section_html = f'''
        <h2>Flow Timeline</h2>
        <table class="flow-table">
            <thead>
                <tr>
                    <th>#</th>
                    <th>Method</th>
                    <th>URL</th>
                    <th>Request IDs</th>
                    <th>Response IDs</th>
                </tr>
            </thead>
            <tbody>
                {''.join(flow_rows)}
            </tbody>
        </table>
        {f'<p style="color: #666; text-align: center;">Showing first 100 of {len(flows)} flows</p>' if len(flows) > 100 else ''}
    '''

    # Select sections based on parameter
    if section == "tree":
        body_sections = tree_section_html
    elif section == "trace":
        body_sections = trace_section_html
    elif section == "timeline":
        body_sections = timeline_section_html
    else:  # all
        body_sections = tree_section_html + trace_section_html + timeline_section_html

    # Only include tree-specific JS if tree section is included
    tree_js = '''
        function getBaseDomain(domain) {
            const parts = domain.split('.');
            if (parts.length >= 2) {
                return parts.slice(-2).join('.');
            }
            return domain;
        }

        function filterIDs() {
            const search = document.getElementById('search').value.toLowerCase();
            const typeFilter = document.getElementById('typeFilter').value;
            const domainFilter = document.getElementById('domainFilter').value;
            const includeSubdomains = document.getElementById('includeSubdomains').checked;
            const idorOnly = document.getElementById('idorOnly').checked;

            document.querySelectorAll('.id-tree').forEach(tree => {
                const idValue = tree.querySelector('.id-value').textContent.toLowerCase();
                const idType = tree.querySelector('.id-type').textContent;
                const isIdor = tree.classList.contains('idor');
                const treeDomains = (tree.dataset.domains || '').split(',').filter(d => d);
                const treeBaseDomains = (tree.dataset.baseDomains || '').split(',').filter(d => d);

                let show = true;
                if (search && !idValue.includes(search)) show = false;
                if (typeFilter !== 'all' && !idType.includes(typeFilter)) show = false;
                if (idorOnly && !isIdor) show = false;

                // Domain filtering
                if (domainFilter !== 'all') {
                    if (includeSubdomains) {
                        const filterBaseDomain = getBaseDomain(domainFilter);
                        const hasMatchingDomain = treeBaseDomains.some(bd => bd === filterBaseDomain) ||
                                                   treeDomains.some(d => d === domainFilter || d.endsWith('.' + domainFilter));
                        if (!hasMatchingDomain) show = false;
                    } else {
                        if (!treeDomains.includes(domainFilter)) show = false;
                    }
                }

                tree.style.display = show ? 'block' : 'none';
            });
        }

        function toggleAll(open) {
            document.querySelectorAll('.id-tree').forEach(tree => {
                tree.open = open;
            });
        }
    ''' if section in ("tree", "all") else ''

    html_content = f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>idotaku - {section_titles[section]}</title>
    <style>
        * {{ box-sizing: border-box; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: #1a1a2e;
            color: #eee;
            margin: 0;
            padding: 20px;
            line-height: 1.6;
        }}
        .container {{ max-width: 1200px; margin: 0 auto; }}
        h1 {{ color: #00d9ff; border-bottom: 2px solid #00d9ff; padding-bottom: 10px; }}
        h2 {{ color: #ff6b6b; margin-top: 30px; }}

        /* Summary Cards */
        .summary {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
            gap: 15px;
            margin: 20px 0;
        }}
        .card {{
            background: #16213e;
            padding: 20px;
            border-radius: 10px;
            text-align: center;
        }}
        .card.danger {{ background: #4a1942; border: 2px solid #ff6b6b; }}
        .card-value {{ font-size: 2em; font-weight: bold; color: #00d9ff; }}
        .card.danger .card-value {{ color: #ff6b6b; }}
        .card-label {{ color: #888; font-size: 0.9em; }}

        /* ID Trees */
        .id-tree {{
            background: #16213e;
            border-radius: 8px;
            margin: 10px 0;
            overflow: hidden;
        }}
        .id-tree.idor {{ border-left: 4px solid #ff6b6b; }}
        .id-tree summary {{
            padding: 12px 15px;
            cursor: pointer;
            display: flex;
            align-items: center;
            gap: 10px;
            background: #1f2b47;
        }}
        .id-tree summary:hover {{ background: #2a3a5e; }}
        .id-value {{ color: #00d9ff; font-size: 1.1em; }}
        .id-tree.idor .id-value {{ color: #ff6b6b; }}
        .id-type {{ color: #888; }}
        .badge {{ padding: 2px 8px; border-radius: 4px; font-size: 0.75em; font-weight: bold; }}
        .idor-badge {{ background: #ff6b6b; color: #fff; }}

        .tree-children {{
            list-style: none;
            margin: 0;
            padding: 0 15px 15px 30px;
        }}
        .tree-children li {{
            padding: 8px 12px;
            margin: 5px 0;
            border-left: 2px solid #333;
            background: #0f1729;
            border-radius: 0 6px 6px 0;
            display: flex;
            flex-wrap: wrap;
            align-items: center;
            gap: 8px;
        }}
        .tree-children li.origin {{ border-left-color: #4ade80; }}
        .tree-children li.usage {{ border-left-color: #fbbf24; }}
        .tree-children li.no-origin {{ border-left-color: #ff6b6b; color: #ff6b6b; font-style: italic; }}
        .tree-children li.no-usage {{ color: #666; font-style: italic; }}

        .label {{
            padding: 2px 6px;
            border-radius: 3px;
            font-size: 0.75em;
            font-weight: bold;
        }}
        .origin-label {{ background: #166534; color: #4ade80; }}
        .usage-label {{ background: #78350f; color: #fbbf24; }}
        .method {{ font-weight: bold; color: #a78bfa; }}
        .url {{ color: #94a3b8; font-size: 0.9em; word-break: break-all; }}
        .location-info {{ display: flex; align-items: center; gap: 4px; }}
        .location-type {{ color: #67e8f9; font-style: italic; }}
        .field-name {{
            background: #7c3aed;
            color: #fff;
            padding: 2px 8px;
            border-radius: 4px;
            font-family: monospace;
            font-size: 0.85em;
            font-weight: bold;
            margin-left: 4px;
        }}
        .tree-children li.origin .field-name {{ background: #15803d; }}
        .tree-children li.usage .field-name {{ background: #b45309; }}
        .time {{ color: #666; font-size: 0.85em; }}

        /* Flow Table */
        .flow-table {{
            width: 100%;
            border-collapse: collapse;
            margin-top: 15px;
            font-size: 0.9em;
        }}
        .flow-table th {{
            background: #1f2b47;
            padding: 12px;
            text-align: left;
            color: #00d9ff;
        }}
        .flow-table td {{
            padding: 10px 12px;
            border-bottom: 1px solid #2a3a5e;
        }}
        .flow-table tr:hover {{ background: #1f2b47; }}
        .url-cell {{ max-width: 300px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; color: #94a3b8; }}
        .method-badge {{ background: #4c1d95; color: #c4b5fd; padding: 2px 6px; border-radius: 3px; font-weight: bold; }}
        .id-badge {{ font-family: monospace; font-size: 0.85em; padding: 2px 5px; border-radius: 3px; margin: 1px; display: inline-block; }}
        .id-badge.req {{ background: #78350f; color: #fbbf24; }}
        .id-badge.res {{ background: #166534; color: #4ade80; }}
        .more {{ color: #666; font-size: 0.85em; }}

        /* Filter */
        .filter-bar {{
            background: #16213e;
            padding: 15px;
            border-radius: 8px;
            margin-bottom: 20px;
            display: flex;
            gap: 15px;
            align-items: center;
            flex-wrap: wrap;
        }}
        .filter-bar label {{ color: #888; }}
        .filter-bar input, .filter-bar select {{
            background: #0f1729;
            border: 1px solid #333;
            color: #eee;
            padding: 8px 12px;
            border-radius: 5px;
        }}
        .filter-bar button {{
            background: #00d9ff;
            color: #000;
            border: none;
            padding: 8px 16px;
            border-radius: 5px;
            cursor: pointer;
            font-weight: bold;
        }}
        .filter-bar button:hover {{ background: #00b8d9; }}

        /* API Trace */
        .api-trace-item {{
            background: #16213e;
            border-radius: 8px;
            margin: 10px 0;
            overflow: hidden;
        }}
        .api-trace-item summary {{
            padding: 12px 15px;
            cursor: pointer;
            display: flex;
            align-items: center;
            gap: 10px;
            background: #1f2b47;
        }}
        .api-trace-item summary:hover {{ background: #2a3a5e; }}
        .trace-url {{ color: #94a3b8; font-size: 0.9em; }}
        .trace-time {{ color: #666; font-size: 0.85em; }}
        .trace-body {{ padding: 10px 15px 15px 15px; }}
        .trace-section {{ margin: 8px 0; }}
        .trace-section ul {{ list-style: none; margin: 5px 0 5px 20px; padding: 0; }}
        .trace-section li {{ margin: 4px 0; padding: 6px 10px; background: #0f1729; border-radius: 4px; }}
        .trace-section.req .trace-label {{ background: #78350f; color: #fbbf24; padding: 2px 6px; border-radius: 3px; font-size: 0.75em; font-weight: bold; }}
        .trace-section.res .trace-label {{ background: #166534; color: #4ade80; padding: 2px 6px; border-radius: 3px; font-size: 0.75em; font-weight: bold; }}
        .trace-id {{ display: inline-flex; align-items: center; gap: 6px; flex-wrap: wrap; }}
        .trace-id code {{ color: #00d9ff; font-size: 0.95em; }}
        .trace-id.idor code {{ color: #ff6b6b; }}
        .trace-id-type {{ color: #666; font-size: 0.8em; }}
        .trace-loc {{ color: #67e8f9; font-size: 0.85em; font-style: italic; }}
        .trace-field {{ background: #7c3aed; color: #fff; padding: 1px 6px; border-radius: 3px; font-family: monospace; font-size: 0.8em; }}
        .trace-transitions {{ margin-left: 20px; margin-top: 8px; border-left: 2px solid #4c1d95; padding-left: 12px; }}
        .trace-transition {{ margin: 6px 0; padding: 6px 10px; background: #1a1a3e; border-radius: 4px; }}
        .trace-arrow {{ color: #fbbf24; font-weight: bold; margin-right: 6px; }}
        .trace-next-api {{ display: inline-flex; align-items: center; gap: 8px; flex-wrap: wrap; }}
        .trace-next-url {{ color: #94a3b8; font-size: 0.85em; }}
        .trace-at {{ color: #67e8f9; font-size: 0.8em; }}
        .trace-next-res {{ margin-top: 4px; margin-left: 20px; padding: 4px 8px; background: #0f1729; border-radius: 4px; display: flex; flex-wrap: wrap; gap: 8px; align-items: center; }}
        .trace-next-id {{ display: inline-flex; align-items: center; gap: 4px; }}
        .more {{ color: #666; font-size: 0.85em; font-style: italic; }}

        /* Origin tracking (backward trace for REQ IDs) */
        .trace-origin {{ margin-top: 6px; margin-left: 16px; padding: 4px 10px; background: #1e293b; border-left: 2px solid #3b82f6; border-radius: 0 4px 4px 0; display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }}
        .trace-arrow-back {{ color: #3b82f6; font-weight: bold; }}
        .trace-origin-label {{ color: #94a3b8; font-size: 0.85em; }}
        .trace-origin-url {{ color: #94a3b8; font-size: 0.85em; }}

        footer {{ margin-top: 40px; text-align: center; color: #666; font-size: 0.9em; }}
        footer a {{ color: #00d9ff; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>idotaku {section_titles[section]}</h1>
        <p style="color: #666;">Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>

        <div class="summary">
            <div class="card">
                <div class="card-value">{summary.get('total_unique_ids', 0)}</div>
                <div class="card-label">Unique IDs</div>
            </div>
            <div class="card">
                <div class="card-value">{summary.get('ids_with_origin', 0)}</div>
                <div class="card-label">With Origin</div>
            </div>
            <div class="card">
                <div class="card-value">{summary.get('ids_with_usage', 0)}</div>
                <div class="card-label">With Usage</div>
            </div>
            <div class="card">
                <div class="card-value">{summary.get('total_flows', 0)}</div>
                <div class="card-label">Total Flows</div>
            </div>
            <div class="card danger">
                <div class="card-value">{len(potential_idor)}</div>
                <div class="card-label">Potential IDOR</div>
            </div>
        </div>

        {body_sections}

        <footer>
            Generated by <a href="https://github.com/yourname/idotaku">idotaku</a>
        </footer>
    </div>

    <script>
        {tree_js}
    </script>
</body>
</html>
'''

    with open(output, "w", encoding="utf-8") as f:
        f.write(html_content)

    console.print(f"[green]Report exported to:[/green] {output}")


@main.command()
def version():
    """Show version."""
    from idotaku import __version__
    console.print(f"idotaku {__version__}")


if __name__ == "__main__":
    main()
