"""Risk scoring command."""

import click
from rich.console import Console
from rich.table import Table

from ..report import load_report
from ..report.scoring import score_all_findings

console = Console()

LEVEL_COLORS = {
    "critical": "red",
    "high": "yellow",
    "medium": "blue",
    "low": "dim",
}


@click.command("score")
@click.argument("report_file", default="id_tracker_report.json", type=click.Path(exists=True))
@click.option("--min-score", default=0, help="Minimum risk score to show (0-100)")
@click.option("--level", "-l", type=click.Choice(["critical", "high", "medium", "low"]),
              default=None, help="Filter by risk level")
def score(report_file, min_score, level):
    """Score IDOR candidates by risk severity.

    Assigns a risk score (0-100) and level (critical/high/medium/low)
    based on HTTP method, parameter location, ID type, and usage patterns.
    """
    data = load_report(report_file)

    if not data.potential_idor:
        console.print("[green]No IDOR candidates to score.[/green]")
        return

    scored = score_all_findings(data.potential_idor)

    # Apply filters
    if min_score > 0:
        scored = [s for s in scored if s["risk_score"] >= min_score]
    if level:
        scored = [s for s in scored if s["risk_level"] == level]

    if not scored:
        console.print("[dim]No findings match the filter criteria.[/dim]")
        return

    # Display table
    table = Table(title="IDOR Risk Scores")
    table.add_column("Score", style="bold", width=6)
    table.add_column("Level", width=10)
    table.add_column("ID Value", style="cyan")
    table.add_column("Type", style="yellow")
    table.add_column("Factors", style="dim")

    for item in scored:
        color = LEVEL_COLORS.get(item["risk_level"], "white")
        table.add_row(
            str(item["risk_score"]),
            f"[{color}]{item['risk_level']}[/{color}]",
            item["id_value"][:30],
            item["id_type"],
            ", ".join(item["risk_factors"][:3]),
        )

    console.print(table)
