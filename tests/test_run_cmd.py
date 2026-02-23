"""Tests for the run command (run_proxy function)."""

import subprocess
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from idotaku.commands.run import run_proxy


class TestRunProxyMitmwebNotFound:
    """Tests for run_proxy when mitmweb is not available."""

    def test_exits_when_mitmweb_not_found(self):
        """Should call sys.exit(1) when find_mitmweb returns None."""
        with patch("idotaku.commands.run.find_mitmweb", return_value=None), \
             patch("idotaku.commands.run.console") as mock_console:
            with pytest.raises(SystemExit) as exc_info:
                run_proxy(
                    port=8080, web_port=8081, output="report.json",
                    min_numeric=100, config=None, no_browser=True, browser="auto",
                )
            assert exc_info.value.code == 1
            # Verify error message was printed
            mock_console.print.assert_any_call(
                "[red]Error:[/red] mitmweb not found. Install with: pip install mitmproxy"
            )


class TestRunProxyNoBrowser:
    """Tests for run_proxy with no_browser=True."""

    def test_no_browser_flag_skips_browser_launch(self):
        """Should not launch a browser when no_browser=True."""
        mock_proc = MagicMock()
        mock_proc.wait.return_value = 0
        mock_proc.poll.return_value = 0  # Already exited after wait

        with patch("idotaku.commands.run.find_mitmweb", return_value="/usr/bin/mitmweb"), \
             patch("idotaku.commands.run.get_tracker_script_path", return_value=Path("/fake/tracker.py")), \
             patch("idotaku.commands.run.print_banner"), \
             patch("idotaku.commands.run.console"), \
             patch("idotaku.commands.run.subprocess.Popen", return_value=mock_proc) as mock_popen, \
             patch("idotaku.commands.run.find_browser") as mock_find_browser, \
             patch("idotaku.commands.run.find_browser_by_name") as mock_find_by_name:
            run_proxy(
                port=8080, web_port=8081, output="report.json",
                min_numeric=100, config=None, no_browser=True, browser="auto",
            )
            # Browser detection functions should not be called
            mock_find_browser.assert_not_called()
            mock_find_by_name.assert_not_called()
            # Only one Popen call (mitmweb), no browser Popen
            assert mock_popen.call_count == 1


class TestRunProxyAutoBrowserChrome:
    """Tests for run_proxy with auto browser detection finding chrome."""

    def test_auto_browser_launches_chrome_with_correct_args(self):
        """Should launch chrome with proxy and temp profile args."""
        mock_mitmweb_proc = MagicMock()
        mock_mitmweb_proc.wait.return_value = 0
        mock_mitmweb_proc.poll.return_value = 0

        mock_browser_proc = MagicMock()
        mock_browser_proc.poll.return_value = 0

        popen_calls = []

        def fake_popen(cmd, **kwargs):
            popen_calls.append(cmd)
            if len(popen_calls) == 1:
                return mock_mitmweb_proc
            return mock_browser_proc

        with patch("idotaku.commands.run.find_mitmweb", return_value="/usr/bin/mitmweb"), \
             patch("idotaku.commands.run.get_tracker_script_path", return_value=Path("/fake/tracker.py")), \
             patch("idotaku.commands.run.print_banner"), \
             patch("idotaku.commands.run.console"), \
             patch("idotaku.commands.run.subprocess.Popen", side_effect=fake_popen), \
             patch("idotaku.commands.run.find_browser", return_value=("chrome", "/usr/bin/chrome")), \
             patch("idotaku.commands.run.tempfile.mkdtemp", return_value="/tmp/idotaku_test"), \
             patch("idotaku.commands.run.os.path.exists", return_value=False):
            run_proxy(
                port=8080, web_port=8081, output="report.json",
                min_numeric=100, config=None, no_browser=False, browser="auto",
            )

        # Two Popen calls: mitmweb + browser
        assert len(popen_calls) == 2
        browser_cmd = popen_calls[1]
        assert browser_cmd[0] == "/usr/bin/chrome"
        assert "--proxy-server=127.0.0.1:8080" in browser_cmd
        assert any("--user-data-dir=" in arg for arg in browser_cmd)
        assert "--ignore-certificate-errors" in browser_cmd
        assert "--no-first-run" in browser_cmd


