"""Tests for browser and mitmweb detection utilities."""

import sys
from pathlib import Path
from unittest.mock import patch


from idotaku.browser import (
    find_browser,
    find_browser_by_name,
    find_mitmweb,
    get_tracker_script_path,
)


class TestGetTrackerScriptPath:
    """Tests for get_tracker_script_path()."""

    def test_returns_path_object(self):
        """Should return a Path instance."""
        result = get_tracker_script_path()
        assert isinstance(result, Path)

    def test_path_ends_with_tracker_py(self):
        """Should return a path ending in tracker.py."""
        result = get_tracker_script_path()
        assert result.name == "tracker.py"

    def test_path_is_inside_idotaku_package(self):
        """Should point to tracker.py inside the idotaku package directory."""
        result = get_tracker_script_path()
        assert "idotaku" in str(result)

    def test_tracker_file_exists(self):
        """The returned path should point to an existing file."""
        result = get_tracker_script_path()
        assert result.exists()


class TestFindBrowser:
    """Tests for find_browser()."""

    def test_returns_none_when_no_browser_found(self):
        """Should return None when no browser is available."""
        with patch("idotaku.browser.os.path.isfile", return_value=False), \
             patch("idotaku.browser.shutil.which", return_value=None):
            result = find_browser()
            assert result is None

    def test_returns_chrome_when_isfile_matches(self):
        """Should return chrome when os.path.isfile matches a chrome path."""
        def fake_isfile(path):
            return path == r"C:\Program Files\Google\Chrome\Application\chrome.exe"

        with patch("idotaku.browser.os.path.isfile", side_effect=fake_isfile), \
             patch("idotaku.browser.shutil.which", return_value=None):
            result = find_browser()
            assert result is not None
            name, path = result
            assert name == "chrome"
            assert path == r"C:\Program Files\Google\Chrome\Application\chrome.exe"

    def test_returns_chrome_when_which_matches(self):
        """Should return chrome when shutil.which finds it."""
        def fake_which(cmd):
            if cmd == "google-chrome":
                return "/usr/bin/google-chrome"
            return None

        with patch("idotaku.browser.os.path.isfile", return_value=False), \
             patch("idotaku.browser.shutil.which", side_effect=fake_which):
            result = find_browser()
            assert result is not None
            name, path = result
            assert name == "chrome"
            assert path == "/usr/bin/google-chrome"

    def test_returns_edge_when_chrome_not_found_but_edge_found(self):
        """Should fall through to edge when chrome paths are not found."""
        def fake_isfile(path):
            return path == r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"

        with patch("idotaku.browser.os.path.isfile", side_effect=fake_isfile), \
             patch("idotaku.browser.shutil.which", return_value=None):
            result = find_browser()
            assert result is not None
            name, path = result
            assert name == "edge"
            assert path == r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"

    def test_returns_firefox_when_chrome_and_edge_not_found(self):
        """Should fall through to firefox when chrome and edge are not found."""
        def fake_which(cmd):
            if cmd == "firefox":
                return "/usr/bin/firefox"
            return None

        with patch("idotaku.browser.os.path.isfile", return_value=False), \
             patch("idotaku.browser.shutil.which", side_effect=fake_which):
            result = find_browser()
            assert result is not None
            name, path = result
            assert name == "firefox"
            assert path == "/usr/bin/firefox"

    def test_prefers_isfile_over_which_for_same_path(self):
        """Should return the direct path when isfile matches, not the which result."""
        chrome_path = r"C:\Program Files\Google\Chrome\Application\chrome.exe"

        def fake_isfile(path):
            return path == chrome_path

        with patch("idotaku.browser.os.path.isfile", side_effect=fake_isfile), \
             patch("idotaku.browser.shutil.which", return_value="/other/chrome"):
            result = find_browser()
            assert result is not None
            name, path = result
            assert name == "chrome"
            assert path == chrome_path

    def test_returns_chrome_x86_when_isfile_matches(self):
        """Should return chrome when the x86 path is found."""
        chrome_path = r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"

        def fake_isfile(path):
            return path == chrome_path

        with patch("idotaku.browser.os.path.isfile", side_effect=fake_isfile), \
             patch("idotaku.browser.shutil.which", return_value=None):
            result = find_browser()
            assert result is not None
            name, path = result
            assert name == "chrome"
            assert path == chrome_path

    def test_returns_chrome_via_chromium_which(self):
        """Should return chrome when shutil.which finds chromium."""
        def fake_which(cmd):
            if cmd == "chromium":
                return "/usr/bin/chromium"
            return None

        with patch("idotaku.browser.os.path.isfile", return_value=False), \
             patch("idotaku.browser.shutil.which", side_effect=fake_which):
            result = find_browser()
            assert result is not None
            name, path = result
            assert name == "chrome"
            assert path == "/usr/bin/chromium"

    def test_returns_firefox_via_isfile_on_mac(self):
        """Should return firefox when macOS path is found via isfile."""
        firefox_path = "/Applications/Firefox.app/Contents/MacOS/firefox"

        def fake_isfile(path):
            return path == firefox_path

        with patch("idotaku.browser.os.path.isfile", side_effect=fake_isfile), \
             patch("idotaku.browser.shutil.which", return_value=None):
            result = find_browser()
            assert result is not None
            name, path = result
            assert name == "firefox"
            assert path == firefox_path


