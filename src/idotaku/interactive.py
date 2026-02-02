"""Interactive CLI prompts for idotaku."""

from pathlib import Path
from collections import Counter

import questionary
from questionary import Style

from .utils import extract_domain


# Custom style for prompts
STYLE = Style([
    ("qmark", "fg:cyan bold"),
    ("question", "bold"),
    ("answer", "fg:cyan"),
    ("pointer", "fg:cyan bold"),
    ("highlighted", "fg:cyan bold"),
    ("selected", "fg:green"),
    ("separator", "fg:gray"),
    ("instruction", "fg:gray italic"),
])


COMMANDS = [
    {"value": "chain", "name": "chain   - Analyze parameter chains (main flows)"},
    {"value": "tree", "name": "tree    - View ID transition tree"},
    {"value": "trace", "name": "trace   - Trace specific ID usage"},
    {"value": "report", "name": "report  - View summary report"},
    {"value": "flow", "name": "flow    - View request flows"},
    {"value": "graph", "name": "graph   - View API dependency graph"},
    {"value": "export", "name": "export  - Export to HTML"},
]


def prompt_command() -> str | None:
    """Prompt user to select a command."""
    result = questionary.select(
        "Select command:",
        choices=COMMANDS,
        style=STYLE,
        instruction="(↑/↓ to move, Enter to select, Ctrl+C to cancel)",
    ).ask()
    return result


def prompt_report_file(default: str = "id_tracker_report.json") -> str | None:
    """Prompt user to select or enter a report file."""
    # Find JSON files in current directory
    json_files = list(Path.cwd().glob("*.json"))

    if not json_files:
        # No JSON files found, ask for path
        return questionary.path(
            "Enter report file path:",
            default=default,
            style=STYLE,
        ).ask()

    # Sort by modification time (newest first)
    json_files.sort(key=lambda f: f.stat().st_mtime, reverse=True)

    # Build choices with file info
    choices = []
    for f in json_files[:10]:  # Limit to 10 files
        size = f.stat().st_size
        size_str = f"{size / 1024:.1f}KB" if size > 1024 else f"{size}B"
        choices.append({
            "value": str(f),
            "name": f"{f.name} ({size_str})",
        })

    choices.append({"value": "__other__", "name": "Other (enter path)..."})

    result = questionary.select(
        "Select report file:",
        choices=choices,
        style=STYLE,
    ).ask()

    if result == "__other__":
        return questionary.path(
            "Enter report file path:",
            default=default,
            style=STYLE,
        ).ask()

    return result


def prompt_domains(flows: list[dict], min_flows: int = 10) -> list[str] | None:
    """Prompt user to select domains to filter.

    Args:
        flows: List of flow records
        min_flows: Minimum number of flows to show a domain

    Returns:
        List of selected domains, empty list for no filter, None if cancelled
    """
    # Count domains
    domain_counts = Counter()
    for flow in flows:
        url = flow.get("url", "")
        domain = extract_domain(url)
        if domain:
            domain_counts[domain] += 1

    if len(domain_counts) <= 1:
        # Only one domain, no need to filter
        return []

    # Build choices sorted by count
    choices = []
    for domain, count in domain_counts.most_common():
        if count >= min_flows:
            choices.append({
                "value": domain,
                "name": f"{domain} ({count} flows)",
                "checked": True,  # Default to selected
            })

    if not choices:
        return []

    # Add option to skip filtering
    result = questionary.checkbox(
        f"Filter domains? ({len(domain_counts)} found, Enter to include all)",
        choices=choices,
        style=STYLE,
        instruction="(Space to toggle, Enter to confirm)",
    ).ask()

    if result is None:
        return None

    # If all selected, return empty (no filter)
    if len(result) == len(choices):
        return []

    return result


def prompt_id_value(default: str = "") -> str | None:
    """Prompt user to enter an ID value for tracing."""
    return questionary.text(
        "Enter ID value to trace:",
        default=default,
        style=STYLE,
    ).ask()


def prompt_html_output(default: str = "chain.html") -> str | None:
    """Prompt user for HTML output file path."""
    result = questionary.confirm(
        "Export to HTML?",
        default=True,
        style=STYLE,
    ).ask()

    if not result:
        return None

    return questionary.path(
        "Output file:",
        default=default,
        style=STYLE,
    ).ask()


def prompt_continue() -> bool:
    """Prompt user if they want to continue with another command."""
    return questionary.confirm(
        "Run another command?",
        default=True,
        style=STYLE,
    ).ask() or False


def run_interactive_mode():
    """Run the interactive CLI mode."""
    from rich.console import Console
    from .report import load_report

    console = Console()
    console.print()
    console.print("[bold cyan]idotaku[/bold cyan] - Interactive Mode")
    console.print("[dim]API ID tracking tool for security testing[/dim]")
    console.print()

    while True:
        # Select command
        command = prompt_command()
        if command is None:
            console.print("\n[dim]Cancelled.[/dim]")
            break

        # Select report file
        report_file = prompt_report_file()
        if report_file is None:
            console.print("\n[dim]Cancelled.[/dim]")
            break

        # Load report to get domain info
        try:
            data = load_report(report_file)
        except Exception as e:
            console.print(f"[red]Error loading report: {e}[/red]")
            continue

        if not data.flows:
            console.print("[yellow]No flows found in report.[/yellow]")
            continue

        # Build command arguments
        args = [command, report_file]

        # Domain filter for relevant commands
        if command in ("chain", "tree", "flow", "graph"):
            domains = prompt_domains(data.flows)
            if domains is None:
                console.print("\n[dim]Cancelled.[/dim]")
                break
            if domains:
                args.extend(["--domains", ",".join(domains)])

        # ID input for trace command
        if command == "trace":
            id_value = prompt_id_value()
            if id_value is None:
                console.print("\n[dim]Cancelled.[/dim]")
                break
            args.extend(["--id", id_value])

        # HTML output for chain/export
        if command in ("chain", "export"):
            html_output = prompt_html_output()
            if html_output:
                if command == "chain":
                    args.extend(["--html", html_output])
                else:
                    args.extend(["--output", html_output])

        # Execute command
        console.print()
        console.print(f"[dim]Running: idotaku {' '.join(args[1:])}[/dim]")
        console.print()

        from .cli import main
        from click.testing import CliRunner

        runner = CliRunner()
        result = runner.invoke(main, args, catch_exceptions=False)
        console.print(result.output)

        # Continue?
        console.print()
        if not prompt_continue():
            break

    console.print("\n[dim]Goodbye![/dim]")
