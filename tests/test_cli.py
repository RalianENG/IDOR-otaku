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


class TestTreeCommand:
    """Tests for tree command."""

    def test_tree_help(self, runner):
        """Test tree --help."""
        result = runner.invoke(main, ["tree", "--help"])
        assert result.exit_code == 0
        assert "Visualize IDs as a tree" in result.output

    def test_tree_with_file(self, runner, sample_report_file):
        """Test tree command with valid file."""
        result = runner.invoke(main, ["tree", str(sample_report_file)])
        assert result.exit_code == 0
        assert "ID Flow Visualization" in result.output

    def test_tree_idor_only(self, runner, sample_report_file):
        """Test tree command with --idor-only flag."""
        result = runner.invoke(main, ["tree", str(sample_report_file), "--idor-only"])
        assert result.exit_code == 0

    def test_tree_type_filter(self, runner, sample_report_file):
        """Test tree command with --type filter."""
        result = runner.invoke(main, ["tree", str(sample_report_file), "--type", "numeric"])
        assert result.exit_code == 0

    def test_tree_empty_report(self, runner, empty_report_file):
        """Test tree command with empty report."""
        result = runner.invoke(main, ["tree", str(empty_report_file)])
        assert result.exit_code == 0
        assert "No IDs found" in result.output


class TestFlowCommand:
    """Tests for flow command."""

    def test_flow_help(self, runner):
        """Test flow --help."""
        result = runner.invoke(main, ["flow", "--help"])
        assert result.exit_code == 0
        assert "timeline" in result.output.lower()

    def test_flow_with_file(self, runner, sample_report_file):
        """Test flow command with valid file."""
        result = runner.invoke(main, ["flow", str(sample_report_file)])
        assert result.exit_code == 0
        assert "ID Flow Timeline" in result.output


class TestTraceCommand:
    """Tests for trace command."""

    def test_trace_help(self, runner):
        """Test trace --help."""
        result = runner.invoke(main, ["trace", "--help"])
        assert result.exit_code == 0
        assert "API call transitions" in result.output

    def test_trace_with_file(self, runner, sample_report_file):
        """Test trace command with valid file."""
        result = runner.invoke(main, ["trace", str(sample_report_file)])
        assert result.exit_code == 0
        assert "API Call Trace" in result.output

    def test_trace_compact(self, runner, sample_report_file):
        """Test trace command with --compact flag."""
        result = runner.invoke(main, ["trace", str(sample_report_file), "--compact"])
        assert result.exit_code == 0


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


class TestGraphCommand:
    """Tests for graph command."""

    def test_graph_help(self, runner):
        """Test graph --help."""
        result = runner.invoke(main, ["graph", "--help"])
        assert result.exit_code == 0
        assert "dependency graph" in result.output.lower()

    def test_graph_with_file(self, runner, sample_report_file):
        """Test graph command with valid file."""
        result = runner.invoke(main, ["graph", str(sample_report_file)])
        assert result.exit_code == 0
        assert "API Dependency Graph" in result.output


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


class TestExportCommand:
    """Tests for export command."""

    def test_export_help(self, runner):
        """Test export --help."""
        result = runner.invoke(main, ["export", "--help"])
        assert result.exit_code == 0
        assert "HTML" in result.output

    def test_export_with_file(self, runner, sample_report_file, tmp_path):
        """Test export command creates HTML file."""
        output_file = tmp_path / "output.html"
        result = runner.invoke(main, [
            "export", str(sample_report_file),
            "--output", str(output_file)
        ])
        assert result.exit_code == 0
        assert output_file.exists()

        # Check HTML content
        content = output_file.read_text(encoding="utf-8")
        assert "<!DOCTYPE html>" in content
        assert "idotaku" in content

    def test_export_sections(self, runner, sample_report_file, tmp_path):
        """Test export command with different sections."""
        for section in ["tree", "trace", "timeline", "all"]:
            output_file = tmp_path / f"output_{section}.html"
            result = runner.invoke(main, [
                "export", str(sample_report_file),
                "--output", str(output_file),
                "--section", section
            ])
            assert result.exit_code == 0
            assert output_file.exists()
