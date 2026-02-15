"""Tests for the demo runner utility functions."""

import importlib.util
import os
import socket
import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


# Import run_demo.py from examples/vulnerable_api/ (not a package)
_DEMO_PATH = Path(__file__).parent.parent / "examples" / "vulnerable_api" / "run_demo.py"
_spec = importlib.util.spec_from_file_location("run_demo", _DEMO_PATH)
run_demo = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(run_demo)


class TestCheckPortFree:
    """Tests for check_port_free()."""

    def test_free_port_returns_true(self):
        """A random high port should be free."""
        # Use port 0 trick to find a free port
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("127.0.0.1", 0))
            free_port = s.getsockname()[1]
        # Port is now released, should be free
        assert run_demo.check_port_free(free_port) is True

    def test_occupied_port_returns_false(self):
        """A port that's already bound should return False."""
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("127.0.0.1", 0))
            occupied_port = s.getsockname()[1]
            # Port is still bound, should not be free
            assert run_demo.check_port_free(occupied_port) is False


class TestWaitForUrl:
    """Tests for wait_for_url()."""

    def test_timeout_on_unreachable_url(self):
        """Should return False quickly when URL is unreachable."""
        result = run_demo.wait_for_url("http://127.0.0.1:1", timeout=1)
        assert result is False

    def test_success_with_mock_server(self):
        """Should return True when URL responds with 200."""
        import http.server
        import threading

        # Start a minimal HTTP server
        handler = http.server.BaseHTTPRequestHandler

        class OKHandler(handler):
            def do_GET(self):
                self.send_response(200)
                self.end_headers()

            def log_message(self, format, *args):
                pass  # Suppress log output

        server = http.server.HTTPServer(("127.0.0.1", 0), OKHandler)
        port = server.server_address[1]
        thread = threading.Thread(target=server.serve_forever)
        thread.daemon = True
        thread.start()

        try:
            result = run_demo.wait_for_url(f"http://127.0.0.1:{port}/", timeout=5)
            assert result is True
        finally:
            server.shutdown()


class TestFindMitmdump:
    """Tests for find_mitmdump()."""

    def test_found_via_which(self):
        """Should return path when mitmdump is on PATH."""
        with patch("shutil.which", return_value="/usr/bin/mitmdump"):
            result = run_demo.find_mitmdump()
            assert result == "/usr/bin/mitmdump"

    def test_found_via_scripts_dir(self, tmp_path):
        """Should find mitmdump in Python Scripts directory."""
        scripts_dir = tmp_path / "Scripts"
        scripts_dir.mkdir()
        mitmdump_exe = scripts_dir / "mitmdump.exe"
        mitmdump_exe.touch()

        with patch("shutil.which", return_value=None), \
             patch.object(sys, "prefix", str(tmp_path)):
            result = run_demo.find_mitmdump()
            assert result == str(mitmdump_exe)

    def test_not_found_raises(self):
        """Should raise FileNotFoundError when not found anywhere."""
        with patch("shutil.which", return_value=None), \
             patch.dict(os.environ, {"APPDATA": ""}, clear=False), \
             patch.object(sys, "prefix", "/nonexistent"):
            with pytest.raises(FileNotFoundError, match="mitmdump not found"):
                run_demo.find_mitmdump()


class TestFindIdotaku:
    """Tests for find_idotaku()."""

    def test_found_via_which(self):
        """Should return path when idotaku is on PATH."""
        with patch("shutil.which", return_value="/usr/bin/idotaku"):
            result = run_demo.find_idotaku()
            assert result == "/usr/bin/idotaku"

    def test_found_via_scripts_dir(self, tmp_path):
        """Should find idotaku in Python Scripts directory."""
        scripts_dir = tmp_path / "Scripts"
        scripts_dir.mkdir()
        idotaku_exe = scripts_dir / "idotaku.exe"
        idotaku_exe.touch()

        with patch("shutil.which", return_value=None), \
             patch.object(sys, "prefix", str(tmp_path)):
            result = run_demo.find_idotaku()
            assert result == str(idotaku_exe)

    def test_not_found_raises(self):
        """Should raise FileNotFoundError when not found."""
        with patch("shutil.which", return_value=None), \
             patch.object(sys, "prefix", "/nonexistent"):
            with pytest.raises(FileNotFoundError, match="idotaku not found"):
                run_demo.find_idotaku()


class TestGetTrackerPath:
    """Tests for get_tracker_path()."""

    def test_returns_tracker_py_path(self):
        """Should return a valid path to tracker.py."""
        result = run_demo.get_tracker_path()
        assert result.endswith("tracker.py")
        assert Path(result).exists()


