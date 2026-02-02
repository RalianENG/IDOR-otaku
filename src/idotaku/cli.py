"""idotaku CLI entry point."""

import click

from .commands import (
    run_proxy,
    report,
    tree,
    flow,
    trace,
    sequence,
    lifeline,
    graph,
    chain,
    export,
    version,
    interactive,
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
main.add_command(tree)
main.add_command(flow)
main.add_command(trace)
main.add_command(sequence)
main.add_command(lifeline)
main.add_command(graph)
main.add_command(chain)
main.add_command(export)
main.add_command(version)
main.add_command(interactive)


if __name__ == "__main__":
    main()
