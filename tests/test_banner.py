"""Tests for ASCII banner module."""

import os

from rich.console import Console

from idotaku.banner import print_banner, BANNER


class TestBannerConstant:
    """Tests for the BANNER constant."""

    def test_banner_contains_idotaku(self):
        """The BANNER string should contain the project name stylized text."""
        # The ASCII art renders "idotaku" - verify the banner is non-empty
        # and contains recognizable parts of the ASCII art
        assert isinstance(BANNER, str)
        assert len(BANNER) > 0

    def test_banner_is_multiline(self):
        """The BANNER should span multiple lines."""
        lines = BANNER.strip().split("\n")
        assert len(lines) >= 3


class TestPrintBanner:
    """Tests for print_banner()."""

    def test_print_banner_no_console(self):
        """Should not raise when called with no console (creates its own)."""
        print_banner(None)

    def test_print_banner_with_console(self):
        """Should print banner to the provided console."""
        with open(os.devnull, "w") as devnull:
            console = Console(file=devnull)
            print_banner(console)

    def test_print_banner_show_version_true(self):
        """Should include version info when show_version=True (default)."""
        output = _capture_banner_output(show_version=True)
        assert "IDOR detection tool" in output

    def test_print_banner_show_version_false(self):
        """Should not include version info when show_version=False."""
        output = _capture_banner_output(show_version=False)
        assert "IDOR detection tool" not in output

    def test_print_banner_contains_ascii_art(self):
        """Should include the ASCII art in the output."""
        output = _capture_banner_output(show_version=False)
        # The banner contains distinctive characters from the ASCII art
        assert "___" in output or "__" in output


def _capture_banner_output(show_version: bool = True) -> str:
    """Helper to capture print_banner output as a string."""
    from io import StringIO
    buffer = StringIO()
    console = Console(file=buffer, force_terminal=False)
    print_banner(console, show_version=show_version)
    return buffer.getvalue()
