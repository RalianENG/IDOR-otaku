"""Version command - show version."""

import click
from rich.console import Console

console = Console()


@click.command()
def version():
    """Show version."""
    from idotaku import __version__
    console.print(f"idotaku {__version__}")
