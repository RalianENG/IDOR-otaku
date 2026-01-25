#!/usr/bin/env python
"""
Development launcher for idotaku.

Usage:
    python dev.py           # Start mitmweb with tracker
    python dev.py --dump    # Start mitmdump (no web UI)
"""
import sys
import os
import subprocess

def find_mitmproxy_script(name):
    """Find mitmproxy script in Python's Scripts directory."""
    # Python Scripts directory
    scripts_dir = os.path.join(os.path.dirname(sys.executable), "Scripts")

    # Try .exe on Windows
    for ext in [".exe", ""]:
        script_path = os.path.join(scripts_dir, name + ext)
        if os.path.exists(script_path):
            return script_path

    # Try user's Scripts directory
    user_scripts = os.path.join(os.path.dirname(sys.executable).replace("Python314", ""),
                                 "AppData", "Roaming", "Python", "Python314", "Scripts")
    for ext in [".exe", ""]:
        script_path = os.path.join(user_scripts, name + ext)
        if os.path.exists(script_path):
            return script_path

    return None


if __name__ == "__main__":
    script_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "main.py")

    # Determine which tool to use
    if "--dump" in sys.argv:
        sys.argv.remove("--dump")
        tool_name = "mitmdump"
    else:
        tool_name = "mitmweb"

    # Find the mitmproxy executable
    tool_path = find_mitmproxy_script(tool_name)

    if tool_path:
        # Use found executable
        cmd = [tool_path, "-s", script_path] + sys.argv[1:]
    else:
        # Fallback: use python -m
        cmd = [sys.executable, "-m", f"mitmproxy.tools.{tool_name}", "-s", script_path] + sys.argv[1:]

    print(f"Running: {' '.join(cmd)}")
    subprocess.run(cmd)
