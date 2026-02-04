"""HAR import command."""

import click
from rich.console import Console

from ..import_har import import_har_to_file
from ..config import load_config

console = Console()


@click.command("import-har")
@click.argument("har_file", type=click.Path(exists=True))
@click.option("--output", "-o", default="id_tracker_report.json", help="Output report file")
@click.option("--config", "-c", default=None, help="Config file path (idotaku.yaml)")
def har_import(har_file, output, config):
    """Import a HAR file and generate an idotaku report.

    Analyzes HTTP traffic captured by browsers (DevTools) or tools like
    Burp Suite. Produces the same JSON report format as the proxy tracker.
    """
    cfg = load_config(config)
    try:
        report = import_har_to_file(har_file, output, cfg)
    except ValueError as e:
        console.print(f"[red]Error:[/red] {e}")
        return

    summary = report.get("summary", {})
    console.print(f"[green]Report generated:[/green] {output}")
    console.print(f"  Flows: {summary.get('total_flows', 0)}")
    console.print(f"  Unique IDs: {summary.get('total_unique_ids', 0)}")
    console.print(f"  Potential IDOR: {len(report.get('potential_idor', []))}")
