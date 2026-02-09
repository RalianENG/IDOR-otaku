"""Tests for config commands."""

import pytest
from click.testing import CliRunner

from idotaku.cli import main


@pytest.fixture
def runner():
    return CliRunner()


class TestConfigInit:
    def test_creates_file(self, runner, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        result = runner.invoke(main, ["config", "init"])
        assert result.exit_code == 0
        assert "Config file created" in result.output
        assert (tmp_path / "idotaku.yaml").exists()

    def test_no_overwrite(self, runner, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        (tmp_path / "idotaku.yaml").write_text("existing: true")
        result = runner.invoke(main, ["config", "init"])
        assert result.exit_code == 0
        assert "already exists" in result.output
        assert (tmp_path / "idotaku.yaml").read_text() == "existing: true"

    def test_force_overwrite(self, runner, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        (tmp_path / "idotaku.yaml").write_text("existing: true")
        result = runner.invoke(main, ["config", "init", "--force"])
        assert result.exit_code == 0
        assert "Config file created" in result.output
        assert "existing" not in (tmp_path / "idotaku.yaml").read_text()

    def test_custom_filename(self, runner, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        result = runner.invoke(main, ["config", "init", "--filename", "custom.yaml"])
        assert result.exit_code == 0
        assert (tmp_path / "custom.yaml").exists()


class TestConfigShow:
    def test_show_defaults(self, runner, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        result = runner.invoke(main, ["config", "show"])
        assert result.exit_code == 0
        assert "output" in result.output
        assert "min_numeric" in result.output

    def test_show_with_file(self, runner, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        cfg = tmp_path / "test.yaml"
        cfg.write_text("idotaku:\n  min_numeric: 500\n")
        result = runner.invoke(main, ["config", "show", "-c", str(cfg)])
        assert result.exit_code == 0
        assert "500" in result.output


class TestConfigGet:
    def test_get_scalar(self, runner, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        result = runner.invoke(main, ["config", "get", "min_numeric"])
        assert result.exit_code == 0
        assert "100" in result.output

    def test_get_nested(self, runner, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        result = runner.invoke(main, ["config", "get", "patterns.uuid"])
        assert result.exit_code == 0

    def test_get_unknown_key(self, runner, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        result = runner.invoke(main, ["config", "get", "nonexistent"])
        assert result.exit_code != 0
        assert "Unknown key" in result.output


class TestConfigSet:
    def test_set_value(self, runner, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        runner.invoke(main, ["config", "init"])
        result = runner.invoke(main, ["config", "set", "min_numeric", "500"])
        assert result.exit_code == 0
        assert "Set" in result.output
        # Verify
        result = runner.invoke(main, ["config", "get", "min_numeric"])
        assert "500" in result.output

    def test_set_no_file(self, runner, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        result = runner.invoke(main, ["config", "set", "min_numeric", "500"])
        assert result.exit_code != 0
        assert "No config file" in result.output

    def test_set_list_value(self, runner, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        runner.invoke(main, ["config", "init"])
        result = runner.invoke(main, ["config", "set", "target_domains", "api.example.com,*.test.com"])
        assert result.exit_code == 0


class TestConfigValidate:
    def test_valid_config(self, runner, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        runner.invoke(main, ["config", "init"])
        result = runner.invoke(main, ["config", "validate"])
        assert result.exit_code == 0
        assert "valid" in result.output.lower()

    def test_invalid_regex(self, runner, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        cfg = tmp_path / "idotaku.yaml"
        cfg.write_text('idotaku:\n  patterns:\n    bad: "[invalid(regex"\n')
        result = runner.invoke(main, ["config", "validate"])
        assert result.exit_code != 0
        assert "error" in result.output.lower()

    def test_no_file(self, runner, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        result = runner.invoke(main, ["config", "validate"])
        assert result.exit_code == 0
        assert "No config file" in result.output


class TestConfigPath:
    def test_found(self, runner, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        (tmp_path / "idotaku.yaml").write_text("idotaku:\n  output: test.json\n")
        result = runner.invoke(main, ["config", "path"])
        assert result.exit_code == 0
        assert "idotaku.yaml" in result.output

    def test_not_found(self, runner, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        result = runner.invoke(main, ["config", "path"])
        assert result.exit_code != 0
        assert "No config file" in result.output