class TestRunProxyAutoBrowserFirefox:
    """Tests for run_proxy with auto browser detection finding firefox."""

    def test_auto_browser_launches_firefox_with_correct_args(self):
        """Should launch firefox with -no-remote and -profile args."""
        mock_mitmweb_proc = MagicMock()
        mock_mitmweb_proc.wait.return_value = 0
        mock_mitmweb_proc.poll.return_value = 0

        mock_browser_proc = MagicMock()
        mock_browser_proc.poll.return_value = 0

        popen_calls = []

        def fake_popen(cmd, **kwargs):
            popen_calls.append(cmd)
            if len(popen_calls) == 1:
                return mock_mitmweb_proc
            return mock_browser_proc

        with patch("idotaku.commands.run.find_mitmweb", return_value="/usr/bin/mitmweb"), \
             patch("idotaku.commands.run.get_tracker_script_path", return_value=Path("/fake/tracker.py")), \
             patch("idotaku.commands.run.print_banner"), \
             patch("idotaku.commands.run.console"), \
             patch("idotaku.commands.run.subprocess.Popen", side_effect=fake_popen), \
             patch("idotaku.commands.run.find_browser", return_value=("firefox", "/usr/bin/firefox")), \
             patch("idotaku.commands.run.tempfile.mkdtemp", return_value="/tmp/idotaku_test"), \
             patch("idotaku.commands.run.os.path.exists", return_value=False):
            run_proxy(
                port=8080, web_port=8081, output="report.json",
                min_numeric=100, config=None, no_browser=False, browser="auto",
            )

        assert len(popen_calls) == 2
        browser_cmd = popen_calls[1]
        assert browser_cmd[0] == "/usr/bin/firefox"
        assert "-no-remote" in browser_cmd
        assert "-profile" in browser_cmd
        assert "/tmp/idotaku_test" in browser_cmd


class TestRunProxyNamedBrowserFallback:
    """Tests for run_proxy with a named browser that is not found."""

    def test_falls_back_to_auto_when_named_browser_not_found(self):
        """Should fall back to find_browser() when find_browser_by_name returns None."""
        mock_mitmweb_proc = MagicMock()
        mock_mitmweb_proc.wait.return_value = 0
        mock_mitmweb_proc.poll.return_value = 0

        mock_browser_proc = MagicMock()
        mock_browser_proc.poll.return_value = 0

        def fake_popen(cmd, **kwargs):
            if cmd[0] == "/usr/bin/mitmweb":
                return mock_mitmweb_proc
            return mock_browser_proc

        with patch("idotaku.commands.run.find_mitmweb", return_value="/usr/bin/mitmweb"), \
             patch("idotaku.commands.run.get_tracker_script_path", return_value=Path("/fake/tracker.py")), \
             patch("idotaku.commands.run.print_banner"), \
             patch("idotaku.commands.run.console") as mock_console, \
             patch("idotaku.commands.run.subprocess.Popen", side_effect=fake_popen), \
             patch("idotaku.commands.run.find_browser_by_name", return_value=None) as mock_by_name, \
             patch("idotaku.commands.run.find_browser", return_value=("chrome", "/usr/bin/chrome")) as mock_find, \
             patch("idotaku.commands.run.tempfile.mkdtemp", return_value="/tmp/idotaku_test"), \
             patch("idotaku.commands.run.os.path.exists", return_value=False):
            run_proxy(
                port=8080, web_port=8081, output="report.json",
                min_numeric=100, config=None, no_browser=False, browser="opera",
            )
            mock_by_name.assert_called_once_with("opera")
            mock_find.assert_called_once()
            # Should print fallback warning
            mock_console.print.assert_any_call(
                "[yellow]Browser 'opera' not found, falling back to auto-detect.[/yellow]"
            )


