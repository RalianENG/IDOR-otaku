"""Interactive command - launch interactive mode."""

import click


@click.command("interactive")
def interactive():
    """Launch interactive mode with guided menus.

    Use arrow keys to navigate, Enter to select.
    """
    from ..interactive import run_interactive_mode
    run_interactive_mode()
