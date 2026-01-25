"""
idotaku - API ID tracking tool for security testing.

Legacy entry point for direct mitmproxy usage:
    mitmweb -s main.py
    mitmdump -s main.py

For CLI usage, install the package and run:
    idotaku
"""

# Re-export tracker for mitmproxy addon compatibility
try:
    from src.idotaku.tracker import IDTracker, addons
except ImportError:
    # Fallback for direct execution
    from idotaku.tracker import IDTracker, addons

__all__ = ["IDTracker", "addons"]