class TestRunProxyNoBrowserFound:
    """Tests for run_proxy when no browser is found at all."""

    def test_prints_warning_when_no_browser_found(self):
        """Should print a warning when find_browser returns None."""
        mock_proc = MagicMock()
        mock_proc.wait.return_value = 0
        mock_proc.poll.return_value = 0

        with patch("idotaku.commands.run.find_mitmweb", return_value="/usr/bin/mitmweb"), \
             patch("idotaku.commands.run.get_tracker_script_path", return_value=Path("/fake/tracker.py")), \
             patch("idotaku.commands.run.print_banner"), \
             patch("idotaku.commands.run.console") as mock_console, \
             patch("idotaku.commands.run.subprocess.Popen", return_value=mock_proc), \
             patch("idotaku.commands.run.find_browser", return_value=None):
            run_proxy(
                port=8080, web_port=8081, output="report.json",
                min_numeric=100, config=None, no_browser=False, browser="auto",
            )
            mock_console.print.assert_any_call(
                "[yellow]No browser found. Configure proxy manually.[/yellow]"
            )


class TestRunProxyWithConfig:
    """Tests for run_proxy with a config file specified."""

    def test_config_option_included_in_command(self):
        """Should include config path in mitmweb command when config is specified."""
        mock_proc = MagicMock()
        mock_proc.wait.return_value = 0
        mock_proc.poll.return_value = 0

        popen_calls = []

        def fake_popen(cmd, **kwargs):
            popen_calls.append(cmd)
            return mock_proc

        with patch("idotaku.commands.run.find_mitmweb", return_value="/usr/bin/mitmweb"), \
             patch("idotaku.commands.run.get_tracker_script_path", return_value=Path("/fake/tracker.py")), \
             patch("idotaku.commands.run.print_banner"), \
             patch("idotaku.commands.run.console"), \
             patch("idotaku.commands.run.subprocess.Popen", side_effect=fake_popen):
            run_proxy(
                port=8080, web_port=8081, output="report.json",
                min_numeric=100, config="test.yaml", no_browser=True, browser="auto",
            )

        mitmweb_cmd = popen_calls[0]
        # Should have --set idotaku_config=<resolved path>
        assert "--set" in mitmweb_cmd
        config_idx = None
        for i, arg in enumerate(mitmweb_cmd):
            if arg == "--set" and i + 1 < len(mitmweb_cmd):
                if mitmweb_cmd[i + 1].startswith("idotaku_config="):
                    config_idx = i + 1
                    break
        assert config_idx is not None, "idotaku_config not found in mitmweb command"
        config_value = mitmweb_cmd[config_idx]
        assert "test.yaml" in config_value


