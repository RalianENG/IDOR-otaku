"""Version command - show version."""

import click
from rich.console import Console

from ..banner import print_banner

console = Console()


@click.command()
def version():
    """Show version."""
    print_banner(console)
