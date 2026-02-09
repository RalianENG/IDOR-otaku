"""Tests for CLI commands."""

import json

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
        assert "IDOR detection tool" in result.output


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

    def test_interactive_command_invokes(self, runner):
        """Test interactive command calls run_interactive_mode."""
        from unittest.mock import patch
        with patch("idotaku.interactive.run_interactive_mode") as mock_run:
            result = runner.invoke(main, ["interactive"])
            assert result.exit_code == 0
            mock_run.assert_called_once()

    def test_interactive_flag_invokes(self, runner):
        """Test -i flag calls run_interactive_mode."""
        from unittest.mock import patch
        with patch("idotaku.interactive.run_interactive_mode") as mock_run:
            result = runner.invoke(main, ["-i"])
            assert result.exit_code == 0
            mock_run.assert_called_once()


class TestDiffCommand:
    """Tests for diff command."""

    def test_diff_help(self, runner):
        result = runner.invoke(main, ["diff", "--help"])
        assert result.exit_code == 0
        assert "Compare two reports" in result.output

    def test_diff_identical_reports(self, runner, sample_report_file):
        result = runner.invoke(main, ["diff", str(sample_report_file), str(sample_report_file)])
        assert result.exit_code == 0
        assert "No changes" in result.output

    def test_diff_with_changes(self, runner, sample_report_data, tmp_path):
        file_a = tmp_path / "a.json"
        file_b = tmp_path / "b.json"

        with open(file_a, "w") as f:
            json.dump(sample_report_data, f)

        # Modify report B: add a new IDOR finding
        data_b = {**sample_report_data}
        data_b["potential_idor"] = sample_report_data["potential_idor"] + [{
            "id_value": "new_id_777",
            "id_type": "numeric",
            "reason": "test",
            "usages": [{"method": "GET", "url": "https://x.com/777", "location": "path"}],
        }]
        with open(file_b, "w") as f:
            json.dump(data_b, f)

        result = runner.invoke(main, ["diff", str(file_a), str(file_b)])
        assert result.exit_code == 0
        assert "New IDOR" in result.output

    def test_diff_removed_idor(self, runner, sample_report_data, tmp_path):
        """Test diff showing removed IDOR candidates."""
        file_a = tmp_path / "a.json"
        file_b = tmp_path / "b.json"

        with open(file_a, "w") as f:
            json.dump(sample_report_data, f)

        # Report B has no IDOR findings (removed)
        data_b = {**sample_report_data, "potential_idor": []}
        with open(file_b, "w") as f:
            json.dump(data_b, f)

        result = runner.invoke(main, ["diff", str(file_a), str(file_b)])
        assert result.exit_code == 0
        assert "Removed IDOR" in result.output

    def test_diff_new_and_removed_ids(self, runner, sample_report_data, tmp_path):
        """Test diff showing new and removed tracked IDs."""
        file_a = tmp_path / "a.json"
        file_b = tmp_path / "b.json"

        with open(file_a, "w") as f:
            json.dump(sample_report_data, f)

        # Report B: remove one ID, add another
        data_b = {**sample_report_data}
        tracked = dict(sample_report_data["tracked_ids"])
        del tracked["12345"]
        tracked["new_id_999"] = {
            "type": "numeric", "first_seen": "2024-01-01T10:05:00",
            "origin": None, "usages": [],
        }
        data_b["tracked_ids"] = tracked
        data_b["summary"] = {**sample_report_data["summary"], "total_unique_ids": 3}
        with open(file_b, "w") as f:
            json.dump(data_b, f)

        result = runner.invoke(main, ["diff", str(file_a), str(file_b)])
        assert result.exit_code == 0
        assert "new tracked ID" in result.output
        assert "removed tracked ID" in result.output

    def test_diff_json_export_with_changes(self, runner, sample_report_data, tmp_path):
        """Test diff JSON export when there are actual changes."""
        file_a = tmp_path / "a.json"
        file_b = tmp_path / "b.json"
        output = tmp_path / "diff.json"

        with open(file_a, "w") as f:
            json.dump(sample_report_data, f)

        data_b = {**sample_report_data, "potential_idor": []}
        with open(file_b, "w") as f:
            json.dump(data_b, f)

        result = runner.invoke(main, [
            "diff", str(file_a), str(file_b),
            "--json-output", str(output),
        ])
        assert result.exit_code == 0
        assert output.exists()
        assert "Diff exported" in result.output
        with open(output) as f:
            diff_data = json.load(f)
        assert diff_data["has_changes"] is True

    def test_diff_json_export(self, runner, sample_report_file, tmp_path):
        output = tmp_path / "diff.json"
        result = runner.invoke(main, [
            "diff", str(sample_report_file), str(sample_report_file),
            "--json-output", str(output),
        ])
        assert result.exit_code == 0


