"""Auth context analysis command."""

import click
from rich.console import Console
from rich.table import Table

from ..report import load_report
from ..report.auth_analysis import detect_cross_user_access

console = Console()


@click.command("auth")
@click.argument("report_file", default="id_tracker_report.json", type=click.Path(exists=True))
def auth(report_file):
    """Analyze authentication context and cross-user access patterns.

    Detects cases where different auth tokens (users) access the same
    resource with the same ID - a strong indicator of IDOR vulnerability.
    """
    data = load_report(report_file)

    if not data.flows:
        console.print("[yellow]No flows found in report.[/yellow]")
        return

    # Check if any flows have auth context
    flows_with_auth = [f for f in data.flows if f.get("auth_context")]
    if not flows_with_auth:
        console.print("[yellow]No authentication context found in flows.[/yellow]")
        console.print("[dim]Auth context is captured during proxy tracking.[/dim]")
        console.print("[dim]Make sure requests include Authorization headers or session cookies.[/dim]")
        return

    console.print(f"[dim]{len(flows_with_auth)}/{len(data.flows)} flows have auth context[/dim]")

    # Detect cross-user access
    cross_user = detect_cross_user_access(data.flows)

    if not cross_user:
        console.print("[green]No cross-user access patterns detected.[/green]")
        return

    console.print(f"\n[bold red]Cross-User Access Detected: {len(cross_user)} case(s)[/bold red]")

    table = Table()
    table.add_column("ID Value", style="cyan")
    table.add_column("URL Pattern")
    table.add_column("Auth Tokens", style="yellow")
    table.add_column("Flows", style="dim")

    for ca in cross_user:
        table.add_row(
            ca.id_value[:30],
            ca.url_pattern[:50],
            ", ".join(ca.auth_tokens),
            str(len(ca.flows)),
        )

    console.print(table)
