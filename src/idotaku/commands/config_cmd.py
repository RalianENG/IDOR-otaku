"""Config management commands."""

from __future__ import annotations

import sys
from io import StringIO
from pathlib import Path

import click
from rich.console import Console
from rich.syntax import Syntax

from ..config import (
    find_config_path,
    get_default_config_yaml,
    load_config,
    save_config_value,
    validate_config,
)

console = Console()

DEFAULT_FILENAME = "idotaku.yaml"


@click.group("config")
def config():
    """Manage idotaku configuration.

    View, create, and modify idotaku.yaml settings.
    """


@config.command()
@click.option("--force", "-f", is_flag=True, help="Overwrite existing config file")
@click.option("--filename", default=DEFAULT_FILENAME,
              help="Config filename (default: idotaku.yaml)")
def init(force, filename):
    """Create a default idotaku.yaml config file in the current directory."""
    target = Path.cwd() / filename

    if target.exists() and not force:
        console.print(f"[yellow]Config file already exists:[/yellow] {target}")
        console.print("[dim]Use --force to overwrite.[/dim]")
        return

    target.write_text(get_default_config_yaml(), encoding="utf-8")
    console.print(f"[green]Config file created:[/green] {target}")


@config.command()
@click.option("--config", "-c", "config_path", default=None, help="Config file path")
def show(config_path):
    """Show the effective configuration (defaults + config file)."""
    cfg = load_config(config_path)

    from dataclasses import asdict
    data = asdict(cfg)
    data["ignore_headers"] = sorted(data["ignore_headers"])

    from ruamel.yaml import YAML

    yaml = YAML()
    yaml.default_flow_style = False
    buf = StringIO()
    yaml.dump({"idotaku": data}, buf)
    yaml_str = buf.getvalue()

    syntax = Syntax(yaml_str, "yaml", theme="monokai", line_numbers=False)
    console.print(syntax)

    if config_path:
        console.print(f"\n[dim]Config file: {Path(config_path).resolve()}[/dim]")
    else:
        found = find_config_path()
        if found:
            console.print(f"\n[dim]Config file: {found}[/dim]")
        else:
            console.print("\n[dim]No config file found (using defaults)[/dim]")


@config.command()
@click.argument("key")
@click.option("--config", "-c", "config_path", default=None, help="Config file path")
def get(key, config_path):
    """Get a single config value by key.

    Supports dotted keys for nested values: patterns.uuid, exclude_extensions, etc.
    """
    cfg = load_config(config_path)

    from dataclasses import asdict
    data = asdict(cfg)

    parts = key.split(".")
    current = data
    for part in parts:
        if isinstance(current, dict) and part in current:
            current = current[part]
        else:
            console.print(f"[red]Unknown key:[/red] {key}")
            sys.exit(1)

    if isinstance(current, (list, dict, set)):
        from ruamel.yaml import YAML

        yaml = YAML()
        yaml.default_flow_style = False
        buf = StringIO()
        yaml.dump(current, buf)
        click.echo(buf.getvalue().rstrip())
    else:
        click.echo(current)


@config.command("set")
@click.argument("key")
@click.argument("value")
@click.option("--config", "-c", "config_path", default=None, help="Config file path")
def set_value(key, value, config_path):
    """Set a config value in the YAML file.

    For list fields (target_domains, exclude_extensions, etc.),
    pass comma-separated values: idotaku config set target_domains "api.example.com,*.test.com"
    """
    if config_path:
        path = Path(config_path)
    else:
        path = find_config_path()

    if path is None or not path.exists():
        console.print("[red]No config file found.[/red]")
        console.print("[dim]Run 'idotaku config init' first.[/dim]")
        sys.exit(1)

    try:
        save_config_value(path, key, value)
    except Exception as e:
        console.print(f"[red]Error writing config:[/red] {e}")
        sys.exit(1)

    console.print(f"[green]Set[/green] {key} = {value}")
    console.print(f"[dim]Updated: {path}[/dim]")


@config.command()
@click.option("--config", "-c", "config_path", default=None, help="Config file path")
def validate(config_path):
    """Validate the config file for errors.

    Checks YAML syntax, key names, types, and regex patterns.
    """
    if config_path:
        path = Path(config_path)
    else:
        path = find_config_path()

    if path is None:
        console.print("[yellow]No config file found.[/yellow]")
        console.print("[dim]Run 'idotaku config init' to create one.[/dim]")
        return

    if not path.exists():
        console.print(f"[red]Config file not found:[/red] {path}")
        sys.exit(1)

    errors = validate_config(path)

    if not errors:
        console.print(f"[green]Config is valid:[/green] {path}")
    else:
        console.print(f"[red]Config has {len(errors)} error(s):[/red] {path}")
        for err in errors:
            console.print(f"  [red]-[/red] {err}")
        sys.exit(1)


@config.command()
def path():
    """Print the path to the active config file."""
    found = find_config_path()
    if found:
        click.echo(str(found))
    else:
        console.print("[dim]No config file found.[/dim]")
        sys.exit(1)
