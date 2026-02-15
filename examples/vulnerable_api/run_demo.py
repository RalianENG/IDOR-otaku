#!/usr/bin/env python3
"""Cross-platform demo runner for idotaku vulnerable API example.

Starts the vulnerable API server, runs an in-process mitmproxy with the
idotaku tracker, executes the automated attack scenario, and generates
analysis reports including interactive HTML exports.

Works on Windows, macOS, and Linux.

Usage:
    python run_demo.py
    python run_demo.py --api-port 4000 --proxy-port 9090
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import shutil
import signal
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent.resolve()

# ANSI color codes (disabled on Windows without VT100 support)
_COLOR = os.name != "nt" or os.environ.get("WT_SESSION")  # Windows Terminal supports ANSI
if _COLOR:
    _CYAN = "\033[0;36m"
    _GREEN = "\033[0;32m"
    _YELLOW = "\033[0;33m"
    _RED = "\033[0;31m"
    _BOLD = "\033[1m"
    _NC = "\033[0m"
else:
    _CYAN = _GREEN = _YELLOW = _RED = _BOLD = _NC = ""


def info(msg: str) -> None:
    print(f"{_CYAN}[INFO]{_NC} {msg}")


def success(msg: str) -> None:
    print(f"{_GREEN}[OK]{_NC} {msg}")


def error(msg: str) -> None:
    print(f"{_RED}[ERROR]{_NC} {msg}", file=sys.stderr)


def header(msg: str) -> None:
    print(f"\n{_BOLD}===== {msg} ====={_NC}")


def check_port_free(port: int) -> bool:
    """Check if a TCP port is available."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind(("127.0.0.1", port))
            return True
        except OSError:
            return False


def wait_for_url(url: str, timeout: int = 30, proxy: str | None = None) -> bool:
    """Wait for a URL to respond with HTTP 200."""
    import urllib.error
    import urllib.request

    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            if proxy:
                handler = urllib.request.ProxyHandler({"http": proxy})
                opener = urllib.request.build_opener(handler)
            else:
                opener = urllib.request.build_opener()
            req = urllib.request.Request(url, method="GET")
            resp = opener.open(req, timeout=2)
            if resp.status == 200:
                return True
        except (urllib.error.URLError, OSError, ConnectionError):
            pass
        time.sleep(0.5)
    return False


def find_mitmdump() -> str:
    """Find the mitmdump executable."""
    result = shutil.which("mitmdump")
    if result:
        return result

    # Windows: check Scripts directory
    scripts_dir = Path(sys.prefix) / "Scripts"
    for name in ("mitmdump.exe", "mitmdump"):
        p = scripts_dir / name
        if p.exists():
            return str(p)

    # Also check user-local Scripts on Windows
    appdata = os.environ.get("APPDATA")
    if appdata:
        ver = f"Python{sys.version_info.major}{sys.version_info.minor}"
        p = Path(appdata) / "Python" / ver / "Scripts" / "mitmdump.exe"
        if p.exists():
            return str(p)

    raise FileNotFoundError(
        "mitmdump not found. Install mitmproxy: pip install mitmproxy"
    )


def find_idotaku() -> str:
    """Find the idotaku CLI executable."""
    result = shutil.which("idotaku")
    if result:
        return result

    scripts_dir = Path(sys.prefix) / "Scripts"
    for name in ("idotaku.exe", "idotaku"):
        p = scripts_dir / name
        if p.exists():
            return str(p)

    raise FileNotFoundError(
        "idotaku not found. Install it: pip install -e . (from the project root)"
    )


def get_tracker_path() -> str:
    """Get the path to tracker.py from the installed idotaku package."""
    from idotaku.browser import get_tracker_script_path

    return str(get_tracker_script_path())


def terminate_process(proc: subprocess.Popen) -> None:  # type: ignore[type-arg]
    """Terminate a process gracefully, cross-platform."""
    if proc.poll() is not None:
        return
    try:
        if os.name == "nt":
            # On Windows, send CTRL_BREAK_EVENT if the process was created
            # with CREATE_NEW_PROCESS_GROUP, otherwise just terminate
            try:
                os.kill(proc.pid, signal.CTRL_BREAK_EVENT)  # type: ignore[attr-defined]
                proc.wait(timeout=5)
            except (OSError, subprocess.TimeoutExpired):
                proc.terminate()
                proc.wait(timeout=5)
        else:
            proc.terminate()
            proc.wait(timeout=5)
    except (OSError, subprocess.TimeoutExpired):
        proc.kill()
        proc.wait(timeout=3)


def run_command(cmd: list[str], label: str) -> None:
    """Run a command and print output."""
    header(label)
    subprocess.run(cmd, check=False)


