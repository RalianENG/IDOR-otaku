"""idotaku CLI entry point."""

import click

from .commands import (
    run_proxy,
    report,
    sequence,
    lifeline,
    chain,
    version,
    interactive,
    csv_export,
    sarif_export,
    score,
    har_import,
    diff,
    auth,
    config,
)


@click.group(invoke_without_command=True)
@click.option("--port", "-p", default=8080, help="Proxy port")
@click.option("--web-port", "-w", default=8081, help="Web UI port")
@click.option("--output", "-o", default="id_tracker_report.json", help="Output report file")
@click.option("--min-numeric", default=100, help="Minimum numeric ID value to track")
@click.option("--config", "-c", default=None, help="Config file path (idotaku.yaml)")
@click.option("--no-browser", is_flag=True, help="Don't launch browser automatically")
@click.option("--browser", type=click.Choice(["chrome", "edge", "firefox", "auto"]), default="auto", help="Browser to use")
@click.option("--interactive", "-i", is_flag=True, help="Run in interactive mode")
@click.pass_context
def main(ctx, port, web_port, output, min_numeric, config, no_browser, browser, interactive):
    """idotaku - API ID tracking tool for security testing.

    Tracks ID generation and usage patterns to detect potential IDOR vulnerabilities.

    Use -i or --interactive for guided menu selection.
    """
    if ctx.invoked_subcommand is not None:
        return

    # Interactive mode
    if interactive:
        from .interactive import run_interactive_mode
        run_interactive_mode()
        return

    # Run proxy when called without subcommand
    run_proxy(port, web_port, output, min_numeric, config, no_browser, browser)


# Register commands
main.add_command(report)
main.add_command(sequence)
main.add_command(lifeline)
main.add_command(chain)
main.add_command(version)
main.add_command(interactive)
main.add_command(csv_export)
main.add_command(sarif_export)
main.add_command(score)
main.add_command(har_import)
main.add_command(diff)
main.add_command(auth)
main.add_command(config)


if __name__ == "__main__":
    main()