class TestFindBrowserByName:
    """Tests for find_browser_by_name()."""

    def test_chrome_found_via_isfile(self):
        """Should return chrome when os.path.isfile finds it."""
        chrome_path = r"C:\Program Files\Google\Chrome\Application\chrome.exe"

        def fake_isfile(path):
            return path == chrome_path

        with patch("idotaku.browser.os.path.isfile", side_effect=fake_isfile), \
             patch("idotaku.browser.shutil.which", return_value=None):
            result = find_browser_by_name("chrome")
            assert result is not None
            name, path = result
            assert name == "chrome"
            assert path == chrome_path

    def test_chrome_found_via_which(self):
        """Should return chrome when shutil.which finds it."""
        def fake_which(cmd):
            if cmd == "google-chrome":
                return "/usr/bin/google-chrome"
            return None

        with patch("idotaku.browser.os.path.isfile", return_value=False), \
             patch("idotaku.browser.shutil.which", side_effect=fake_which):
            result = find_browser_by_name("chrome")
            assert result is not None
            name, path = result
            assert name == "chrome"
            assert path == "/usr/bin/google-chrome"

    def test_unknown_browser_returns_none(self):
        """Should return None for an unknown browser name."""
        with patch("idotaku.browser.os.path.isfile", return_value=False), \
             patch("idotaku.browser.shutil.which", return_value=None):
            result = find_browser_by_name("unknown")
            assert result is None

    def test_case_insensitive_name(self):
        """Should handle browser names case-insensitively."""
        chrome_path = r"C:\Program Files\Google\Chrome\Application\chrome.exe"

        def fake_isfile(path):
            return path == chrome_path

        with patch("idotaku.browser.os.path.isfile", side_effect=fake_isfile), \
             patch("idotaku.browser.shutil.which", return_value=None):
            result = find_browser_by_name("Chrome")
            assert result is not None
            name, _ = result
            assert name == "chrome"

    def test_edge_found_via_isfile(self):
        """Should return edge when os.path.isfile finds it."""
        edge_path = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"

        def fake_isfile(path):
            return path == edge_path

        with patch("idotaku.browser.os.path.isfile", side_effect=fake_isfile), \
             patch("idotaku.browser.shutil.which", return_value=None):
            result = find_browser_by_name("edge")
            assert result is not None
            name, path = result
            assert name == "edge"
            assert path == edge_path

    def test_firefox_not_found_returns_none(self):
        """Should return None when firefox is not found in any location."""
        with patch("idotaku.browser.os.path.isfile", return_value=False), \
             patch("idotaku.browser.shutil.which", return_value=None):
            result = find_browser_by_name("firefox")
            assert result is None

    def test_firefox_found_via_which(self):
        """Should return firefox when shutil.which finds it."""
        def fake_which(cmd):
            if cmd == "firefox":
                return "/usr/bin/firefox"
            return None

        with patch("idotaku.browser.os.path.isfile", return_value=False), \
             patch("idotaku.browser.shutil.which", side_effect=fake_which):
            result = find_browser_by_name("firefox")
            assert result is not None
            name, path = result
            assert name == "firefox"
            assert path == "/usr/bin/firefox"

    def test_chrome_found_via_chromium_which(self):
        """Should return chrome when shutil.which finds chromium."""
        def fake_which(cmd):
            if cmd == "chromium":
                return "/usr/bin/chromium"
            return None

        with patch("idotaku.browser.os.path.isfile", return_value=False), \
             patch("idotaku.browser.shutil.which", side_effect=fake_which):
            result = find_browser_by_name("chrome")
            assert result is not None
            name, path = result
            assert name == "chrome"
            assert path == "/usr/bin/chromium"

    def test_edge_found_via_second_path(self):
        """Should return edge when second edge path is found via isfile."""
        edge_path = r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"

        def fake_isfile(path):
            return path == edge_path

        with patch("idotaku.browser.os.path.isfile", side_effect=fake_isfile), \
             patch("idotaku.browser.shutil.which", return_value=None):
            result = find_browser_by_name("edge")
            assert result is not None
            name, path = result
            assert name == "edge"
            assert path == edge_path


