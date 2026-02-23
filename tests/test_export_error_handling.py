"""Tests for OSError handling in export/save commands."""

from unittest.mock import patch

from click.testing import CliRunner

from idotaku.cli import main


class TestCsvExportOSError:
    def test_csv_export_oserror(self, sample_report_file):
        runner = CliRunner()
        with patch(
            "idotaku.commands.csv_cmd.export_csv",
            side_effect=OSError("Permission denied"),
        ):
            result = runner.invoke(main, ["csv", str(sample_report_file), "-o", "out.csv"])
        assert result.exit_code == 1
        assert "Error writing CSV" in result.output


class TestSarifExportOSError:
    def test_sarif_export_oserror(self, sample_report_file):
        runner = CliRunner()
        with patch(
            "idotaku.commands.sarif_cmd.export_sarif",
            side_effect=OSError("Permission denied"),
        ):
            result = runner.invoke(main, ["sarif", str(sample_report_file), "-o", "out.sarif"])
        assert result.exit_code == 1
        assert "Error writing SARIF" in result.output


class TestDiffExportOSError:
    def test_diff_json_export_oserror(self, sample_report_file):
        """Diff with same file = no changes, so -o path is never reached."""
        runner = CliRunner()
        with patch("builtins.open", side_effect=OSError("Permission denied")):
            runner.invoke(
                main,
                ["diff", str(sample_report_file), str(sample_report_file), "-o", "diff.json"],
            )

    def test_diff_json_export_oserror_with_changes(self, sample_report_file, tmp_path):
        """Test OSError when diff has changes and tries to write JSON."""
        import json

        # Create a second report with different data
        report_b = tmp_path / "report_b.json"
        with open(sample_report_file) as f:
            data = json.load(f)
        data["potential_idor"].append({
            "id_value": "new_id",
            "id_type": "numeric",
            "found_in": [{"url": "http://example.com/api", "location": "url_path"}],
        })
        data["summary"]["total_unique_ids"] += 1
        with open(report_b, "w") as f:
            json.dump(data, f)

        runner = CliRunner()
        with patch(
            "idotaku.commands.diff_cmd.open",
            side_effect=OSError("Permission denied"),
            create=True,
        ):
            result = runner.invoke(
                main,
                ["diff", str(sample_report_file), str(report_b), "-o", "diff.json"],
            )
        assert result.exit_code == 1
        assert "Error writing diff" in result.output


class TestChainHtmlOSError:
    def test_chain_html_export_oserror(self, sample_report_file):
        runner = CliRunner()
        with patch(
            "idotaku.commands.chain.export_chain_html",
            side_effect=OSError("Permission denied"),
        ):
            result = runner.invoke(
                main, ["chain", str(sample_report_file), "--html", "chain.html"]
            )
        assert result.exit_code == 1
        assert "Error writing HTML" in result.output


class TestSequenceHtmlOSError:
    def test_sequence_html_export_oserror(self, sample_report_file):
        runner = CliRunner()
        with patch(
            "idotaku.commands.sequence.export_sequence_html",
            side_effect=OSError("Permission denied"),
        ):
            result = runner.invoke(
                main, ["sequence", str(sample_report_file), "--html", "seq.html"]
            )
        assert result.exit_code == 1
        assert "Error writing HTML" in result.output


class TestVerifySaveOSError:
    def test_save_results_oserror(self, tmp_path):
        """Test _save_results raises OSError on invalid path."""
        import pytest
        from idotaku.commands.verify_cmd import _save_results
        from idotaku.verify.models import (
            ComparisonResult,
            Modification,
            RequestData,
            ResponseData,
            VerifyResult,
        )

        mock_result = VerifyResult(
            finding_id_value="123",
            finding_id_type="numeric",
            modification=Modification(
                original_value="123",
                modified_value="456",
                location="url_path",
                field_name=None,
                description="test",
            ),
            original_request=RequestData(method="GET", url="http://example.com/123"),
            modified_request=RequestData(method="GET", url="http://example.com/456"),
            response=ResponseData(status_code=200, body="ok"),
            original_response=ResponseData(status_code=200, body="ok"),
            comparison=ComparisonResult(
                status_match=True,
                status_original=200,
                status_modified=200,
                content_length_diff=0,
                verdict="NOT_VULNERABLE",
            ),
            timestamp="2026-01-01T00:00:00Z",
        )

        # Valid path works
        output = str(tmp_path / "results.json")
        _save_results([mock_result], output, "report.json")
        assert (tmp_path / "results.json").exists()

        # Invalid path raises OSError
        bad_path = str(tmp_path / "nonexistent_dir" / "results.json")
        with pytest.raises(OSError):
            _save_results([mock_result], bad_path, "report.json")
