"""SARIF export command."""

import click
from rich.console import Console

from ..report import load_report
from ..export.sarif_exporter import export_sarif

console = Console()


@click.command("sarif")
@click.argument("report_file", default="id_tracker_report.json", type=click.Path(exists=True))
@click.option("--output", "-o", default="idotaku.sarif.json", help="Output SARIF file path")
def sarif_export(report_file, output):
    """Export IDOR findings to SARIF format.

    Generates a SARIF 2.1.0 file for GitHub Code Scanning and other
    SARIF-compatible security tools.
    """
    data = load_report(report_file)
    export_sarif(output, data)

    finding_count = len(data.potential_idor)
    console.print(f"[green]SARIF exported to:[/green] {output}")
    console.print(f"[dim]{finding_count} finding(s) exported[/dim]")
