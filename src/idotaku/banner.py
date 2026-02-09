"""ASCII banner for idotaku CLI."""

from rich.console import Console

BANNER = r"""
   _    __     __       __
  (_)__/ /__  / /____ _/ /____ __
 / / _  / _ \/ __/ _ `/ //_/ // /
/_/\_,_/\___/\__/\_,_/_/|_|\___/
"""


def print_banner(console: Console | None = None, show_version: bool = True) -> None:
    """Print the idotaku ASCII banner."""
    if console is None:
        console = Console()

    console.print(f"[bold cyan]{BANNER}[/bold cyan]", highlight=False)

    if show_version:
        from idotaku import __version__

        console.print(f"  [dim]v{__version__} - IDOR detection tool[/dim]")
        console.print()
