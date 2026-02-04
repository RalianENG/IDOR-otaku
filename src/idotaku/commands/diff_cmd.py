"""Diff analysis command."""

import json

import click
from rich.console import Console

from ..report import load_report
from ..report.diff import diff_reports, diff_to_dict

console = Console()


@click.command("diff")
@click.argument("report_a", type=click.Path(exists=True))
@click.argument("report_b", type=click.Path(exists=True))
@click.option("--json-output", "-o", default=None, help="Export diff as JSON file")
def diff(report_a, report_b, json_output):
    """Compare two reports to see what changed.

    REPORT_A is the 'before' report, REPORT_B is the 'after' report.
    Shows new/removed IDOR candidates, tracked IDs, and flow count changes.
    """
    data_a = load_report(report_a)
    data_b = load_report(report_b)

    result = diff_reports(data_a, data_b)

    if not result.has_changes:
        console.print("[green]No changes between reports.[/green]")
        return

    console.print("[bold blue]Report Diff[/bold blue]")
    console.print(f"[dim]A: {report_a}[/dim]")
    console.print(f"[dim]B: {report_b}[/dim]")
    console.print()

    # Flow/ID count changes
    flow_delta = result.flow_count_b - result.flow_count_a
    id_delta = result.id_count_b - result.id_count_a
    console.print(f"  Flows: {result.flow_count_a} -> {result.flow_count_b} ({flow_delta:+d})")
    console.print(f"  IDs:   {result.id_count_a} -> {result.id_count_b} ({id_delta:+d})")
    console.print()

    # New IDOR findings
    if result.new_idor:
        console.print(f"[bold red]+ {len(result.new_idor)} New IDOR Candidate(s)[/bold red]")
        for item in result.new_idor:
            console.print(f"  [red]+[/red] {item['id_value']} ({item['id_type']})")
        console.print()

    # Removed IDOR findings
    if result.removed_idor:
        console.print(f"[bold green]- {len(result.removed_idor)} Removed IDOR Candidate(s)[/bold green]")
        for item in result.removed_idor:
            console.print(f"  [green]-[/green] {item['id_value']} ({item['id_type']})")
        console.print()

    # New/removed tracked IDs
    if result.new_ids:
        console.print(f"[dim]+ {len(result.new_ids)} new tracked ID(s)[/dim]")
    if result.removed_ids:
        console.print(f"[dim]- {len(result.removed_ids)} removed tracked ID(s)[/dim]")

    # JSON export
    if json_output:
        diff_dict = diff_to_dict(result)
        with open(json_output, "w", encoding="utf-8") as f:
            json.dump(diff_dict, f, indent=2, ensure_ascii=False)
        console.print(f"\n[green]Diff exported to:[/green] {json_output}")