class TestFindMitmweb:
    """Tests for find_mitmweb()."""

    def test_returns_from_shutil_which(self):
        """Should return path from shutil.which when mitmweb is on PATH."""
        with patch("idotaku.browser.shutil.which", return_value="/usr/bin/mitmweb"):
            result = find_mitmweb()
            assert result == "/usr/bin/mitmweb"

    def test_returns_none_when_not_found_anywhere(self):
        """Should return None when mitmweb is not found via which or fallback locations."""
        with patch("idotaku.browser.shutil.which", return_value=None), \
             patch.object(Path, "exists", return_value=False):
            result = find_mitmweb()
            assert result is None

    def test_returns_from_fallback_scripts_location(self, tmp_path):
        """Should find mitmweb in Scripts directory when which fails."""
        scripts_dir = tmp_path / "Scripts"
        scripts_dir.mkdir()
        mitmweb_exe = scripts_dir / "mitmweb.exe"
        mitmweb_exe.touch()

        with patch("idotaku.browser.shutil.which", return_value=None), \
             patch.object(sys, "prefix", str(tmp_path)):
            result = find_mitmweb()
            assert result == str(mitmweb_exe)

    def test_returns_from_fallback_bin_location(self, tmp_path):
        """Should find mitmweb in bin directory when which fails."""
        bin_dir = tmp_path / "bin"
        bin_dir.mkdir()
        mitmweb_bin = bin_dir / "mitmweb"
        mitmweb_bin.touch()

        with patch("idotaku.browser.shutil.which", return_value=None), \
             patch.object(sys, "prefix", str(tmp_path)):
            result = find_mitmweb()
            assert result == str(mitmweb_bin)

    def test_which_takes_priority_over_fallback(self, tmp_path):
        """Should prefer shutil.which result over fallback locations."""
        # Create a fallback location too
        scripts_dir = tmp_path / "Scripts"
        scripts_dir.mkdir()
        (scripts_dir / "mitmweb.exe").touch()

        with patch("idotaku.browser.shutil.which", return_value="/usr/bin/mitmweb"), \
             patch.object(sys, "prefix", str(tmp_path)):
            result = find_mitmweb()
            assert result == "/usr/bin/mitmweb"
