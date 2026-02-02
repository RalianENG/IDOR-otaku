"""Report command - view ID tracking report summary."""

import click
from rich.console import Console
from rich.table import Table

from ..report import load_report

console = Console()


@click.command()
@click.argument("report_file", default="id_tracker_report.json", type=click.Path(exists=True))
def report(report_file):
    """View ID tracking report."""
    data = load_report(report_file)

    summary = data.summary
    console.print()
    console.print("[bold blue]ID Tracker Report[/bold blue]")
    console.print(f"  Total unique IDs: [green]{summary.total_unique_ids}[/green]")
    console.print(f"  IDs with origin: [green]{summary.ids_with_origin}[/green]")
    console.print(f"  IDs with usage: [green]{summary.ids_with_usage}[/green]")
    console.print()

    # Potential IDOR table
    potential_idor = data.potential_idor
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
