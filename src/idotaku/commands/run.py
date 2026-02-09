"""Main run command - starts mitmweb proxy and browser."""

import os
import sys
import shutil
import subprocess
import tempfile
from pathlib import Path

from rich.console import Console

from ..browser import find_browser, find_browser_by_name, find_mitmweb, get_tracker_script_path

console = Console()


def run_proxy(port, web_port, output, min_numeric, config, no_browser, browser):
    """Run mitmweb proxy with browser.

    This is the main functionality when idotaku is called without subcommand.
    """
    # Find mitmweb
    mitmweb_path = find_mitmweb()
    if not mitmweb_path:
        console.print("[red]Error:[/red] mitmweb not found. Install with: pip install mitmproxy")
        sys.exit(1)

    tracker_script = get_tracker_script_path()

    console.print("[bold blue]idotaku[/bold blue] - API ID Tracker")
    console.print(f"  Proxy: [green]127.0.0.1:{port}[/green]")
    console.print(f"  Web UI: [green]http://127.0.0.1:{web_port}[/green]")
    console.print(f"  Report: [green]{output}[/green]")
    if config:
        config_path = Path(config).resolve()
        console.print(f"  Config: [green]{config_path}[/green]")
    console.print()

    # Build mitmweb command
    cmd = [
        mitmweb_path,
        "-s", str(tracker_script),
        "--listen-port", str(port),
        "--web-port", str(web_port),
        "--set", f"idotaku_output={output}",
        "--set", f"idotaku_min_numeric={min_numeric}",
    ]

    if config:
        config_abs = str(Path(config).resolve())
        cmd.extend(["--set", f"idotaku_config={config_abs}"])

    # Start mitmweb
    console.print("[yellow]Starting mitmweb...[/yellow]")
    mitmweb_proc = subprocess.Popen(cmd)

    browser_proc = None
    temp_profile = None

    try:
        if not no_browser:
            # Find and launch browser
            if browser == "auto":
                browser_info = find_browser()
            else:
                browser_info = find_browser_by_name(browser)
                if not browser_info:
                    console.print(f"[yellow]Browser '{browser}' not found, falling back to auto-detect.[/yellow]")
                    browser_info = find_browser()

            if browser_info:
                browser_name, browser_path = browser_info
                temp_profile = tempfile.mkdtemp(prefix="idotaku_")

                console.print(f"[yellow]Launching {browser_name}...[/yellow]")

                if browser_name in ("chrome", "edge"):
                    browser_cmd = [
                        browser_path,
                        f"--proxy-server=127.0.0.1:{port}",
                        f"--user-data-dir={temp_profile}",
                        "--ignore-certificate-errors",
                        "--no-first-run",
                        "--no-default-browser-check",
                    ]
                else:  # firefox
                    browser_cmd = [
                        browser_path,
                        "-no-remote",
                        "-profile", temp_profile,
                    ]
                    console.print(f"[yellow]Note: Set Firefox proxy manually to 127.0.0.1:{port}[/yellow]")

                browser_proc = subprocess.Popen(browser_cmd)
            else:
                console.print("[yellow]No browser found. Configure proxy manually.[/yellow]")

        console.print()
        console.print("[bold green]Ready![/bold green] Press Ctrl+C to stop and generate report.")
        console.print()

        # Wait for mitmweb
        mitmweb_proc.wait()

    except KeyboardInterrupt:
        console.print()
        console.print("[yellow]Stopping...[/yellow]")

    finally:
        # Cleanup
        if mitmweb_proc and mitmweb_proc.poll() is None:
            mitmweb_proc.terminate()
            try:
                mitmweb_proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                mitmweb_proc.kill()

        if browser_proc and browser_proc.poll() is None:
            browser_proc.terminate()

        if temp_profile and os.path.exists(temp_profile):
            try:
                shutil.rmtree(temp_profile)
            except OSError as e:
                # Non-critical: temp directory cleanup failed
                # Common causes: file locked by browser, permission denied on Windows
                # OS will eventually clean up temp directories
                console.print(
                    f"[dim]Note: Could not remove temp profile {temp_profile}: {e}[/dim]"
                )

    console.print(f"[bold green]Done![/bold green] Report saved to: {output}")