class TestRunProxyKeyboardInterrupt:
    """Tests for run_proxy cleanup on KeyboardInterrupt."""

    def test_cleanup_runs_on_keyboard_interrupt(self):
        """Should terminate processes and clean up on KeyboardInterrupt."""
        mock_mitmweb_proc = MagicMock()
        mock_mitmweb_proc.wait.side_effect = KeyboardInterrupt()
        mock_mitmweb_proc.poll.return_value = None  # Still running
        mock_mitmweb_proc.terminate.return_value = None
        # After terminate, wait with timeout succeeds
        def mitmweb_wait_side_effect(timeout=None):
            if timeout is None:
                raise KeyboardInterrupt()
            return None
        mock_mitmweb_proc.wait.side_effect = mitmweb_wait_side_effect

        mock_browser_proc = MagicMock()
        mock_browser_proc.poll.return_value = None  # Still running

        call_count = [0]

        def fake_popen(cmd, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                return mock_mitmweb_proc
            return mock_browser_proc

        with patch("idotaku.commands.run.find_mitmweb", return_value="/usr/bin/mitmweb"), \
             patch("idotaku.commands.run.get_tracker_script_path", return_value=Path("/fake/tracker.py")), \
             patch("idotaku.commands.run.print_banner"), \
             patch("idotaku.commands.run.console"), \
             patch("idotaku.commands.run.subprocess.Popen", side_effect=fake_popen), \
             patch("idotaku.commands.run.find_browser", return_value=("chrome", "/usr/bin/chrome")), \
             patch("idotaku.commands.run.tempfile.mkdtemp", return_value="/tmp/idotaku_test"), \
             patch("idotaku.commands.run.os.path.exists", return_value=False), \
             patch("idotaku.commands.run.shutil.rmtree"):
            run_proxy(
                port=8080, web_port=8081, output="report.json",
                min_numeric=100, config=None, no_browser=False, browser="auto",
            )

        # mitmweb process should have been terminated
        mock_mitmweb_proc.terminate.assert_called_once()
        # browser process should have been terminated
        mock_browser_proc.terminate.assert_called_once()


class TestRunProxyTerminateTimeout:
    """Tests for run_proxy when process terminate times out."""

    def test_kills_process_on_terminate_timeout(self):
        """Should call kill() when mitmweb_proc.wait(timeout=5) raises TimeoutExpired."""
        mock_proc = MagicMock()

        # First call: wait() with no timeout raises KeyboardInterrupt
        # Second call: wait(timeout=5) raises TimeoutExpired
        wait_call_count = [0]

        def wait_side_effect(timeout=None):
            wait_call_count[0] += 1
            if timeout is None:
                raise KeyboardInterrupt()
            raise subprocess.TimeoutExpired(cmd="mitmweb", timeout=5)

        mock_proc.wait.side_effect = wait_side_effect
        mock_proc.poll.return_value = None  # Still running
        mock_proc.kill.return_value = None

        with patch("idotaku.commands.run.find_mitmweb", return_value="/usr/bin/mitmweb"), \
             patch("idotaku.commands.run.get_tracker_script_path", return_value=Path("/fake/tracker.py")), \
             patch("idotaku.commands.run.print_banner"), \
             patch("idotaku.commands.run.console"), \
             patch("idotaku.commands.run.subprocess.Popen", return_value=mock_proc):
            run_proxy(
                port=8080, web_port=8081, output="report.json",
                min_numeric=100, config=None, no_browser=True, browser="auto",
            )

        mock_proc.terminate.assert_called_once()
        mock_proc.kill.assert_called_once()


class TestRunProxyTempProfileCleanupError:
    """Tests for run_proxy when temp profile cleanup fails."""

    def test_handles_rmtree_oserror_gracefully(self):
        """Should handle OSError from shutil.rmtree gracefully."""
        mock_mitmweb_proc = MagicMock()
        mock_mitmweb_proc.wait.return_value = 0
        mock_mitmweb_proc.poll.return_value = 0

        mock_browser_proc = MagicMock()
        mock_browser_proc.poll.return_value = 0

        call_count = [0]

        def fake_popen(cmd, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                return mock_mitmweb_proc
            return mock_browser_proc

        with patch("idotaku.commands.run.find_mitmweb", return_value="/usr/bin/mitmweb"), \
             patch("idotaku.commands.run.get_tracker_script_path", return_value=Path("/fake/tracker.py")), \
             patch("idotaku.commands.run.print_banner"), \
             patch("idotaku.commands.run.console") as mock_console, \
             patch("idotaku.commands.run.subprocess.Popen", side_effect=fake_popen), \
             patch("idotaku.commands.run.find_browser", return_value=("chrome", "/usr/bin/chrome")), \
             patch("idotaku.commands.run.tempfile.mkdtemp", return_value="/tmp/idotaku_test"), \
             patch("idotaku.commands.run.os.path.exists", return_value=True), \
             patch("idotaku.commands.run.shutil.rmtree", side_effect=OSError("Permission denied")):
            # Should not raise
            run_proxy(
                port=8080, web_port=8081, output="report.json",
                min_numeric=100, config=None, no_browser=False, browser="auto",
            )

        # Should print a note about cleanup failure
        cleanup_calls = [
            c for c in mock_console.print.call_args_list
            if "Could not remove temp profile" in str(c)
        ]
        assert len(cleanup_calls) >= 1


class TestRunProxyNamedBrowserSuccess:
    """Tests for run_proxy when a named browser is found successfully."""

    def test_named_browser_found_launches_it_directly(self):
        """Should use find_browser_by_name and launch the browser when found."""
        mock_mitmweb_proc = MagicMock()
        mock_mitmweb_proc.wait.return_value = 0
        mock_mitmweb_proc.poll.return_value = 0

        mock_browser_proc = MagicMock()
        mock_browser_proc.poll.return_value = 0

        popen_calls = []

        def fake_popen(cmd, **kwargs):
            popen_calls.append(cmd)
            if len(popen_calls) == 1:
                return mock_mitmweb_proc
            return mock_browser_proc

        with patch("idotaku.commands.run.find_mitmweb", return_value="/usr/bin/mitmweb"), \
             patch("idotaku.commands.run.get_tracker_script_path", return_value=Path("/fake/tracker.py")), \
             patch("idotaku.commands.run.print_banner"), \
             patch("idotaku.commands.run.console"), \
             patch("idotaku.commands.run.subprocess.Popen", side_effect=fake_popen), \
             patch("idotaku.commands.run.find_browser_by_name", return_value=("chrome", "/usr/bin/chrome")) as mock_by_name, \
             patch("idotaku.commands.run.find_browser") as mock_find_auto, \
             patch("idotaku.commands.run.tempfile.mkdtemp", return_value="/tmp/idotaku_test"), \
             patch("idotaku.commands.run.os.path.exists", return_value=False):
            run_proxy(
                port=8080, web_port=8081, output="report.json",
                min_numeric=100, config=None, no_browser=False, browser="chrome",
            )
            mock_by_name.assert_called_once_with("chrome")
            mock_find_auto.assert_not_called()  # Should NOT fall back to auto

        # Two Popen calls: mitmweb + browser
        assert len(popen_calls) == 2
        browser_cmd = popen_calls[1]
        assert browser_cmd[0] == "/usr/bin/chrome"
        assert "--proxy-server=127.0.0.1:8080" in browser_cmd


class TestRunProxyAutoBrowserEdge:
    """Tests for run_proxy with auto browser detection finding edge."""

    def test_auto_browser_launches_edge_with_chrome_style_args(self):
        """Should launch edge with proxy and temp profile args (same as chrome)."""
        mock_mitmweb_proc = MagicMock()
        mock_mitmweb_proc.wait.return_value = 0
        mock_mitmweb_proc.poll.return_value = 0

        mock_browser_proc = MagicMock()
        mock_browser_proc.poll.return_value = 0

        popen_calls = []

        def fake_popen(cmd, **kwargs):
            popen_calls.append(cmd)
            if len(popen_calls) == 1:
                return mock_mitmweb_proc
            return mock_browser_proc

        with patch("idotaku.commands.run.find_mitmweb", return_value="/usr/bin/mitmweb"), \
             patch("idotaku.commands.run.get_tracker_script_path", return_value=Path("/fake/tracker.py")), \
             patch("idotaku.commands.run.print_banner"), \
             patch("idotaku.commands.run.console"), \
             patch("idotaku.commands.run.subprocess.Popen", side_effect=fake_popen), \
             patch("idotaku.commands.run.find_browser", return_value=("edge", r"C:\Program Files\Microsoft\Edge\Application\msedge.exe")), \
             patch("idotaku.commands.run.tempfile.mkdtemp", return_value="/tmp/idotaku_test"), \
             patch("idotaku.commands.run.os.path.exists", return_value=False):
            run_proxy(
                port=8080, web_port=8081, output="report.json",
                min_numeric=100, config=None, no_browser=False, browser="auto",
            )

        assert len(popen_calls) == 2
        browser_cmd = popen_calls[1]
        assert browser_cmd[0] == r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"
        assert "--proxy-server=127.0.0.1:8080" in browser_cmd
        assert any("--user-data-dir=" in arg for arg in browser_cmd)
        assert "--ignore-certificate-errors" in browser_cmd
        assert "--no-first-run" in browser_cmd
        assert "--no-default-browser-check" in browser_cmd
