"""CSV export command."""

from typing import Literal, cast

import click
from rich.console import Console

from ..report import load_report
from ..export.csv_exporter import export_csv

console = Console()


@click.command("csv")
@click.argument("report_file", default="id_tracker_report.json", type=click.Path(exists=True))
@click.option("--output", "-o", default=None, help="Output CSV file path")
@click.option("--mode", "-m", type=click.Choice(["idor", "flows"]), default="idor",
              help="Export mode: idor (IDOR candidates) or flows (all flows)")
def csv_export(report_file: str, output: str | None, mode: str) -> None:
    """Export report data to CSV format.

    Exports IDOR candidates or flow records as CSV for spreadsheet analysis.
    """
    data = load_report(report_file)

    if output is None:
        output = f"idotaku_{mode}.csv"

    try:
        export_csv(output, data, mode=cast(Literal["idor", "flows"], mode))
    except OSError as e:
        console.print(f"[red]Error writing CSV to {output}:[/red] {e}")
        raise SystemExit(1) from e
    console.print(f"[green]CSV exported to:[/green] {output}")
