"""Tests for interactive CLI prompts."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from idotaku.interactive import (
    ANALYSIS_COMMANDS,
    COMMANDS,
    _run_config_setup,
    prompt_command,
    prompt_continue,
    prompt_domains,
    prompt_html_output,
    prompt_proxy_settings,
    prompt_report_file,
    run_interactive_mode,
)


def _prompt(return_value):
    """Create mock questionary prompt with .ask() returning given value."""
    m = MagicMock()
    m.ask.return_value = return_value
    return m


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

class TestConstants:
    def test_commands_not_empty(self):
        assert len(COMMANDS) > 0

    def test_analysis_commands_subset(self):
        command_values = {c["value"] for c in COMMANDS}
        for cmd in ANALYSIS_COMMANDS:
            assert cmd in command_values


# ---------------------------------------------------------------------------
# prompt_command
# ---------------------------------------------------------------------------

class TestPromptCommand:
    @patch("idotaku.interactive.questionary")
    def test_returns_selected(self, mock_q):
        mock_q.select.return_value = _prompt("report")
        assert prompt_command() == "report"

    @patch("idotaku.interactive.questionary")
    def test_cancel(self, mock_q):
        mock_q.select.return_value = _prompt(None)
        assert prompt_command() is None


# ---------------------------------------------------------------------------
# prompt_report_file
# ---------------------------------------------------------------------------

class TestPromptReportFile:
    @patch("idotaku.interactive.questionary")
    def test_no_json_files(self, mock_q, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        mock_q.path.return_value = _prompt("/some/report.json")
        assert prompt_report_file() == "/some/report.json"

    @patch("idotaku.interactive.questionary")
    def test_selects_existing_file(self, mock_q, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        (tmp_path / "report.json").write_text("{}")
        mock_q.select.return_value = _prompt(str(tmp_path / "report.json"))
        result = prompt_report_file()
        assert "report.json" in result

    @patch("idotaku.interactive.questionary")
    def test_other_option(self, mock_q, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        (tmp_path / "report.json").write_text("{}")
        mock_q.select.return_value = _prompt("__other__")
        mock_q.path.return_value = _prompt("custom.json")
        assert prompt_report_file() == "custom.json"

    @patch("idotaku.interactive.questionary")
    def test_cancel(self, mock_q, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        (tmp_path / "report.json").write_text("{}")
        mock_q.select.return_value = _prompt(None)
        assert prompt_report_file() is None


# ---------------------------------------------------------------------------
# prompt_domains
# ---------------------------------------------------------------------------

class TestPromptDomains:
    def test_single_domain_no_filter(self):
        flows = [
            {"url": "https://api.example.com/a"},
            {"url": "https://api.example.com/b"},
        ]
        assert prompt_domains(flows) == []

    @patch("idotaku.interactive.questionary")
    def test_multiple_domains_subset(self, mock_q):
        flows = [{"url": f"https://a.com/{i}"} for i in range(15)]
        flows += [{"url": f"https://b.com/{i}"} for i in range(15)]
        mock_q.checkbox.return_value = _prompt(["a.com"])
        assert prompt_domains(flows) == ["a.com"]

    @patch("idotaku.interactive.questionary")
    def test_all_selected_means_no_filter(self, mock_q):
        flows = [{"url": f"https://a.com/{i}"} for i in range(15)]
        flows += [{"url": f"https://b.com/{i}"} for i in range(15)]
        mock_q.checkbox.return_value = _prompt(["a.com", "b.com"])
        assert prompt_domains(flows) == []

    @patch("idotaku.interactive.questionary")
    def test_cancel(self, mock_q):
        flows = [{"url": f"https://a.com/{i}"} for i in range(15)]
        flows += [{"url": f"https://b.com/{i}"} for i in range(15)]
        mock_q.checkbox.return_value = _prompt(None)
        assert prompt_domains(flows) is None

    def test_below_min_flows(self):
        flows = [{"url": "https://a.com/1"}, {"url": "https://b.com/1"}]
        assert prompt_domains(flows, min_flows=10) == []

    def test_empty_flows(self):
        assert prompt_domains([]) == []

    def test_empty_urls(self):
        flows = [{"url": ""}, {"no_url": "x"}]
        assert prompt_domains(flows) == []


# ---------------------------------------------------------------------------
# prompt_html_output
# ---------------------------------------------------------------------------

class TestPromptHtmlOutput:
    @patch("idotaku.interactive.questionary")
    def test_yes(self, mock_q):
        mock_q.confirm.return_value = _prompt(True)
        mock_q.path.return_value = _prompt("out.html")
        assert prompt_html_output() == "out.html"

    @patch("idotaku.interactive.questionary")
    def test_no(self, mock_q):
        mock_q.confirm.return_value = _prompt(False)
        assert prompt_html_output() is None


# ---------------------------------------------------------------------------
# prompt_continue
# ---------------------------------------------------------------------------

class TestPromptContinue:
    @patch("idotaku.interactive.questionary")
    def test_yes(self, mock_q):
        mock_q.confirm.return_value = _prompt(True)
        assert prompt_continue() is True

    @patch("idotaku.interactive.questionary")
    def test_no(self, mock_q):
        mock_q.confirm.return_value = _prompt(False)
        assert prompt_continue() is False

    @patch("idotaku.interactive.questionary")
    def test_none_returns_false(self, mock_q):
        mock_q.confirm.return_value = _prompt(None)
        assert prompt_continue() is False


# ---------------------------------------------------------------------------
# prompt_proxy_settings
# ---------------------------------------------------------------------------

class TestPromptProxySettings:
    @patch("idotaku.interactive.questionary")
    def test_complete(self, mock_q):
        mock_q.select.return_value = _prompt("chrome")
        mock_q.text.side_effect = [_prompt("8080"), _prompt("report.json")]
        result = prompt_proxy_settings()
        assert result == {"browser": "chrome", "port": 8080, "output": "report.json"}

    @patch("idotaku.interactive.questionary")
    def test_cancel_browser(self, mock_q):
        mock_q.select.return_value = _prompt(None)
        assert prompt_proxy_settings() is None

    @patch("idotaku.interactive.questionary")
    def test_cancel_port(self, mock_q):
        mock_q.select.return_value = _prompt("auto")
        mock_q.text.side_effect = [_prompt(None)]
        assert prompt_proxy_settings() is None

    @patch("idotaku.interactive.questionary")
    def test_cancel_output(self, mock_q):
        mock_q.select.return_value = _prompt("auto")
        mock_q.text.side_effect = [_prompt("8080"), _prompt(None)]
        assert prompt_proxy_settings() is None

    @patch("idotaku.interactive.questionary")
    def test_non_numeric_port_defaults(self, mock_q):
        mock_q.select.return_value = _prompt("auto")
        mock_q.text.side_effect = [_prompt("abc"), _prompt("out.json")]
        result = prompt_proxy_settings()
        assert result["port"] == 8080


# ---------------------------------------------------------------------------
# _run_config_setup
# ---------------------------------------------------------------------------

class TestRunConfigSetup:
    @patch("idotaku.interactive.questionary")
    def test_create_and_configure(self, mock_q, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        console = MagicMock()
        mock_q.confirm.return_value = _prompt(True)
        mock_q.text.side_effect = [
            _prompt("custom.json"),
            _prompt("200"),
            _prompt("api.example.com"),
            _prompt(""),
            _prompt(""),
        ]
        _run_config_setup(console)
        assert (tmp_path / "idotaku.yaml").exists()

    @patch("idotaku.interactive.questionary")
    def test_decline_creation(self, mock_q, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        console = MagicMock()
        mock_q.confirm.return_value = _prompt(False)
        _run_config_setup(console)
        assert not (tmp_path / "idotaku.yaml").exists()

    @patch("idotaku.interactive.questionary")
    def test_cancel_at_output(self, mock_q, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        from idotaku.config import get_default_config_yaml
        (tmp_path / "idotaku.yaml").write_text(get_default_config_yaml(), encoding="utf-8")
        console = MagicMock()
        mock_q.text.return_value = _prompt(None)
        _run_config_setup(console)

    @patch("idotaku.interactive.questionary")
    def test_cancel_at_min_numeric(self, mock_q, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        from idotaku.config import get_default_config_yaml
        (tmp_path / "idotaku.yaml").write_text(get_default_config_yaml(), encoding="utf-8")
        console = MagicMock()
        mock_q.text.side_effect = [_prompt("id_tracker_report.json"), _prompt(None)]
        _run_config_setup(console)

    @patch("idotaku.interactive.questionary")
    def test_cancel_at_target_domains(self, mock_q, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        from idotaku.config import get_default_config_yaml
        (tmp_path / "idotaku.yaml").write_text(get_default_config_yaml(), encoding="utf-8")
        console = MagicMock()
        mock_q.text.side_effect = [
            _prompt("id_tracker_report.json"), _prompt("100"), _prompt(None),
        ]
        _run_config_setup(console)

    @patch("idotaku.interactive.questionary")
    def test_cancel_at_exclude_domains(self, mock_q, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        from idotaku.config import get_default_config_yaml
        (tmp_path / "idotaku.yaml").write_text(get_default_config_yaml(), encoding="utf-8")
        console = MagicMock()
        mock_q.text.side_effect = [
            _prompt("id_tracker_report.json"), _prompt("100"),
            _prompt(""), _prompt(None),
        ]
        _run_config_setup(console)

    @patch("idotaku.interactive.questionary")
    def test_cancel_at_extra_headers(self, mock_q, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        from idotaku.config import get_default_config_yaml
        (tmp_path / "idotaku.yaml").write_text(get_default_config_yaml(), encoding="utf-8")
        console = MagicMock()
        mock_q.text.side_effect = [
            _prompt("id_tracker_report.json"), _prompt("100"),
            _prompt(""), _prompt(""), _prompt(None),
        ]
        _run_config_setup(console)

    @patch("idotaku.interactive.questionary")
    def test_no_changes_when_defaults_kept(self, mock_q, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        from idotaku.config import get_default_config_yaml
        (tmp_path / "idotaku.yaml").write_text(get_default_config_yaml(), encoding="utf-8")
        console = MagicMock()
        mock_q.text.side_effect = [
            _prompt("id_tracker_report.json"),
            _prompt("100"),
            _prompt(""),
            _prompt(""),
            _prompt(""),
        ]
        _run_config_setup(console)

    @patch("idotaku.interactive.questionary")
    def test_set_all_values(self, mock_q, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        from idotaku.config import get_default_config_yaml, load_config
        (tmp_path / "idotaku.yaml").write_text(get_default_config_yaml(), encoding="utf-8")
        console = MagicMock()
        mock_q.text.side_effect = [
            _prompt("custom.json"),
            _prompt("50"),
            _prompt("api.example.com,api2.example.com"),
            _prompt("analytics.example.com"),
            _prompt("x-trace-id,x-debug"),
        ]
        _run_config_setup(console)
        cfg = load_config(str(tmp_path / "idotaku.yaml"))
        assert cfg.output == "custom.json"
        assert cfg.min_numeric == 50


# ---------------------------------------------------------------------------
# run_interactive_mode
# ---------------------------------------------------------------------------

class TestRunInteractiveMode:
    @patch("idotaku.interactive.prompt_command", return_value=None)
    @patch("idotaku.banner.print_banner")
    def test_cancel_at_command(self, mock_banner, mock_cmd):
        run_interactive_mode()
        mock_banner.assert_called_once()

    @patch("idotaku.interactive.prompt_proxy_settings", return_value=None)
    @patch("idotaku.interactive.prompt_command", return_value="proxy")
    @patch("idotaku.banner.print_banner")
    def test_proxy_cancel(self, mock_banner, mock_cmd, mock_settings):
        run_interactive_mode()

    @patch("idotaku.commands.run_proxy")
    @patch("idotaku.interactive.prompt_proxy_settings")
    @patch("idotaku.interactive.prompt_command", return_value="proxy")
    @patch("idotaku.banner.print_banner")
    def test_proxy_complete(self, mock_banner, mock_cmd, mock_settings, mock_run):
        mock_settings.return_value = {
            "browser": "auto", "port": 8080, "output": "out.json",
        }
        run_interactive_mode()
        mock_run.assert_called_once()

    @patch("idotaku.interactive.prompt_continue", return_value=False)
    @patch("click.echo")
    @patch("click.testing.CliRunner")
    @patch("idotaku.interactive.questionary")
    @patch("idotaku.interactive.prompt_command", return_value="config")
    @patch("idotaku.banner.print_banner")
    def test_config_show(self, mock_banner, mock_cmd, mock_q,
                         MockRunner, mock_echo, mock_continue):
        mock_q.select.return_value = _prompt("show")
        mock_result = MagicMock()
        mock_result.output = "Config output"
        MockRunner.return_value.invoke.return_value = mock_result
        run_interactive_mode()

    @patch("idotaku.interactive.questionary")
    @patch("idotaku.interactive.prompt_command", return_value="config")
    @patch("idotaku.banner.print_banner")
    def test_config_cancel(self, mock_banner, mock_cmd, mock_q):
        mock_q.select.return_value = _prompt(None)
        run_interactive_mode()

    @patch("idotaku.interactive.prompt_continue", return_value=False)
    @patch("idotaku.interactive._run_config_setup")
    @patch("idotaku.interactive.questionary")
    @patch("idotaku.interactive.prompt_command", return_value="config")
    @patch("idotaku.banner.print_banner")
    def test_config_setup(self, mock_banner, mock_cmd, mock_q,
                          mock_setup, mock_continue):
        mock_q.select.return_value = _prompt("setup")
        run_interactive_mode()
        mock_setup.assert_called_once()

    @patch("idotaku.interactive.prompt_command", return_value="report")
    @patch("idotaku.interactive.prompt_report_file", return_value=None)
    @patch("idotaku.banner.print_banner")
    def test_analysis_cancel_at_file(self, mock_banner, mock_file, mock_cmd):
        run_interactive_mode()

    @patch("idotaku.interactive.prompt_command")
    @patch("idotaku.interactive.prompt_report_file", return_value="bad.json")
    @patch("idotaku.banner.print_banner")
    def test_analysis_load_error(self, mock_banner, mock_file, mock_cmd):
        mock_cmd.side_effect = ["report", None]
        from idotaku.report import ReportLoadError
        with patch("idotaku.report.load_report", side_effect=ReportLoadError("bad")):
            run_interactive_mode()

    @patch("idotaku.interactive.prompt_command")
    @patch("idotaku.interactive.prompt_report_file", return_value="empty.json")
    @patch("idotaku.banner.print_banner")
    def test_analysis_empty_flows(self, mock_banner, mock_file, mock_cmd):
        mock_cmd.side_effect = ["report", None]
        mock_data = MagicMock()
        mock_data.flows = []
        with patch("idotaku.report.load_report", return_value=mock_data):
            run_interactive_mode()

    @patch("idotaku.interactive.prompt_continue", return_value=False)
    @patch("click.echo")
    @patch("click.testing.CliRunner")
    @patch("idotaku.interactive.prompt_report_file", return_value="report.json")
    @patch("idotaku.interactive.prompt_command", return_value="report")
    @patch("idotaku.banner.print_banner")
    def test_analysis_report_success(self, mock_banner, mock_cmd, mock_file,
                                     MockRunner, mock_echo, mock_continue):
        mock_data = MagicMock()
        mock_data.flows = [{"url": "https://a.com"}]
        mock_result = MagicMock()
        mock_result.output = "Report output"
        MockRunner.return_value.invoke.return_value = mock_result
        with patch("idotaku.report.load_report", return_value=mock_data):
            run_interactive_mode()

    @patch("idotaku.interactive.prompt_continue", return_value=False)
    @patch("click.echo")
    @patch("click.testing.CliRunner")
    @patch("idotaku.interactive.prompt_html_output", return_value="chain.html")
    @patch("idotaku.interactive.prompt_domains", return_value=["a.com"])
    @patch("idotaku.interactive.prompt_report_file", return_value="report.json")
    @patch("idotaku.interactive.prompt_command", return_value="chain")
    @patch("idotaku.banner.print_banner")
    def test_chain_with_domains_and_html(self, mock_banner, mock_cmd, mock_file,
                                         mock_domains, mock_html,
                                         MockRunner, mock_echo, mock_continue):
        mock_data = MagicMock()
        mock_data.flows = [{"url": "https://a.com/1"}]
        mock_result = MagicMock()
        mock_result.output = "Chain output"
        MockRunner.return_value.invoke.return_value = mock_result
        with patch("idotaku.report.load_report", return_value=mock_data):
            run_interactive_mode()
        # Verify CliRunner was called with domain and html args
        call_args = MockRunner.return_value.invoke.call_args
        args = call_args[0][1]  # positional args[1] is the command list
        assert "--domains" in args
        assert "--html" in args

    @patch("idotaku.interactive.prompt_command", return_value="chain")
    @patch("idotaku.interactive.prompt_report_file", return_value="report.json")
    @patch("idotaku.interactive.prompt_domains", return_value=None)
    @patch("idotaku.banner.print_banner")
    def test_chain_cancel_at_domains(self, mock_banner, mock_domains,
                                     mock_file, mock_cmd):
        mock_data = MagicMock()
        mock_data.flows = [{"url": "https://a.com/1"}]
        with patch("idotaku.report.load_report", return_value=mock_data):
            run_interactive_mode()
