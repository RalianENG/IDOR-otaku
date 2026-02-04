"""Tests for CLI commands."""

import pytest
from click.testing import CliRunner

from idotaku.cli import main


@pytest.fixture
def runner():
    """Create a CLI test runner."""
    return CliRunner()


class TestCliMain:
    """Tests for main CLI group."""

    def test_help(self, runner):
        """Test --help option."""
        result = runner.invoke(main, ["--help"])
        assert result.exit_code == 0
        assert "idotaku" in result.output
        assert "API ID tracking tool" in result.output

    def test_version_command(self, runner):
        """Test version command."""
        result = runner.invoke(main, ["version"])
        assert result.exit_code == 0
        assert "idotaku" in result.output


class TestReportCommand:
    """Tests for report command."""

    def test_report_help(self, runner):
        """Test report --help."""
        result = runner.invoke(main, ["report", "--help"])
        assert result.exit_code == 0
        assert "View ID tracking report" in result.output

    def test_report_with_file(self, runner, sample_report_file):
        """Test report command with valid file."""
        result = runner.invoke(main, ["report", str(sample_report_file)])
        assert result.exit_code == 0
        assert "ID Tracker Report" in result.output
        assert "Total unique IDs" in result.output

    def test_report_nonexistent_file(self, runner, tmp_path):
        """Test report command with non-existent file."""
        result = runner.invoke(main, ["report", str(tmp_path / "nonexistent.json")])
        assert result.exit_code != 0


class TestSequenceCommand:
    """Tests for sequence command."""

    def test_sequence_help(self, runner):
        """Test sequence --help."""
        result = runner.invoke(main, ["sequence", "--help"])
        assert result.exit_code == 0
        assert "API call sequence" in result.output

    def test_sequence_with_file(self, runner, sample_report_file):
        """Test sequence command with valid file."""
        result = runner.invoke(main, ["sequence", str(sample_report_file)])
        assert result.exit_code == 0
        assert "API Sequence Timeline" in result.output

    def test_sequence_limit(self, runner, sample_report_file):
        """Test sequence command with --limit option."""
        result = runner.invoke(main, ["sequence", str(sample_report_file), "--limit", "5"])
        assert result.exit_code == 0


class TestLifelineCommand:
    """Tests for lifeline command."""

    def test_lifeline_help(self, runner):
        """Test lifeline --help."""
        result = runner.invoke(main, ["lifeline", "--help"])
        assert result.exit_code == 0
        assert "lifespan" in result.output.lower()

    def test_lifeline_with_file(self, runner, sample_report_file):
        """Test lifeline command with valid file."""
        result = runner.invoke(main, ["lifeline", str(sample_report_file)])
        assert result.exit_code == 0
        assert "Parameter Lifeline" in result.output

    def test_lifeline_sort_options(self, runner, sample_report_file):
        """Test lifeline command with different sort options."""
        for sort_opt in ["lifespan", "uses", "first"]:
            result = runner.invoke(main, ["lifeline", str(sample_report_file), "--sort", sort_opt])
            assert result.exit_code == 0


class TestChainCommand:
    """Tests for chain command."""

    def test_chain_help(self, runner):
        """Test chain --help."""
        result = runner.invoke(main, ["chain", "--help"])
        assert result.exit_code == 0
        assert "parameter chains" in result.output.lower()

    def test_chain_with_file(self, runner, sample_report_file):
        """Test chain command with valid file."""
        result = runner.invoke(main, ["chain", str(sample_report_file)])
        assert result.exit_code == 0

    def test_chain_min_depth(self, runner, sample_report_file):
        """Test chain command with --min-depth option."""
        result = runner.invoke(main, ["chain", str(sample_report_file), "--min-depth", "1"])
        assert result.exit_code == 0

    def test_chain_domain_filter(self, runner, sample_report_file):
        """Test chain command with --domains option."""
        result = runner.invoke(main, ["chain", str(sample_report_file), "--domains", "api.example.com"])
        assert result.exit_code == 0

    def test_chain_domain_filter_wildcard(self, runner, sample_report_file):
        """Test chain command with wildcard domain filter."""
        result = runner.invoke(main, ["chain", str(sample_report_file), "--domains", "*.example.com"])
        assert result.exit_code == 0


class TestInteractiveCommand:
    """Tests for interactive command."""

    def test_interactive_help(self, runner):
        """Test interactive --help."""
        result = runner.invoke(main, ["interactive", "--help"])
        assert result.exit_code == 0
        assert "interactive mode" in result.output.lower()

    def test_interactive_flag_help(self, runner):
        """Test main --interactive flag in help."""
        result = runner.invoke(main, ["--help"])
        assert result.exit_code == 0
        assert "--interactive" in result.output or "-i" in result.output
