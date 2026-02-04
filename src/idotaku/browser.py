"""Browser and mitmweb detection utilities."""

import os
import sys
import shutil
from pathlib import Path


def get_tracker_script_path() -> Path:
    """Get path to tracker.py for mitmproxy addon."""
    return Path(__file__).parent / "tracker.py"


def find_browser() -> tuple[str, str] | None:
    """Find available browser.

    Returns:
        Tuple of (browser_name, browser_path) or None if not found
    """
    browsers = [
        ("chrome", [
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
            "google-chrome",
            "chromium",
        ]),
        ("edge", [
            r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
            r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        ]),
        ("firefox", [
            r"C:\Program Files\Mozilla Firefox\firefox.exe",
            r"C:\Program Files (x86)\Mozilla Firefox\firefox.exe",
            "/Applications/Firefox.app/Contents/MacOS/firefox",
            "firefox",
        ]),
    ]

    for browser_name, paths in browsers:
        for path in paths:
            if os.path.isfile(path):
                return browser_name, path
            which_result = shutil.which(path)
            if which_result:
                return browser_name, which_result

    return None


def find_browser_by_name(name: str) -> tuple[str, str] | None:
    """Find a specific browser by name.

    Args:
        name: Browser name ("chrome", "edge", "firefox")

    Returns:
        Tuple of (browser_name, browser_path) or None if not found
    """
    browser_paths = {
        "chrome": [
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
            "google-chrome",
            "chromium",
        ],
        "edge": [
            r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
            r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        ],
        "firefox": [
            r"C:\Program Files\Mozilla Firefox\firefox.exe",
            r"C:\Program Files (x86)\Mozilla Firefox\firefox.exe",
            "/Applications/Firefox.app/Contents/MacOS/firefox",
            "firefox",
        ],
    }

    paths = browser_paths.get(name.lower(), [])
    for path in paths:
        if os.path.isfile(path):
            return name.lower(), path
        which_result = shutil.which(path)
        if which_result:
            return name.lower(), which_result

    return None


def find_mitmweb() -> str | None:
    """Find mitmweb executable.

    Returns:
        Path to mitmweb or None if not found
    """
    # Check if mitmweb is in PATH
    mitmweb = shutil.which("mitmweb")
    if mitmweb:
        return mitmweb

    # Check common locations
    locations = [
        Path(sys.prefix) / "Scripts" / "mitmweb.exe",
        Path(sys.prefix) / "bin" / "mitmweb",
        Path.home() / "AppData" / "Roaming" / "Python" / f"Python{sys.version_info.major}{sys.version_info.minor}" / "Scripts" / "mitmweb.exe",
    ]

    for loc in locations:
        if loc.exists():
            return str(loc)

    return None