def start_proxy(port: int, config_file: str) -> tuple:
    """Start mitmproxy in-process in a background thread.

    Returns (tracker, master, thread) tuple.
    """
    from mitmproxy.options import Options
    from mitmproxy.tools.dump import DumpMaster

    from idotaku.config import load_config
    from idotaku.tracker import IDTracker

    config = load_config(config_file)
    tracker = IDTracker(config)
    tracker._use_ctx = True

    master_holder: list = []
    ready_event = threading.Event()
    error_holder: list = []

    async def _run() -> None:
        opts = Options(listen_port=port)
        m = DumpMaster(opts)
        m.addons.add(tracker)
        master_holder.append(m)
        ready_event.set()
        await m.run()

    def _thread() -> None:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(_run())
        except Exception as exc:
            error_holder.append(exc)
            ready_event.set()

    t = threading.Thread(target=_thread, daemon=True)
    t.start()

    # Wait for proxy to be ready
    ready_event.wait(timeout=15)
    if error_holder:
        raise RuntimeError(f"Proxy failed to start: {error_holder[0]}")
    if not master_holder:
        raise RuntimeError("Proxy failed to initialize")

    return tracker, master_holder[0], t


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run the idotaku demo with the vulnerable API"
    )
    parser.add_argument(
        "--api-port", type=int, default=3000, help="API server port (default: 3000)"
    )
    parser.add_argument(
        "--proxy-port", type=int, default=8080, help="Proxy port (default: 8080)"
    )
    args = parser.parse_args()

    api_port = args.api_port
    proxy_port = args.proxy_port
    report_file = SCRIPT_DIR / "test_report.json"
    config_file = str(SCRIPT_DIR / "idotaku.yaml")

    server_proc: subprocess.Popen | None = None  # type: ignore[type-arg]
    proxy_master = None

    try:
        # ---- Step 1: Prerequisites ----
        header("Checking prerequisites")

        try:
            find_mitmdump()
            success("mitmproxy found")
        except FileNotFoundError as e:
            error(str(e))
            sys.exit(1)

        try:
            idotaku_path = find_idotaku()
            success(f"idotaku found: {idotaku_path}")
        except FileNotFoundError as e:
            error(str(e))
            sys.exit(1)

        if not check_port_free(api_port):
            error(f"Port {api_port} is already in use. Use --api-port to change.")
            sys.exit(1)
        if not check_port_free(proxy_port):
            error(f"Port {proxy_port} is already in use. Use --proxy-port to change.")
            sys.exit(1)
        success(f"Ports {api_port} and {proxy_port} are available")

        # ---- Step 2: Install dependencies ----
        header("Installing demo dependencies")
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "-r",
             str(SCRIPT_DIR / "requirements.txt"), "--quiet"],
            check=True,
        )
        success("Dependencies installed")

        # ---- Step 3: Start API server ----
        header(f"Starting vulnerable API server (port {api_port})")
        creation_flags = subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0
        server_proc = subprocess.Popen(
            [sys.executable, str(SCRIPT_DIR / "server.py"), "--port", str(api_port)],
            creationflags=creation_flags,
        )
        info(f"Server PID: {server_proc.pid}")

        api_url = f"http://127.0.0.1:{api_port}"
        if not wait_for_url(f"{api_url}/api/health"):
            error("API server failed to start within 30 seconds")
            sys.exit(1)
        success("API server is ready")

        # ---- Step 4: Start in-process proxy ----
        header(f"Starting proxy (port {proxy_port})")
        try:
            tracker, proxy_master, proxy_thread = start_proxy(proxy_port, config_file)
        except RuntimeError as e:
            error(str(e))
            sys.exit(1)

        # Verify proxy works
        proxy_url = f"http://127.0.0.1:{proxy_port}"
        if not wait_for_url(f"{api_url}/api/health", proxy=proxy_url):
            error("Proxy failed to respond within 30 seconds")
            sys.exit(1)
        success("Proxy is ready")

        # ---- Step 5: Run test scenario ----
        header("Running test scenario")
        result = subprocess.run(
            [
                sys.executable, str(SCRIPT_DIR / "test_scenario.py"),
                "--api", api_url,
                "--proxy", proxy_url,
            ],
            check=False,
        )
        if result.returncode != 0:
            error("Test scenario failed")
            sys.exit(1)
        success("Test scenario complete")

        # ---- Step 6: Generate report ----
        header("Generating report")
        time.sleep(1)  # Allow any pending responses to be processed

        tracker.output_file = str(report_file)
        report = tracker.generate_report()

        with open(report_file, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)

        info(f"Tracked {report['summary']['total_flows']} flows, "
             f"{report['summary']['total_unique_ids']} unique IDs")

        if report["potential_idor"]:
            info(f"Found {len(report['potential_idor'])} potential IDOR candidates")

        success(f"Report generated: {report_file.name}")

        # ---- Step 7: Shutdown proxy and server ----
        if proxy_master:
            proxy_master.shutdown()
            proxy_master = None

        terminate_process(server_proc)
        server_proc = None
        success("Services stopped")

        # ---- Step 8: Run analysis ----
        report_str = str(report_file)
        run_command([idotaku_path, "report", report_str], "Report Summary")
        run_command([idotaku_path, "score", report_str], "Risk Scores")
        run_command([idotaku_path, "chain", report_str], "Parameter Chains")
        run_command([idotaku_path, "auth", report_str], "Cross-User Access")

        # ---- Step 9: Generate HTML exports ----
        header("Generating HTML exports")
        chain_html = str(SCRIPT_DIR / "chain.html")
        sequence_html = str(SCRIPT_DIR / "sequence.html")

        # Suppress console output for HTML generation (avoids Unicode
        # encoding issues on Windows with Rich's legacy console renderer)
        subprocess.run(
            [idotaku_path, "chain", report_str, "--html", chain_html],
            check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        success(f"Chain HTML: {chain_html}")

        subprocess.run(
            [idotaku_path, "sequence", report_str, "--html", sequence_html],
            check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        success(f"Sequence HTML: {sequence_html}")

        # ---- Done ----
        print(f"\n{_GREEN}{_BOLD}Demo complete!{_NC}\n")
        print("Generated files:")
        print(f"  Report:   {report_file}")
        print(f"  Chain:    {chain_html}")
        print(f"  Sequence: {sequence_html}")
        print()
        print("Open the HTML files in a browser to explore interactive visualizations.")

    finally:
        if proxy_master is not None:
            try:
                proxy_master.shutdown()
            except Exception:
                pass
        if server_proc is not None:
            terminate_process(server_proc)


if __name__ == "__main__":
    main()