class TestTerminateProcess:
    """Tests for terminate_process()."""

    def test_already_exited_process(self):
        """Should do nothing for an already-exited process."""
        mock_proc = MagicMock()
        mock_proc.poll.return_value = 0  # Already exited
        run_demo.terminate_process(mock_proc)
        mock_proc.terminate.assert_not_called()
        mock_proc.kill.assert_not_called()

    def test_terminate_running_process(self):
        """Should terminate a running process."""
        mock_proc = MagicMock()
        mock_proc.poll.return_value = None  # Still running
        mock_proc.wait.return_value = None

        with patch("os.name", "posix"):
            run_demo.terminate_process(mock_proc)
            mock_proc.terminate.assert_called_once()

    def test_kill_on_timeout(self):
        """Should kill if terminate times out."""
        mock_proc = MagicMock()
        mock_proc.poll.return_value = None
        mock_proc.terminate.return_value = None
        # terminate().wait() raises TimeoutExpired, then kill().wait() succeeds
        mock_proc.wait.side_effect = [
            subprocess.TimeoutExpired(cmd="test", timeout=5),  # first wait (after terminate)
            None,  # second wait (after kill)
        ]

        with patch("os.name", "posix"):
            run_demo.terminate_process(mock_proc)
            mock_proc.kill.assert_called_once()

    def test_real_process_termination(self):
        """Should terminate a real subprocess."""
        # Start a long-running process
        if os.name == "nt":
            proc = subprocess.Popen(
                [sys.executable, "-c", "import time; time.sleep(60)"],
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP,
            )
        else:
            proc = subprocess.Popen(
                [sys.executable, "-c", "import time; time.sleep(60)"],
            )

        assert proc.poll() is None  # Still running
        run_demo.terminate_process(proc)
        assert proc.poll() is not None  # Now exited


class TestRunCommand:
    """Tests for run_command()."""

    def test_runs_command_and_prints_header(self, capsys):
        """Should run a command and print a header."""
        run_demo.run_command([sys.executable, "-c", "print('hello')"], "Test Label")
        captured = capsys.readouterr()
        assert "Test Label" in captured.out
        # subprocess output goes to the real stdout, not capsys
        # Just verify the header is printed and no exception is raised


class TestOutputHelpers:
    """Tests for info(), success(), error(), header()."""

    def test_info_output(self, capsys):
        run_demo.info("test message")
        captured = capsys.readouterr()
        assert "test message" in captured.out
        assert "[INFO]" in captured.out

    def test_success_output(self, capsys):
        run_demo.success("done")
        captured = capsys.readouterr()
        assert "done" in captured.out
        assert "[OK]" in captured.out

    def test_error_output(self, capsys):
        run_demo.error("failed")
        captured = capsys.readouterr()
        assert "failed" in captured.err
        assert "[ERROR]" in captured.err

    def test_header_output(self, capsys):
        run_demo.header("Section")
        captured = capsys.readouterr()
        assert "Section" in captured.out
        assert "=====" in captured.out


class TestRequirementsFile:
    """Tests for requirements.txt content."""

    def test_requirements_file_exists(self):
        req_file = Path(__file__).parent.parent / "examples" / "vulnerable_api" / "requirements.txt"
        assert req_file.exists()

    def test_requirements_has_expected_packages(self):
        req_file = Path(__file__).parent.parent / "examples" / "vulnerable_api" / "requirements.txt"
        content = req_file.read_text()
        assert "fastapi" in content
        assert "uvicorn" in content
        assert "requests" in content

    def test_requirements_has_version_constraints(self):
        req_file = Path(__file__).parent.parent / "examples" / "vulnerable_api" / "requirements.txt"
        content = req_file.read_text()
        lines = [line.strip() for line in content.splitlines() if line.strip()]
        for line in lines:
            assert ">=" in line, f"Missing version constraint in: {line}"


class TestDemoShellScript:
    """Tests for run_demo.sh content."""

    def test_shell_script_exists(self):
        script = Path(__file__).parent.parent / "examples" / "vulnerable_api" / "run_demo.sh"
        assert script.exists()

    def test_shell_script_has_shebang(self):
        script = Path(__file__).parent.parent / "examples" / "vulnerable_api" / "run_demo.sh"
        content = script.read_text()
        assert content.startswith("#!/usr/bin/env bash")

    def test_shell_script_has_set_options(self):
        script = Path(__file__).parent.parent / "examples" / "vulnerable_api" / "run_demo.sh"
        content = script.read_text()
        assert "set -euo pipefail" in content

    def test_shell_script_has_cleanup_trap(self):
        script = Path(__file__).parent.parent / "examples" / "vulnerable_api" / "run_demo.sh"
        content = script.read_text()
        assert "trap cleanup EXIT" in content

    def test_shell_script_has_all_analysis_commands(self):
        script = Path(__file__).parent.parent / "examples" / "vulnerable_api" / "run_demo.sh"
        content = script.read_text()
        assert "idotaku report" in content
        assert "idotaku score" in content
        assert "idotaku chain" in content
        assert "idotaku auth" in content

    def test_shell_script_generates_html_exports(self):
        script = Path(__file__).parent.parent / "examples" / "vulnerable_api" / "run_demo.sh"
        content = script.read_text()
        assert "--html" in content
        assert "chain.html" in content
        assert "sequence.html" in content


class TestDemoScriptStructure:
    """Tests for run_demo.py script structure."""

    def test_module_has_main_function(self):
        assert hasattr(run_demo, "main")
        assert callable(run_demo.main)

    def test_module_has_all_utility_functions(self):
        expected = [
            "check_port_free", "wait_for_url", "find_mitmdump",
            "find_idotaku", "get_tracker_path", "terminate_process",
            "run_command", "info", "success", "error", "header",
        ]
        for name in expected:
            assert hasattr(run_demo, name), f"Missing function: {name}"

    def test_script_dir_points_to_examples(self):
        assert run_demo.SCRIPT_DIR.name == "vulnerable_api"
        assert (run_demo.SCRIPT_DIR / "server.py").exists()
        assert (run_demo.SCRIPT_DIR / "test_scenario.py").exists()