class TestAuthCommand:
    """Tests for auth command."""

    def test_auth_help(self, runner):
        result = runner.invoke(main, ["auth", "--help"])
        assert result.exit_code == 0

    def test_auth_no_auth_context(self, runner, sample_report_file):
        result = runner.invoke(main, ["auth", str(sample_report_file)])
        assert result.exit_code == 0
        assert "No authentication context" in result.output

    def test_auth_with_auth_context(self, runner, tmp_path):
        data = {
            "summary": {"total_unique_ids": 1, "ids_with_origin": 0, "ids_with_usage": 1, "total_flows": 2},
            "tracked_ids": {},
            "flows": [
                {
                    "method": "GET", "url": "https://api.example.com/users/123",
                    "timestamp": "t1",
                    "request_ids": [{"value": "123", "type": "numeric", "location": "path"}],
                    "response_ids": [],
                    "auth_context": {"auth_type": "Bearer", "token_hash": "aaa11111"},
                },
                {
                    "method": "GET", "url": "https://api.example.com/users/123",
                    "timestamp": "t2",
                    "request_ids": [{"value": "123", "type": "numeric", "location": "path"}],
                    "response_ids": [],
                    "auth_context": {"auth_type": "Bearer", "token_hash": "bbb22222"},
                },
            ],
            "potential_idor": [],
        }
        report_file = tmp_path / "auth_report.json"
        with open(report_file, "w") as f:
            json.dump(data, f)

        result = runner.invoke(main, ["auth", str(report_file)])
        assert result.exit_code == 0
        assert "Cross-User Access" in result.output

    def test_auth_empty_report(self, runner, empty_report_file):
        result = runner.invoke(main, ["auth", str(empty_report_file)])
        assert result.exit_code == 0
        assert "No flows found" in result.output


class TestScoreCommand:
    """Tests for score command."""

    def test_score_help(self, runner):
        result = runner.invoke(main, ["score", "--help"])
        assert result.exit_code == 0

    def test_score_with_findings(self, runner, sample_report_file):
        result = runner.invoke(main, ["score", str(sample_report_file)])
        assert result.exit_code == 0
        assert "Risk Scores" in result.output

    def test_score_no_findings(self, runner, empty_report_file):
        result = runner.invoke(main, ["score", str(empty_report_file)])
        assert result.exit_code == 0
        assert "No IDOR candidates" in result.output

    def test_score_min_score_filter(self, runner, sample_report_file):
        result = runner.invoke(main, ["score", str(sample_report_file), "--min-score", "99"])
        assert result.exit_code == 0

    def test_score_level_filter(self, runner, sample_report_file):
        result = runner.invoke(main, ["score", str(sample_report_file), "--level", "critical"])
        assert result.exit_code == 0


class TestCsvCommand:
    """Tests for csv command."""

    def test_csv_help(self, runner):
        result = runner.invoke(main, ["csv", "--help"])
        assert result.exit_code == 0

    def test_csv_idor_mode(self, runner, sample_report_file, tmp_path):
        output = tmp_path / "idor.csv"
        result = runner.invoke(main, ["csv", str(sample_report_file), "-o", str(output)])
        assert result.exit_code == 0
        assert output.exists()
        assert "CSV exported" in result.output

    def test_csv_flows_mode(self, runner, sample_report_file, tmp_path):
        output = tmp_path / "flows.csv"
        result = runner.invoke(main, ["csv", str(sample_report_file), "-o", str(output), "-m", "flows"])
        assert result.exit_code == 0
        assert output.exists()


class TestSarifCommand:
    """Tests for sarif command."""

    def test_sarif_help(self, runner):
        result = runner.invoke(main, ["sarif", "--help"])
        assert result.exit_code == 0

    def test_sarif_export(self, runner, sample_report_file, tmp_path):
        output = tmp_path / "output.sarif.json"
        result = runner.invoke(main, ["sarif", str(sample_report_file), "-o", str(output)])
        assert result.exit_code == 0
        assert output.exists()
        assert "SARIF exported" in result.output

        with open(output) as f:
            sarif = json.load(f)
        assert sarif["version"] == "2.1.0"

    def test_sarif_empty_report(self, runner, empty_report_file, tmp_path):
        output = tmp_path / "empty.sarif.json"
        result = runner.invoke(main, ["sarif", str(empty_report_file), "-o", str(output)])
        assert result.exit_code == 0


class TestHarImportCommand:
    """Tests for import-har command."""

    def test_har_help(self, runner):
        result = runner.invoke(main, ["import-har", "--help"])
        assert result.exit_code == 0

    def test_har_import(self, runner, tmp_path):
        har_data = {
            "log": {
                "version": "1.2",
                "entries": [{
                    "startedDateTime": "2024-01-01T10:00:00.000Z",
                    "request": {
                        "method": "GET",
                        "url": "https://api.example.com/users/12345",
                        "headers": [],
                    },
                    "response": {
                        "status": 200,
                        "headers": [],
                        "content": {"mimeType": "application/json", "text": '{"id": 12345}'},
                    },
                }],
            },
        }
        har_file = tmp_path / "test.har"
        with open(har_file, "w") as f:
            json.dump(har_data, f)

        output = tmp_path / "report.json"
        result = runner.invoke(main, ["import-har", str(har_file), "-o", str(output)])
        assert result.exit_code == 0
        assert "Report generated" in result.output
        assert output.exists()

    def test_har_import_invalid_json(self, runner, tmp_path):
        har_file = tmp_path / "bad.har"
        with open(har_file, "w") as f:
            f.write("not json")

        result = runner.invoke(main, ["import-har", str(har_file)])
        assert result.exit_code == 0  # Handled gracefully
        assert "Error" in result.output
